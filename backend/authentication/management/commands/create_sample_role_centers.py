"""
Management command to create sample Role Centers for common use cases
No need to specify tenant - runs on current tenant context
"""

from django.core.management.base import BaseCommand
from authentication.models import Role, RoleCenter


class Command(BaseCommand):
    help = "Create sample Role Centers (Dispenser, Cashier, Accountant, Manager)"

    def handle(self, *args, **options):
        self.stdout.write("\n" + "=" * 70)
        self.stdout.write(self.style.SUCCESS("Creating Sample Role Centers..."))
        self.stdout.write("=" * 70 + "\n")

        role_centers_config = [
            {
                "role_name": "Dispenser",
                "role_desc": "Dispenser staff role with limited access",
                "role_perms": ["sales", "customers", "items"],
                "center_code": "DISPENSER_CENTER",
                "center_name": "Dispenser Role Center",
                "center_desc": "Role center for dispenser users",
                "modules": ["sales", "customers", "items"],
                "features": {
                    "sales": ["create_invoice", "view_history"],
                    "customers": ["view", "create", "edit"],
                    "items": ["view_only"],
                },
                "widgets": ["sales_today", "recent_customers"],
            },
            {
                "role_name": "Cashier",
                "role_desc": "Cashier role for point of sale",
                "role_perms": ["sales", "customers"],
                "center_code": "CASHIER_CENTER",
                "center_name": "Cashier Role Center",
                "center_desc": "Role center for cashiers at POS",
                "modules": ["sales", "customers"],
                "features": {
                    "sales": ["create_invoice", "process_payment"],
                    "customers": ["view", "create"],
                },
                "widgets": ["sales_today", "cash_drawer"],
            },
            {
                "role_name": "Accountant",
                "role_desc": "Accountant role with financial access",
                "role_perms": ["financials", "reports", "payments", "expenses"],
                "center_code": "ACCOUNTANT_CENTER",
                "center_name": "Accountant Role Center",
                "center_desc": "Role center for accountants",
                "modules": ["financials", "reports", "payments", "expenses"],
                "features": {
                    "financials": [
                        "chart_of_accounts",
                        "journal_entries",
                        "reconciliation",
                    ],
                    "reports": ["profit_loss", "balance_sheet", "trial_balance"],
                    "payments": ["view", "approve"],
                    "expenses": ["view", "approve"],
                },
                "widgets": ["financial_summary", "account_balances", "monthly_pl"],
            },
            {
                "role_name": "Manager",
                "role_desc": "Manager role with full access",
                "role_perms": ["admin"],  # 'admin' gives full access
                "center_code": "MANAGER_CENTER",
                "center_name": "Manager Role Center",
                "center_desc": "Role center for managers - full access",
                "modules": [
                    "sales",
                    "customers",
                    "items",
                    "purchases",
                    "financials",
                    "payments",
                    "expenses",
                    "reports",
                    "settings",
                    "company",
                    "roles",
                    "profile",
                ],
                "features": {},  # No restrictions
                "widgets": [
                    "sales_summary",
                    "financial_summary",
                    "inventory_status",
                    "team_performance",
                    "recent_activities",
                ],
            },
        ]

        created_count = 0
        existing_count = 0

        for config in role_centers_config:
            # Create/Get Role
            role, role_created = Role.objects.get_or_create(
                name=config["role_name"],
                defaults={
                    "description": config["role_desc"],
                    "permissions": config["role_perms"],
                    "is_active": True,
                },
            )

            if role_created:
                self.stdout.write(self.style.SUCCESS(f"  ✅ Created role: {role.name}"))
            else:
                self.stdout.write(self.style.WARNING(f"  ℹ️  Role exists: {role.name}"))

            # Create/Get Role Center
            center, center_created = RoleCenter.objects.get_or_create(
                code=config["center_code"],
                defaults={
                    "name": config["center_name"],
                    "description": config["center_desc"],
                    "linked_role": role,
                    "modules": config["modules"],
                    "features": config["features"],
                    "dashboard_widgets": config["widgets"],
                    "is_active": True,
                },
            )

            if center_created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f'  ✅ Created: {center.name} → Modules: {", ".join(center.modules)}'
                    )
                )
            else:
                existing_count += 1
                self.stdout.write(
                    self.style.WARNING(
                        f'  ℹ️  Exists: {center.name} → Modules: {", ".join(center.modules)}'
                    )
                )

        # Display summary
        self.stdout.write("\n" + "=" * 70)
        self.stdout.write(self.style.SUCCESS("SUMMARY"))
        self.stdout.write("=" * 70)
        self.stdout.write(f"Created: {created_count} role centers")
        self.stdout.write(f"Already existed: {existing_count} role centers")

        self.stdout.write("\n" + "=" * 70)
        self.stdout.write(self.style.SUCCESS("ROLE CENTERS CREATED"))
        self.stdout.write("=" * 70)
        for center in RoleCenter.objects.all().order_by("name"):
            self.stdout.write(
                f'{center.name} ({center.code}) → {", ".join(center.modules)}'
            )

        self.stdout.write("\n" + "=" * 70)
        self.stdout.write(self.style.SUCCESS("NEXT STEPS"))
        self.stdout.write("=" * 70)
        self.stdout.write("1. Go to Admin Panel: /admin/authentication/customuser/")
        self.stdout.write("2. Select a user")
        self.stdout.write(
            "3. Assign a role (Dispenser, Cashier, Accountant, or Manager)"
        )
        self.stdout.write("4. Login as that user")
        self.stdout.write("5. Verify they see only the configured modules")
        self.stdout.write("=" * 70 + "\n")

        self.stdout.write(
            self.style.SUCCESS(
                f"✅ Done! {created_count + existing_count} Role Centers ready!"
            )
        )
