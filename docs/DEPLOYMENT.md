# Deployment and operations

## Current deployment
- Frontend: https://smart-parking-slot-allocation.vercel.app/ (Vercel Hobby project; root directory frontend).
- Backend: https://smart-parking-slot-allocation.onrender.com/ (Render web service; root directory backend).
- Database: PostgreSQL on Neon.
- API health/database check: https://smart-parking-slot-allocation.onrender.com/health

The frontend's production bundle points to the Render API. Vercel builds the Vite app from the frontend directory. The backend Dockerfile runs Alembic migrations before starting Uvicorn on the platform-provided PORT.

## Required environment settings
Configure these only in the hosting providers' private settings; never commit their values:
- Render: DATABASE_URL (Neon PostgreSQL connection string using the SQLAlchemy psycopg scheme), JWT_SECRET (random, long secret), CORS_ORIGINS (https://smart-parking-slot-allocation.vercel.app).
- Vercel: VITE_API_URL=https://smart-parking-slot-allocation.onrender.com. This is a public API origin, not a credential.

No Supabase, payment, maps, SMS, analytics, or AI API key is required by the app. Do not add real credentials to this repository. Do not expose a default administrator password. An administrator must be created privately through the backend's admin CLI.

## Verification performed 2026-10-26
- Vercel website returned HTTP 200 and rendered the login/create-account screen.
- Render /health returned HTTP 200 with status ok, including the database check.
- Browser test: created a synthetic account, loaded the slot map, allocated a space, checked out, and saw the checkout-complete message.
- API smoke test: registration, login, 12-slot availability, allocation, idempotent allocation replay, ordinary-user admin denial (403), checkout, repeated checkout, and booking history all passed.
- This is an application/API smoke test, not a formal production-readiness audit or a fresh multi-process race test. Refer to the verification record for earlier local test coverage and limitations.

## Limitations
This is an academic demo, not a production parking service. Hosting plans, free quotas, cold starts, expiry rules, and availability are controlled by the providers and may change. Do not rely on it for payment, actual parking enforcement, personal vehicle data, or an availability SLA. Use synthetic accounts and vehicle registrations. For local use see the root README.
