"""Fix posting_date mismatches across all ledger tables.

This command walks through every posted source document (sales invoice, purchase
invoice, expense) and ensures that all derived ledger entries (General Ledger,
Customer Ledger, Item Ledger, Value Entries) use the same posting date as the
originating document. Entries are grouped by **document number** and, when
available, by **transaction number** so that every record created in the same
posting batch is updated together.

Usage examples::

    python manage.py tenant_command fix_posting_dates --schema=daurice --dry-run
    python manage.py tenant_command fix_posting_dates --schema=daurice --verbose
"""

from typing import Dict, Iterable, List, Optional, Set, Tuple

from django.core.management.base import BaseCommand
from django.db.models import Q

from financials.models import GeneralLedgerEntry
from sales.models import CustomerLedgerEntry, SalesInvoice
from purchases.models import PurchaseInvoice
from expenses.models import Expense
from items.models import ItemLedgerEntries, ValueEntry


class Command(BaseCommand):
    help = "Fix posting_date mismatches between source documents and all ledger entries"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be changed without actually making changes",
        )
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Show detailed output for each correction",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        verbose = options["verbose"]

        # Initialise stats & processed trackers for each ledger table
        self.entry_configs: Dict[str, Dict] = {
            "gl_entries": {
                "model": GeneralLedgerEntry,
                "doc_field": "document_no",
                "txn_field": "transaction_no",
                "label": "General Ledger Entries",
            },
            "customer_ledger": {
                "model": CustomerLedgerEntry,
                "doc_field": "document_no",
                "txn_field": "transaction_no",
                "label": "Customer Ledger Entries",
            },
            "item_ledger": {
                "model": ItemLedgerEntries,
                "doc_field": "document_no",
                "txn_field": "transaction_no",
                "label": "Item Ledger Entries",
            },
            "value_entries": {
                "model": ValueEntry,
                "doc_field": "document_no",
                "txn_field": "transaction_no",
                "label": "Value Entries",
            },
        }

        self.stats: Dict[str, Dict[str, int]] = {
            key: {"fixed": 0, "total": 0} for key in self.entry_configs
        }
        self.processed_ids: Dict[str, Set[int]] = {
            key: set() for key in self.entry_configs
        }

        if dry_run:
            self.stdout.write(
                self.style.WARNING("🔍 DRY RUN MODE - No changes will be made\n")
            )

        self.stdout.write(self.style.SUCCESS("=" * 80))
        self.stdout.write(
            self.style.SUCCESS("FIXING POSTING DATE MISMATCHES IN ALL LEDGER ENTRIES")
        )
        self.stdout.write(self.style.SUCCESS("=" * 80 + "\n"))

        # Process posted documents (sales, purchases, expenses)
        self._process_sales_invoices(dry_run, verbose)
        self._process_purchase_invoices(dry_run, verbose)
        self._process_expenses(dry_run, verbose)

        # Summary
        self.stdout.write("\n" + self.style.SUCCESS("=" * 80))
        self.stdout.write(self.style.SUCCESS("SUMMARY"))
        self.stdout.write(self.style.SUCCESS("=" * 80))
        for key, config in self.entry_configs.items():
            self.stdout.write(
                f"✅ {config['label']}: {self.stats[key]['fixed']}/{self.stats[key]['total']} fixed"
            )

        total_fixed = sum(s["fixed"] for s in self.stats.values())
        total_entries = sum(s["total"] for s in self.stats.values())

        self.stdout.write(
            f"\n{'🔄 WOULD FIX' if dry_run else '✅ FIXED'}: {total_fixed}/{total_entries} total entries\n"
        )

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    "\n⚠️  This was a DRY RUN. Run without --dry-run to apply changes."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS("\n🎉 All posting dates corrected successfully!")
            )

    # ------------------------------------------------------------------
    # Processing helpers
    # ------------------------------------------------------------------

    def _process_sales_invoices(self, dry_run: bool, verbose: bool) -> None:
        invoices = SalesInvoice.objects.filter(status="Posted")
        count = invoices.count()
        if count:
            self.stdout.write(
                self.style.HTTP_INFO(
                    f"\n🧾 Processing {count} posted sales invoices..."
                )
            )
        for invoice in invoices:
            # Fix entries using invoice_no as document_no
            self._fix_document_entries(
                document_no=invoice.invoice_no,
                posting_date=invoice.posting_date,
                source_label=f"SalesInvoice {invoice.invoice_no}",
                dry_run=dry_run,
                verbose=verbose,
            )
            # Also check customer_invoice_no in case some entries use it
            if (
                invoice.customer_invoice_no
                and invoice.customer_invoice_no != invoice.invoice_no
            ):
                self._fix_document_entries(
                    document_no=invoice.customer_invoice_no,
                    posting_date=invoice.posting_date,
                    source_label=f"SalesInvoice {invoice.invoice_no} (customer_invoice_no: {invoice.customer_invoice_no})",
                    dry_run=dry_run,
                    verbose=verbose,
                )

    def _process_purchase_invoices(self, dry_run: bool, verbose: bool) -> None:
        purchases = PurchaseInvoice.objects.filter(status="Posted")
        count = purchases.count()
        if count:
            self.stdout.write(
                self.style.HTTP_INFO(
                    f"\n📦 Processing {count} posted purchase invoices..."
                )
            )
        for purchase in purchases:
            self._fix_document_entries(
                document_no=purchase.invoice_no,
                posting_date=purchase.posting_date,
                source_label=f"PurchaseInvoice {purchase.invoice_no}",
                dry_run=dry_run,
                verbose=verbose,
            )

    def _process_expenses(self, dry_run: bool, verbose: bool) -> None:
        expenses = Expense.objects.filter(status="Posted")
        count = expenses.count()
        if count:
            self.stdout.write(
                self.style.HTTP_INFO(f"\n💳 Processing {count} posted expenses...")
            )
        for expense in expenses:
            self._fix_document_entries(
                document_no=expense.document_no,
                posting_date=expense.posting_date,
                source_label=f"Expense {expense.document_no}",
                dry_run=dry_run,
                verbose=verbose,
            )

    # ------------------------------------------------------------------
    # Core correction logic
    # ------------------------------------------------------------------

    def _fix_document_entries(
        self,
        *,
        document_no: str,
        posting_date,
        source_label: str,
        dry_run: bool,
        verbose: bool,
    ) -> None:
        """Fix all ledger entries linked to a document via document_no/transaction_no."""

        if not document_no:
            return

        # First, collect all transaction numbers for this document from all ledger types
        transaction_numbers = self._collect_transaction_numbers(document_no)

        # Build comprehensive filter: entries by document_no OR by any related transaction_no
        # This ensures we catch all entries from the same posting batch
        for key, config in self.entry_configs.items():
            model = config["model"]
            doc_field = config["doc_field"]
            txn_field = config["txn_field"]

            # Start with document_no filter
            filters = Q(**{doc_field: document_no})

            # Also include entries with matching transaction numbers
            # This catches entries that might be linked by transaction_no but different document_no
            if transaction_numbers and txn_field and hasattr(model, txn_field):
                filters |= Q(**{f"{txn_field}__in": transaction_numbers})

            # Get all entries matching our filters, excluding already processed ones
            queryset = model.objects.filter(filters).exclude(
                pk__in=self.processed_ids[key]
            )

            total = queryset.count()
            if not total:
                continue

            self.stats[key]["total"] += total

            # Process each entry
            for entry in queryset:
                entry_posting_date = getattr(entry, "posting_date", None)

                # Mark as processed
                self.processed_ids[key].add(entry.pk)

                # Skip if posting_date already matches
                if entry_posting_date == posting_date:
                    continue

                if verbose:
                    self.stdout.write(
                        f"  📝 {config['label']} ID {entry.pk} ({source_label}): {entry_posting_date} → {posting_date}"
                    )

                if not dry_run:
                    entry.posting_date = posting_date
                    entry.save(update_fields=["posting_date"])

                self.stats[key]["fixed"] += 1

    def _collect_transaction_numbers(self, document_no: str) -> List[str]:
        """Collect all distinct transaction numbers tied to a document.

        This method finds all transaction numbers associated with a document_no
        across all ledger types. These transaction numbers are then used to find
        all related entries from the same posting batch.
        """
        txn_numbers: Set[str] = set()

        # Collect transaction numbers from all ledger types for this document
        for key, config in self.entry_configs.items():
            model = config["model"]
            txn_field = config["txn_field"]
            doc_field = config["doc_field"]

            if not txn_field or not hasattr(model, txn_field):
                continue

            # Get transaction numbers directly linked to this document_no
            numbers = (
                model.objects.filter(**{doc_field: document_no})
                .exclude(**{f"{txn_field}__isnull": True})
                .exclude(**{txn_field: ""})
                .values_list(txn_field, flat=True)
                .distinct()
            )
            txn_numbers.update(numbers)

        return sorted([tn for tn in txn_numbers if tn])
