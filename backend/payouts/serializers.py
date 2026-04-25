from rest_framework import serializers

from .models import BankAccount, LedgerEntry, Merchant, PayoutRequest


class BankAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = BankAccount
        fields = ["id", "account_number", "ifsc_code", "account_holder_name", "is_primary"]


class MerchantSerializer(serializers.ModelSerializer):
    available_balance_paise = serializers.SerializerMethodField()
    held_balance_paise = serializers.SerializerMethodField()
    bank_accounts = BankAccountSerializer(many=True, read_only=True)

    class Meta:
        model = Merchant
        fields = [
            "id",
            "name",
            "email",
            "available_balance_paise",
            "held_balance_paise",
            "bank_accounts",
            "created_at",
        ]

    def get_available_balance_paise(self, obj):
        return obj.get_available_balance()

    def get_held_balance_paise(self, obj):
        return obj.get_held_balance()


class LedgerEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = LedgerEntry
        fields = ["id", "amount_paise", "entry_type", "reference_id", "description", "created_at"]


class PayoutRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = PayoutRequest
        fields = [
            "id",
            "merchant",
            "bank_account",
            "amount_paise",
            "status",
            "failure_reason",
            "attempt_count",
            "idempotency_key",
            "created_at",
            "updated_at",
        ]


class CreatePayoutSerializer(serializers.Serializer):
    amount_paise = serializers.IntegerField(min_value=100)
    bank_account_id = serializers.UUIDField()

    def validate_amount_paise(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be positive")
        return value
