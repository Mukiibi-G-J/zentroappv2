"""
Fix ValueEntry rows whose qty/cost sign does not match entry type (BC alignment).

Symptom: Inventory Value Movement G/L vs ValueEntry variance (e.g. negative adj
counted as stock in when qty was positive).

Usage:
  python manage.py tenant_command repair_negative_adjustment_value_entries \\
      --schema=<tenant> --dry-run
  python manage.py tenant_command repair_negative_adjustment_value_entries \\
      --schema=<tenant> --apply
"""

from django.core.management.base import BaseCommand

from items.models import ValueEntry
from items.value_entry_posting import (
    apply_bc_signs_to_value_entry_instance,
    bc_normalize_value_entry_fields,
    entry_type_stock_direction,
)

try:
    from django_tenants.utils import schema_context
except ImportError:
    schema_context = None


class Command(BaseCommand):
    help = (
        "Repair ValueEntry rows so qty/cost signs match Business Central rules "
        "(stock-in types positive, stock-out types negative)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--schema",
            type=str,
            help="Tenant schema (use with tenant_command).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report rows that would change (default).",
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Apply fixes to the database.",
        )
        parser.add_argument(
            "--branch-id",
            type=int,
            default=None,
            help="Optional global_dimension_1 id filter.",
        )

    def handle(self, *args, **options):
        if options.get("apply") and options.get("dry_run"):
            self.stdout.write(self.style.ERROR("Use either --dry-run or --apply, not both."))
            return
        apply_changes = bool(options.get("apply"))
        dry_run = not apply_changes

        def run():
            qs = ValueEntry.objects.filter(reversed=False)
            if options.get("branch_id"):
                qs = qs.filter(global_dimension_1_id=options["branch_id"])

            candidates = []
            for ve in qs.iterator():
                if not entry_type_stock_direction(ve.entry_type):
                    continue
                expected = bc_normalize_value_entry_fields(
                    ve.entry_type,
                    ve.item_ledger_entry_quantity,
                    ve.cost_amount,
                    cost_per_unit=ve.cost_per_unit,
                )
                if (
                    ve.item_ledger_entry_quantity == expected["item_ledger_entry_quantity"]
                    and str(ve.cost_amount) == expected["cost_amount"]
                    and ve.invoiced_quantity == expected["invoiced_quantity"]
                ):
                    continue
                candidates.append({"ve": ve, "expected": expected})

            self.stdout.write(
                f"\nFound {len(candidates)} ValueEntry row(s) to repair "
                f"({'dry-run' if dry_run else 'apply'}).\n"
            )
            for item in candidates[:50]:
                ve = item["ve"]
                exp = item["expected"]
                self.stdout.write(
                    f"  id={ve.id} doc={ve.document_no!r} type={ve.entry_type!r} "
                    f"qty {ve.item_ledger_entry_quantity} -> {exp['item_ledger_entry_quantity']} "
                    f"cost {ve.cost_amount!r} -> {exp['cost_amount']!r}"
                )
            if len(candidates) > 50:
                self.stdout.write(f"  ... and {len(candidates) - 50} more")

            if dry_run:
                self.stdout.write(
                    self.style.WARNING("\nDry-run only. Re-run with --apply to update.\n")
                )
                return

            updated = 0
            for item in candidates:
                ve = item["ve"]
                apply_bc_signs_to_value_entry_instance(ve)
                ve.save(
                    update_fields=[
                        "item_ledger_entry_quantity",
                        "invoiced_quantity",
                        "valued_quantity",
                        "cost_amount",
                        "cost_per_unit",
                        "updated_at",
                    ]
                )
                updated += 1
            self.stdout.write(self.style.SUCCESS(f"\nUpdated {updated} ValueEntry row(s).\n"))

        if schema_context and options.get("schema"):
            with schema_context(options["schema"]):
                run()
        else:
            run()
