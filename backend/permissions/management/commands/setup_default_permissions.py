from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from permissions.models import PermissionSet, PermissionSetLine
from authentication.models import Role
from base.models import Objects

User = get_user_model()


class Command(BaseCommand):
    help = "Create default permission sets for the permission system"

    def add_arguments(self, parser):
        parser.add_argument(
            "--update",
            action="store_true",
            help="Update existing permission sets instead of skipping them",
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS("\n🔐 Setting up default permission sets...\n")
        )

        # Define default permission sets
        default_sets = [
            {
                "name": "Admin - Full Access",
                "code": "ADMIN_FULL",
                "description": "Full access to all objects and operations",
                "role_name": "Admin",
                "permissions": {
                    "read_permission": True,
                    "insert_permission": True,
                    "modify_permission": True,
                    "delete_permission": True,
                    "execute_permission": True,
                },
            },
            {
                "name": "Manager",
                "code": "MANAGER",
                "description": "Manager level access to most objects",
                "role_name": "Manager",
                "permissions": {
                    "read_permission": True,
                    "insert_permission": True,
                    "modify_permission": True,
                    "delete_permission": False,  # Managers can't delete
                    "execute_permission": True,
                },
            },
            {
                "name": "Cashier",
                "code": "CASHIER",
                "description": "Cashier access for sales and customer operations",
                "role_name": "Cashier",
                "permissions": {
                    "read_permission": True,
                    "insert_permission": True,
                    "modify_permission": True,
                    "delete_permission": False,
                    "execute_permission": True,
                },
            },
            {
                "name": "Sales",
                "code": "SALES",
                "description": "Sales team access for customer and sales operations",
                "role_name": "Sales",
                "permissions": {
                    "read_permission": True,
                    "insert_permission": True,
                    "modify_permission": True,
                    "delete_permission": False,
                    "execute_permission": True,
                },
            },
            {
                "name": "Inventory",
                "code": "INVENTORY",
                "description": "Inventory management access",
                "role_name": "Inventory",
                "permissions": {
                    "read_permission": True,
                    "insert_permission": True,
                    "modify_permission": True,
                    "delete_permission": False,
                    "execute_permission": True,
                },
            },
        ]

        # Get objects that require permissions
        objects = Objects.objects.filter(requires_permission=True)

        if not objects.exists():
            self.stdout.write(
                self.style.WARNING(
                    "⚠️  No objects found that require permissions. "
                    'Run "python manage.py populate_objects_table" first.'
                )
            )
            return

        created_count = 0
        updated_count = 0

        for set_data in default_sets:
            # Get or create the role
            role = None
            if set_data["role_name"]:
                role, _ = Role.objects.get_or_create(
                    name=set_data["role_name"],
                    defaults={"description": f'{set_data["role_name"]} role'},
                )

            # Get or create permission set
            permission_set, created = PermissionSet.objects.get_or_create(
                code=set_data["code"],
                defaults={
                    "name": set_data["name"],
                    "description": set_data["description"],
                    "linked_role": role,
                    "is_active": True,
                },
            )

            if created:
                created_count += 1
                self.stdout.write(f"  ✓ Created: {permission_set.name}")
            else:
                if options["update"]:
                    # Update existing permission set
                    permission_set.name = set_data["name"]
                    permission_set.description = set_data["description"]
                    permission_set.linked_role = role
                    permission_set.save()
                    updated_count += 1
                    self.stdout.write(f"  🔄 Updated: {permission_set.name}")
                else:
                    self.stdout.write(
                        f'  {set_data["code"]} already exists (use --update to refresh)'
                    )
                    continue

            # Clear existing permission lines if updating
            if options["update"] and not created:
                PermissionSetLine.objects.filter(permissionset=permission_set).delete()

            # Create permission lines for all objects
            permission_lines_created = 0
            for obj in objects:
                # Skip objects that don't exist (from populate errors)
                try:
                    permission_line, line_created = (
                        PermissionSetLine.objects.get_or_create(
                            permissionset=permission_set,
                            application_object=obj,
                            defaults=set_data["permissions"],
                        )
                    )

                    if line_created:
                        permission_lines_created += 1

                except Exception as e:
                    self.stdout.write(
                        self.style.WARNING(
                            f"  ⚠️  Object {obj.object_id} not found, skipping"
                        )
                    )

            if permission_lines_created > 0:
                self.stdout.write(
                    f"    └── Created {permission_lines_created} permission lines"
                )

        # Summary
        self.stdout.write("\n" + "=" * 50)
        self.stdout.write(
            self.style.SUCCESS(f"✅ Default permission sets setup complete!")
        )

        if created_count > 0:
            self.stdout.write(f"📝 Created: {created_count} permission sets")
        if updated_count > 0:
            self.stdout.write(f"🔄 Updated: {updated_count} permission sets")

        self.stdout.write("\nYou can now:")
        self.stdout.write("  • View permission sets in Django Admin")
        self.stdout.write("  • Assign users to roles (existing system)")
        self.stdout.write("  • Permission sets automatically apply through role links")
        self.stdout.write(
            "\n💡 Tip: Run 'python manage.py setup_default_permissions --update' to refresh all sets"
        )

