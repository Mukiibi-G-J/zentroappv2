from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import datetime, timedelta
from company.models import ZentroStarterOffer
from decimal import Decimal


class Command(BaseCommand):
    help = "Set up Zentro Starter offers with correct pricing and payment plan options"

    def handle(self, *args, **options):
        # Set end date to August 31st of current year (or next year if already passed)
        now = timezone.now()
        current_year = now.year

        # If August 31st has passed, set it for next year
        if now.month > 8 or (now.month == 8 and now.day > 31):
            end_date = datetime(current_year + 1, 8, 31, 23, 59, 59)
        else:
            end_date = datetime(current_year, 8, 31, 23, 59, 59)

        end_date = timezone.make_aware(end_date)

        # Create or update Free Trial offer (UGX 0 - Free Trial)
        free_trial_offer, created = ZentroStarterOffer.objects.get_or_create(
            name="Zentro Starter - Free Trial",
            defaults={
                "end_date": end_date,
                "is_active": True,
                "free_months": 12,
                "device_price": Decimal("0.00"),
                "payment_plan": "one_time",
                "allows_installments": False,
                "default_installment_count": 0,
            },
        )

        # Update existing offer if it was found
        if not created:
            free_trial_offer.end_date = end_date
            free_trial_offer.is_active = True
            free_trial_offer.free_months = 12
            free_trial_offer.device_price = Decimal("0.00")
            free_trial_offer.payment_plan = "one_time"
            free_trial_offer.allows_installments = False
            free_trial_offer.default_installment_count = 0
            free_trial_offer.save()

        action = "Created" if created else "Updated"
        self.stdout.write(
            self.style.SUCCESS(
                f"{action} Free Trial offer: {free_trial_offer.name} - UGX {free_trial_offer.device_price:,}"
            )
        )

        # Create or update Zentro Starter Pack offer (UGX 800,000 - with installments)
        # First check if there's an existing offer with 800k price
        starter_pack_offer = ZentroStarterOffer.objects.filter(
            device_price=Decimal("800000.00")
        ).first()

        if starter_pack_offer:
            created = False
            # Update existing offer to new name and settings
            starter_pack_offer.name = "Zentro Starter Pack"
        else:
            # Create new offer
            starter_pack_offer, created = ZentroStarterOffer.objects.get_or_create(
                name="Zentro Starter Pack",
                defaults={
                    "end_date": end_date,
                    "is_active": True,
                    "free_months": 12,
                    "device_price": Decimal("800000.00"),
                    "payment_plan": "installments",
                    "allows_installments": True,
                    "default_installment_count": 4,
                },
            )
            if not created:
                created = False

        # Update offer settings
        starter_pack_offer.end_date = end_date
        starter_pack_offer.is_active = True
        starter_pack_offer.free_months = 12
        starter_pack_offer.device_price = Decimal("800000.00")
        starter_pack_offer.payment_plan = "installments"
        starter_pack_offer.allows_installments = True
        starter_pack_offer.default_installment_count = 4
        starter_pack_offer.name = "Zentro Starter Pack"
        starter_pack_offer.save()

        action = "Created" if created else "Updated"
        self.stdout.write(
            self.style.SUCCESS(
                f"{action} Starter Pack offer: {starter_pack_offer.name} - UGX {starter_pack_offer.device_price:,} (Allows installments)"
            )
        )

        # Create or update Zentro Kit offer (UGX 1,500,000 - with device, with installments)
        # Software: 800,000 + Machine: 700,000 = 1,500,000
        kit_offer = ZentroStarterOffer.objects.filter(
            name__icontains="Zentro Kit"
        ).first()

        if kit_offer:
            created = False
            # Update to new price of 1.5M
            existing_price = Decimal("1500000.00")
        else:
            # Create new offer with 1.5M price
            kit_offer, created = ZentroStarterOffer.objects.get_or_create(
                name="Zentro Kit - Device",
                defaults={
                    "end_date": end_date,
                    "is_active": True,
                    "free_months": 12,
                    "device_price": Decimal("1500000.00"),
                    "payment_plan": "installments",
                    "allows_installments": True,
                    "default_installment_count": 4,
                },
            )
            if not created:
                created = False
                existing_price = Decimal("1500000.00")
            else:
                existing_price = Decimal("1500000.00")

        # Update offer settings with new price
        kit_offer.end_date = end_date
        kit_offer.is_active = True
        kit_offer.free_months = 12
        kit_offer.device_price = existing_price  # Set to 1.5M
        kit_offer.payment_plan = "installments"
        kit_offer.allows_installments = True
        kit_offer.default_installment_count = 4
        kit_offer.name = "Zentro Kit - Device"
        kit_offer.save()

        action = "Created" if created else "Updated"
        self.stdout.write(
            self.style.SUCCESS(
                f"{action} Zentro Kit offer: {kit_offer.name} - UGX {kit_offer.device_price:,} (Allows installments)"
            )
        )

        # Zentro Starter (500k) removed - no longer needed

        self.stdout.write(
            self.style.SUCCESS(
                "\n[SUCCESS] All Zentro Starter offers have been set up successfully!"
            )
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"\n[SUMMARY]\n"
                f"   - Free Trial: UGX 0 (one-time payment only)\n"
                f"   - Starter Pack: UGX 800,000 (supports installments)\n"
                f"   - Zentro Kit: UGX 1,500,000 (supports installments)\n"
            )
        )
