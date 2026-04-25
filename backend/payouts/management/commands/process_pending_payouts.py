from django.core.management.base import BaseCommand
from django.db import close_old_connections

from payouts.models import PayoutRequest
from payouts.tasks import process_payout, retry_stuck_payouts


class Command(BaseCommand):
    help = (
        "Process payout lifecycle inline (no Celery worker). "
        "1) Retry stuck PROCESSING payouts. "
        "2) Process all PENDING payouts synchronously."
    )

    def handle(self, *args, **options):
        close_old_connections()

        self.stdout.write("Running retry_stuck_payouts() ...")
        retry_stuck_payouts()

        pending_ids = list(
            PayoutRequest.objects.filter(status=PayoutRequest.Status.PENDING).values_list(
                "id", flat=True
            )
        )

        if not pending_ids:
            self.stdout.write("No PENDING payouts found.")
            return

        self.stdout.write(f"Processing {len(pending_ids)} PENDING payouts inline ...")
        processed = 0
        failed = 0

        for payout_id in pending_ids:
            close_old_connections()
            try:
                # Synchronous execution of the Celery task logic (no apply_async / no delay).
                # Celery tasks are callable; calling executes .run() inline.
                process_payout(str(payout_id))
                processed += 1
            except Exception as exc:  # noqa: BLE001 - command should keep going
                failed += 1
                self.stderr.write(f"Error processing payout {payout_id}: {exc!r}")

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. processed={processed} failed={failed} total={len(pending_ids)}"
            )
        )
        close_old_connections()
