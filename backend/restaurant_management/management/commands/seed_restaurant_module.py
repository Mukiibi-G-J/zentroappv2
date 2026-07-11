"""
Seed restaurant module: number series, page permission sets, and user groups.

Discoverable by Seed Manager (Setup → Seed Manager) because the filename contains ``seed``.

**Prerequisites (run order for a new tenant)**

1. Apply migrations for the tenant schema.
2. (Optional) Page ``Objects`` are created automatically before permission lines by
   running ``populate_page_objects`` from this command. You can still run it manually
   if you prefer.
3. Run this command (per tenant):

   python manage.py tenant_command seed_restaurant_module --schema=YOUR_SCHEMA

   Or all tenants::

   python manage.py migrate_schemas --command=seed_restaurant_module

   This also seeds receipt templates (KOT, bar, guest check, sale) for restaurant printing.

**Flags**

- ``--skip-permissions``: Only ensure number series (and SERV-MENU via sub-command).
- ``--skip-groups``: Create/update permission sets but do not assign user groups.
- ``--skip-receipt-templates``: Skip receipt template / assignment seeding.

Missing page Objects are skipped with a warning; run ``populate_page_objects`` first.
"""

from __future__ import annotations

from io import StringIO

from django.core.management import call_command
from django.core.management.base import BaseCommand

from setup.models import NoSeries, NoSeriesLines

SERIES_DEFINITIONS = {
    "FLOOR": {
        "description": "Restaurant floor numbers",
        "start_number": "FLOOR-000001",
        "increment_by": 1,
    },
    "TABLE": {
        "description": "Restaurant table numbers",
        "start_number": "TABLE-000001",
        "increment_by": 1,
    },
    "RESERVATION": {
        "description": "Restaurant reservation numbers",
        "start_number": "RES-000001",
        "increment_by": 1,
    },
    "MENU-CAT": {
        "description": "Menu category codes",
        "start_number": "MCAT-000001",
        "increment_by": 1,
    },
    "REST-ORDER": {
        "description": "Restaurant order numbers",
        "start_number": "REST-ORDER-000001",
        "increment_by": 1,
    },
}

# (code, name, description, [(page_name, permission_flags)])
# Flags: R/I/M/D like setup_page_permissions
RESTAURANT_PERMISSION_SETS = [
    (
        "RESTAURANT_FULL",
        "Restaurant - Full Access",
        "Full access to restaurant management, POS, and menu layout",
        [
            # Legacy SPA routes (backward compatible)
            ("Restaurant Dashboard", "RIMD"),
            ("Table Management", "RIMD"),
            ("Reservations", "RIMD"),
            ("Orders", "RIMD"),
            ("Menu Management", "RIMD"),
            ("Restaurant Menus", "RIMD"),
            ("Kitchen Display", "RIMD"),
            ("Restaurant Settings", "RIMD"),
            ("Restaurant POS", "RIMD"),
            ("Menu Layout Editor", "RIMD"),
            # Page-engine pages (BC-style)
            ("RestaurantOrderList", "RIMD"),
            ("TableList", "RIMD"),
            ("FloorList", "RIMD"),
            ("ReservationList", "RIMD"),
            ("MenuCategoryList", "RIMD"),
            ("MenuItemList", "RIMD"),
            ("MenuList", "RIMD"),
            ("MenuBuilder", "RIMD"),
            ("KitchenDisplay", "RIMD"),
            ("KitchenDisplayList", "RIMD"),
            ("RestaurantPOS", "RIMD"),
        ],
    ),
    (
        "RESTAURANT_KITCHEN",
        "Restaurant - Kitchen / KDS",
        "Kitchen display and order bumping (modify orders/KDS)",
        [
            ("Kitchen Display", "RIMD"),
            ("Orders", "RIM"),
            ("KitchenDisplayList", "RIMD"),
            ("RestaurantOrderList", "RIM"),
        ],
    ),
    (
        "RESTAURANT_FOH",
        "Restaurant - Front of house",
        "POS, floor, reservations, and orders",
        [
            ("Restaurant POS", "RIMD"),
            ("Orders", "RIMD"),
            ("Table Management", "RIMD"),
            ("Reservations", "RIMD"),
            ("RestaurantPOS", "RIMD"),
            ("RestaurantOrderList", "RIMD"),
            ("TableList", "RIMD"),
            ("ReservationList", "RIMD"),
        ],
    ),
]

# Table-data permissions (BC-style) keyed by permission set code.
RESTAURANT_TABLE_PERMISSIONS = {
    "RESTAURANT_FULL": [
        ("RestaurantOrder", "RIMD"),
        ("RestaurantOrderItem", "RIMD"),
        ("Table", "RIMD"),
        ("Reservation", "RIMD"),
        ("MenuItem", "RIMD"),
        ("MenuCategory", "RIMD"),
        ("Menu", "RIMD"),
        ("Floor", "RIMD"),
    ],
    "RESTAURANT_KITCHEN": [
        ("RestaurantOrder", "RIM"),
        ("RestaurantOrderItem", "RIM"),
    ],
    "RESTAURANT_FOH": [
        ("RestaurantOrder", "RIMD"),
        ("RestaurantOrderItem", "RIMD"),
        ("Table", "RIMD"),
        ("Reservation", "RIMD"),
        ("Floor", "RIM"),
    ],
}

