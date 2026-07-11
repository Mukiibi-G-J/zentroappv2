"""
Management command to check user's roles and user groups

Usage:
    python manage.py tenant_command check_user_roles --schema=daurice --email=mukiibijoseph19@gmail.com
"""

from django.core.management.base import BaseCommand
from authentication.models import CustomUser


class Command(BaseCommand):
    help = "Check user's roles and user groups"

    def add_arguments(self, parser):
        parser.add_argument(
            "--email",
            type=str,
            help="User email to check",
            required=True,
        )

    def handle(self, *args, **options):
        email = options["email"]

        self.stdout.write("\n" + "=" * 80)
        self.stdout.write(self.style.SUCCESS(f"CHECKING USER: {email}"))
        self.stdout.write("=" * 80 + "\n")

        try:
            user = CustomUser.objects.get(email=email)
        except CustomUser.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"❌ User not found: {email}"))
            return

        # Check user groups
        self.stdout.write(self.style.SUCCESS("\n📋 USER GROUPS:"))
        user_groups = user.user_groups.all()
        if user_groups.exists():
            for group in user_groups:
                self.stdout.write(f"   • Code: {group.code}")
                self.stdout.write(f"     Name: {group.name}")
                self.stdout.write(
                    f"     Default Profile: {group.default_profile.name if group.default_profile else 'None'}"
                )
                self.stdout.write(
                    f"     Permission Sets: {group.permission_sets.count()}"
                )
                if group.default_profile and group.default_profile.role_center:
                    self.stdout.write(
                        f"     Role Center: {group.default_profile.role_center.name}"
                    )
                    self.stdout.write(
                        f"     Modules: {group.default_profile.role_center.modules}"
                    )
                self.stdout.write("")
        else:
            self.stdout.write("   ❌ No user groups assigned!")

        # Check direct role assignments
        self.stdout.write(self.style.SUCCESS("\n📋 DIRECT ROLES:"))
        direct_roles = user.roles.all()
        if direct_roles.exists():
            for role in direct_roles:
                self.stdout.write(f"   • {role.name}")
                if role.role_center:
                    self.stdout.write(f"     Role Center: {role.role_center.name}")
        else:
            self.stdout.write("   ℹ️  No direct role assignments (expected)")

        # Check what get_authority returns
        self.stdout.write(self.style.SUCCESS("\n📋 GET_AUTHORITY:"))
        authority = user.get_authority()
        self.stdout.write(f"   {authority}")

        # Check superuser status
        self.stdout.write(self.style.SUCCESS("\n📋 USER STATUS:"))
        self.stdout.write(f"   is_superuser: {user.is_superuser}")
        self.stdout.write(f"   is_staff: {user.is_staff}")
        self.stdout.write(f"   is_active: {user.is_active}")

        self.stdout.write("\n" + "=" * 80)
        self.stdout.write(self.style.SUCCESS("✅ User check complete!"))
        self.stdout.write("=" * 80 + "\n")
