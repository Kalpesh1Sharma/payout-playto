# Playto Payout Engine - Explainer

## 1) The Ledger

Balance is derived from immutable ledger entries. Merchant has no balance column.

```python
result = LedgerEntry.objects.filter(merchant=self).aggregate(
    total=Coalesce(Sum("amount_paise"), Value(0))
)
```

Why this model:
- `CREDIT` rows are positive, `DEBIT` rows are negative, `REFUND` rows are positive.
- `amount_paise` is `BigIntegerField` everywhere (no float precision risk).
- Ledger rows are append-only (`LedgerEntry.save()` blocks updates), so history is auditable.

## 2) The Lock

The anti-overdraw lock now uses two DB primitives inside one transaction:

```python
with transaction.atomic():
    locked_merchant = Merchant.objects.select_for_update().get(id=merchant.id)
    locked_entries = LedgerEntry.objects.select_for_update().filter(
        merchant=locked_merchant
    )
    balance = locked_entries.aggregate(
        total=Coalesce(Sum("amount_paise"), Value(0))
    )["total"]
```

Why this matters:
- Merchant row lock serializes payout requests for the same merchant even if ledger is sparse.
- Ledger row lock keeps the balance read and debit write in the same pessimistic lock scope.
- Two simultaneous 6000-paise requests on 10000 balance cannot both pass.

## 3) The Idempotency

Idempotency is stored in DB and scoped by merchant:

```python
unique_together = [("merchant", "key")]
```

Flow:
1. Fast-path check for a non-expired key (`created_at >= now-24h`).
2. Inside `transaction.atomic()`, reserve the key with a placeholder response.
3. Execute payout create + debit.
4. Update that same idempotency row to the final JSON-safe response before commit.

The critical fix here is atomicity: previously payout/debit committed before key persistence (crash window). Now key reservation and final response update happen in the same transaction as monetary writes.

Expired keys are deleted on-demand in the request path (for the same merchant/key) before reserving a new key. This is intentional for simplicity. The tradeoff is slight latency on the first request after expiry, in exchange for avoiding operational overhead of a separate background cleanup job.

## 4) The State Machine

All illegal transitions are blocked centrally in `PayoutRequest.transition_to()`:

```python
allowed = self.LEGAL_TRANSITIONS.get(self.status, [])
if new_status not in allowed:
    raise ValueError(
        f"Illegal state transition: {self.status} -> {new_status}. "
        f"Allowed from {self.status}: {allowed}"
    )
```

So transitions like `FAILED -> COMPLETED` are rejected at model level, not scattered in task code.

## 5) The AI Audit (Concrete)

### Real bug we hit: UUID JSON serialization in idempotency cache

During testing, the original generated `create_payout()` implementation attempted to **persist the DRF serializer output directly** into `IdempotencyKey.response_body`. DRF returns native Python types (including `uuid.UUID` objects), and Django `JSONField` expects JSON-serializable primitives. The result was a crash like: **`TypeError: Object of type UUID is not JSON serializable`** right at the idempotency write.

#### Before (broken)

This was the problematic pattern: storing `PayoutRequestSerializer(...).data` directly.

```python
def _store_idempotency_key(merchant, key, response_status_code, response_body):
    IdempotencyKey.objects.get_or_create(
        merchant=merchant,
        key=key,
        defaults={
            "response_status": response_status_code,
            "response_body": response_body,  # <-- contained UUID objects
        },
    )
```

#### After (fixed in `backend/payouts/views.py`)

The fix was to **force a JSON render/parse roundtrip** before writing to `JSONField`, ensuring UUIDs (and other non-JSON primitives) are converted to strings.

```python
def _update_idempotency_key(idempotency_record, response_status_code, response_body):
    safe_response_body = json.loads(JSONRenderer().render(response_body))
    idempotency_record.response_status = response_status_code
    idempotency_record.response_body = safe_response_body
    idempotency_record.save(update_fields=["response_status", "response_body"])
```

This is intentionally “boring” but correct: the idempotency cache now stores exactly what the API would emit as JSON.
