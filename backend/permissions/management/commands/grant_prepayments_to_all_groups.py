"""
Grant prepayments page permissions to every user group in the current tenant schema.

Also optionally adds module code `prePayments` to all Role Centers so the Prepayments
item appears in the sidebar for roles that use those centers (Layer 1).

Usage:
    python manage.py tenant_command grant_prepayments_to_all_groups --schema=primewise
    python manage.py tenant_command grant_prepayments_to_all_groups --schema=primewise --level=view
    python manage.py tenant_command grant_prepayments_to_all_groups --schema=primewise --skip-role-centers
"""

from django.core.management.base import BaseCommand

from authentication.models import RoleCenter, UserGroup
from permissions.models import PermissionSet


PREPAYMENTS_MODULE_CODE = "prePayments"


class Command(BaseCommand):
    help = (
        "Add prepayments permission set to all active user groups; "
        "optionally extend all role centers with the prePayments module."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--level",
            choices=("full", "view"),
            default="full",
            help="full = PREPAYMENTS_FULL (RIMD), view = PREPAYMENTS_VIEW (read only)",
        )
        parser.add_argument(
            "--skip-role-centers",
            action="store_true",
            help="Do not add prePayments to RoleCenter.modules",
        )

    def handle(self, *args, **options):
        level = options["level"]
        skip_role_centers = options["skip_role_centers"]

        code = "PREPAYMENTS_FULL" if level == "full" else "PREPAYMENTS_VIEW"
        try:
            perm_set = PermissionSet.objects.get(code=code, is_active=True)
        except PermissionSet.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(
                    f'Permission set "{code}" not found. Run:\n'
                    "  python manage.py tenant_command setup_page_permissions --schema=<tenant>"
                )
            )
            return

        self.stdout.write(self.style.WARNING("\n" + "=" * 70))
        self.stdout.write(
            self.style.SUCCESS(f"Granting {code} to all active user groups")
        )
        self.stdout.write(self.style.WARNING("=" * 70 + "\n"))

        groups = UserGroup.objects.filter(is_active=True).order_by("code")
        attached = 0
        for group in groups:
            if group.permission_sets.filter(pk=perm_set.pk).exists():
                self.stdout.write(f"  (skip) {group.code} already has {code}")
                continue
            group.permission_sets.add(perm_set)
            attached += 1
            self.stdout.write(self.style.SUCCESS(f"  + {group.code}: added {code}"))

        self.stdout.write(
            self.style.SUCCESS(f"\nUser groups updated: {attached} (skipped already had set)")
        )

        if not skip_role_centers:
            self.stdout.write("\n" + self.style.WARNING("Role centers (prePayments module)"))
            rc_updated = 0
            for rc in RoleCenter.objects.filter(is_active=True).order_by("code"):
                mods = list(rc.modules or [])
                if PREPAYMENTS_MODULE_CODE in mods:
                    self.stdout.write(f"  (skip) {rc.code} already has {PREPAYMENTS_MODULE_CODE}")
                    continue
                mods.append(PREPAYMENTS_MODULE_CODE)
                rc.modules = mods
                rc.save()
                rc_updated += 1
                self.stdout.write(
                    self.style.SUCCESS(f"  + {rc.code}: appended {PREPAYMENTS_MODULE_CODE}")
                )
            self.stdout.write(
                self.style.SUCCESS(f"Role centers updated: {rc_updated}")
            )

        self.stdout.write(
            self.style.WARNING(
                "\nUsers must sign out and sign in again (new JWT) for UI permissions to refresh."
            )
        )
        self.stdout.write(self.style.SUCCESS("Done.\n"))
