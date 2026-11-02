import math, re, secrets, hashlib, time, threading
from collections import deque
from datetime import datetime, timezone
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field, ConfigDict, field_validator
from sqlalchemy import select, exists
from sqlalchemy.exc import IntegrityError
from .models import Session, User, Slot, Booking, SlotAudit, BookingTicket
from .security import hash_password, verify_password, token, SECRET
from .demo import run_demo
import jwt, os

APP_VERSION = "1.1.0"
app = FastAPI(title="Smart Parking", version=APP_VERSION)
app.add_middleware(CORSMiddleware, allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5173").split(","), allow_methods=["GET","POST","PATCH"], allow_headers=["Authorization","Content-Type"])
@app.middleware("http")
async def sensitive_ticket_responses(request, call_next):
    response = await call_next(request)
    if "/ticket" in request.url.path:
        response.headers["Cache-Control"] = "no-store"
        response.headers["Pragma"] = "no-cache"
    return response

bearer = HTTPBearer()
class Credentials(BaseModel):
    username: str = Field(min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_-]+$")
    password: str = Field(min_length=10, max_length=128)
class Allocate(BaseModel):
    vehicle: str = Field(min_length=2, max_length=20, pattern=r"^[a-zA-Z0-9 -]+$")
    request_key: str = Field(min_length=8, max_length=80)
def current_user(auth: HTTPAuthorizationCredentials = Depends(bearer)):
    try:
        claims = jwt.decode(auth.credentials, SECRET, algorithms=["HS256"], issuer="smart-parking", options={"require":["exp","sub","iss"]})
        uid = int(claims["sub"])
    except (jwt.PyJWTError, ValueError, KeyError): raise HTTPException(401, "Invalid or expired token")
    with Session() as db:
        user = db.get(User, uid)
        if not user: raise HTTPException(401, "Unknown user")
        return user

def admin(user=Depends(current_user)):
    if user.role != "admin": raise HTTPException(403, "Administrator required")
    return user

def serialize(b):
    return {"id": b.id, "slot_id": b.slot_id, "slot_label": b.slot.label, "vehicle": b.vehicle, "started_at": b.started_at, "ended_at": b.ended_at, "amount_cents": b.amount_cents}
@app.get("/health")
def health():
    with Session() as db: db.execute(select(1))
    return {"status":"ok", "version": APP_VERSION}
@app.post("/auth/register", status_code=201)
def register(body: Credentials):
    with Session.begin() as db:
        user = User(username=body.username.lower(), password_hash=hash_password(body.password), role="user")
        db.add(user)
        try: db.flush()
        except IntegrityError: raise HTTPException(409, "Username already registered")
        return {"token":token(user.id)}
@app.post("/auth/login")
def login(body: Credentials):
    with Session() as db:
        user = db.scalar(select(User).where(User.username == body.username.lower()))
        if not user or not verify_password(body.password, user.password_hash): raise HTTPException(401, "Invalid credentials")
        return {"token":token(user.id)}
@app.get("/me")
def me(user=Depends(current_user)):
    return {"id":user.id,"username":user.username,"role":user.role}
@app.get("/slots")
def slots(user=Depends(current_user)):
    with Session() as db:
        occupied = set(db.scalars(select(Booking.slot_id).where(Booking.ended_at.is_(None))))
        return [serialize_slot(s, s.id in occupied) for s in db.scalars(select(Slot).order_by(Slot.id))]
@app.get("/bookings")
def bookings(user=Depends(current_user)):
    with Session() as db:
        return [serialize(b) for b in db.scalars(select(Booking).where(Booking.user_id==user.id).order_by(Booking.id.desc()))]
@app.post("/allocate")
def allocate(body: Allocate, user=Depends(current_user)):
    with Session.begin() as db:
        # Serialize requests by one user, including replay checks.
        db.scalar(select(User).where(User.id==user.id).with_for_update())
        previous = db.scalar(select(Booking).where(Booking.user_id==user.id, Booking.request_key==body.request_key))
        if previous:
            if previous.vehicle != body.vehicle.upper().strip(): raise HTTPException(409,"Idempotency key reused with different vehicle")
            return serialize(previous)
        if db.scalar(select(Booking.id).where(Booking.user_id==user.id, Booking.ended_at.is_(None))):
            raise HTTPException(409,"You already have an active booking")
        busy = exists(select(Booking.id).where(Booking.slot_id==Slot.id, Booking.ended_at.is_(None)))
        slot = db.scalar(select(Slot).where(Slot.enabled.is_(True), ~busy).order_by(Slot.id).with_for_update(skip_locked=True).limit(1))
        if not slot: raise HTTPException(409,"No slot available right now; retry shortly")
        b = Booking(user_id=user.id, slot=slot, vehicle=body.vehicle.upper().strip(), request_key=body.request_key)
        db.add(b)
        try: db.flush()
        except IntegrityError: raise HTTPException(409,"Slot changed concurrently; retry with the same request key")
        db.refresh(b)
        return serialize(b)
@app.post("/bookings/{booking_id}/checkout")
def checkout(booking_id: int, user=Depends(current_user)):
    with Session.begin() as db:
        b = db.scalar(select(Booking).where(Booking.id==booking_id).with_for_update())
        if not b: raise HTTPException(404,"Booking not found")
        if b.user_id != user.id: raise HTTPException(403,"Not your booking")
        return finish_checkout(b)
@app.get("/admin/dashboard")
def dashboard(user=Depends(admin)):
    with Session() as db:
        # Booking-owner names are exposed only through this administrator-only route.
        rows = list(db.execute(select(Booking, User.username).join(User, Booking.user_id == User.id).order_by(Booking.id.desc())))
        return {"slots":len(list(db.scalars(select(Slot.id)))), "active":sum(b.ended_at is None for b, _ in rows), "revenue_cents":sum(b.amount_cents or 0 for b, _ in rows), "bookings":[{**serialize(b), "username": username} for b, username in rows]}

@app.post("/admin/bookings/{booking_id}/checkout")
def admin_checkout(booking_id: int, user=Depends(admin)):
    # A manual removal ends the visit; never delete its owner or booking history.
    # Lock and reuse the same idempotent billing operation as owner/ticket checkout.
    with Session.begin() as db:
        booking = db.scalar(select(Booking).where(Booking.id == booking_id).with_for_update())
        if not booking:
            raise HTTPException(404, "Booking not found")
        return finish_checkout(booking)
@app.post("/admin/demo")
def demo(user=Depends(admin)): return run_demo()

# Slot writes and allocation lock the same slots row. No delete API is exposed.
class SlotCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    label: str = Field(min_length=1, max_length=20, pattern=r"^[A-Za-z0-9_-]+$")
    zone: str = Field(default="A", min_length=1, max_length=20, pattern=r"^[A-Za-z0-9_-]+$")
    row: int = Field(ge=1, le=10000)
    column: int = Field(ge=1, le=10000)
    enabled: bool = True
    maintenance_note: str = Field(default="", max_length=500)

class SlotPatch(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    version: int = Field(ge=1)
    label: str | None = Field(default=None, min_length=1, max_length=20, pattern=r"^[A-Za-z0-9_-]+$")
    zone: str | None = Field(default=None, min_length=1, max_length=20, pattern=r"^[A-Za-z0-9_-]+$")
    row: int | None = Field(default=None, ge=1, le=10000)
    column: int | None = Field(default=None, ge=1, le=10000)
    enabled: bool | None = None
    maintenance_note: str | None = Field(default=None, max_length=500)

    @field_validator("label", "zone", "row", "column", "enabled", "maintenance_note", mode="before")
    @classmethod
    def reject_explicit_null(cls, value):
        if value is None:
            raise ValueError("Use omission, not null, for unchanged fields")
        return value

def slot_state(slot):
    return {k: getattr(slot, k) for k in ("id", "label", "zone", "row", "column", "enabled", "maintenance_note", "version")}

def serialize_slot(slot, occupied=False):
    return {**slot_state(slot), "occupied": occupied, "available": slot.enabled and not occupied}

def finish_checkout(booking):
    # Caller must lock the booking. Replays retain the exact original timestamp and bill.
    if booking.ended_at is None:
        booking.ended_at = datetime.now(timezone.utc)
        hours = max(1, math.ceil((booking.ended_at-booking.started_at).total_seconds()/3600))
        booking.amount_cents = hours * 2000  # INR 20 per started hour, expressed in paise.
    return serialize(booking)

@app.post("/admin/slots", status_code=201)
def create_slot(body: SlotCreate, user=Depends(admin)):
    with Session.begin() as db:
        slot = Slot(**body.model_dump())
        db.add(slot)
        try:
            db.flush()
        except IntegrityError:
            raise HTTPException(409, "Slot label or zone/row/column already exists")
        db.add(SlotAudit(slot_id=slot.id, actor_id=user.id, action="create", before=None, after=slot_state(slot)))
        return serialize_slot(slot)

@app.patch("/admin/slots/{slot_id}")
def update_slot(slot_id: int, body: SlotPatch, user=Depends(admin)):
    with Session.begin() as db:
        slot = db.scalar(select(Slot).where(Slot.id==slot_id).with_for_update())
        if not slot:
            raise HTTPException(404, "Slot not found")
        if slot.version != body.version:
            raise HTTPException(409, "Slot changed; refresh and retry with its current version")
        before = slot_state(slot)
        for key, value in body.model_dump(exclude_unset=True, exclude={"version"}).items():
            setattr(slot, key, value)
        slot.version += 1
        try:
            db.flush()
        except IntegrityError:
            raise HTTPException(409, "Slot label or zone/row/column already exists")
        db.add(SlotAudit(slot_id=slot.id, actor_id=user.id, action="update", before=before, after=slot_state(slot)))
        occupied = db.scalar(select(Booking.id).where(Booking.slot_id==slot.id, Booking.ended_at.is_(None))) is not None
        return serialize_slot(slot, occupied)

class TicketInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token: str = Field(min_length=43, max_length=43, pattern=r"^[A-Za-z0-9_-]{43}$")

# Bounded per-process throttle, not a distributed abuse prevention system. No tokens are logged.
_ticket_attempts = {}
_ticket_attempts_lock = threading.Lock()

def ticket_rate_limit(user=Depends(current_user)):
    now = time.monotonic()
    with _ticket_attempts_lock:
        for uid in list(_ticket_attempts):
            if not _ticket_attempts[uid] or _ticket_attempts[uid][-1] <= now - 60:
                del _ticket_attempts[uid]
        attempts = _ticket_attempts.setdefault(user.id, deque())
        while attempts and attempts[0] <= now - 60:
            attempts.popleft()
        if len(attempts) >= 60:
            raise HTTPException(429, "Too many ticket requests; retry in one minute", headers={"Retry-After":"60"})
        attempts.append(now)
    return user

def digest_ticket(value):
    return hashlib.sha256(value.encode("ascii")).hexdigest()

@app.post("/bookings/{booking_id}/ticket")
def issue_ticket(booking_id: int, user=Depends(ticket_rate_limit)):
    with Session.begin() as db:
        booking = db.scalar(select(Booking).where(Booking.id==booking_id).with_for_update())
        if not booking:
            raise HTTPException(404, "Booking not found")
        if booking.user_id != user.id and user.role != "admin":
            raise HTTPException(403, "Not your booking")
        value = secrets.token_urlsafe(32)
        ticket = db.scalar(select(BookingTicket).where(BookingTicket.booking_id==booking_id))
        if ticket:
            ticket.token_hash = digest_ticket(value)
            ticket.created_at = datetime.now(timezone.utc)
        else:
            db.add(BookingTicket(booking_id=booking_id, token_hash=digest_ticket(value)))
        return {"booking": serialize(booking), "token": value}

def booking_for_ticket(db, value, lock=False):
    # Find candidate without locking, then lock booking first, exactly like ticket rotation.
    # Re-read hash AFTER acquiring that lock so rotation cannot leave a stale token usable.
    token_hash = digest_ticket(value)
    booking_id = db.scalar(select(BookingTicket.booking_id).where(BookingTicket.token_hash==token_hash))
    if booking_id is None:
        raise HTTPException(404, "Ticket not found or rotated")
    query = select(Booking).where(Booking.id==booking_id)
    if lock:
        query = query.with_for_update()
    booking = db.scalar(query)
    if not booking or not db.scalar(select(BookingTicket.id).where(BookingTicket.booking_id==booking_id, BookingTicket.token_hash==token_hash)):
        raise HTTPException(404, "Ticket not found or rotated")
    return booking

@app.post("/admin/tickets/preview")
def preview_ticket(body: TicketInput, user=Depends(admin), limited=Depends(ticket_rate_limit)):
    with Session() as db:
        return serialize(booking_for_ticket(db, body.token))

@app.post("/admin/tickets/checkout")
def checkout_ticket(body: TicketInput, user=Depends(admin), limited=Depends(ticket_rate_limit)):
    with Session.begin() as db:
        return finish_checkout(booking_for_ticket(db, body.token, lock=True))
