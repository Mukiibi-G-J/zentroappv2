"""
Backfill dimension assignments for ledger entries.
For multi-tenant: python manage.py tenant_command backfill_entry_dimensions --schema=<schema> [--first-branch]
"""
from collections import defaultdict

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.utils import ProgrammingError

try:
    from django_tenants.utils import schema_context
except ImportError:
    schema_context = None

from financials.models import GeneralLedgerEntry
from items.models import ItemLedgerEntries, ValueEntry
from purchases.models import DetailedVendorLedgerEntry, VendorLedger
from sales.models import (
    CustomerLedgerEntry,
    DetailedCustomerLedgerEntry,
)


class Command(BaseCommand):
    help = (
        "Backfill dimension assignments for ledger entries and document headers. "
        "Use --first-branch to backfill null global_dimension_1 and dimension_set_id "
        "with the first branch dimension value. Includes: GL, Customer/Vendor/Item "
        "ledgers, Bank entries; Sales/Purchase Invoices, Posted Invoices, Credit Memos, "
        "Prepayments. For multi-tenant: use tenant_command with --schema=<tenant_schema>."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--first-branch",
            action="store_true",
            help="Backfill null global_dimension_1 and dimension_set_id with first branch",
        )
        parser.add_argument(
            "--schema",
            type=str,
            help="Tenant schema name (required for multi-tenant; use tenant_command).",
        )

    def handle(self, *args, **options):
        schema_name = options.get("schema")

        def run():
            if options.get("first_branch"):
                self._run_first_branch_backfill()
            else:
                self._run_user_based_backfill()

        if schema_name and schema_context:
            with schema_context(schema_name):
                run()
        elif schema_name and not schema_context:
            self.stdout.write(
                self.style.WARNING("--schema requires django-tenants; ignoring. Use: tenant_command backfill_entry_dimensions --schema=<schema> --first-branch")
            )
            run()
        else:
            run()

    def _run_first_branch_backfill(self):
        from dimension.backfill import run_branch_dimension_backfill

        try:
            from django.db import connection
            if getattr(connection, "schema_name", None) in (None, "public"):
                self.stdout.write(
                    self.style.WARNING(
                        "This project uses django-tenants. Run in tenant context: "
                        "python manage.py tenant_command backfill_entry_dimensions --schema=<tenant_schema> --first-branch"
                    )
                )
        except Exception:
            pass

        results, err = run_branch_dimension_backfill(
            allow_multiple_branch_values=True,
            write_audit=True,
        )
        if err:
            self.stdout.write(
                self.style.ERROR(
                    f"Branch backfill: {err} "
                    "Ensure General Ledger Setup has global_dimension_1 or BRANCH dimension exists."
                )
            )
            return

        self.stdout.write(self.style.SUCCESS("=" * 80))
        self.stdout.write(self.style.SUCCESS("FIRST-BRANCH DIMENSION BACKFILL SUMMARY (full registry)"))
        self.stdout.write(self.style.SUCCESS("=" * 80))
        for r in results:
            extra = f"  ({r.skipped})" if r.skipped else ""
            self.stdout.write(
                f"{r.label}: updated={r.updated}  matched={r.matched_rows}{extra}"
            )
        self.stdout.write(self.style.SUCCESS("-" * 80))

    def _run_user_based_backfill(self):
        summary = []
        summary.append(self._backfill_general_ledger_entries())
        summary.append(self._backfill_customer_ledger_entries())
        summary.append(self._backfill_detailed_customer_entries())
        summary.append(self._backfill_item_ledger_entries())
        summary.append(self._backfill_value_entries())
        summary.append(self._backfill_vendor_ledger_entries())
        summary.append(self._backfill_detailed_vendor_entries())

        self.stdout.write(self.style.SUCCESS("=" * 80))
        self.stdout.write(self.style.SUCCESS("DIMENSION BACKFILL SUMMARY (user-based)"))
        self.stdout.write(self.style.SUCCESS("=" * 80))
        for label, updated, total in summary:
            self.stdout.write(f"{label}: {updated}/{total} updated")
        self.stdout.write(self.style.SUCCESS("-" * 80))

    def _backfill_general_ledger_entries(self):
        queryset = GeneralLedgerEntry.objects.select_related(
            "user", "global_dimension_1"
        ).all()
        total = queryset.count()
        updated = 0

        for entry in queryset.iterator(chunk_size=1000):
            user = entry.user
            if not user:
                continue
            user_dimension = getattr(user, "global_dimension_1", None)
            if not user_dimension:
                continue
            if entry.global_dimension_1_id != user_dimension.pk:
                entry.global_dimension_1 = user_dimension
                entry.save(update_fields=["global_dimension_1"])
                updated += 1

        return ("General Ledger Entries", updated, total)

    def _backfill_customer_ledger_entries(self):
        queryset = CustomerLedgerEntry.objects.select_related(
            "user", "global_dimension_1"
        ).all()
        total = queryset.count()
        updated = 0

        for entry in queryset.iterator(chunk_size=1000):
            user = entry.user
            if not user:
                continue
            user_dimension = getattr(user, "global_dimension_1", None)
            if not user_dimension:
                continue
            if entry.global_dimension_1_id != user_dimension.pk:
                entry.global_dimension_1 = user_dimension
                entry.save(update_fields=["global_dimension_1"])
                updated += 1

        return ("Customer Ledger Entries", updated, total)

    def _backfill_detailed_customer_entries(self):
        queryset = DetailedCustomerLedgerEntry.objects.select_related(
            "customer_ledger_entry__global_dimension_1", "global_dimension_1"
        )
        total = queryset.count()
        updated = 0

        for entry in queryset.iterator(chunk_size=1000):
            source_entry = entry.customer_ledger_entry
            if not source_entry:
                continue
            source_dimension = source_entry.global_dimension_1
            if not source_dimension:
                continue
            if entry.global_dimension_1_id != source_dimension.pk:
                entry.global_dimension_1 = source_dimension
                entry.save(update_fields=["global_dimension_1"])
                updated += 1

        return ("Detailed Customer Ledger Entries", updated, total)

    def _backfill_item_ledger_entries(self):
        queryset = ItemLedgerEntries.objects.select_related("user", "global_dimension_1").all()
        total = queryset.count()
        updated = 0

        for entry in queryset.iterator(chunk_size=1000):
            user = entry.user
            if not user:
                continue
            user_dimension = getattr(user, "global_dimension_1", None)
            if not user_dimension:
                continue
            if entry.global_dimension_1_id != user_dimension.pk:
                entry.global_dimension_1 = user_dimension
                entry.save(update_fields=["global_dimension_1"])
                updated += 1

        return ("Item Ledger Entries", updated, total)

    def _backfill_value_entries(self):
        queryset = ValueEntry.objects.select_related(
            "item_ledger_entry_no__global_dimension_1", "global_dimension_1"
        )
        total = queryset.count()
        updated = 0

        for entry in queryset.iterator(chunk_size=1000):
            source_entry = entry.item_ledger_entry_no
            if not source_entry:
                continue
            source_dimension = source_entry.global_dimension_1
            if not source_dimension:
                continue
            if entry.global_dimension_1_id != source_dimension.pk:
                entry.global_dimension_1 = source_dimension
                entry.save(update_fields=["global_dimension_1"])
                updated += 1

        return ("Value Entries", updated, total)

    def _backfill_vendor_ledger_entries(self):
        queryset = VendorLedger.objects.select_related("global_dimension_1").all()
        total = queryset.count()
        updated = 0

        transaction_dimension_map = self._build_transaction_dimension_map()

        for entry in queryset.iterator(chunk_size=500):
            current_dimension_id = entry.global_dimension_1_id
            if current_dimension_id:
                continue

            new_dimension_id = None

            if entry.transaction_no:
                new_dimension_id = transaction_dimension_map.get(entry.transaction_no)

            if not new_dimension_id and entry.detailed_entries.exists():
                new_dimension_id = (
                    entry.detailed_entries.filter(global_dimension_1__isnull=False)
                    .values_list("global_dimension_1", flat=True)
                    .first()
                )

            if new_dimension_id:
                entry.global_dimension_1_id = new_dimension_id
                entry.save(update_fields=["global_dimension_1"])
                updated += 1

        return ("Vendor Ledger Entries", updated, total)

    def _backfill_detailed_vendor_entries(self):
        queryset = DetailedVendorLedgerEntry.objects.select_related(
            "vendor_ledger_entry__global_dimension_1", "global_dimension_1"
        )
        total = queryset.count()
        updated = 0

        for entry in queryset.iterator(chunk_size=1000):
            parent_entry = entry.vendor_ledger_entry
            if not parent_entry:
                continue
            parent_dimension_id = parent_entry.global_dimension_1_id
            if not parent_dimension_id:
                continue
            if entry.global_dimension_1_id != parent_dimension_id:
                entry.global_dimension_1_id = parent_dimension_id
                entry.save(update_fields=["global_dimension_1"])
                updated += 1

        return ("Detailed Vendor Ledger Entries", updated, total)

    def _build_transaction_dimension_map(self):
        mapping = {}
        gl_entries = (
            GeneralLedgerEntry.objects.filter(
                transaction_no__isnull=False, global_dimension_1__isnull=False
            )
            .values_list("transaction_no", "global_dimension_1")
            .iterator(chunk_size=1000)
        )

        for transaction_no, dimension_id in gl_entries:
            if transaction_no and transaction_no not in mapping:
                mapping[transaction_no] = dimension_id

        return mapping
