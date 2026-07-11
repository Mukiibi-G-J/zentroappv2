"""
Management command to setup user permissions for all users
Usage: python manage.py setup_user_permissions --schema=<tenant>
"""

from django.core.management.base import BaseCommand
from authentication.models import CustomUser, UserSetup


class Command(BaseCommand):
    help = "Create UserSetup for all users who don't have one"

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Reset all existing setups to defaults",
        )
        parser.add_argument(
            "--restrict-sales",
            action="store_true",
            help="Apply restricted permissions suitable for sales staff",
        )
        parser.add_argument(
            "--restrict-cashiers",
            action="store_true",
            help="Apply minimal permissions suitable for cashiers",
        )

    def handle(self, *args, **options):
        reset = options.get("reset", False)
        restrict_sales = options.get("restrict_sales", False)
        restrict_cashiers = options.get("restrict_cashiers", False)

        users = CustomUser.objects.all()
        created_count = 0
        updated_count = 0

        self.stdout.write(
            self.style.SUCCESS(f"Processing {users.count()} users...")
        )

        for user in users:
            try:
                if reset:
                    # Reset existing setup or create new one
                    user_setup, created = UserSetup.objects.get_or_create(
                        user=user
                    )

                    # Reset to defaults
                    user_setup.can_see_buying_price = True
                    user_setup.can_see_profit_margin = True
                    user_setup.can_see_item_cost = True
                    user_setup.can_reverse_purchase_invoice = True

                    if restrict_sales:
                        # Apply sales staff restrictions
                        user_setup.can_see_buying_price = False
                        user_setup.can_see_profit_margin = False
                        user_setup.can_see_item_cost = False
                        user_setup.notes = (
                            "Sales staff - restricted financial access"
                        )
                    elif restrict_cashiers:
                        # Apply cashier restrictions
                        user_setup.can_see_buying_price = False
                        user_setup.can_see_profit_margin = False
                        user_setup.notes = "Cashier - POS access only"

                    user_setup.save()

                    if created:
                        created_count += 1
                        self.stdout.write(
                            f"  ✓ Created setup for {user.username}"
                        )
                    else:
                        updated_count += 1
                        self.stdout.write(
                            f"  ↻ Reset setup for {user.username}"
                        )

                else:
                    # Only create if doesn't exist
                    user_setup, created = UserSetup.objects.get_or_create(
                        user=user,
                        defaults={
                            "can_see_buying_price": True,
                            "can_see_profit_margin": True,
                            "can_see_item_cost": True,
                            "can_reverse_purchase_invoice": True,
                        },
                    )

                    if created:
                        created_count += 1
                        self.stdout.write(
                            f"  ✓ Created setup for {user.username}"
                        )
                    else:
                        self.stdout.write(
                            f"  - Setup already exists for {user.username}"
                        )

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f"  ✗ Error processing {user.username}: {str(e)}"
                    )
                )

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(f"✓ Created {created_count} new user setups")
        )
        if updated_count > 0:
            self.stdout.write(
                self.style.SUCCESS(f"↻ Updated {updated_count} existing setups")
            )
        self.stdout.write(self.style.SUCCESS("Done!"))

