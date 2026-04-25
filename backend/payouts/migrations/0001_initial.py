from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="BankAccount",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("account_number", models.CharField(max_length=20)),
                ("ifsc_code", models.CharField(max_length=11)),
                ("account_holder_name", models.CharField(max_length=255)),
                ("is_primary", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"db_table": "bank_accounts"},
        ),
        migrations.CreateModel(
            name="Merchant",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=255)),
                ("email", models.EmailField(max_length=254, unique=True)),
                ("bank_account_number", models.CharField(max_length=20)),
                ("bank_ifsc", models.CharField(max_length=11)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"db_table": "merchants"},
        ),
        migrations.CreateModel(
            name="PayoutRequest",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("amount_paise", models.BigIntegerField()),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("PENDING", "Pending"),
                            ("PROCESSING", "Processing"),
                            ("COMPLETED", "Completed"),
                            ("FAILED", "Failed"),
                        ],
                        default="PENDING",
                        max_length=20,
                    ),
                ),
                ("idempotency_key", models.CharField(blank=True, max_length=255, null=True)),
                ("failure_reason", models.TextField(blank=True, null=True)),
                ("attempt_count", models.IntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("processing_started_at", models.DateTimeField(blank=True, null=True)),
                ("bank_account", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="payouts.bankaccount")),
                (
                    "merchant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="payout_requests",
                        to="payouts.merchant",
                    ),
                ),
            ],
            options={"db_table": "payout_requests"},
        ),
        migrations.AddField(
            model_name="bankaccount",
            name="merchant",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="bank_accounts",
                to="payouts.merchant",
            ),
        ),
        migrations.CreateModel(
            name="LedgerEntry",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("amount_paise", models.BigIntegerField()),
                ("entry_type", models.CharField(choices=[("CREDIT", "Credit"), ("DEBIT", "Debit"), ("REFUND", "Refund")], max_length=10)),
                ("reference_id", models.UUIDField(blank=True, null=True)),
                ("description", models.CharField(max_length=500)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "merchant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="ledger_entries",
                        to="payouts.merchant",
                    ),
                ),
            ],
            options={"db_table": "ledger_entries"},
        ),
        migrations.CreateModel(
            name="IdempotencyKey",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("key", models.CharField(max_length=255)),
                ("response_status", models.IntegerField()),
                ("response_body", models.JSONField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("merchant", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="payouts.merchant")),
            ],
            options={
                "db_table": "idempotency_keys",
                "unique_together": {("merchant", "key")},
            },
        ),
        migrations.AddIndex(
            model_name="payoutrequest",
            index=models.Index(fields=["merchant", "status"], name="payout_requ_merchan_6f8a8f_idx"),
        ),
        migrations.AddIndex(
            model_name="payoutrequest",
            index=models.Index(fields=["status", "processing_started_at"], name="payout_requ_status_807387_idx"),
        ),
        migrations.AddIndex(
            model_name="ledgerentry",
            index=models.Index(fields=["merchant", "created_at"], name="ledger_entr_merchan_0dbf08_idx"),
        ),
        migrations.AddIndex(
            model_name="idempotencykey",
            index=models.Index(fields=["merchant", "key"], name="idempotency_merchant_8c8f90_idx"),
        ),
    ]
