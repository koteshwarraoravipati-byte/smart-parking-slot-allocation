# Hosting the academic demo

Deployment is not yet verified. Never treat a frontend-only page as a working parking system. Use synthetic data only.

## Backend and database
Create a PostgreSQL database on your chosen free provider. Keep its connection string private; convert its scheme to postgresql+psycopg:// for SQLAlchemy and retain TLS query parameters.
Create a Render Docker web service from this repository, root directory backend. Choose the free instance if available; stop rather than accept charges. Set DATABASE_URL privately, JWT_SECRET to a generated 48-byte random value, and CORS_ORIGINS to the exact frontend HTTPS origin. The container runs migrations before serving and uses the hosting PORT. Check /health returns {"status":"ok"}.
No default administrator exists; create one through a private backend terminal with python -m app.admin. Do not add a public bootstrap endpoint.

## Vercel frontend
Import this repository with root directory frontend, Vite preset, npm ci install command, npm run build build command and dist output. Set VITE_API_URL to the backend HTTPS origin before building. This is a public API origin, not a secret.

## Verification
Verify register/login, availability, allocation, checkout, replay, history and denied admin access. Use a separate disposable PostgreSQL database for integration tests because they drop tables. Free hosting may sleep, expire or impose quotas; this academic demo has no production SLA.
