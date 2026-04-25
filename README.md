# Playto Payout Engine

Production-style payout engine built with Django, DRF, Celery, PostgreSQL, Redis, React, and Tailwind.

## Stack

- Backend: Django 4.2 + DRF
- Queue: Celery + Redis
- DB: PostgreSQL
- Frontend: React + Vite + Tailwind

## Project Layout

- `backend/` - API, ledger, payout state machine, celery tasks, tests
- `frontend/` - merchant dashboard for balances and payout operations
- `docker-compose.yml` - local orchestration for db/redis/backend/worker/frontend

## Quick Start (Local)

### 1) Backend

```bash
cd backend
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
# source .venv/bin/activate
pip install -r requirements.txt
python manage.py makemigrations payouts
python manage.py migrate
python manage.py seed_merchants
python manage.py runserver
```

### 2) Worker

```bash
cd backend
celery -A config worker --loglevel=info
```

### 3) Frontend

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173).

## Docker Smoke Check

Use this when you want a quick end-to-end validation without relying on local Python setup.

### Start + validate (Windows PowerShell)

```powershell
.\scripts\smoke-check.ps1
```

### Start + validate (macOS/Linux)

```bash
chmod +x ./scripts/smoke-check.sh
./scripts/smoke-check.sh
```

### Fast rerun without rebuild

```powershell
.\scripts\smoke-check.ps1 -NoRebuild
```

```bash
./scripts/smoke-check.sh --no-build
```

### Teardown

```bash
docker compose down
```

## API Endpoints

- `GET /api/v1/merchants/`
- `GET /api/v1/merchants/{merchant_id}/`
- `GET /api/v1/merchants/{merchant_id}/ledger/`
- `POST /api/v1/merchants/{merchant_id}/payouts/create/`
  - Requires `Idempotency-Key` header
- `GET /api/v1/merchants/{merchant_id}/payouts/`
- `GET /api/v1/merchants/{merchant_id}/payouts/{payout_id}/`

## Running Tests

```bash
cd backend
python manage.py test payouts
```

## Notes

- All money is stored in paise using `BigIntegerField`.
- Merchant balance is derived from immutable ledger aggregation.
- Concurrency protection uses `select_for_update()` inside `transaction.atomic()`.
- Idempotency is enforced by DB unique constraint on `(merchant, key)`.
