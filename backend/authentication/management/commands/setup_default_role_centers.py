"""
Management command to create DEFAULT (built-in) Role Centers
BUSINESS CENTRAL STYLE: Role → specifies Role Center ID
Run this during initial setup or tenant creation
"""

from django.core.management.base import BaseCommand
from authentication.models import Role, RoleCenter


class Command(BaseCommand):
    help = "Create default (built-in) role centers for standard roles (Business Central style!)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--skip-existing",
            action="store_true",
            help="Skip creating role centers that already exist",
        )

    def handle(self, *args, **options):
        skip_existing = options.get("skip_existing", False)

        self.stdout.write("\n" + "=" * 70)
        self.stdout.write(self.style.SUCCESS("Creating DEFAULT Role Centers..."))
        self.stdout.write(
            self.style.SUCCESS("(Business Central Style: Role → Role Center ID)")
        )
        self.stdout.write("=" * 70 + "\n")

        # Define DEFAULT (built-in) role centers
        default_role_centers = [
            {
                "role_name": "Admin",
                "role_desc": "System administrator with full access",
                "role_perms": ["admin"],  # Special 'admin' permission
                "center_code": "ADMIN_CENTER",
                "center_name": "Admin Center",
                "center_desc": "Full system access for administrators",
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
                    "configPackages",
                    "trackingCodes",
                    "company",
                    "userManagement",
                    "roles",
                    "profile",
                    "bankAccounts",
                    "loans",
                    "prePayments",
                ],
                "features": {},  # No restrictions
                "widgets": [
                    "system_health",
                    "user_activity",
                    "sales_summary",
                    "financial_summary",
                    "inventory_status",
                ],
            },
            {
                "role_name": "Manager",
                "role_desc": "Manager with broad access to operations",
                "role_perms": [
                    "sales",
                    "customers",
                    "items",
                    "purchases",
                    "financials",
                    "reports",
                ],
                "center_code": "MANAGER_CENTER",
                "center_name": "Manager Center",
                "center_desc": "Operational access for managers",
                "modules": [
                    "sales",
                    "customers",
                    "items",
                    "purchases",
                    "financials",
                    "payments",
                    "expenses",
                    "reports",
                    "profile",
                ],
                "features": {},
                "widgets": ["sales_summary", "financial_summary", "inventory_status"],
            },
            {
                "role_name": "Accountant",
                "role_desc": "Accountant with financial module access",
                "role_perms": ["financials", "reports"],
                "center_code": "ACCOUNTANT_CENTER",
                "center_name": "Accountant Center",
                "center_desc": "Financial and reporting access for accountants",
                "modules": ["financials", "reports", "payments", "expenses", "profile"],
                "features": {},
                "widgets": ["financial_summary", "expenses_summary"],
            },
            {
                "role_name": "Sales",
                "role_desc": "Sales personnel with customer and sales access",
                "role_perms": ["sales", "customers"],
                "center_code": "SALES_CENTER",
                "center_name": "Sales Center",
                "center_desc": "Sales and customer management for sales team",
                "modules": ["sales", "customers", "items", "reports", "profile"],
                "features": {},
                "widgets": ["sales_summary", "customer_summary"],
            },
            {
                "role_name": "Cashier",
                "role_desc": "Cashier with limited sales access",
                "role_perms": ["sales"],
                "center_code": "CASHIER_CENTER",
                "center_name": "Cashier Center",
                "center_desc": "Point of sale access for cashiers",
                "modules": ["sales", "customers", "profile"],
                "features": {},
                "widgets": ["sales_summary"],
            },
            {
                "role_name": "Inventory",
                "role_desc": "Inventory manager with items and purchase access",
                "role_perms": ["items", "purchases"],
                "center_code": "INVENTORY_CENTER",
                "center_name": "Inventory Center",
                "center_desc": "Inventory and purchasing for warehouse staff",
                "modules": ["items", "purchases", "profile"],
                "features": {},
                "widgets": ["inventory_status"],
            },
            {
                "role_name": "User",
                "role_desc": "Basic user with minimal access",
                "role_perms": [],
                "center_code": "USER_CENTER",
                "center_name": "User Center",
                "center_desc": "Basic profile access only",
                "modules": ["profile"],
                "features": {},
                "widgets": [],
            },
        ]

        created_count = 0
        updated_count = 0
        linked_count = 0

        for config in default_role_centers:
            self.stdout.write(f"\n📋 Processing: {config['role_name']}...")

            # Step 1: Get or create Role
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

            # Step 2: Create/Update Role Center (NO linked_role field!)
            center, center_created = RoleCenter.objects.update_or_create(
                code=config["center_code"],
                defaults={
                    "name": config["center_name"],
                    "description": config["center_desc"],
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
                        f'  ✅ Created: {center.name} → {", ".join(center.modules[:3])}...'
                    )
                )
            else:
                updated_count += 1
                self.stdout.write(
                    self.style.WARNING(
                        f'  🔄 Updated: {center.name} → {", ".join(center.modules[:3])}...'
                    )
                )

            # Step 3: Link Role → Role Center (Business Central style!)
            if not role.role_center or role.role_center != center:
                role.role_center = center
                role.save(update_fields=["role_center"])
                linked_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f"  🔗 Linked: {role.name} → {center.name}")
                )
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f"  ℹ️  Already linked: {role.name} → {center.name}"
                    )
                )

        # Display summary
        self.stdout.write("\n" + "=" * 70)
        self.stdout.write(self.style.SUCCESS("SUMMARY"))
        self.stdout.write("=" * 70)
        self.stdout.write(f"Created Role Centers: {created_count}")
        self.stdout.write(f"Updated Role Centers: {updated_count}")
        self.stdout.write(f"Linked Roles → Role Centers: {linked_count}")

        self.stdout.write("\n" + "=" * 70)
        self.stdout.write(self.style.SUCCESS("ROLE → ROLE CENTER MAPPING"))
        self.stdout.write("=" * 70)
        for role in Role.objects.all().order_by("name"):
            if role.role_center:
                module_preview = ", ".join(role.role_center.modules[:3])
                if len(role.role_center.modules) > 3:
                    module_preview += f" (+{len(role.role_center.modules) - 3} more)"
                self.stdout.write(
                    f"{role.name:15} → {role.role_center.name:25} [{module_preview}]"
                )
            else:
                self.stdout.write(f"{role.name:15} → (No Role Center)")

        self.stdout.write("\n" + "=" * 70)
        self.stdout.write(self.style.SUCCESS("NEXT STEPS"))
        self.stdout.write("=" * 70)
        self.stdout.write("✅ Default role centers are ready!")
        self.stdout.write(
            "✅ Roles are linked to role centers (Business Central style!)"
        )
        self.stdout.write("")
        self.stdout.write("You can:")
        self.stdout.write(
            "1. Assign roles to users → They get role center modules automatically"
        )
        self.stdout.write("2. Create custom role centers → Assign to roles")
        self.stdout.write(
            "3. Change role center for any role → Users see new modules on next login"
        )
        self.stdout.write("=" * 70 + "\n")

        self.stdout.write(
            self.style.SUCCESS(
                "✅ Default role centers setup complete (Business Central style!)!"
            )
        )
