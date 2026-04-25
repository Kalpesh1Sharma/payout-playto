import json
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.db.models import Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response

from .audit import log_audit
from .models import BankAccount, IdempotencyKey, LedgerEntry, Merchant, PayoutRequest
from .serializers import (
    CreatePayoutSerializer,
    LedgerEntrySerializer,
    MerchantSerializer,
    PayoutRequestSerializer,
)
from .tasks import process_payout


@api_view(["GET"])
def merchant_list(request):
    merchants = Merchant.objects.all()
    serializer = MerchantSerializer(merchants, many=True)
    return Response(serializer.data)


@api_view(["GET"])
def merchant_detail(request, merchant_id):
    try:
        merchant = Merchant.objects.get(id=merchant_id)
    except Merchant.DoesNotExist:
        return Response({"error": "Merchant not found"}, status=404)
    serializer = MerchantSerializer(merchant)
    return Response(serializer.data)


@api_view(["GET"])
def merchant_ledger(request, merchant_id):
    try:
        merchant = Merchant.objects.get(id=merchant_id)
    except Merchant.DoesNotExist:
        return Response({"error": "Merchant not found"}, status=404)

    entries = LedgerEntry.objects.filter(merchant=merchant).order_by("-created_at")[:50]
    return Response(
        {
            "available_balance_paise": merchant.get_available_balance(),
            "held_balance_paise": merchant.get_held_balance(),
            "entries": LedgerEntrySerializer(entries, many=True).data,
        }
    )


@api_view(["POST"])
def create_payout(request, merchant_id):
    try:
        merchant = Merchant.objects.get(id=merchant_id)
    except Merchant.DoesNotExist:
        return Response({"error": "Merchant not found"}, status=404)

    idempotency_key = request.headers.get("Idempotency-Key")
    if not idempotency_key:
        return Response(
            {"error": "Idempotency-Key header is required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    expiry = timezone.now() - timedelta(hours=24)
    existing = IdempotencyKey.objects.filter(
        merchant=merchant, key=idempotency_key, created_at__gte=expiry
    ).first()
    if existing:
        return Response(existing.response_body, status=existing.response_status)

    serializer = CreatePayoutSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    amount_paise = serializer.validated_data["amount_paise"]
    bank_account_id = serializer.validated_data["bank_account_id"]

    try:
        bank_account = BankAccount.objects.get(id=bank_account_id, merchant=merchant)
    except BankAccount.DoesNotExist:
        return Response({"error": "Bank account not found"}, status=404)

    try:
        with transaction.atomic():
            # Serialize concurrent requests for this merchant (even with empty ledger).
            locked_merchant = Merchant.objects.select_for_update().get(id=merchant.id)

            # Allow key reuse after 24h by removing expired rows before reserving.
            IdempotencyKey.objects.filter(
                merchant=locked_merchant,
                key=idempotency_key,
                created_at__lt=expiry,
            ).delete()

            try:
                idempotency_record = IdempotencyKey.objects.create(
                    merchant=locked_merchant,
                    key=idempotency_key,
                    response_status=status.HTTP_202_ACCEPTED,
                    response_body={"status": "IN_PROGRESS"},
                )
            except IntegrityError:
                existing = IdempotencyKey.objects.filter(
                    merchant=locked_merchant,
                    key=idempotency_key,
                    created_at__gte=expiry,
                ).first()
                if existing:
                    return Response(existing.response_body, status=existing.response_status)
                raise

            locked_entries = LedgerEntry.objects.select_for_update().filter(
                merchant=locked_merchant
            )
            balance = locked_entries.aggregate(
                total=Coalesce(Sum("amount_paise"), Value(0))
            )["total"]

            if balance < amount_paise:
                response_body = {
                    "error": "Insufficient balance",
                    "available_paise": balance,
                    "requested_paise": amount_paise,
                }
                response_status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
                _update_idempotency_key(idempotency_record, response_status_code, response_body)
                log_audit(
                    merchant=locked_merchant,
                    action="PAYOUT_REJECTED_INSUFFICIENT_BALANCE",
                    resource_type="PayoutRequest",
                    resource_id=idempotency_key,
                    metadata={
                        "idempotency_key": idempotency_key,
                        "available_paise": balance,
                        "requested_paise": amount_paise,
                    },
                    actor_type="API",
                )
                return Response(response_body, status=response_status_code)

            payout = PayoutRequest.objects.create(
                merchant=locked_merchant,
                bank_account=bank_account,
                amount_paise=amount_paise,
                status=PayoutRequest.Status.PENDING,
                idempotency_key=idempotency_key,
            )

            LedgerEntry.objects.create(
                merchant=locked_merchant,
                amount_paise=-amount_paise,
                entry_type=LedgerEntry.EntryType.DEBIT,
                reference_id=payout.id,
                description=f"Payout hold: {amount_paise} paise",
            )

            response_body = PayoutRequestSerializer(payout).data
            response_status_code = status.HTTP_201_CREATED
            _update_idempotency_key(idempotency_record, response_status_code, response_body)
            log_audit(
                merchant=locked_merchant,
                action="PAYOUT_REQUEST_CREATED",
                resource_type="PayoutRequest",
                resource_id=payout.id,
                metadata={
                    "amount_paise": amount_paise,
                    "idempotency_key": idempotency_key,
                    "status": payout.status,
                },
                actor_type="API",
            )

        process_payout.apply_async(args=[str(payout.id)], countdown=2)
        return Response(response_body, status=response_status_code)
    except IntegrityError:
        existing = IdempotencyKey.objects.filter(
            merchant=merchant, key=idempotency_key, created_at__gte=expiry
        ).first()
        if existing:
            return Response(existing.response_body, status=existing.response_status)
        raise


def _update_idempotency_key(idempotency_record, response_status_code, response_body):
    safe_response_body = json.loads(JSONRenderer().render(response_body))
    idempotency_record.response_status = response_status_code
    idempotency_record.response_body = safe_response_body
    idempotency_record.save(update_fields=["response_status", "response_body"])


@api_view(["GET"])
def payout_list(request, merchant_id):
    try:
        merchant = Merchant.objects.get(id=merchant_id)
    except Merchant.DoesNotExist:
        return Response({"error": "Merchant not found"}, status=404)

    payouts = PayoutRequest.objects.filter(merchant=merchant).order_by("-created_at")[:50]
    return Response(PayoutRequestSerializer(payouts, many=True).data)


@api_view(["GET"])
def payout_detail(request, merchant_id, payout_id):
    try:
        payout = PayoutRequest.objects.get(id=payout_id, merchant__id=merchant_id)
    except PayoutRequest.DoesNotExist:
        return Response({"error": "Payout not found"}, status=404)
    return Response(PayoutRequestSerializer(payout).data)
