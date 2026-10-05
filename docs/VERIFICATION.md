# Builder verification record

Date: 2026-10-05.

- Frontend: npm install succeeded in a shorter permitted Windows folder, then npm run build passed TypeScript compilation and Vite production bundling (26 transformed modules).
- Backend: Python compileall succeeded for app, migrations and tests.
- Pytest: 5 passed, 3 skipped. Passed checks: semaphore capacity/counter/event completion, scrypt hashing/verification, JWT claims, PostgreSQL locking SQL compilation and partial unique-index DDL compilation.
- Skipped: 3 real PostgreSQL integration tests (concurrent allocation, same-user race, idempotency/checkout/authorization) because a disposable PostgreSQL server was unavailable. SQL compilation is not execution and does not prove database concurrency behavior.
- Docker CLI was installed, but docker version reported no running Docker engine pipe. PostgreSQL and git executables were not found in PATH or standard PostgreSQL Program Files location. No large runtime was installed or container image downloaded.
- First frontend install failed because the deeply nested Windows agent path caused esbuild binary ENOENT. Repeating in the shorter permitted shared parking-build folder resolved it; this is an environment/path limitation, not an application build failure.
- Included GitHub Actions runs the full suite against a PostgreSQL 16 service and builds the frontend. Its remote outcome is separate from this local verification record and must be checked in the repository Actions tab.
- No deployment, live payments, real parking sensors, or full browser-to-database end-to-end validation was performed.
