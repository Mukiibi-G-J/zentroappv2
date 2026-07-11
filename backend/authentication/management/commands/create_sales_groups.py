from django.core.management.base import BaseCommand
from authentication.models import UserGroup, Role
from permissions.models import PermissionSet


class Command(BaseCommand):
    help = "Create user groups for Sales module (PILOT)"

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("\n👥 Creating Sales User Groups...\n"))

        # Define user groups for Sales module
        groups_config = [
            {
                "code": "SALES_CASHIERS",
                "name": "Sales - Cashiers",
                "description": "All sales cashiers (can create invoices, manage customers, but cannot delete)",
                "default_role": "Cashier",
                "permission_sets": ["SALES_CASHIER"],
            },
            {
                "code": "SALES_TEAM",
                "name": "Sales Team",
                "description": "Sales representatives with full sales access (can do everything in sales)",
                "default_role": "Sales",
                "permission_sets": ["SALES_FULL"],
            },
            {
                "code": "SALES_VIEWERS",
                "name": "Sales - Viewers",
                "description": "Users who can only view sales data (read-only access)",
                "default_role": None,
                "permission_sets": ["SALES_VIEW_ONLY"],
            },
        ]

        created_count = 0
        updated_count = 0

        for config in groups_config:
            self.stdout.write(f"\n🔧 Processing: {config['name']}")
            self.stdout.write("-" * 70)

            # Get role if specified
            default_role = None
            if config["default_role"]:
                default_role, role_created = Role.objects.get_or_create(
                    name=config["default_role"],
                    defaults={"description": f'{config["default_role"]} role'},
                )
                if role_created:
                    self.stdout.write(f"  ✓ Created role: {default_role.name}")
                else:
                    self.stdout.write(f"  ℹ️  Using existing role: {default_role.name}")

            # Create user group
            group, created = UserGroup.objects.get_or_create(
                code=config["code"],
                defaults={
                    "name": config["name"],
                    "description": config["description"],
                    "default_profile": default_role,
                    "is_active": True,
                },
            )

            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f"  ✓ Created user group: {group.name}")
                )

                # Add permission sets
                for perm_code in config["permission_sets"]:
                    try:
                        perm_set = PermissionSet.objects.get(code=perm_code)
                        group.permission_sets.add(perm_set)
                        self.stdout.write(
                            f"    └── Linked permission set: {perm_set.name}"
                        )
                    except PermissionSet.DoesNotExist:
                        self.stdout.write(
                            self.style.ERROR(
                                f"    ✗ Permission set '{perm_code}' not found - run setup_sales_permissions first"
                            )
                        )
            else:
                updated_count += 1
                self.stdout.write(
                    self.style.WARNING(f"  ⚠️  User group '{group.name}' already exists")
                )

                # Still update permission sets
                group.permission_sets.clear()
                for perm_code in config["permission_sets"]:
                    try:
                        perm_set = PermissionSet.objects.get(code=perm_code)
                        group.permission_sets.add(perm_set)
                        self.stdout.write(
                            f"    └── Updated permission set: {perm_set.name}"
                        )
                    except PermissionSet.DoesNotExist:
                        self.stdout.write(
                            self.style.ERROR(
                                f"    ✗ Permission set '{perm_code}' not found"
                            )
                        )

        # Summary
        self.stdout.write("\n" + "=" * 70)
        self.stdout.write(self.style.SUCCESS("✅ Sales user groups setup complete!"))

        if created_count > 0:
            self.stdout.write(f"\n📝 Created: {created_count} user groups")
        if updated_count > 0:
            self.stdout.write(f"🔄 Updated: {updated_count} user groups")

        self.stdout.write("\n💡 Next Steps:")
        self.stdout.write(
            "  1. Visit admin: http://ekk.localhost:8000/admin/authentication/usergroup/"
        )
        self.stdout.write("  2. Add users to the appropriate groups")
        self.stdout.write("  3. Test permissions with different user roles")
        self.stdout.write("\n📖 User Groups Created:")
        for config in groups_config:
            role_info = (
                f" (Role: {config['default_role']})" if config["default_role"] else ""
            )
            self.stdout.write(f"  • {config['name']}{role_info}")
        self.stdout.write("")