USER_GROUP_DEFINITIONS = [
    (
        "REST_MANAGER",
        "Restaurant managers",
        "Full restaurant module access (assign to head waiter / shift lead).",
        ["RESTAURANT_FULL"],
        "Manager",
    ),
    (
        "REST_KITCHEN",
        "Restaurant kitchen staff",
        "Kitchen display and KDS order updates.",
        ["RESTAURANT_KITCHEN"],
        "Restaurant Kitchen",
    ),
    (
        "REST_FOH",
        "Restaurant front of house",
        "POS, tables, reservations, and orders.",
        ["RESTAURANT_FOH"],
        "Restaurant Front of House",
    ),
]


def _ensure_restaurant_roles(stdout, style):
    """
    Roles + role centers whose modules include ``restaurant`` so JWT role_center_modules
    is not empty before page-permission merges (SPA sidebar relies on Layer 1 + Layer 2).
    """
    from authentication.models import Role, RoleCenter

    center, _ = RoleCenter.objects.update_or_create(
        code="RESTAURANT_OPS_CENTER",
        defaults={
            "name": "Restaurant Operations",
            "description": "Restaurant app visibility for FO and kitchen roles",
            "modules": ["restaurant", "profile"],
            "features": {},
            "dashboard_widgets": [],
            "is_active": True,
        },
    )

    defs = (
        (
            "Restaurant Front of House",
            "POS, tables, reservations, and orders.",
        ),
        (
            "Restaurant Kitchen",
            "Kitchen display and order bumps.",
        ),
    )
    for name, desc in defs:
        role, created = Role.objects.update_or_create(
            name=name,
            defaults={
                "description": desc,
                "is_active": True,
                "permissions": [],
            },
        )
        updates = []
        if role.role_center_id != center.id:
            role.role_center = center
            updates.append("role_center")
        if created:
            stdout.write(style.SUCCESS(f"Role created for restaurant seed: {name}"))
        if updates:
            role.save(update_fields=updates)


def _ensure_number_series(stdout, style):
    created = 0
    updated = 0
    for code, definition in SERIES_DEFINITIONS.items():
        no_series, ns_created = NoSeries.objects.get_or_create(
            code=code,
            defaults={"description": definition["description"]},
        )
        if ns_created:
            created += 1
            stdout.write(
                style.SUCCESS(
                    f'Created NoSeries: {code} — {definition["description"]}'
                )
            )
        else:
            if no_series.description != definition["description"]:
                no_series.description = definition["description"]
                no_series.save(update_fields=["description"])
                updated += 1
                stdout.write(style.WARNING(f"Updated NoSeries description: {code}"))

        line = (
            NoSeriesLines.objects.filter(no_series=no_series).order_by("id").first()
        )
        if not line:
            NoSeriesLines.objects.create(
                no_series=no_series,
                start_number=definition["start_number"],
                increment_by=definition["increment_by"],
            )
            created += 1
            stdout.write(
                style.SUCCESS(
                    f'Created NoSeriesLines: {code} — start {definition["start_number"]}'
                )
            )
            continue

        fields_to_update = []
        if not line.start_number:
            line.start_number = definition["start_number"]
            fields_to_update.append("start_number")
        if not line.increment_by:
            line.increment_by = definition["increment_by"]
            fields_to_update.append("increment_by")
        if line.start_number != definition["start_number"] and not line.last_used_number:
            line.start_number = definition["start_number"]
            fields_to_update.append("start_number")
        if fields_to_update:
            line.save(update_fields=fields_to_update)
            updated += 1
            stdout.write(
                style.WARNING(
                    f"Updated NoSeriesLines: {code} — {', '.join(fields_to_update)}"
                )
            )

    return created, updated


def _apply_permission_sets(stdout, style):
    from permissions.models import PermissionSet
    from permissions.table_permissions import create_permission_lines

    created_sets = 0
    updated_sets = 0
    created_lines = 0

    for code, name, description, page_permissions in RESTAURANT_PERMISSION_SETS:
        perm_set, created = PermissionSet.objects.update_or_create(
            code=code,
            defaults={
                "name": name,
                "description": description,
                "is_active": True,
            },
        )
        if created:
            created_sets += 1
            stdout.write(style.SUCCESS(f"Permission set created: {code}"))
        else:
            updated_sets += 1
            stdout.write(style.WARNING(f"Permission set updated: {code}"))

        from permissions.models import PermissionSetLine
        PermissionSetLine.objects.filter(permissionset=perm_set).delete()

        created_lines += create_permission_lines(
            perm_set,
            page_permissions,
            object_type="Page",
            stdout=stdout,
            style=style,
        )
        table_entries = RESTAURANT_TABLE_PERMISSIONS.get(code, [])
        created_lines += create_permission_lines(
            perm_set,
            table_entries,
            object_type="Table",
            stdout=stdout,
            style=style,
        )

    stdout.write(
        style.SUCCESS(
            f"Permission lines written: {created_lines} "
            f"(sets created {created_sets}, updated {updated_sets})"
        )
    )


