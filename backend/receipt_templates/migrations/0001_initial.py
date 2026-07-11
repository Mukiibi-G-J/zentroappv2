import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("dimension", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="ReceiptTemplate",
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
                    "created_at",
                    models.DateTimeField(
                        auto_now_add=True, db_index=True, verbose_name="Created At"
                    ),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True, verbose_name="Updated At"),
                ),
                (
                    "system_id",
                    models.CharField(
                        db_index=True,
                        default=uuid.uuid4,
                        editable=False,
                        max_length=36,
                        unique=True,
                        verbose_name="System ID",
                    ),
                ),
                ("code", models.SlugField(max_length=64, unique=True)),
                ("name", models.CharField(max_length=120)),
                (
                    "receipt_type",
                    models.CharField(
                        choices=[
                            ("sale", "Sale"),
                            ("prepayment", "Prepayment"),
                            ("kot", "Kitchen order"),
                            ("bar", "Bar order"),
                            ("payment_journal", "Payment journal"),
                        ],
                        db_index=True,
                        max_length=32,
                    ),
                ),
                (
                    "layout_preset",
                    models.CharField(
                        choices=[
                            ("compact", "Compact"),
                            ("standard", "Standard"),
                            ("detailed", "Detailed"),
                        ],
                        default="standard",
                        max_length=16,
                    ),
                ),
                ("paper_profile", models.JSONField(default=dict)),
                ("sections", models.JSONField(default=list)),
                ("is_system", models.BooleanField(default=False)),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={
                "verbose_name": "Receipt template",
                "verbose_name_plural": "Receipt templates",
                "ordering": ["receipt_type", "name"],
            },
        ),
        migrations.CreateModel(
            name="ReceiptTemplateAssignment",
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
                    "created_at",
                    models.DateTimeField(
                        auto_now_add=True, db_index=True, verbose_name="Created At"
                    ),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True, verbose_name="Updated At"),
                ),
                (
                    "system_id",
                    models.CharField(
                        db_index=True,
                        default=uuid.uuid4,
                        editable=False,
                        max_length=36,
                        unique=True,
                        verbose_name="System ID",
                    ),
                ),
                (
                    "device_type",
                    models.CharField(
                        choices=[
                            ("any", "Any device"),
                            ("web", "Web"),
                            ("mobile", "Mobile"),
                            ("desktop", "Desktop"),
                        ],
                        db_index=True,
                        default="any",
                        max_length=16,
                    ),
                ),
                (
                    "printer_type",
                    models.CharField(
                        choices=[
                            ("any", "Any printer"),
                            ("browser", "Browser print"),
                            ("serial", "Serial / ESC-POS"),
                            ("sunmi", "Sunmi built-in"),
                            ("bluetooth", "Bluetooth"),
                            ("usb", "USB"),
                            ("desktop_silent", "Desktop silent print"),
                        ],
                        db_index=True,
                        default="any",
                        max_length=20,
                    ),
                ),
                (
                    "process",
                    models.CharField(
                        choices=[
                            ("any", "Any process"),
                            ("pos_sale", "POS sale"),
                            ("sales_history_reprint", "Sales history reprint"),
                            ("prepayment_post", "Prepayment post"),
                            ("restaurant_settle", "Restaurant settle"),
                            ("restaurant_kot", "Restaurant KOT"),
                            ("restaurant_bar", "Restaurant bar"),
                            ("payment_journal", "Payment journal"),
                        ],
                        db_index=True,
                        default="any",
                        max_length=32,
                    ),
                ),
                ("priority", models.IntegerField(default=0)),
                (
                    "branch",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="receipt_template_assignments",
                        to="dimension.dimensionvalue",
                    ),
                ),
                (
                    "template",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="assignments",
                        to="receipt_templates.receipttemplate",
                    ),
                ),
            ],
            options={
                "verbose_name": "Receipt template assignment",
                "verbose_name_plural": "Receipt template assignments",
                "ordering": ["-priority", "-created_at"],
            },
        ),
    ]
