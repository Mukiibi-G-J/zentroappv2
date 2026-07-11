"""
Management command to check and display admin user permissions
"""

from django.core.management.base import BaseCommand
from authentication.models import UserGroup, CustomUser
from permissions.models import PermissionSet


class Command(BaseCommand):
    help = "Check admin user permissions and role center modules"

    def handle(self, *args, **options):
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write(self.style.SUCCESS("ADMIN USER PERMISSIONS CHECK"))
        self.stdout.write("=" * 80 + "\n")

        # Get admin user
        admin_user = CustomUser.objects.filter(is_superuser=True).first()

        if not admin_user:
            self.stdout.write(self.style.ERROR("❌ No superuser found"))
            return

        self.stdout.write(self.style.SUCCESS(f"✅ Admin user: {admin_user.email}"))
        self.stdout.write(f"   Full name: {admin_user.full_name}")

        # Check user groups
        user_groups = admin_user.user_groups.all()
        self.stdout.write(f"\n👥 User Groups ({user_groups.count()}):")

        if user_groups.count() == 0:
            self.stdout.write(self.style.WARNING("   ⚠️  Admin has no user groups!"))
        else:
            for group in user_groups:
                self.stdout.write(f"   • {group.name} ({group.code})")

                # Check role center
                if group.default_profile and group.default_profile.role_center:
                    role_center = group.default_profile.role_center
                    self.stdout.write(f"     Role Center: {role_center.name}")
                    self.stdout.write(f"     Modules: {', '.join(role_center.modules)}")

                # Check permission sets
                perm_sets = group.permission_sets.all()
                if perm_sets.count() > 0:
                    self.stdout.write(f"     Permission Sets:")
                    for perm_set in perm_sets:
                        self.stdout.write(f"       - {perm_set.name} ({perm_set.code})")

        # Check for purchases and payments permissions
        self.stdout.write(f"\n🔍 Checking for Purchase & Payment History access:")

        purchases_perm = PermissionSet.objects.filter(code="PURCHASES_FULL").first()
        payments_perm = PermissionSet.objects.filter(code="PAYMENTS_FULL").first()

        has_purchases = any(
            purchases_perm in group.permission_sets.all() for group in user_groups
        )
        has_payments = any(
            payments_perm in group.permission_sets.all() for group in user_groups
        )

        if has_purchases:
            self.stdout.write(self.style.SUCCESS("   ✅ Has PURCHASES_FULL permission"))
        else:
            self.stdout.write(
                self.style.WARNING("   ❌ Missing PURCHASES_FULL permission")
            )

        if has_payments:
            self.stdout.write(self.style.SUCCESS("   ✅ Has PAYMENTS_FULL permission"))
        else:
            self.stdout.write(
                self.style.WARNING("   ❌ Missing PAYMENTS_FULL permission")
            )

        self.stdout.write("\n" + "=" * 80)
        self.stdout.write(self.style.SUCCESS("✅ Check complete!"))
        self.stdout.write("=" * 80 + "\n")





