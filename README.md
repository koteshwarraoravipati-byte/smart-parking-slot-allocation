# Smart Parking Slot Allocation System

A responsive academic full-stack parking application demonstrating safe parking-slot allocation, registration/login, bookings and checkout.

## Live application
- Website: https://smart-parking-slot-allocation.vercel.app/
- Backend health: https://smart-parking-slot-allocation.onrender.com/health
- Source repository: https://github.com/koteshwarraoravipati-byte/smart-parking-slot-allocation

Create an account on the website to try the parking map and booking flow. Use synthetic vehicle numbers for the classroom demo. There are 12 seeded slots. The rate is ₹20 per commenced hour; the app does not collect real payments.

## Features
- Mobile-friendly slot map, availability counts, account registration and sign-in.
- Automatic available-slot allocation, booking history and checkout.
- Administrator-only occupancy, booking and revenue dashboard; ordinary users are denied access.
- A teaching demo of Python semaphore/mutex concepts, separate from real booking protection.
- PostgreSQL transactions, row locks, uniqueness constraints and idempotent booking/checkout operations.

## Technology and services
- Frontend: React, TypeScript and Vite, deployed on Vercel.
- Backend: Python, FastAPI, SQLAlchemy and Alembic, deployed on Render.
- Database: PostgreSQL hosted on Neon.
- No third-party API keys, payment credentials, map keys, or AI keys are required. The backend does require private deployment configuration: DATABASE_URL and JWT_SECRET. CORS_ORIGINS must allow the website origin. VITE_API_URL is the frontend's backend address and is public configuration, not a secret. Keep credentials out of GitHub.

## Run locally with Docker Compose
1. Install and start Docker Desktop.
2. Copy .env.example to .env and set a private PostgreSQL password plus a random JWT secret. Do not commit .env.
3. From the repository root run: `docker compose up --build`
4. Open http://localhost:5173. The API docs are at http://localhost:8000/docs.
5. Create a normal user on the site. No default admin account is created.
6. To create an administrator for a local demo, run `docker compose exec backend python -m app.admin` and enter credentials privately in the terminal.

The initial migration creates 12 slots. `docker compose down` keeps the local database volume; `docker compose down -v` deletes local data.

## Local tools
Requires Docker Desktop with Compose for the simplest setup. Manual development uses Python 3.12, Node.js 20.19+ or 22+, and PostgreSQL. Backend dependencies are in backend/requirements.txt; frontend dependencies are in frontend/package-lock.json. No global/external API keys are needed for local development.

## Tests
From backend, run `python -m pytest tests -q`. PostgreSQL integration tests require TEST_DATABASE_URL to point to a separate disposable database; those tests drop/recreate tables. Never use production or personal data. Without TEST_DATABASE_URL, integration tests are skipped, not passed.

## Synchronization model
The educational semaphore/mutex illustration is process-local and exists to explain OS synchronization. It does not protect the deployed application across multiple web requests or backend processes. Real booking protection is provided by PostgreSQL transactions and constraints. Availability is a snapshot; a slot is confirmed only after allocation succeeds.

See [presentation notes](docs/PRESENTATION.md), [deployment details](docs/DEPLOYMENT.md), and [verification record](docs/VERIFICATION.md).
