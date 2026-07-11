from django.core.management.base import BaseCommand
from authentication.models import Role
from django_tenants.utils import schema_context


class Command(BaseCommand):
    help = "Seed default user roles for the application"

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Clear existing roles before seeding",
        )
        parser.add_argument(
            "--tenant",
            type=str,
            default="ekk",
            help="Tenant schema name (default: ekk)",
        )

    def handle(self, *args, **options):
        clear_existing = options["clear"]

        # Get tenant from command line or use default
        tenant_schema = options.get("tenant", "ekk")

        self.stdout.write(f"Seeding roles for tenant: {tenant_schema}")

        # Use tenant context
        with schema_context(tenant_schema):
            # Default roles to create
            default_roles = [
                {
                    "name": "Admin",
                    "description": "Full system administrator with all permissions",
                    "permissions": ["all"],
                    "is_active": True,
                },
                {
                    "name": "Manager",
                    "description": "Business manager with most permissions",
                    "permissions": [
                        "view_sales",
                        "create_sales",
                        "edit_sales",
                        "delete_sales",
                        "view_purchases",
                        "create_purchases",
                        "edit_purchases",
                        "delete_purchases",
                        "view_inventory",
                        "create_inventory",
                        "edit_inventory",
                        "delete_inventory",
                        "view_financials",
                        "create_financials",
                        "edit_financials",
                        "delete_financials",
                        "view_reports",
                        "view_users",
                        "create_users",
                        "edit_users",
                    ],
                    "is_active": True,
                },
                {
                    "name": "Sales",
                    "description": "Sales staff with sales-related permissions",
                    "permissions": [
                        "view_sales",
                        "create_sales",
                        "edit_sales",
                        "view_customers",
                        "create_customers",
                        "edit_customers",
                        "view_reports",
                    ],
                    "is_active": True,
                },
                {
                    "name": "Cashier",
                    "description": "Cashier with basic sales permissions",
                    "permissions": [
                        "view_sales",
                        "create_sales",
                        "view_customers",
                        "view_reports",
                    ],
                    "is_active": True,
                },
                {
                    "name": "Inventory",
                    "description": "Inventory manager with inventory-related permissions",
                    "permissions": [
                        "view_inventory",
                        "create_inventory",
                        "edit_inventory",
                        "delete_inventory",
                        "view_purchases",
                        "create_purchases",
                        "edit_purchases",
                        "view_reports",
                    ],
                    "is_active": True,
                },
                {
                    "name": "Accountant",
                    "description": "Accountant with financial permissions",
                    "permissions": [
                        "view_financials",
                        "create_financials",
                        "edit_financials",
                        "delete_financials",
                        "view_reports",
                        "view_sales",
                        "view_purchases",
                    ],
                    "is_active": True,
                },
                {
                    "name": "User",
                    "description": "Basic user with limited permissions",
                    "permissions": [
                        "view_sales",
                        "view_reports",
                    ],
                    "is_active": True,
                },
            ]

            try:
                if clear_existing:
                    self.stdout.write("Clearing existing roles...")
                    Role.objects.all().delete()
                    self.stdout.write(
                        self.style.SUCCESS("Existing roles cleared successfully")
                    )

                created_count = 0
                updated_count = 0

                for role_data in default_roles:
                    role, created = Role.objects.update_or_create(
                        name=role_data["name"],
                        defaults={
                            "description": role_data["description"],
                            "permissions": role_data["permissions"],
                            "is_active": role_data["is_active"],
                        },
                    )

                    if created:
                        created_count += 1
                        self.stdout.write(
                            self.style.SUCCESS(f"Created role: {role.name}")
                        )
                    else:
                        updated_count += 1
                        self.stdout.write(
                            self.style.WARNING(f"Updated role: {role.name}")
                        )

                self.stdout.write(
                    self.style.SUCCESS(
                        f"\nRole seeding completed successfully!"
                        f"\n- Created: {created_count} roles"
                        f"\n- Updated: {updated_count} roles"
                        f"\n- Total: {created_count + updated_count} roles"
                    )
                )

                # Display all roles
                self.stdout.write("\nAvailable roles:")
                for role in Role.objects.all().order_by("name"):
                    self.stdout.write(
                        f"  - {role.name}: {role.description} "
                        f"(Permissions: {len(role.permissions)})"
                    )

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error seeding roles: {str(e)}"))
