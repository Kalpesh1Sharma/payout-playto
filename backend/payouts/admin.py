from django.contrib import admin

from .models import (
    BankAccount,
    IdempotencyKey,
    LedgerEntry,
    Merchant,
    PayoutAuditLog,
    PayoutRequest,
    WebhookEndpoint,
)

admin.site.register(Merchant)
admin.site.register(LedgerEntry)
admin.site.register(PayoutRequest)
admin.site.register(BankAccount)
admin.site.register(IdempotencyKey)
admin.site.register(WebhookEndpoint)
admin.site.register(PayoutAuditLog)
