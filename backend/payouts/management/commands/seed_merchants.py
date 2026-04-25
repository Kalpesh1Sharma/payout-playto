from django.core.management.base import BaseCommand
from django.db import transaction

from payouts.models import BankAccount, LedgerEntry, Merchant


class Command(BaseCommand):
    help = "Seed merchant data with credit history"

    def handle(self, *args, **options):
        with transaction.atomic():
            self.stdout.write("Seeding merchants...")

            merchants_data = [
                {
                    "name": "Arjun Design Studio",
                    "email": "arjun@designstudio.in",
                    "bank_account_number": "1234567890123456",
                    "bank_ifsc": "HDFC0001234",
                    "credits": [500000, 250000, 750000, 100000],
                },
                {
                    "name": "Priya SaaS Solutions",
                    "email": "priya@saassolutions.in",
                    "bank_account_number": "9876543210987654",
                    "bank_ifsc": "ICIC0009876",
                    "credits": [1000000, 500000, 2000000],
                },
                {
                    "name": "Rahul Freelance Dev",
                    "email": "rahul@freelance.dev",
                    "bank_account_number": "1111222233334444",
                    "bank_ifsc": "SBIN0001111",
                    "credits": [150000, 300000, 450000, 200000, 600000],
                },
            ]

            for data in merchants_data:
                merchant, created = Merchant.objects.get_or_create(
                    email=data["email"],
                    defaults={
                        "name": data["name"],
                        "bank_account_number": data["bank_account_number"],
                        "bank_ifsc": data["bank_ifsc"],
                    },
                )

                if created:
                    BankAccount.objects.create(
                        merchant=merchant,
                        account_number=data["bank_account_number"],
                        ifsc_code=data["bank_ifsc"],
                        account_holder_name=data["name"],
                        is_primary=True,
                    )

                    for i, amount in enumerate(data["credits"]):
                        LedgerEntry.objects.create(
                            merchant=merchant,
                            amount_paise=amount,
                            entry_type=LedgerEntry.EntryType.CREDIT,
                            description=f"Customer payment #{i + 1} via Playto Pay",
                        )

                    self.stdout.write(
                        f"  Created: {merchant.name} | Balance: Rs {sum(data['credits']) / 100:.0f}"
                    )
                else:
                    self.stdout.write(f"  Already exists: {merchant.name}")

        self.stdout.write(self.style.SUCCESS("Seeding complete."))
