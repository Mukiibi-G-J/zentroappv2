"""
Management command to ensure Admin user group has ALL permission sets including newly added ones

Usage:
    python manage.py tenant_command update_admin_complete_permissions --schema=daurice
"""

from django.core.management.base import BaseCommand
from authentication.models import UserGroup
from permissions.models import PermissionSet


class Command(BaseCommand):
    help = "Ensure Admin user group has ALL permission sets"

    def handle(self, *args, **options):
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write(self.style.SUCCESS("UPDATING ADMIN GROUP PERMISSIONS"))
        self.stdout.write("=" * 80 + "\n")

        # Get Admin user group (tenants may use different casing, e.g. ADMIN vs Admin)
        admin_group = (
            UserGroup.objects.filter(code__iexact="admin").first()
            or UserGroup.objects.filter(name__iexact="admin").first()
        )

        if not admin_group:
            # Avoid unicode symbols (Windows consoles may not be UTF-8 by default).
            self.stdout.write(self.style.ERROR("Admin user group not found!"))
            return

        # Get ALL active permission sets
        all_permission_sets = PermissionSet.objects.filter(is_active=True)

        # Clear existing and add all
        admin_group.permission_sets.clear()
        admin_group.permission_sets.add(*all_permission_sets)

        self.stdout.write("\n" + "=" * 80)
        self.stdout.write(self.style.SUCCESS("SUMMARY"))
        self.stdout.write("=" * 80)
        self.stdout.write(
            f"Admin group now has {all_permission_sets.count()} permission sets"
        )
        self.stdout.write("\nPermission sets assigned:")
        for ps in all_permission_sets.order_by("code"):
            self.stdout.write(f"   - {ps.code}: {ps.name}")

        self.stdout.write("\n" + "=" * 80)
        self.stdout.write(self.style.SUCCESS("Admin permissions updated successfully!"))
        self.stdout.write("=" * 80 + "\n")
