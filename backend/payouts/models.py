import uuid

from django.db import models


class Merchant(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    bank_account_number = models.CharField(max_length=20)
    bank_ifsc = models.CharField(max_length=11)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "merchants"

    def __str__(self):
        return self.name

    def get_balance(self):
        from django.db.models import Sum, Value
        from django.db.models.functions import Coalesce

        result = LedgerEntry.objects.filter(merchant=self).aggregate(
            total=Coalesce(Sum("amount_paise"), Value(0))
        )
        return result["total"]

    def get_available_balance(self):
        return self.get_balance()

    def get_held_balance(self):
        from django.db.models import Sum, Value
        from django.db.models.functions import Coalesce

        result = PayoutRequest.objects.filter(
            merchant=self,
            status__in=[PayoutRequest.Status.PENDING, PayoutRequest.Status.PROCESSING],
        ).aggregate(total=Coalesce(Sum("amount_paise"), Value(0)))
        return result["total"]


class LedgerEntry(models.Model):
    class EntryType(models.TextChoices):
        CREDIT = "CREDIT", "Credit"
        DEBIT = "DEBIT", "Debit"
        REFUND = "REFUND", "Refund"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merchant = models.ForeignKey(
        Merchant, on_delete=models.PROTECT, related_name="ledger_entries"
    )
    amount_paise = models.BigIntegerField()
    entry_type = models.CharField(max_length=10, choices=EntryType.choices)
    reference_id = models.UUIDField(null=True, blank=True)
    description = models.CharField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "ledger_entries"
        indexes = [
            models.Index(fields=["merchant", "created_at"]),
        ]

    def save(self, *args, **kwargs):
        if self.pk and LedgerEntry.objects.filter(pk=self.pk).exists():
            raise ValueError("LedgerEntry is immutable. Do not update.")
        super().save(*args, **kwargs)


class BankAccount(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merchant = models.ForeignKey(
        Merchant, on_delete=models.PROTECT, related_name="bank_accounts"
    )
    account_number = models.CharField(max_length=20)
    ifsc_code = models.CharField(max_length=11)
    account_holder_name = models.CharField(max_length=255)
    is_primary = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "bank_accounts"


class IdempotencyKey(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merchant = models.ForeignKey(Merchant, on_delete=models.CASCADE)
    key = models.CharField(max_length=255)
    response_status = models.IntegerField()
    response_body = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "idempotency_keys"
        unique_together = [("merchant", "key")]
        indexes = [
            models.Index(fields=["merchant", "key"]),
        ]


class PayoutRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        PROCESSING = "PROCESSING", "Processing"
        COMPLETED = "COMPLETED", "Completed"
        FAILED = "FAILED", "Failed"

    LEGAL_TRANSITIONS = {
        Status.PENDING: [Status.PROCESSING],
        Status.PROCESSING: [Status.COMPLETED, Status.FAILED],
        Status.COMPLETED: [],
        Status.FAILED: [],
    }

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merchant = models.ForeignKey(
        Merchant, on_delete=models.PROTECT, related_name="payout_requests"
    )
    bank_account = models.ForeignKey(BankAccount, on_delete=models.PROTECT)
    amount_paise = models.BigIntegerField()
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    idempotency_key = models.CharField(max_length=255, null=True, blank=True)
    failure_reason = models.TextField(null=True, blank=True)
    attempt_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    processing_started_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "payout_requests"
        indexes = [
            models.Index(fields=["merchant", "status"]),
            models.Index(fields=["status", "processing_started_at"]),
        ]

    def transition_to(self, new_status):
        allowed = self.LEGAL_TRANSITIONS.get(self.status, [])
        if new_status not in allowed:
            raise ValueError(
                f"Illegal state transition: {self.status} -> {new_status}. "
                f"Allowed from {self.status}: {allowed}"
            )
        self.status = new_status
        self.save(update_fields=["status", "updated_at"])


class WebhookEndpoint(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merchant = models.OneToOneField(
        Merchant, on_delete=models.CASCADE, related_name="webhook_endpoint"
    )
    url = models.URLField(max_length=500)
    secret = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "webhook_endpoints"


class WebhookEvent(models.Model):
    class DeliveryStatus(models.TextChoices):
        PENDING = "PENDING", "Pending"
        DELIVERED = "DELIVERED", "Delivered"
        FAILED = "FAILED", "Failed"
        FAILED_PERMANENT = "FAILED_PERMANENT", "Failed (Permanent)"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merchant = models.ForeignKey(Merchant, on_delete=models.PROTECT, related_name="webhook_events")
    event_type = models.CharField(max_length=50)
    payload = models.JSONField()
    delivery_status = models.CharField(
        max_length=20, choices=DeliveryStatus.choices, default=DeliveryStatus.PENDING
    )
    attempt_count = models.IntegerField(default=0)
    next_attempt_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(null=True, blank=True)
    idempotency_key = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "webhook_events"


class PayoutAuditLog(models.Model):
    merchant = models.ForeignKey(Merchant, on_delete=models.PROTECT, related_name="audit_logs")
    actor_type = models.CharField(max_length=50, default="SYSTEM")
    actor_id = models.CharField(max_length=255, null=True, blank=True)
    action = models.CharField(max_length=255)
    resource_type = models.CharField(max_length=255)
    resource_id = models.CharField(max_length=255)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "payout_audit_logs"
        indexes = [
            models.Index(fields=["merchant", "created_at"]),
            models.Index(fields=["resource_type", "resource_id"]),
        ]
