"""
Management command to create a sample "Dispenser" Role Center
Example: python manage.py create_dispenser_center --schema=hardwareworld
"""

from django.core.management.base import BaseCommand
from authentication.models import Role, RoleCenter


class Command(BaseCommand):
    help = "Create a sample Dispenser Role Center"

    def handle(self, *args, **options):
        self.stdout.write("\n" + "=" * 70)
        self.stdout.write(self.style.SUCCESS("Creating Dispenser Role Center..."))
        self.stdout.write("=" * 70 + "\n")

        # Step 1: Create/Get Dispenser Role
        dispenser_role, created = Role.objects.get_or_create(
            name="Dispenser",
            defaults={
                "description": "Dispenser staff role with limited access",
                "permissions": ["sales", "customers", "items"],
                "is_active": True,
            },
        )

        if created:
            self.stdout.write(self.style.SUCCESS(f"✅ Created new Dispenser role"))
        else:
            self.stdout.write(self.style.WARNING(f"ℹ️  Dispenser role already exists"))

        # Step 2: Create Dispenser Role Center
        role_center, created = RoleCenter.objects.get_or_create(
            code="DISPENSER_CENTER",
            defaults={
                "name": "Dispenser Role Center",
                "description": "Role center for dispenser users with access to sales, customers, items, and purchases",
                "modules": ["sales", "customers", "items", "purchases"],
                "features": {
                    "sales": ["create_invoice", "view_history"],
                    "customers": ["view", "create", "edit"],
                    "items": ["view_only"],
                    "purchases": ["view", "create"],
                },
                "dashboard_widgets": ["sales_today", "recent_customers"],
                "is_active": True,
            },
        )

        # Step 3: Link Role Center to Role
        if dispenser_role.role_center != role_center:
            dispenser_role.role_center = role_center
            dispenser_role.save()
            self.stdout.write(
                self.style.SUCCESS(f"✅ Linked Role Center to Dispenser role")
            )

        if created:
            self.stdout.write(self.style.SUCCESS(f"✅ Created Dispenser Role Center"))
        else:
            self.stdout.write(
                self.style.WARNING(f"ℹ️  Dispenser Role Center already exists")
            )

        # Display summary
        self.stdout.write("\n" + "=" * 70)
        self.stdout.write(self.style.SUCCESS("SUMMARY"))
        self.stdout.write("=" * 70)
        self.stdout.write(f"Code: {role_center.code}")
        self.stdout.write(f"Name: {role_center.name}")
        self.stdout.write(f"Linked Role: {dispenser_role.name}")
        self.stdout.write(f'Modules: {", ".join(role_center.modules)}')
        self.stdout.write(f'Is Active: {"Yes" if role_center.is_active else "No"}')

        self.stdout.write("\n" + "=" * 70)
        self.stdout.write(self.style.SUCCESS("NEXT STEPS"))
        self.stdout.write("=" * 70)
        self.stdout.write(
            "1. Go to Admin Panel: http://ekk.localhost:8000/admin/authentication/customuser/"
        )
        self.stdout.write("2. Select a user")
        self.stdout.write('3. Add "Dispenser" role to the user')
        self.stdout.write("4. Login as that user")
        self.stdout.write("5. Verify they only see: Sales, Customers, Items, Purchases")
        self.stdout.write("=" * 70 + "\n")

        self.stdout.write(
            self.style.SUCCESS("✅ Done! Dispenser Role Center is ready!")
        )
