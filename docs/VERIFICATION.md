# Builder verification record

Date: 2026-10-05.

- Frontend: npm install succeeded in a shorter permitted Windows folder, then npm run build passed TypeScript compilation and Vite production bundling (26 transformed modules).
- Backend: Python compileall succeeded for app, migrations and tests.
- Pytest: 5 passed, 3 skipped. Passed checks: semaphore capacity/counter/event completion, scrypt hashing/verification, JWT claims, PostgreSQL locking SQL compilation and partial unique-index DDL compilation.
- Skipped: 3 real PostgreSQL integration tests (concurrent allocation, same-user race, idempotency/checkout/authorization) because a disposable PostgreSQL server was unavailable. SQL compilation is not execution and does not prove database concurrency behavior.
- Docker CLI was installed, but docker version reported no running Docker engine pipe. PostgreSQL and git executables were not found in PATH or standard PostgreSQL Program Files location. No large runtime was installed or container image downloaded.
- First frontend install failed because the deeply nested Windows agent path caused esbuild binary ENOENT. Repeating in the shorter permitted shared parking-build folder resolved it; this is an environment/path limitation, not an application build failure.
- GitHub connector rejected writing .github/workflows/ci.yml (404/permission limitation). No CI workflow is enabled or verified. The equivalent template is committed at docs/ci-example.yml; the repository owner can copy it to .github/workflows/ci.yml to enable tests with a PostgreSQL 16 service. No browser fallback was used.
- No deployment, live payments, real parking sensors, or full browser-to-database end-to-end validation was performed.

- Recheck: 5 passed, 3 skipped in 2.24 seconds. FastAPI imported successfully and generated an OpenAPI schema with 10 paths.
- docker compose is unavailable in this environment (unknown command); Compose runtime/config validation could not run. PyYAML parsed the configuration and verified the three service names, which is not a Docker execution test. Start/install a working Docker Desktop with Compose for the documented launch.
