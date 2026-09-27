# EVE Healthcare — Diagnostic Booking API

A backend service for diagnostic test bookings and simulated payments, built with FastAPI + PostgreSQL.

## Stack

- **FastAPI** (sync route handlers — no async needed for this workload; SQLAlchemy runs them in a threadpool)
- **PostgreSQL** via **SQLAlchemy 2.0** (SQLite in-memory for tests)
- **JWT** auth (PyJWT) with **bcrypt** password hashing (passlib)
- **pytest** + FastAPI `TestClient` for tests

## Running locally

### Option A: Docker (recommended)

```bash
docker compose up --build
```

API is at `http://localhost:8000`, interactive docs at `http://localhost:8000/docs`. Postgres runs as the `db` service; the app waits for its healthcheck before starting.

### Option B: Local Python + your own Postgres

```bash
python -m venv .venv
source .venv/Scripts/activate      # Windows Git Bash; use .venv\Scripts\activate on cmd/PowerShell
pip install -r requirements.txt

cp .env.example .env               # edit DATABASE_URL to point at your Postgres
export $(cat .env | xargs)         # or just set the vars in your shell

uvicorn app.main:app --reload
```

Tables are created automatically on startup (`Base.metadata.create_all`) — no separate migration step needed for this project (see "Assumptions" below).

## Running tests

```bash
pip install -r requirements.txt
pytest -v
```

Tests run entirely against an in-memory SQLite database (forced via `DATABASE_URL` at the top of `tests/conftest.py`), so **no Postgres instance is required to run the test suite**. 34 tests cover auth, centre/test management, booking lifecycle, ownership checks, payment success/failure, and — most importantly — webhook idempotency (including a duplicate-delivery race and a "late success after user-cancel" case).

## API endpoints

All request/response bodies are JSON. Interactive docs (Swagger) are auto-generated at `/docs`.

### Auth

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/auth/signup` | — | Create a user, returns JWT |
| POST | `/auth/login` | — | Returns JWT |

```bash
curl -X POST localhost:8000/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"email":"jane@example.com","password":"password123"}'
# -> {"access_token": "...", "token_type": "bearer"}
```

Use the token as `Authorization: Bearer <token>` on all endpoints below marked "auth required".

### Centres & tests

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/centres/` | — | List centres (with their tests), paginated via `?skip=&limit=` |
| GET | `/centres/{id}` | — | Get one centre |
| POST | `/centres/` | required | Create a centre |
| POST | `/centres/{id}/tests` | required | Add a test (with price) to a centre |

```bash
curl -X POST localhost:8000/centres/ -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" -d '{"name":"City Diagnostics","location":"Pune"}'

curl -X POST localhost:8000/centres/$CENTRE_ID/tests -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" -d '{"name":"Blood Panel","price":"499.00"}'
```

### Bookings (all require auth)

| Method | Path | Description |
|---|---|---|
| POST | `/bookings/` | Book a test (`test_id`, `appointment_time`); status starts `PENDING` |
| GET | `/bookings/` | List the caller's own bookings, paginated |
| GET | `/bookings/{id}` | Get one booking (404 if missing, 403 if not yours) |
| PATCH | `/bookings/{id}/cancel` | Cancel a `PENDING`/`CONFIRMED` booking |

```bash
curl -X POST localhost:8000/bookings/ -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"test_id":"'$TEST_ID'","appointment_time":"2026-10-01T10:00:00Z"}'
```

The booking `amount` is always the test's current price, set server-side — a client cannot supply its own amount.

### Payments

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/payments/` | required | Simulate processing payment for one's own `PENDING` booking |
| POST | `/payments/webhook/` | — (provider callback) | Idempotent payment-status callback |

```bash
# Direct simulated payment (random SUCCESS/FAILED unless force_result is given)
curl -X POST localhost:8000/payments/ -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" -d '{"booking_id":"'$BOOKING_ID'"}'

# Provider webhook
curl -X POST localhost:8000/payments/webhook/ \
  -H "Content-Type: application/json" \
  -d '{"event_id":"evt_123","booking_id":"'$BOOKING_ID'","status":"SUCCESS"}'
