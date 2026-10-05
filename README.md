# Smart Parking Slot Allocation

An academic full-stack project: React + TypeScript + Vite, FastAPI, PostgreSQL, SQLAlchemy and Alembic. No Supabase account or API keys are needed. This is a local academic MVP, not a deployed payment/production service.

## Features
- Register/login with salted scrypt password hashes and signed, expiring JWT sessions.
- Live slot availability, vehicle entry, first-available allocation, booking history and checkout.
- Minimum one hour, INR 20 per commenced hour (integer paise stored; no real payment).
- Administrator dashboard with occupancy, booking history and revenue.
- Observable semaphore/mutex thread laboratory, explicitly separate from database safety.
- Transactions, row locks, partial unique indexes, replay-safe allocation and atomic, repeatable checkout.

## Quick start (Docker Desktop)
1. Install/start Docker Desktop with Linux containers. Docker must report a running server via `docker version`.
2. Copy `.env.example` to `.env`. Set your own PostgreSQL password and random JWT secret (32+ characters). Do not commit this file.
   Generate a secret with `python -c "import secrets; print(secrets.token_urlsafe(48))"`.
   For the PostgreSQL password use URL-safe letters/numbers to avoid escaping the connection URL.
3. From this repository: `docker compose up --build`.
4. Visit http://localhost:5173 ; API documentation: http://localhost:8000/docs.
5. Create an ordinary account in the UI. No default admin account exists.
6. Create your administrator explicitly: `docker compose exec backend python -m app.admin`. Enter a new username/password privately in the terminal, then sign in through the UI.

The initial Alembic migration creates 12 parking slots. Data persists in the Docker volume. `docker compose down` preserves data; `docker compose down -v` **deletes all local data**.

## Manual development
Requires Node 20.19+ or 22+, Python 3.12 and PostgreSQL 16.
Create an empty database and set `DATABASE_URL=postgresql+psycopg://USER:PASSWORD@localhost:5432/DB` and `JWT_SECRET` in your terminal environment. Windows PowerShell: `$env:NAME="value"`; macOS/Linux: `export NAME="value"`.

Backend, from `backend/`:
`python -m venv .venv` then activate it, `python -m pip install -r requirements.txt`, `alembic upgrade head`, `uvicorn app.main:app --reload`.

Frontend, from `frontend/`: `npm ci`, `npm run dev`. It uses http://localhost:8000; this project deliberately targets local operation only. Frontend tokens stay in memory; refresh requires sign-in again.

## Tests
From backend, set a test-only random `JWT_SECRET` and run `python -m pytest tests/test_demo.py tests/test_security.py -q`.

Real PostgreSQL integration tests intentionally drop and recreate application tables. **Use a separate disposable database, never your normal parking database.** Set `TEST_DATABASE_URL` to its connection URL and run `python -m pytest tests -q`. Without that variable PostgreSQL tests are marked skipped, not passed. Test coverage includes 12 concurrent users competing for 3 slots, same-user concurrency, idempotency conflict, checkout replay/release, ownership and role denial.

To run inside Compose against a disposable database:
`docker compose exec db sh -c 'createdb -U "$POSTGRES_USER" parking_test'`
Then (substitute your local password; avoid shell history on shared machines):
`docker compose exec -e TEST_DATABASE_URL=postgresql+psycopg://parking:YOUR_PASSWORD@db:5432/parking_test backend python -m pytest tests -q`

## Correctness and concurrency
Allocation starts a transaction, locks the requesting user's row, checks prior idempotency requests and active bookings, then selects an available slot with `FOR UPDATE SKIP LOCKED`. It inserts a booking before commit. Separate processes are protected by PostgreSQL, not a Python lock.
Partial unique indexes prevent two active bookings for one slot or one user. A permanent unique user/request-key index preserves replay semantics even after checkout. A repeated allocation key returns the original booking (including a completed booking); use a new key to park again. A different vehicle with the same key is rejected.
Checkout locks the booking, verifies ownership, computes the rounded hourly fee once, and writes end time/amount in the same transaction. Clearing the active-index predicate releases the slot atomically. Repeated checkout returns the same stored result.
`SKIP LOCKED` can briefly report no slot while other transactions hold locks. Clients may retry with the same request key. Constraint conflicts safely roll back. Availability displays are snapshots, never a reservation guarantee.

## Security and scope
Passwords use Python's scrypt with independent random salts; JWT signature/issuer/expiry are validated and roles are read from the database for each request. Public registration always creates users, never admins. Ownership is enforced server-side. JWT secret is required at startup. Keep environment secrets private and rotate before any future deployment.
This MVP has no TLS termination, distributed rate limiter, password recovery, token revocation, sensors, plate recognition, payment gateway or production monitoring. Do not expose publicly without adding these controls. Use synthetic vehicle registrations for classroom demos. The public repository contains no credentials.

## Academic materials
See [presentation notes](docs/PRESENTATION.md) for architecture, algorithm, OS concepts, demo flow, viva answers and limitations.
See [verification record](docs/VERIFICATION.md) for checks actually executed by the builder.

## Optional continuous integration
The connector could not write workflow files with its current permissions. Copy docs/ci-example.yml to .github/workflows/ci.yml yourself to enable GitHub Actions (PostgreSQL integration tests and frontend build). The template uses isolated CI-only test credentials, not real secrets. CI has not been run or verified by the builder.
