import hashlib
import hmac
import json
import logging
import random
import uuid
from datetime import timedelta
from urllib import error, request

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from .audit import log_audit
from .models import LedgerEntry, PayoutRequest, WebhookEndpoint, WebhookEvent

logger = logging.getLogger(__name__)

PROCESSING_TIMEOUT_SECONDS = 30
MAX_ATTEMPTS = 3
MAX_WEBHOOK_ATTEMPTS = 8


@shared_task(bind=True, max_retries=3)
def process_payout(self, payout_id: str):
    try:
        payout = PayoutRequest.objects.select_related("merchant").get(id=payout_id)
    except PayoutRequest.DoesNotExist:
        logger.error("Payout %s not found", payout_id)
        return

    if payout.status in [PayoutRequest.Status.COMPLETED, PayoutRequest.Status.FAILED]:
        logger.info("Payout %s already terminal: %s", payout_id, payout.status)
        return

    try:
        with transaction.atomic():
            locked_payout = PayoutRequest.objects.select_for_update().get(id=payout_id)
            if locked_payout.status != PayoutRequest.Status.PENDING:
                logger.info(
                    "Payout %s already being processed: %s",
                    payout_id,
                    locked_payout.status,
                )
                return
            locked_payout.transition_to(PayoutRequest.Status.PROCESSING)
            locked_payout.attempt_count += 1
            locked_payout.processing_started_at = timezone.now()
            locked_payout.save(
                update_fields=["attempt_count", "processing_started_at", "updated_at"]
            )
            log_audit(
                merchant=locked_payout.merchant,
                action="PAYOUT_PROCESSING_STARTED",
                resource_type="PayoutRequest",
                resource_id=locked_payout.id,
                metadata={"attempt_count": locked_payout.attempt_count},
            )
            payout = locked_payout
    except ValueError as exc:
        logger.error("State transition error for %s: %s", payout_id, exc)
        return

    roll = random.random()
    if roll < 0.70:
        _complete_payout(payout)
    elif roll < 0.90:
        _fail_payout(payout, reason="Bank rejected the transfer")
    else:
        logger.warning("Payout %s is hanging (simulated bank timeout)", payout_id)


def _complete_payout(payout: PayoutRequest):
    try:
        with transaction.atomic():
            payout.transition_to(PayoutRequest.Status.COMPLETED)
            log_audit(
                merchant=payout.merchant,
                action="PAYOUT_COMPLETED",
                resource_type="PayoutRequest",
                resource_id=payout.id,
                metadata={"amount_paise": payout.amount_paise},
            )
            _enqueue_webhook_events(payout, "payout.completed")
            logger.info("Payout %s completed successfully", payout.id)
    except ValueError as exc:
        logger.error("Cannot complete payout %s: %s", payout.id, exc)


def _fail_payout(payout: PayoutRequest, reason: str):
    try:
        with transaction.atomic():
            payout.transition_to(PayoutRequest.Status.FAILED)
            payout.failure_reason = reason
            payout.save(update_fields=["failure_reason", "updated_at"])

            LedgerEntry.objects.create(
                merchant=payout.merchant,
                amount_paise=payout.amount_paise,
                entry_type=LedgerEntry.EntryType.REFUND,
                reference_id=payout.id,
                description=f"Payout failed refund: {payout.amount_paise} paise. Reason: {reason}",
            )
            log_audit(
                merchant=payout.merchant,
                action="PAYOUT_FAILED",
                resource_type="PayoutRequest",
                resource_id=payout.id,
                metadata={"amount_paise": payout.amount_paise, "reason": reason},
            )
            log_audit(
                merchant=payout.merchant,
                action="PAYOUT_REFUND_CREATED",
                resource_type="LedgerEntry",
                resource_id=payout.id,
                metadata={"amount_paise": payout.amount_paise},
            )
            _enqueue_webhook_events(payout, "payout.failed")
            logger.info("Payout %s failed. Refunded %s paise.", payout.id, payout.amount_paise)
    except ValueError as exc:
        logger.error("Cannot fail payout %s: %s", payout.id, exc)