```

A `SUCCESS` result moves the booking to `CONFIRMED`; `FAILED` moves it to `FAILED`. Calling `/payments/` a second time for the same booking returns `409 Conflict`.

## Database / schema design

```
users            (id, email UNIQUE, hashed_password, created_at)
diagnostic_centres (id, name, location, created_at)
diagnostic_tests   (id, centre_id FK, name, price, created_at)
bookings         (id, user_id FK, test_id FK, centre_id FK, appointment_time,
                   amount, status ENUM[PENDING|CONFIRMED|FAILED|CANCELLED], created_at, updated_at)
payments         (id, booking_id FK UNIQUE, status ENUM[PENDING|SUCCESS|FAILED], created_at, updated_at)
webhook_events   (id, event_id UNIQUE, payload JSON, created_at)
```

Design notes:
- `bookings.amount` is a **snapshot** of the test's price at booking time (test prices can change later without altering historical bookings).
- `bookings.centre_id` is stored redundantly alongside `test_id` (even though it's derivable via the test) because the spec calls it out as a first-class field on a booking, and it avoids an extra join on every read.
- `payments.booking_id` is `UNIQUE` — one payment attempt per booking by design (see "Idempotency" below for why retries don't need a second row).
- `webhook_events.event_id` is `UNIQUE` — this is the whole idempotency mechanism (see below).

## Idempotency (webhook)

`POST /payments/webhook/` is the part of the spec explicitly called out as needing to survive duplicate delivery. Approach:

1. On receipt, look up `WebhookEvent` by `event_id`. If found, return `200 {"status": "already_processed"}` immediately — no state is touched.
2. Otherwise, apply the status to the booking/payment **and** insert the `WebhookEvent` row, in the same DB transaction.
3. The insert has a `UNIQUE` constraint on `event_id`. If two identical webhook calls race each other past the step-1 check simultaneously, one of the two commits fails with an `IntegrityError`; that request rolls back and also returns `already_processed`. This closes the check-then-act race that a plain "SELECT then INSERT" would otherwise leave open.

A duplicate/late webhook also can't resurrect a booking the user has since cancelled — cancellation is treated as a terminal state that payment events don't override (covered by a test).

The direct `POST /payments/` endpoint additionally refuses a second payment for a booking that already has one (`409`), so double-submitting that endpoint can't create two payment records either.

## Assumptions

- **No Alembic migrations.** Tables are created via `Base.metadata.create_all()` on startup. For a project this size that's simpler and has one less moving part than wiring up a migration tool; see "What I'd improve" for what I'd do instead at a larger scale.
- **No admin/role system.** The spec doesn't call for one, so any authenticated user can create centres and tests (in a real product this would be admin-only). Reading centres/tests is public (no login needed) since a patient browsing options shouldn't need an account first.
- **One payment per booking.** The spec doesn't describe retry-after-failure explicitly, so a `FAILED` booking currently cannot be repaid — the intended flow is to place a new booking. This was the simplest interpretation; a "retry payment" endpoint is a natural extension (see below).
- **Payment result is randomized** unless `force_result` is passed in the request body — added purely so the flow is deterministically testable/demoable without depending on chance.
- **Appointment time must be in the future** at booking time; this is the only scheduling business rule applied (no conflict/slot checking against centre capacity, since the spec doesn't describe centre capacity).

## What I'd improve with more time

- Alembic migrations instead of `create_all`, for real schema evolution.
- A `retry payment` flow for `FAILED` bookings instead of one-shot-only payments.
- Role-based access (admin vs. patient) for centre/test management.
- Redis-backed rate limiting on `/auth/login` and the webhook endpoint.
- Celery/background worker to process webhooks asynchronously with retry/backoff instead of handling them inline in the request.
- Request-scoped structured logging (a request-id per log line) instead of the current minimal JSON formatter.
- Integration tests running against a real Postgres container (via testcontainers) in addition to the current SQLite-based unit/integration tests, to catch Postgres-specific behavior.
