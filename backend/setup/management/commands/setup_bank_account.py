from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from setup.models import BankAccountSetup, NoSeries, NoSeriesLines


class Command(BaseCommand):
    help = "Set up Bank Account Setup with BANK number series"

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write(self.style.SUCCESS("SETTING UP BANK ACCOUNT CONFIGURATION"))
        self.stdout.write("=" * 80 + "\n")

        # Check if BANK No. Series exists, create if it doesn't
        bank_no_series, created = NoSeries.objects.get_or_create(
            code="BANK", defaults={"description": "Bank Account"}
        )

        if created:
            self.stdout.write(
                self.style.SUCCESS("✓ Created BANK No. Series: Bank Account")
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"✓ Found BANK No. Series: {bank_no_series.description}"
                )
            )

        # Check if No. Series Lines exist
        bank_no_series_lines = NoSeriesLines.objects.filter(
            no_series=bank_no_series
        ).first()

        if not bank_no_series_lines:
            # Create the No. Series Lines if they don't exist
            bank_no_series_lines = NoSeriesLines.objects.create(
                no_series=bank_no_series,
                start_number="BANK-000001",
                increment_by=1,
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f"✓ Created No. Series Lines for BANK: {bank_no_series_lines.start_number}"
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"✓ Found No. Series Lines for BANK: {bank_no_series_lines.start_number or 'Not set'}"
                )
            )

        # Create or update BankAccountSetup
        bank_account_setup, created = BankAccountSetup.objects.get_or_create(
            defaults={"bank_account_no_series": bank_no_series}
        )

        if created:
            self.stdout.write(
                self.style.SUCCESS(
                    f"✓ Created Bank Account Setup linked to {bank_no_series.code}"
                )
            )
        else:
            # Update if it exists but isn't linked
            if bank_account_setup.bank_account_no_series != bank_no_series:
                bank_account_setup.bank_account_no_series = bank_no_series
                bank_account_setup.save()
                self.stdout.write(
                    self.style.SUCCESS(
                        f"✓ Updated Bank Account Setup to link to {bank_no_series.code}"
                    )
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS(
                        "✓ Bank Account Setup already exists and is properly configured"
                    )
                )

        self.stdout.write("\n" + "=" * 80)
        self.stdout.write(
            self.style.SUCCESS("BANK ACCOUNT SETUP COMPLETED SUCCESSFULLY")
        )
        self.stdout.write("=" * 80 + "\n")
