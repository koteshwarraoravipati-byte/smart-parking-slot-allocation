# Verification record

Last live verification: 2026-10-26.

## Live website and backend
- Frontend: https://smart-parking-slot-allocation.vercel.app/ returned HTTP 200 and rendered the Smart Parking login form.
- Browser UI flow passed using a synthetic account: account creation, parking-map load, vehicle entry/allocation, and checkout. UI reported “Checkout complete” and ₹20.00; the slot was released.
- Backend health endpoint returned HTTP 200 with {"status":"ok"} after querying the database.
- Fresh API smoke test passed: register (201), login (200), slot availability (12 slots), allocation (200), idempotent allocation replay, non-admin dashboard denial (403), checkout (200), repeated checkout consistency, and booking-history verification.
- The live smoke test used temporary synthetic accounts and a demo vehicle registration. It did not execute a multi-process race test against the hosted service.

## Local checks recorded during implementation (2026-10-05)
- Frontend TypeScript/Vite production build passed.
- Python compilation passed; FastAPI imported and generated an OpenAPI schema with 10 paths.
- Pytest: 5 passed, 3 PostgreSQL integration tests skipped because no disposable PostgreSQL server was available in that local run. Skipped tests are not passing tests.
- Docker Compose runtime and CI were not verified in that local run. docs/ci-example.yml is a template, not proof that CI ran.

## Scope and safety
PostgreSQL constraints/transactions provide actual multi-request allocation protection. The semaphore/mutex visualization is educational and process-local. Smoke tests do not constitute a security audit, production load test, or guarantee of hosting availability. Never point destructive integration tests at the hosted or personal database.
