# Presentation and viva guide

## Suggested eight-slide structure
1. Problem: manual parking management causes searching, double allocation and slow checkout.
2. Objectives: authenticated allocation, occupancy visibility, transaction safety, transparent billing and concurrency learning.
3. Architecture: browser React UI -> REST FastAPI -> SQLAlchemy -> PostgreSQL; Alembic evolves schema.
4. Data model: users (identity/role), slots (physical spaces), bookings (user/slot/vehicle/times/fee/request key). One user has many historical bookings; one slot has many historical bookings; each has at most one active booking.
5. Allocation algorithm: user lock -> replay check -> active booking check -> first free slot row lock with SKIP LOCKED -> insert -> commit. On failure rollback.
6. OS laboratory: semaphore allows up to three workers; mutex protects active count, peak, log and completed counter. Demo shows event ordering and no lost counter updates.
7. Real concurrency: PostgreSQL transactions, row locks and partial unique indexes work across backend instances. Python primitives only synchronize one process.
8. Results/limits: local MVP; discuss verified build/unit checks and whether integration tests ran. Future work: sensors, reservations, rate limiting, secure deployment, payment.

## Demonstration (5–7 minutes)
- Start Compose and show /health and Swagger /docs.
- Register a user, view 12 slots, enter a synthetic vehicle, allocate a slot.
- Refresh to show occupied state. Attempt a second allocation via API: 409.
- Check out: minimum fee INR 20, slot becomes free, history records completion.
- Sign in as locally created admin; show occupancy and revenue.
- Run thread laboratory: eight completions, peak concurrency <=3, 16 enter/exit events.
- Explain integration test: twelve concurrent users, three slots, exactly three winners and no duplicate occupied slot.

## Viva questions
**Why semaphore rather than mutex for capacity?** A semaphore permits several workers at once; a mutex protects one critical section at a time.
**Does the Python semaphore reserve real parking spaces?** No. It illustrates synchronization locally; PostgreSQL enforces persistent allocation in a multi-process system.
**What is a race condition?** Concurrent operations reading the same free state and both trying to write. Locks and constraints prevent duplicate allocation.
**Why both locks and unique indexes?** Locks coordinate the intended path; indexes are a final database invariant even if another code path bypasses the algorithm.
**What is idempotency?** Repeating the same operation key produces the same original booking, avoiding duplicates after network retries.
**Can availability change after display?** Yes. Only successful transaction commit confirms allocation.
**Deadlock prevention?** Allocation consistently locks user then slot. Checkout locks only its booking. Keep transactions short; handle conflicts with retry rather than leaving partial state.
**Billing?** ceil(elapsed seconds / 3600), minimum one hour, 2000 paise per hour; integer amounts avoid floating-point money errors.
**Algorithm complexity?** Ordered slot search depends on slot/booking indexes and database query planner; not falsely claimed constant time. Academic scale is 12 slots.

## Deliverables
Code, dependency manifests/lockfile, migration, Compose, setup guide, repeatable test suite and presentation notes. These notes are not an institution-provided rubric; adapt screenshots/name/roll number/slides to your department's requirements.
