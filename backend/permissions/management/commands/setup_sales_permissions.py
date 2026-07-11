from django.core.management.base import BaseCommand
from permissions.models import PermissionSet, PermissionSetLine
from authentication.models import Role
from base.models import Objects


class Command(BaseCommand):
    help = "Create permission sets for Sales module (PILOT)"

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS("\n🔐 Setting up Sales Permission Sets...\n")
        )

        # Get Sales-related objects
        sales_object_ids = [2600, 2610, 2700, 2710, 2720]
        sales_objects = Objects.objects.filter(object_id__in=sales_object_ids)

        if not sales_objects.exists():
            self.stdout.write(
                self.style.ERROR(
                    "⚠️  No sales objects found! Run 'python manage.py populate_sales_objects' first."
                )
            )
            return

        self.stdout.write(
            f"📊 Found {sales_objects.count()} sales objects to configure\n"
        )

        # Define permission sets for Sales module
        permission_configs = [
            {
                "code": "SALES_CASHIER",
                "name": "Sales - Cashier",
                "description": "Cashier permissions for sales operations (can create invoices, manage customers, but cannot delete)",
                "role": "Cashier",
                "permissions": {
                    2600: ["read", "insert", "modify"],  # Customer
                    2610: ["read"],  # Customer Ledger Entry
                    2700: ["read", "insert"],  # Sales Invoice
                    2710: ["read", "insert"],  # Sales Invoice Line
                    2720: ["read"],  # Sales Setup
                },
            },
            {
                "code": "SALES_FULL",
                "name": "Sales - Full Access",
                "description": "Full access to all sales operations (can do everything)",
                "role": "Sales",
                "permissions": {
                    2600: ["read", "insert", "modify", "delete"],  # Customer
                    2610: ["read", "insert", "modify"],  # Customer Ledger Entry
                    2700: ["read", "insert", "modify", "delete"],  # Sales Invoice
                    2710: ["read", "insert", "modify", "delete"],  # Sales Invoice Line
                    2720: ["read", "modify"],  # Sales Setup
                },
            },
            {
                "code": "SALES_VIEW_ONLY",
                "name": "Sales - View Only",
                "description": "Read-only access to sales data (cannot create, edit, or delete)",
                "role": None,  # Not linked to a default role
                "permissions": {
                    2600: ["read"],  # Customer
                    2610: ["read"],  # Customer Ledger Entry
                    2700: ["read"],  # Sales Invoice
                    2710: ["read"],  # Sales Invoice Line
                    2720: ["read"],  # Sales Setup
                },
            },
        ]

        created_count = 0
        updated_count = 0

        for config in permission_configs:
            self.stdout.write(f"\n🔧 Processing: {config['name']}")
            self.stdout.write("-" * 70)

            # Get or create role
            role = None
            if config["role"]:
                role, role_created = Role.objects.get_or_create(
                    name=config["role"],
                    defaults={"description": f'{config["role"]} role'},
                )
                if role_created:
                    self.stdout.write(f"  ✓ Created role: {role.name}")
                else:
                    self.stdout.write(f"  ℹ️  Using existing role: {role.name}")

            # Create permission set
            perm_set, created = PermissionSet.objects.get_or_create(
                code=config["code"],
                defaults={
                    "name": config["name"],
                    "description": config["description"],
                    "linked_role": role,
                    "is_active": True,
                },
            )

            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f"  ✓ Created permission set: {perm_set.name}")
                )
            else:
                updated_count += 1
                self.stdout.write(
                    self.style.WARNING(
                        f"  ⚠️  Permission set '{perm_set.name}' already exists - updating lines"
                    )
                )
                # Clear existing lines when updating
                PermissionSetLine.objects.filter(permissionset=perm_set).delete()

            # Create permission lines
            lines_created = 0
            for obj_id, perms in config["permissions"].items():
                try:
                    obj = Objects.objects.get(object_id=obj_id)

                    line_data = {
                        "read_permission": "read" in perms,
                        "insert_permission": "insert" in perms,
                        "modify_permission": "modify" in perms,
                        "delete_permission": "delete" in perms,
                        "execute_permission": False,  # Not used for tables
                    }

                    PermissionSetLine.objects.create(
                        permissionset=perm_set, application_object=obj, **line_data
                    )
                    lines_created += 1

                    # Show what permissions were granted
                    perm_str = ", ".join([p.upper()[0] for p in perms])
                    self.stdout.write(
                        f"    └── {obj.object_name} (ID {obj_id}): [{perm_str}]"
                    )

                except Objects.DoesNotExist:
                    self.stdout.write(
                        self.style.ERROR(
                            f"    ✗ Object {obj_id} not found - run populate_sales_objects first"
                        )
                    )

            if lines_created > 0:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  ✅ Created {lines_created} permission lines for {config['name']}"
                    )
                )

        # Summary
        self.stdout.write("\n" + "=" * 70)
        self.stdout.write(
            self.style.SUCCESS("✅ Sales permission sets setup complete!")
        )

        if created_count > 0:
            self.stdout.write(f"\n📝 Created: {created_count} permission sets")
        if updated_count > 0:
            self.stdout.write(f"🔄 Updated: {updated_count} permission sets")

        self.stdout.write("\n💡 Next Steps:")
        self.stdout.write("  1. Run: python manage.py create_sales_groups")
        self.stdout.write(
            "  2. Visit admin: http://ekk.localhost:8000/admin/permissions/permissionset/"
        )
        self.stdout.write("  3. Verify permission sets were created correctly\n")