def _ensure_user_groups(stdout, style):
    from authentication.models import Role, UserGroup
    from permissions.models import PermissionSet

    for code, name, description, perm_codes, default_role_name in USER_GROUP_DEFINITIONS:
        group, _ = UserGroup.objects.update_or_create(
            code=code,
            defaults={
                "name": name,
                "description": description,
                "is_active": True,
            },
        )

        role = None
        if default_role_name:
            role = Role.objects.filter(name=default_role_name).first()
        if role:
            group.default_profile = role
            group.save(update_fields=["default_profile", "updated_at"])

        perm_sets = list(
            PermissionSet.objects.filter(code__in=perm_codes, is_active=True)
        )
        if len(perm_sets) != len(perm_codes):
            missing = set(perm_codes) - {p.code for p in perm_sets}
            stdout.write(
                style.WARNING(
                    f"  {code}: permission set(s) not found {missing}; assign manually."
                )
            )
        group.permission_sets.set(perm_sets)
        stdout.write(style.SUCCESS(f"User group {code}: linked {len(perm_sets)} set(s)"))


class Command(BaseCommand):
    help = (
        "Seed restaurant number series (FLOOR, TABLE, RESERVATION, MENU-CAT, REST-ORDER, "
        "SERV-MENU), receipt templates (KOT/bar/guest check), restaurant permission sets, "
        "and default user groups."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--skip-permissions",
            action="store_true",
            help="Only run number series + SERV-MENU (no permission sets or groups).",
        )
        parser.add_argument(
            "--skip-groups",
            action="store_true",
            help="Skip assigning user groups (still updates permission sets unless --skip-permissions).",
        )
        parser.add_argument(
            "--skip-receipt-templates",
            action="store_true",
            help="Skip seeding receipt templates and print assignments.",
        )

    def handle(self, *args, **options):
        skip_perm = options["skip_permissions"]
        skip_groups = options["skip_groups"]
        skip_receipt_templates = options["skip_receipt_templates"]

        self.stdout.write("Ensuring restaurant NoSeries…")
        c, u = _ensure_number_series(self.stdout, self.style)
        self.stdout.write(self.style.SUCCESS(f"NoSeries: {c} created/line ops, {u} updated"))

        self.stdout.write("Ensuring SERV-MENU (seed_service_menu_no_series)…")
        call_command("seed_service_menu_no_series")

        if not skip_receipt_templates:
            self.stdout.write("Seeding receipt templates (KOT, bar, guest check, sale)…")
            from receipt_templates.seed import seed_receipt_templates

            seed_receipt_templates(self.stdout, self.style)
        else:
            self.stdout.write(
                self.style.WARNING("Skipped receipt templates (--skip-receipt-templates).")
            )

        if skip_perm:
            self.stdout.write(
                self.style.WARNING("Skipped permission sets and groups (--skip-permissions).")
            )
            self.stdout.write(self.style.SUCCESS("Restaurant number series seed done."))
            return

        self.stdout.write(
            "Ensuring Page objects exist for permissions (populate_page_objects)…"
        )
        _pop_stdout = StringIO()
        _pop_stderr = StringIO()
        try:
            call_command(
                "populate_page_objects",
                stdout=_pop_stdout,
                stderr=_pop_stderr,
            )
        except Exception as exc:
            self.stdout.write(
                self.style.ERROR(
                    f"populate_page_objects failed: {exc}. "
                    "Fix the error and re-run seed_restaurant_module."
                )
            )
            raise
        if _pop_stderr.getvalue().strip():
            self.stdout.write(
                self.style.WARNING(_pop_stderr.getvalue()[:500])
            )

        self.stdout.write("Seeding restaurant page-engine pages…")
        try:
            from pages.restaurant_seed import seed_restaurant_pages

            seed_restaurant_pages()
            self.stdout.write(self.style.SUCCESS("Restaurant page-engine pages seeded."))
        except Exception as exc:
            self.stdout.write(
                self.style.ERROR(
                    f"Restaurant page seed failed: {exc}. "
                    "Ensure migrations are applied and re-run seed_restaurant_module."
                )
            )
            raise

        self.stdout.write("Applying restaurant page permission sets…")
        _apply_permission_sets(self.stdout, self.style)

        self.stdout.write("Ensuring restaurant Roles + Role Centers (module visibility)…")
        _ensure_restaurant_roles(self.stdout, self.style)

        if skip_groups:
            self.stdout.write(
                self.style.WARNING("Skipped user groups (--skip-groups).")
            )
        else:
            self.stdout.write("Linking user groups…")
            _ensure_user_groups(self.stdout, self.style)

        self.stdout.write(self.style.SUCCESS("Restaurant module seed complete."))
