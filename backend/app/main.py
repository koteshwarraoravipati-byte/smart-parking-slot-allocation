import math, re
from datetime import datetime, timezone
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from sqlalchemy import select, exists
from sqlalchemy.exc import IntegrityError
from .models import Session, User, Slot, Booking
from .security import hash_password, verify_password, token, SECRET
from .demo import run_demo
import jwt, os

app = FastAPI(title="Smart Parking", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5173").split(","), allow_methods=["GET","POST"], allow_headers=["Authorization","Content-Type"])
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
    return {"id": b.id, "slot_id": b.slot_id, "vehicle": b.vehicle, "started_at": b.started_at, "ended_at": b.ended_at, "amount_cents": b.amount_cents}
@app.get("/health")
def health():
    with Session() as db: db.execute(select(1))
    return {"status":"ok"}
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
        return [{"id":s.id,"label":s.label,"occupied":s.id in occupied} for s in db.scalars(select(Slot).order_by(Slot.id))]
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
        slot = db.scalar(select(Slot).where(~busy).order_by(Slot.id).with_for_update(skip_locked=True).limit(1))
        if not slot: raise HTTPException(409,"No slot available right now; retry shortly")
        b = Booking(user_id=user.id, slot_id=slot.id, vehicle=body.vehicle.upper().strip(), request_key=body.request_key)
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
        if b.ended_at is None:
            b.ended_at = datetime.now(timezone.utc)
            hours = max(1, math.ceil((b.ended_at-b.started_at).total_seconds()/3600))
            b.amount_cents = hours * 2000
        return serialize(b)
@app.get("/admin/dashboard")
def dashboard(user=Depends(admin)):
    with Session() as db:
        all_b = list(db.scalars(select(Booking).order_by(Booking.id.desc())))
        return {"slots":len(list(db.scalars(select(Slot.id)))), "active":sum(b.ended_at is None for b in all_b), "revenue_cents":sum(b.amount_cents or 0 for b in all_b), "bookings":[serialize(b) for b in all_b]}
@app.post("/admin/demo")
def demo(user=Depends(admin)): return run_demo()
