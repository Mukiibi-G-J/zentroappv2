"""
Management command to fix Admin user group's default_profile to point to Admin role

Usage:
    python manage.py tenant_command fix_admin_group_role --schema=daurice
"""

from django.core.management.base import BaseCommand
from authentication.models import UserGroup, Role


class Command(BaseCommand):
    help = "Fix Admin user group's default_profile to point to Admin role"

    def handle(self, *args, **options):
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write(self.style.SUCCESS("FIXING ADMIN USER GROUP"))
        self.stdout.write("=" * 80 + "\n")

        # Get Admin user group
        admin_group = UserGroup.objects.filter(code="Admin").first()

        if not admin_group:
            self.stdout.write(self.style.ERROR("❌ Admin user group not found!"))
            return

        # Get Admin role
        admin_role = Role.objects.filter(name="Admin").first()

        if not admin_role:
            self.stdout.write(self.style.ERROR("❌ Admin role not found!"))
            return

        # Check current state
        self.stdout.write(f"Current default_profile: {admin_group.default_profile}")

        # Fix the default_profile
        admin_group.default_profile = admin_role
        admin_group.save()

        self.stdout.write("\n" + "=" * 80)
        self.stdout.write(self.style.SUCCESS("SUMMARY"))
        self.stdout.write("=" * 80)
        self.stdout.write(
            f"✅ Admin user group default_profile updated to: {admin_role.name}"
        )
        self.stdout.write(
            f"✅ Admin role center: {admin_role.role_center.name if admin_role.role_center else 'None'}"
        )
        if admin_role.role_center:
            self.stdout.write(
                f"✅ Role center modules: {len(admin_role.role_center.modules)} modules"
            )
            self.stdout.write(
                f"   Modules: {', '.join(admin_role.role_center.modules)}"
            )

        self.stdout.write("\n" + "=" * 80)
        self.stdout.write(
            self.style.SUCCESS(
                "✅ Admin group fixed! Users need to logout and login again."
            )
        )
        self.stdout.write("=" * 80 + "\n")
