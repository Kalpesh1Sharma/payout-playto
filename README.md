# Playto Payout Engine (Django)

## Problem Statement
Build a payout engine that remains financially correct under concurrency: multiple payout requests hitting the same merchant must not overspend, must be idempotent, and must leave an auditable, append-only trail of all money movements.

## Architecture

```
                 +-------------------+
                 |  Merchant Client  |
                 +---------+---------+
                           |
                           | HTTP (Idempotency-Key)
                           v
                 +-------------------+          +------------------+
                 | Django + DRF API  |--------->| PostgreSQL       |
                 | (transactional)   |          | - ledger entries |
                 +---------+---------+          | - payouts        |
                           |                    | - idempotency    |
                           | enqueue            | - audit logs     |
                           v                    +------------------+
                 +-------------------+
                 | Celery Worker     |
                 | (async processing)|
                 +---------+---------+
                           |
                           v
                 +-------------------+
                 | Redis (broker)    |
                 +-------------------+
```

## Core Design Decisions
- **Ledger-first accounting**: no stored “balance” column; balances are derived from the source of truth (ledger) to avoid drift.
- **Single-writer per merchant**: concurrency is serialized at the merchant row so “check funds → create payout → create ledger entry” remains correct under parallel requests.
- **Database-enforced idempotency**: correctness primitives live in PostgreSQL constraints, not in-memory locks.
- **Atomic critical writes**: payout request + ledger movement + idempotency record update happen inside one `transaction.atomic()` to prevent partial state.
- **PostgreSQL-only**: SQLite is intentionally unsupported for correctness; it lacks the locking behavior this design relies on.

## Concurrency Handling
The API uses `SELECT ... FOR UPDATE` on the `Merchant` row inside a transaction to serialize all payout writes for a merchant. This prevents race conditions where two concurrent requests both observe the same derived balance and overspend.

## Idempotency
Requests must provide an `Idempotency-Key` header. The system persists:
- the idempotency key (scoped to merchant),
- the response status,
- the response body.

The database constraint ensures only one “winner” can reserve the key under concurrency. Retries return the stored response instead of creating duplicate payouts.

## Ledger System
- **Append-only**: `LedgerEntry` is immutable after creation.
- **Balances are derived**: available balance is computed as `SUM(amount_paise)` over the merchant’s ledger.
- **All money is paise**: stored as `BigIntegerField` to avoid floating point error.

## Audit Logging
Audit records are written with intent:
- **Success-path logs inside the transaction** so they only exist when the business write commits.
- **Failure-path logs outside the transaction** so error evidence is not lost to rollbacks.

## API Endpoints
Base prefix: `/api/v1`

- `GET /merchants/`
- `GET /merchants/{merchant_id}/`
- `GET /merchants/{merchant_id}/ledger/`
- `POST /merchants/{merchant_id}/payouts/create/` (requires `Idempotency-Key`)
- `GET /merchants/{merchant_id}/payouts/`
- `GET /merchants/{merchant_id}/payouts/{payout_id}/`

## Example API Requests

Create a payout (idempotent):

```bash
curl -X POST "http://localhost:8000/api/v1/merchants/<merchant_uuid>/payouts/create/" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: 7b9d2b3a-1c3e-4b9a-9fb2-2a8c2a6f5b1d" \
  -d '{
    "amount_paise": 25000,
    "bank_account_id": "<bank_account_uuid>"
  }'
```

Fetch derived balances + recent ledger entries:

```bash
curl "http://localhost:8000/api/v1/merchants/<merchant_uuid>/ledger/"
```

## How to Run (Docker)
This project expects PostgreSQL for correct locking.

```bash
docker compose up --build
```

Useful follow-ups:
- Backend API: `http://localhost:8000/`
- Admin: `http://localhost:8000/admin/`
- Teardown: `docker compose down -v`

