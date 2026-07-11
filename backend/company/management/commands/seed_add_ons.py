"""
Seed Add-Ons for subscription plans.

AddOn lives in the public schema. Run as a regular command (not tenant_command):
  python manage.py seed_add_ons
"""

from django.core.management.base import BaseCommand
from django_tenants.utils import schema_context, get_public_schema_name

from company.models import AddOn


class Command(BaseCommand):
    help = "Seed add-ons (Restaurant, EFRIS, Extra Users)"

    def handle(self, *args, **options):
        add_ons_data = [
            {
                "code": "restaurant",
                "name": "Restaurant Module",
                "price": 25000,
                "description": "Perfect for food & beverage businesses",
                "is_per_unit": False,
                "order": 1,
            },
            {
                "code": "efris",
                "name": "EFRIS Integration",
                "price": 80000,
                "description": "Seamless compliance with Uganda Revenue Authority",
                "is_per_unit": False,
                "order": 2,
            },
            {
                "code": "extra_users",
                "name": "Extra Active Users",
                "price": 10000,
                "description": "Per additional user (one-time), for any plan",
                "is_per_unit": True,
                "order": 3,
            },
        ]

        with schema_context(get_public_schema_name()):
            for data in add_ons_data:
                obj, created = AddOn.objects.update_or_create(
                    code=data["code"],
                    defaults={
                        "name": data["name"],
                        "price": data["price"],
                        "description": data["description"],
                        "is_per_unit": data["is_per_unit"],
                        "is_active": True,
                        "order": data["order"],
                    },
                )
                action = "Created" if created else "Updated"
                self.stdout.write(
                    self.style.SUCCESS(f"  {action} add-on: {obj.name} (UGX {obj.price:,})")
                )

        self.stdout.write(self.style.SUCCESS("\nAdd-ons seeded successfully!"))
