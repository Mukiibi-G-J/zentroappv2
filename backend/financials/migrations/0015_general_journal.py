# Generated manually for General Journal worksheet

import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("financials", "0014_add_performance_indexes"),
    ]

    operations = [
        migrations.CreateModel(
            name="GeneralJournalBatch",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "system_id",
                    models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=50, unique=True, verbose_name="Name")),
                (
                    "description",
                    models.CharField(
                        blank=True,
                        max_length=200,
                        null=True,
                        verbose_name="Description",
                    ),
                ),
            ],
            options={
                "verbose_name": "General Journal Batch",
                "verbose_name_plural": "General Journal Batches",
                "ordering": ["name"],
                "indexes": [
                    models.Index(fields=["name"], name="fin_gjbatch_name_idx"),
                ],
            },
        ),
        migrations.CreateModel(
            name="GeneralJournalLine",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "system_id",
                    models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("batch_name", models.CharField(max_length=50, verbose_name="Batch Name")),
                ("line_no", models.IntegerField(default=10000, verbose_name="Line No.")),
                (
                    "posting_date",
                    models.DateField(blank=True, null=True, verbose_name="Posting Date"),
                ),
                (
                    "vat_reporting_date",
                    models.DateField(blank=True, null=True, verbose_name="VAT Reporting Date"),
                ),
                (
                    "document_type",
                    models.CharField(
                        blank=True,
                        max_length=30,
                        null=True,
                        verbose_name="Document Type",
                    ),
                ),
                (
                    "document_no",
                    models.CharField(
                        blank=True,
                        max_length=50,
                        null=True,
                        verbose_name="Document No.",
                    ),
                ),
                (
                    "external_document_no",
                    models.CharField(
                        blank=True,
                        max_length=50,
                        null=True,
                        verbose_name="External Document No.",
                    ),
                ),
                (
                    "account_type",
                    models.CharField(
                        blank=True,
                        max_length=20,
                        null=True,
                        verbose_name="Account Type",
                    ),
                ),
                (
                    "account_no",
                    models.CharField(
                        blank=True,
                        max_length=50,
                        null=True,
                        verbose_name="Account No.",
                    ),
                ),
                (
                    "description",
                    models.TextField(blank=True, null=True, verbose_name="Description"),
                ),
                (
                    "amount",
                    models.IntegerField(
                        blank=True, default=0, null=True, verbose_name="Amount"
                    ),
                ),
                (
                    "debit_amount",
                    models.IntegerField(
                        blank=True, default=0, null=True, verbose_name="Debit Amount"
                    ),
                ),
                (
                    "credit_amount",
                    models.IntegerField(
                        blank=True, default=0, null=True, verbose_name="Credit Amount"
                    ),
                ),
                (
                    "bal_account_type",
                    models.CharField(
                        blank=True,
                        max_length=20,
                        null=True,
                        verbose_name="Bal. Account Type",
                    ),
                ),
                (
                    "bal_account_no",
                    models.CharField(
                        blank=True,
                        max_length=50,
                        null=True,
                        verbose_name="Bal. Account No.",
                    ),
                ),
                (
                    "correction",
                    models.BooleanField(default=False, verbose_name="Correction"),
                ),
                (
                    "comment",
                    models.TextField(blank=True, null=True, verbose_name="Comment"),
                ),
                (
                    "status",
                    models.CharField(
                        db_index=True,
                        default="Open",
                        max_length=20,
                        verbose_name="Status",
                    ),
                ),
                (
                    "payment_method",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="general_journal_lines",
                        to="financials.paymentmethod",
                        verbose_name="Payment Method",
                    ),
                ),
            ],
            options={
                "verbose_name": "General Journal Line",
                "verbose_name_plural": "General Journal Lines",
                "ordering": ["batch_name", "line_no"],
                "indexes": [
                    models.Index(
                        fields=["batch_name", "line_no"],
                        name="fin_gjline_batch_line_idx",
                    ),
                    models.Index(
                        fields=["posting_date"],
                        name="fin_gjline_post_date_idx",
                    ),
                    models.Index(
                        fields=["document_no"],
                        name="fin_gjline_doc_no_idx",
                    ),
                    models.Index(
                        fields=["status"],
                        name="fin_gjline_status_idx",
                    ),
                ],
            },
        ),
    ]
