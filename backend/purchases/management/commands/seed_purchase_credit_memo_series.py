"""
Management command to add Purchase Credit Memo number series
and update existing PurchasePayable setup

Usage:
    python manage.py tenant_command seed_purchase_credit_memo_series --schema=hardwareworld
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from setup.models import NoSeries, NoSeriesLines
from purchases.models import PurchasePayable


class Command(BaseCommand):
    help = "Add Purchase Credit Memo number series and update PurchasePayable setup"

    def handle(self, *args, **options):
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write(
            self.style.SUCCESS("SEEDING PURCHASE CREDIT MEMO NUMBER SERIES")
        )
        self.stdout.write("=" * 80 + "\n")

        try:
            with transaction.atomic():
                # Create PURCR (Purchase Credit Memo) number series
                purcr_series, created = NoSeries.objects.get_or_create(
                    code="PURCR",
                    defaults={"description": "Purchase Credit Memo"},
                )

                if created:
                    self.stdout.write(
                        self.style.SUCCESS("✅ Created PURCR number series")
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING("ℹ️  PURCR number series already exists")
                    )

                # Create PURCR number series lines
                purcr_line, line_created = NoSeriesLines.objects.get_or_create(
                    no_series=purcr_series,
                    defaults={
                        "start_number": "PURCR-000001",
                        "increment_by": 1,
                    },
                )

                if line_created:
                    self.stdout.write(
                        self.style.SUCCESS("✅ Created PURCR number series line")
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(
                            "ℹ️  PURCR number series line already exists"
                        )
                    )

                # Create POSTPURCR (Posted Purchase Credit Memo) number series
                postpurcr_series, created = NoSeries.objects.get_or_create(
                    code="POSTPURCR",
                    defaults={"description": "Posted Purchase Credit Memo"},
                )

                if created:
                    self.stdout.write(
                        self.style.SUCCESS("✅ Created POSTPURCR number series")
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING("ℹ️  POSTPURCR number series already exists")
                    )

                # Create POSTPURCR number series lines
                postpurcr_line, line_created = NoSeriesLines.objects.get_or_create(
                    no_series=postpurcr_series,
                    defaults={
                        "start_number": "POSTPURCR-000001",
                        "increment_by": 1,
                    },
                )

                if line_created:
                    self.stdout.write(
                        self.style.SUCCESS("✅ Created POSTPURCR number series line")
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(
                            "ℹ️  POSTPURCR number series line already exists"
                        )
                    )

                # Update existing PurchasePayable setup
                purchase_payable = PurchasePayable.objects.first()

                if purchase_payable:
                    updated = False
                    if not purchase_payable.credit_memo_no:
                        purchase_payable.credit_memo_no = purcr_line
                        updated = True
                        self.stdout.write(
                            self.style.SUCCESS(
                                "✅ Added credit_memo_no to PurchasePayable setup"
                            )
                        )

                    if not purchase_payable.posted_credit_memo_no:
                        purchase_payable.posted_credit_memo_no = postpurcr_line
                        updated = True
                        self.stdout.write(
                            self.style.SUCCESS(
                                "✅ Added posted_credit_memo_no to PurchasePayable setup"
                            )
                        )

                    if updated:
                        purchase_payable.save()
                        self.stdout.write(
                            self.style.SUCCESS(
                                "\n✅ PurchasePayable setup updated successfully!"
                            )
                        )
                    else:
                        self.stdout.write(
                            self.style.WARNING(
                                "\nℹ️  PurchasePayable setup already has credit memo number series configured"
                            )
                        )
                else:
                    self.stdout.write(
                        self.style.ERROR(
                            "\n❌ No PurchasePayable setup found. Please create one first."
                        )
                    )

                self.stdout.write("\n" + "=" * 80)
                self.stdout.write(
                    self.style.SUCCESS(
                        "PURCHASE CREDIT MEMO NUMBER SERIES SEEDING COMPLETED"
                    )
                )
                self.stdout.write("=" * 80 + "\n")

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"\n❌ Error seeding number series: {str(e)}")
            )
            raise

