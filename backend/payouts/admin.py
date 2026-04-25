from django.contrib import admin

from .models import (
    AuditLog,
    BankAccount,
    IdempotencyKey,
    LedgerEntry,
    Merchant,
    PayoutRequest,
    WebhookEndpoint,
    WebhookEvent,
)

admin.site.register(Merchant)
admin.site.register(LedgerEntry)
admin.site.register(PayoutRequest)
admin.site.register(BankAccount)
admin.site.register(IdempotencyKey)
admin.site.register(WebhookEndpoint)
admin.site.register(WebhookEvent)
admin.site.register(AuditLog)
