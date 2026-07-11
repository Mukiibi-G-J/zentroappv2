"""
Create or refresh the Business Central-style SUPER permission set.

Usage:
    python manage.py tenant_command seed_super_permission_set --schema=primewise
    python manage.py tenant_command seed_super_permission_set --schema=primewise --update
    python manage.py tenant_command seed_super_permission_set --schema=primewise --assign-admin
"""

from django.core.management.base import BaseCommand

from permissions.services.super_permission_set import (
    assign_super_to_admin_group,
    ensure_super_permission_set,
    permission_objects_queryset,
)


class Command(BaseCommand):
    help = (
        "Create the SUPER permission set with full RIMDX access on all secured "
        "application objects (Business Central style)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--update",
            action="store_true",
            help="Replace all SUPER permission lines with a fresh full-access set",
        )
        parser.add_argument(
            "--assign-admin",
            action="store_true",
            help="Assign SUPER to the Admin user group when not already assigned",
        )

    def handle(self, *args, **options):
        update = options["update"]
        assign_admin = options["assign_admin"]

        secured_count = permission_objects_queryset().count()
        if secured_count == 0:
            self.stdout.write(
                self.style.WARNING(
                    "No secured application objects found. "
                    "Run populate_page_objects / seed_pages first."
                )
            )
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"\nCreating Business Central-style SUPER permission set "
                f"({secured_count} secured objects)...\n"
            )
        )

        permission_set, stats = ensure_super_permission_set(update=update)

        if stats["created_set"]:
            self.stdout.write(self.style.SUCCESS("  Created SUPER permission set"))
        elif update:
            self.stdout.write(self.style.SUCCESS("  Refreshed SUPER permission set"))
        else:
            self.stdout.write("  SUPER permission set already exists")

        line_count = permission_set.permissionsetline_set.count()
        if stats["lines_created"]:
            self.stdout.write(
                self.style.SUCCESS(f"  Permission lines: {stats['lines_created']} created")
            )
        self.stdout.write(f"  Total lines on SUPER: {line_count}")

        if assign_admin:
            admin_group, assigned = assign_super_to_admin_group()
            if admin_group is None:
                self.stdout.write(
                    self.style.WARNING("  Admin user group not found — skipped assignment")
                )
            elif assigned:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  Assigned SUPER to Admin group ({admin_group.name})"
                    )
                )
            else:
                self.stdout.write("  Admin group already has SUPER")

        self.stdout.write(self.style.SUCCESS("\nSUPER permission set ready.\n"))
        self.stdout.write("Next steps:")
        self.stdout.write(
            "  1. Assign SUPER to a user group (Users → User Groups → Permission Sets)"
        )
        self.stdout.write(
            "  2. Or run with --assign-admin to attach SUPER to the Admin group"
        )
        self.stdout.write("  3. Users must sign out and back in to refresh permissions\n")
