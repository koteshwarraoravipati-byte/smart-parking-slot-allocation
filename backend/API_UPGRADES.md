# Slot management and parking tickets

Apply Alembic revision 002 with `alembic upgrade head` before starting the upgraded server. Migration 001 is frozen to its original schema, rather than importing future live models; 002 is additive for existing databases. It preserves booking data, constraints, and the INR 20 per started hour billing rule (amount_cents stores paise).

All calls use the existing Authorization: Bearer login JWT. Parking-ticket tokens are separate random opaque values, NOT login JWTs. Slot read access requires login; all /admin routes require an administrator.

## Slots

GET /slots returns an array of {id,label,zone,row,column,enabled,maintenance_note,version,occupied,available}. available is enabled && !occupied. Existing slots are placed by ascending ID in zone A, four columns per row, enabled=true, maintenance_note='', version=1.

POST /admin/slots accepts {label,zone?,row,column,enabled?,maintenance_note?} and returns the new slot with HTTP 201. Defaults: zone A, enabled true, empty note. PATCH /admin/slots/{id} accepts {version,...changedFields} and returns the updated slot. version is the expected CURRENT version and is mandatory; a successful patch increments it. Omit unchanged fields; explicit null is rejected. Allowed fields are label, zone, row, column, enabled, maintenance_note. Label and zone allow letters, numbers, underscore and hyphen, up to 20 characters; row/column are positive integers up to 10000. Notes are limited to 500 characters. Duplicate labels or positions return 409; stale versions return 409. There is no deletion route.

Slots may close while occupied; the booking remains active and normal checkout still works. Allocation filters enabled slots and locks the same row as the admin edit, retaining SKIP LOCKED and database unique indexes. Each successful create/edit records actor, action, before/after snapshots and database timestamp in slot_audit.

## Tickets

Booking objects everywhere now include slot_label in addition to id,slot_id,vehicle,started_at,ended_at,amount_cents. Slot relationships use batched select-in loading, not a per-booking query.

POST /bookings/{id}/ticket (owner or admin) returns {booking:<booking object>,token:<opaque string>}. Generate only on explicit request: every call rotates the token, invalidating prior codes. The token is 32 cryptographically random bytes represented as 43 URL-safe characters. Only a SHA-256 digest is persisted in booking_tickets; raw tokens cannot be recovered. The token has no time expiry; it remains usable until rotation. A completed booking can still issue or replay a ticket; it never checks out a later booking.

POST /admin/tickets/preview accepts {token} and returns a booking object directly. It NEVER changes booking state. POST /admin/tickets/checkout accepts {token} and returns a booking object directly. It locks the booking and invokes the same idempotent checkout/billing helper as normal checkout. Replays return the original ended_at and amount, without charging again. Ticket rotation and ticket checkout lock in the same order and recheck the digest after acquiring the booking lock.

There are intentionally NO GET ticket/preview/checkout mutations or query-string token routes. Send raw tokens only in JSON request/response bodies over HTTPS; do not include them in URLs, application logs or analytics. Ticket responses are marked Cache-Control: no-store. Unknown/rotated tickets return 404; malformed tokens 422; wrong owner/non-admin 403. Ticket endpoints enforce a basic per-user 60 requests/minute limit (429 + Retry-After: 60). This limit is process-local; use gateway/shared limits for a multi-worker deployment. CORS now permits PATCH.

## Verification

Run safe tests: `uv run --no-project --with-requirements requirements.txt python -m pytest -q`.

PostgreSQL integration tests are DESTRUCTIVE, including drop_all: point TEST_DATABASE_URL ONLY to a disposable PostgreSQL instance and separately set ALLOW_DESTRUCTIVE_TESTS=1. Never use a production or shared database. Without both settings they are skipped. They cover concurrency, admin denial, version conflicts, audits, closure/allocator locking, occupied-slot checkout, ticket hashing/rotation/ownership/preview/replay, and the historical 001-to-002 migration. Actual PostgreSQL is necessary to validate locking; unit SQL compilation is not a substitute.
