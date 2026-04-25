import threading
import uuid

from django.db import close_old_connections
from django.test import TestCase, TransactionTestCase
from rest_framework.test import APIClient

from .models import BankAccount, LedgerEntry, Merchant, PayoutRequest


def create_test_merchant(name="Test Merchant", balance_paise=10000):
    merchant = Merchant.objects.create(
        name=name,
        email=f"{uuid.uuid4()}@test.com",
        bank_account_number="1234567890",
        bank_ifsc="TEST0000001",
    )
    bank_account = BankAccount.objects.create(
        merchant=merchant,
        account_number="1234567890",
        ifsc_code="TEST0000001",
        account_holder_name=name,
        is_primary=True,
    )
    LedgerEntry.objects.create(
        merchant=merchant,
        amount_paise=balance_paise,
        entry_type=LedgerEntry.EntryType.CREDIT,
        description="Test seed credit",
    )
    return merchant, bank_account


class IdempotencyTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.merchant, self.bank_account = create_test_merchant(balance_paise=100000)
        self.url = f"/api/v1/merchants/{self.merchant.id}/payouts/create/"
        self.idempotency_key = str(uuid.uuid4())

    def test_same_key_returns_same_response(self):
        payload = {
            "amount_paise": 5000,
            "bank_account_id": str(self.bank_account.id),
        }
        headers = {"HTTP_IDEMPOTENCY_KEY": self.idempotency_key}
        response1 = self.client.post(self.url, payload, format="json", **headers)
        response2 = self.client.post(self.url, payload, format="json", **headers)

        self.assertEqual(response1.status_code, 201)
        self.assertEqual(response2.status_code, 201)
        self.assertEqual(response1.data["id"], response2.data["id"])
        self.assertEqual(PayoutRequest.objects.filter(merchant=self.merchant).count(), 1)

    def test_missing_idempotency_key_returns_400(self):
        payload = {"amount_paise": 5000, "bank_account_id": str(self.bank_account.id)}
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, 400)


class ConcurrencyTest(TransactionTestCase):
    def setUp(self):
        self.merchant, self.bank_account = create_test_merchant(balance_paise=10000)
        self.url = f"/api/v1/merchants/{self.merchant.id}/payouts/create/"
        self.results = []
        self.results_lock = threading.Lock()
        self.start_barrier = threading.Barrier(2)

    def _make_request(self, amount_paise):
        close_old_connections()
        client = APIClient()
        payload = {
            "amount_paise": amount_paise,
            "bank_account_id": str(self.bank_account.id),
        }
        self.start_barrier.wait()
        response = client.post(
            self.url, payload, format="json", HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4())
        )
        with self.results_lock:
            self.results.append(response.status_code)
        close_old_connections()

    def test_concurrent_overdraw_rejected(self):
        t1 = threading.Thread(target=self._make_request, args=(6000,))
        t2 = threading.Thread(target=self._make_request, args=(6000,))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        self.assertEqual(self.results.count(201), 1)
        self.assertEqual(self.results.count(422), 1)
        self.merchant.refresh_from_db()
        self.assertEqual(self.merchant.get_available_balance(), 4000)


class StateMachineTest(TestCase):
    def setUp(self):
        self.merchant, self.bank_account = create_test_merchant()

    def _create_payout(self, status):
        return PayoutRequest.objects.create(
            merchant=self.merchant,
            bank_account=self.bank_account,
            amount_paise=1000,
            status=status,
        )

    def test_completed_to_pending_is_illegal(self):
        payout = self._create_payout(PayoutRequest.Status.COMPLETED)
        with self.assertRaises(ValueError):
            payout.transition_to(PayoutRequest.Status.PENDING)

    def test_failed_to_completed_is_illegal(self):
        payout = self._create_payout(PayoutRequest.Status.FAILED)
        with self.assertRaises(ValueError):
            payout.transition_to(PayoutRequest.Status.COMPLETED)

    def test_pending_to_processing_is_legal(self):
        payout = self._create_payout(PayoutRequest.Status.PENDING)
        payout.transition_to(PayoutRequest.Status.PROCESSING)
        self.assertEqual(payout.status, PayoutRequest.Status.PROCESSING)
