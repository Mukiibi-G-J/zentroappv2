"""
Management command to assign all available permission sets to the Admin user group.
This ensures Admin users have full access to all pages.

Usage:
    python manage.py tenant_command setup_admin_permissions --schema=hardwareworld
"""

from django.core.management.base import BaseCommand
from authentication.models import UserGroup
from permissions.models import PermissionSet


class Command(BaseCommand):
    help = "Assign all available permission sets to the Admin user group"

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING("\n" + "=" * 70))
        self.stdout.write(self.style.WARNING("Setting up Admin User Group Permissions"))
        self.stdout.write(self.style.WARNING("=" * 70 + "\n"))

        # Get the Admin user group
        try:
            admin_group = UserGroup.objects.get(code="Admin")
            self.stdout.write(
                self.style.SUCCESS(f"✓ Found Admin user group: {admin_group.name}")
            )
        except UserGroup.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(
                    "✗ Admin user group not found. Please create it first."
                )
            )
            return
        except UserGroup.MultipleObjectsReturned:
            admin_group = UserGroup.objects.filter(code="Admin").first()
            self.stdout.write(
                self.style.WARNING(
                    f"⚠ Multiple Admin groups found, using first one: {admin_group.name}"
                )
            )

        # Get all available permission sets
        all_permission_sets = PermissionSet.objects.filter(is_active=True)
        self.stdout.write(
            self.style.SUCCESS(
                f"\n✓ Found {all_permission_sets.count()} active permission sets"
            )
        )

        # Clear existing permissions
        admin_group.permission_sets.clear()
        self.stdout.write(self.style.WARNING("✓ Cleared existing permission sets"))

        # Assign all permission sets to Admin group
        admin_group.permission_sets.add(*all_permission_sets)
        self.stdout.write(
            self.style.SUCCESS(
                f"✓ Assigned {all_permission_sets.count()} permission sets to Admin group"
            )
        )

        # Display the assigned permission sets
        self.stdout.write(self.style.WARNING("\nAssigned Permission Sets:"))
        for ps in all_permission_sets:
            self.stdout.write(f"  • {ps.code} - {ps.name}")

        self.stdout.write(self.style.SUCCESS("\n" + "=" * 70))
        self.stdout.write(self.style.SUCCESS("✓ Admin permissions setup complete!"))
        self.stdout.write(
            self.style.WARNING(
                "⚠ Users need to log out and log back in to get updated permissions"
            )
        )
        self.stdout.write(self.style.SUCCESS("=" * 70 + "\n"))