@shared_task
def retry_stuck_payouts():
    cutoff = timezone.now() - timedelta(seconds=PROCESSING_TIMEOUT_SECONDS)
    stuck_payouts = PayoutRequest.objects.filter(
        status=PayoutRequest.Status.PROCESSING, processing_started_at__lt=cutoff
    )

    for payout in stuck_payouts:
        if payout.attempt_count >= MAX_ATTEMPTS:
            logger.warning(
                "Payout %s exceeded max attempts (%s). Failing.", payout.id, MAX_ATTEMPTS
            )
            _fail_payout(payout, reason=f"Exceeded max retry attempts ({MAX_ATTEMPTS})")
        else:
            backoff_seconds = 10 * (2 ** payout.attempt_count)
            logger.info(
                "Retrying payout %s (attempt %s), backoff=%ss",
                payout.id,
                payout.attempt_count,
                backoff_seconds,
            )
            with transaction.atomic():
                locked = PayoutRequest.objects.select_for_update().get(id=payout.id)
                if locked.status == PayoutRequest.Status.PROCESSING:
                    locked.status = PayoutRequest.Status.PENDING
                    locked.processing_started_at = None
                    locked.save(
                        update_fields=["status", "processing_started_at", "updated_at"]
                    )
                    log_audit(
                        merchant=locked.merchant,
                        action="PAYOUT_RETRY_SCHEDULED",
                        resource_type="PayoutRequest",
                        resource_id=locked.id,
                        metadata={
                            "attempt_count": locked.attempt_count,
                            "backoff_seconds": backoff_seconds,
                        },
                    )
                    process_payout.apply_async(args=[str(payout.id)], countdown=backoff_seconds)


def _enqueue_webhook_events(payout: PayoutRequest, event_type: str):
    endpoints = WebhookEndpoint.objects.filter(merchant=payout.merchant, is_active=True)
    payload = {
        "event_type": event_type,
        "payout_id": str(payout.id),
        "merchant_id": str(payout.merchant_id),
        "amount_paise": payout.amount_paise,
        "status": payout.status,
        "failure_reason": payout.failure_reason,
        "attempt_count": payout.attempt_count,
        "occurred_at": timezone.now().isoformat(),
    }
    for endpoint in endpoints:
        event = WebhookEvent.objects.create(
            merchant=payout.merchant,
            endpoint=endpoint,
            event_type=event_type,
            payload=payload,
            idempotency_key=str(uuid.uuid4()),
            next_attempt_at=timezone.now(),
        )
        deliver_webhook.delay(str(event.id))


@shared_task
def deliver_webhook(webhook_event_id: str):
    try:
        event = WebhookEvent.objects.select_related("endpoint", "merchant").get(
            id=webhook_event_id
        )
    except WebhookEvent.DoesNotExist:
        return

    if event.delivery_status == WebhookEvent.DeliveryStatus.DELIVERED:
        return
    if event.attempt_count >= MAX_WEBHOOK_ATTEMPTS:
        return

    body = json.dumps(event.payload).encode("utf-8")
    signature = hmac.new(
        event.endpoint.secret.encode("utf-8"), body, hashlib.sha256
    ).hexdigest()

    req = request.Request(
        event.endpoint.url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-Playto-Event-Id": str(event.id),
            "X-Playto-Event-Type": event.event_type,
            "X-Playto-Idempotency-Key": event.idempotency_key,
            "X-Playto-Signature": signature,
        },
    )

    try:
        with request.urlopen(req, timeout=5) as resp:
            status_code = resp.getcode()
    except (error.URLError, error.HTTPError, TimeoutError) as exc:
        _mark_webhook_retry(event, f"Request failed: {exc}")
        return

    if 200 <= status_code < 300:
        event.delivery_status = WebhookEvent.DeliveryStatus.DELIVERED
        event.attempt_count += 1
        event.last_error = None
        event.delivered_at = timezone.now()
        event.next_attempt_at = None
        event.save(
            update_fields=[
                "delivery_status",
                "attempt_count",
                "last_error",
                "delivered_at",
                "next_attempt_at",
            ]
        )
        return

    _mark_webhook_retry(event, f"Non-2xx status: {status_code}")


def _mark_webhook_retry(event: WebhookEvent, error_message: str):
    event.attempt_count += 1
    if event.attempt_count >= MAX_WEBHOOK_ATTEMPTS:
        event.delivery_status = WebhookEvent.DeliveryStatus.FAILED_PERMANENT
        event.next_attempt_at = None
    else:
        backoff_seconds = 10 * (2 ** (event.attempt_count - 1))
        event.delivery_status = WebhookEvent.DeliveryStatus.FAILED_RETRY
        event.next_attempt_at = timezone.now() + timedelta(seconds=backoff_seconds)
    event.last_error = error_message
    event.save(
        update_fields=[
            "attempt_count",
            "delivery_status",
            "next_attempt_at",
            "last_error",
        ]
    )


@shared_task
def retry_pending_webhooks():
    now = timezone.now()
    pending = WebhookEvent.objects.filter(
        delivery_status__in=[
            WebhookEvent.DeliveryStatus.PENDING,
            WebhookEvent.DeliveryStatus.FAILED_RETRY,
        ],
        next_attempt_at__lte=now,
    )[:100]
    for event in pending:
        deliver_webhook.delay(str(event.id))
