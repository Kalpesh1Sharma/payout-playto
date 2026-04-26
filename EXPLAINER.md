# Playto Payout Engine - Explainer

## 1) The Ledger

Balance is derived from immutable ledger entries. Merchant has no balance column.

```python
result = LedgerEntry.objects.filter(merchant=self).aggregate(
    total=Coalesce(Sum("amount_paise"), Value(0))
)
```

Why this design:

1. No balance field is stored on Merchant
2. This guarantees financial correctness even under partial failures or crashes.
3. Ledger is append only → prevents inconsistencies
4. Using integers (paise) avoids floating point errors

## 2) The Lock

The anti-overdraw lock now uses two DB primitives inside one transaction:

```python
with transaction.atomic():
    locked_merchant = Merchant.objects.select_for_update().get(id=merchant.id)
    balance = LedgerEntry.objects.filter(
        merchant=locked_merchant
    ).aggregate(total=Coalesce(Sum("amount_paise"), Value(0)))["total"]

    if balance < amount_paise:
        # reject
    
    LedgerEntry.objects.create(amount_paise=-amount_paise, ...)
```

The Merchant row is locked using SELECT FOR UPDATE.
This serializes all payout requests per merchant and ensures
"check balance → deduct funds" happens atomically.
Locking ledger rows is unnecessary because the merchant lock
already prevents concurrent writes for that merchant.
This prevents double spending under concurrent requests.

## 3) The Idempotency

### How system knows key exists:

1. DB constraint:

```python
class Meta:
    db_table = "idempotency_keys"
    unique_together = [("merchant", "key")]
```
The idempotency response is stored in a JSON-safe format. Initially, storing DRF serializer output caused UUID serialization errors, which would break idempotency guarantees. This was fixed using DRF’s JSONRenderer.

Flow:

1. First request → creates payout + stores response
2. Retry request → reads stored response

Concurrent case:

1. Both requests try to insert same key
2. One succeeds
3. Other gets IntegrityError → returns existing response
4. This ensures safe retries without creating duplicate payouts.



## 4) The State Machine


```python
allowed = self.LEGAL_TRANSITIONS.get(self.status, [])
if new_status not in allowed:
    raise ValueError(
        f"Illegal state transition: {self.status} -> {new_status}. "
        f"Allowed from {self.status}: {allowed}"
    )
```

Where it's enforced:

1. Inside model method (transition_to)
2. Called inside transaction.atomic()

Why it works:

1. Prevents invalid transitions (e.g., FAILED → COMPLETED)
2. Ensures state + ledger updates happen together

## 5) The AI Audit (Concrete)

### What AI generated:

```python
def _store_idempotency_key(merchant, key, response_status_code, response_body):
    IdempotencyKey.objects.get_or_create(
        merchant=merchant,
        key=key,
        defaults={
            'response_status': response_status_code,
            'response_body': response_body,  # raw DRF serializer output
        }
    )
```

#### Issue
1. serializer.data contains UUID objects
2. JSONField requires JSON-serializable data
3. Crash
```
TypeError: Object of type UUID is not JSON serializable
```
4. This bug was critical because it silently broke idempotency guarantees.

### What I replaced it with:

```python
from rest_framework.renderers import JSONRenderer
import json

safe_body = json.loads(JSONRenderer().render(response_body))
IdempotencyKey.objects.get_or_create(
    merchant=merchant,
    key=key,
    defaults={
        'response_status': response_status_code,
        'response_body': safe_body,
    }
)

```

Ensures:

1. UUIDs and datetimes serialized correctly
2. Safe storage in JSONField
3. Without this fix, payouts would succeed but idempotency keys would not be stored. Retries would create duplicate payouts and double deduct the merchant's balance.