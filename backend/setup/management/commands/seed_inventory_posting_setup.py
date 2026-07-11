"""
Seed default Inventory Posting Group and Inventory Posting Setup, including
WIP Account (2140) for manufacturing/production posting.

Ensures GL accounts 2110 (Resale Items) and 2140 (WIP Account, Finished goods)
exist in the chart of accounts, then creates or updates default
InventoryPostingSetup with both inventory_account and wip_account.
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from financials.models import G_LAccount
from postings.models import InventoryPostingGroup, InventoryPostingSetup

try:
    from django_tenants.utils import schema_context
except ImportError:
    schema_context = None


# Default GL accounts used by inventory posting setup
DEFAULT_INVENTORY_ACCOUNT = {
    "no": "2110",
    "name": "Resale Items",
    "indentation": 3,
    "income_balance": "Balance Sheet",
    "accountcategory": "Assets",
    "debit_credit": "Both",
    "accounttype": "Posting",
    "totaling": None,
    "direct_posting": False,
    "blocked": False,
}

# WIP Account for finished goods / production posting (inventory posting setup)
WIP_ACCOUNT = {
    "no": "2140",
    "name": "WIP Account, Finished goods",
    "indentation": 3,
    "income_balance": "Balance Sheet",
    "accountcategory": "Assets",
    "debit_credit": "Both",
    "accounttype": "Posting",
    "totaling": None,
    "direct_posting": False,
    "blocked": False,
}

DEFAULT_INVENTORY_POSTING_GROUP_CODE = "RETAIL"

# Additional inventory posting groups (same GL accounts as RETAIL unless configured elsewhere)
INVENTORY_POSTING_GROUPS = [
    ("RETAIL", "RETAIL", True),   # (code, description, default)
    ("RAW MAT", "Raw Materials", False),
]


class Command(BaseCommand):
    help = (
        "Seed default Inventory Posting Group and Inventory Posting Setup with "
        "Inventory Account (2110) and WIP Account (2140)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Do not create new setups; only ensure GL accounts and group exist.",
        )
        parser.add_argument(
            "--schema",
            type=str,
            default=None,
            help="Tenant schema name. If set, run in that schema (requires django-tenants).",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        schema_name = options.get("schema")
        if schema_name and schema_context is None:
            self.stdout.write(
                self.style.ERROR("--schema requires django-tenants; ignoring.")
            )
            schema_name = None

        self.stdout.write("=" * 80)
        self.stdout.write(
            self.style.SUCCESS("SEEDING INVENTORY POSTING SETUP (WITH WIP ACCOUNT)")
        )
        self.stdout.write("=" * 80 + "\n")
        if schema_name:
            self.stdout.write(f"  Schema: {schema_name}\n")

        if schema_name:
            with schema_context(schema_name):
                self._do_seed(options)
        else:
            self._do_seed(options)

    def _do_seed(self, options):
        # 1. Ensure WIP Account (2140) and default Inventory Account (2110) exist in chart of accounts
        inv_account = self._get_or_create_gl_account(
            DEFAULT_INVENTORY_ACCOUNT, "Inventory Account (Resale Items)"
        )
        wip_gl = self._get_or_create_gl_account(
            WIP_ACCOUNT, "WIP Account, Finished goods"
        )

        # 2. Ensure all inventory posting groups and setups exist (RETAIL, RAW MAT, etc.)
        defaults_setups = {
            "inventory_account": inv_account,
            "wip_account": wip_gl,
        }
        for code, description, is_default in INVENTORY_POSTING_GROUPS:
            ipg, ipg_created = InventoryPostingGroup.objects.get_or_create(
                code=code,
                defaults={"description": description, "default": is_default},
            )
            if ipg_created:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  ✓ Created Inventory Posting Group: {code}"
                    )
                )
            else:
                self.stdout.write(f"  ⊙ Inventory Posting Group already exists: {code}")

            if options.get("clear"):
                continue

            setup = (
                InventoryPostingSetup.objects.filter(
                    inventory_posting_group=ipg, location__isnull=True
                )
                .first()
            )
            if not setup:
                setup = InventoryPostingSetup.objects.create(
                    inventory_posting_group=ipg,
                    location=None,
                    **defaults_setups,
                )
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  ✓ Created Inventory Posting Setup: {code} "
                        f"(Inventory: {inv_account.no}, WIP: {wip_gl.no})"
                    )
                )
            else:
                updated = []
                if setup.wip_account_id != wip_gl.no:
                    setup.wip_account = wip_gl
                    updated.append("wip_account")
                if setup.inventory_account_id != inv_account.no:
                    setup.inventory_account = inv_account
                    updated.append("inventory_account")
                if updated:
                    setup.save(update_fields=updated)
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"  ↻ Updated Inventory Posting Setup: {code} - set {', '.join(updated)}"
                        )
                    )
                else:
                    self.stdout.write(
                        f"  ⊙ Inventory Posting Setup already up to date: {code}"
                    )

        if options.get("clear"):
            self.stdout.write(
                self.style.WARNING(
                    "  (--clear: skipping Inventory Posting Setup creation)"
                )
            )
            ipg_first = InventoryPostingGroup.objects.filter(
                code=DEFAULT_INVENTORY_POSTING_GROUP_CODE
            ).first()
            self._print_summary(inv_account, wip_gl, ipg_first, None)
            return

        ipg_first = InventoryPostingGroup.objects.filter(
            code=DEFAULT_INVENTORY_POSTING_GROUP_CODE
        ).first()

        from postings.setup import ensure_inventory_posting_setups_for_all_locations

        loc_created = ensure_inventory_posting_setups_for_all_locations()
        if loc_created:
            self.stdout.write(
                self.style.SUCCESS(
                    f"  ✓ Created {loc_created} location-specific Inventory Posting Setup row(s)"
                )
            )

        self._print_summary(inv_account, wip_gl, ipg_first, None)

    def _get_or_create_gl_account(self, account_data, label):
        no = account_data["no"]
        try:
            account = G_LAccount.objects.get(no=no)
            self.stdout.write(f"  ⊙ GL Account already exists: {no} - {account.name}")
            return account
        except G_LAccount.DoesNotExist:
            pass
        account = G_LAccount.objects.create(**account_data)
        self.stdout.write(
            self.style.SUCCESS(f"  ✓ Created GL Account: {no} - {label}")
        )
        return account

    def _print_summary(self, inv_account, wip_account, ipg, setup):
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write(self.style.SUCCESS("INVENTORY POSTING SETUP SUMMARY"))
        self.stdout.write("=" * 80)
        self.stdout.write(f"  Inventory Account (2110): {inv_account.name}")
        self.stdout.write(f"  WIP Account (2140):      {wip_account.name}")
        self.stdout.write(f"  Default group:           {ipg.code}")
        if setup:
            self.stdout.write(
                f"  Setup:                    {setup.inventory_posting_group_id} "
                f"(Inventory: {setup.inventory_account_id}, WIP: {getattr(setup.wip_account, 'no', '-')})"
            )
        self.stdout.write("=" * 80 + "\n")
