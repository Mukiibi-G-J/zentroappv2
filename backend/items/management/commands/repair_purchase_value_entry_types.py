"""
Reclassify purchase ValueEntry rows stored as Direct Cost → Purchase (BC alignment).

Symptom: Inventory Value Movement shows G/L Purchase in stock in but VE purchase
missing and amount appears under COGS / Direct Cost.

Usage:
  python manage.py tenant_command repair_purchase_value_entry_types --schema=<tenant> --dry-run
  python manage.py tenant_command repair_purchase_value_entry_types --schema=<tenant> --apply
"""

from django.core.management.base import BaseCommand

from items.enums import DocumentType, EntryType
from items.models import ValueEntry
from items.value_entry_posting import (
    apply_bc_signs_to_value_entry_instance,
    resolve_inventory_entry_type,
)

try:
    from django_tenants.utils import schema_context
except ImportError:
    schema_context = None

PURCHASE_DOCS = {
    DocumentType.Purchase.value,
    DocumentType.PurchaseReceipt.value,
    EntryType.Purchase.value,
    "Purchase",
    "Purchase Receipt",
}


class Command(BaseCommand):
    help = "Set entry_type=Purchase on purchase invoices posted as Direct Cost."

    def add_arguments(self, parser):
        parser.add_argument("--schema", type=str, help="Tenant schema.")
        parser.add_argument("--dry-run", action="store_true", help="Report only.")
        parser.add_argument("--apply", action="store_true", help="Apply updates.")

    def handle(self, *args, **options):
        if options.get("apply") and options.get("dry_run"):
            self.stdout.write(self.style.ERROR("Use either --dry-run or --apply."))
            return
        dry_run = not options.get("apply")

        def run():
            qs = ValueEntry.objects.filter(reversed=False)
            candidates = []
            for ve in qs.iterator():
                resolved = resolve_inventory_entry_type(ve.entry_type, ve.document_type)
                if resolved != EntryType.Purchase.value:
                    continue
                if (ve.document_type or "") not in PURCHASE_DOCS and (
                    ve.document_type or ""
                ).lower().find("purchase") < 0:
                    continue
                if ve.entry_type == EntryType.Purchase.value:
                    continue
                candidates.append(ve)

            self.stdout.write(
                f"\nFound {len(candidates)} purchase ValueEntry row(s) to reclassify "
                f"({'dry-run' if dry_run else 'apply'}).\n"
            )
            for ve in candidates[:50]:
                self.stdout.write(
                    f"  id={ve.id} doc={ve.document_no!r} "
                    f"type {ve.entry_type!r} -> {EntryType.Purchase.value!r} "
                    f"document_type={ve.document_type!r}"
                )
            if len(candidates) > 50:
                self.stdout.write(f"  ... and {len(candidates) - 50} more")

            if dry_run:
                self.stdout.write(self.style.WARNING("\nDry-run only.\n"))
                return

            updated = 0
            for ve in candidates:
                ve.entry_type = EntryType.Purchase.value
                apply_bc_signs_to_value_entry_instance(ve)
                ve.save(
                    update_fields=[
                        "entry_type",
                        "item_ledger_entry_quantity",
                        "invoiced_quantity",
                        "valued_quantity",
                        "cost_amount",
                        "cost_per_unit",
                        "updated_at",
                    ]
                )
                updated += 1
            self.stdout.write(self.style.SUCCESS(f"\nUpdated {updated} row(s).\n"))

        if schema_context and options.get("schema"):
            with schema_context(options["schema"]):
                run()
        else:
            run()
