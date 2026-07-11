from django.core.management.base import BaseCommand
from django.db.models import Q


class Command(BaseCommand):
    help = (
        "Backfill global_dimension_1 and dimension_set on all ledger/document records "
        "where either field is NULL or invalid (dangling FK / wrong value), using the "
        "first branch DimensionValue and its corresponding DimensionSet."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show counts of records that would be updated without writing.",
        )
        parser.add_argument(
            "--fix-invalid",
            action="store_true",
            help=(
                "Also fix records where global_dimension_1 or dimension_set point to "
                "non-existent or incorrect values (e.g. dangling FK ids)."
            ),
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        fix_invalid = options["fix_invalid"]

        from dimension.utils import get_first_branch_dimension_value
        from dimension.models import get_or_create_dimension_set

        branch_value = get_first_branch_dimension_value()
        if not branch_value:
            self.stderr.write(
                self.style.ERROR(
                    "No branch DimensionValue found. "
                    "Ensure GeneralLedgerSetup.global_dimension_1 is configured "
                    "or a Dimension with code 'BRANCH' exists with at least one value."
                )
            )
            return

        branch_dim = branch_value.dimension_code
        if not branch_dim:
            self.stderr.write(
                self.style.ERROR(
                    f"DimensionValue '{branch_value.code}' has no dimension_code set."
                )
            )
            return

        dim_set = get_or_create_dimension_set({branch_dim: branch_value})
        if not dim_set:
            self.stderr.write(self.style.ERROR("Failed to get or create DimensionSet."))
            return

        mode = "FIX-INVALID" if fix_invalid else "NULL-ONLY"
        self.stdout.write(
            self.style.SUCCESS(
                f"Branch: {branch_dim.code} = {branch_value.code} "
                f"(DimensionSet id={dim_set.pk})  Mode: {mode}"
            )
        )
        if dry_run:
            self.stdout.write(
                self.style.WARNING("DRY RUN — no records will be modified.\n")
            )

        models_to_backfill = self._get_models()
        total_updated = 0

        for label, model_cls in models_to_backfill:
            if fix_invalid:
                qs = model_cls.objects.exclude(
                    dimension_set=dim_set,
                    global_dimension_1=branch_value,
                )
            else:
                qs = model_cls.objects.filter(
                    Q(dimension_set__isnull=True)
                    | Q(global_dimension_1__isnull=True)
                )
            count = qs.count()

            if count == 0:
                self.stdout.write(f"  {label}: 0 records (skip)")
                continue

            if dry_run:
                self.stdout.write(
                    self.style.WARNING(f"  {label}: {count} records would be updated")
                )
            else:
                updated = qs.update(
                    dimension_set=dim_set,
                    global_dimension_1=branch_value,
                )
                self.stdout.write(
                    self.style.SUCCESS(f"  {label}: {updated} records updated")
                )
                total_updated += updated

        self.stdout.write("")
        if dry_run:
            self.stdout.write(
                self.style.WARNING("DRY RUN complete — no changes were made.")
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Backfill complete. Total records updated: {total_updated}"
                )
            )

    @staticmethod
    def _get_models():
        from purchases.models import (
            PurchaseInvoice,
            PurchaseInvoiceLine,
            PostedPurchaseInvoice,
            PostedPurchaseInvoiceLine,
            VendorLedger,
            PurchaseCreditMemo,
            PurchaseCreditMemoLine,
            DetailedVendorLedgerEntry,
        )
        from sales.models import (
            SalesInvoice,
            SalesInvoiceLine,
            SalesOrderLine,
            PostedSalesInvoice,
            PostedSalesInvoiceLine,
            CustomerLedgerEntry,
            DetailedCustomerLedgerEntry,
            SalesCreditMemo,
            SalesCreditMemoLine,
        )
        from financials.models import GeneralLedgerEntry
        from bank_account.models import BankAccountLedgerEntry
        from items.models import ItemLedgerEntries, ValueEntry
        from production.models import ProductionOrderLine
        from prepayment.models import Preayment, PreaymentLine
        from expenses.models import Expense

        return [
            ("PurchaseInvoice", PurchaseInvoice),
            ("PurchaseInvoiceLine", PurchaseInvoiceLine),
            ("PostedPurchaseInvoice", PostedPurchaseInvoice),
            ("PostedPurchaseInvoiceLine", PostedPurchaseInvoiceLine),
            ("VendorLedger", VendorLedger),
            ("PurchaseCreditMemo", PurchaseCreditMemo),
            ("PurchaseCreditMemoLine", PurchaseCreditMemoLine),
            ("DetailedVendorLedgerEntry", DetailedVendorLedgerEntry),
            ("SalesInvoice", SalesInvoice),
            ("SalesInvoiceLine", SalesInvoiceLine),
            ("SalesOrderLine", SalesOrderLine),
            ("PostedSalesInvoice", PostedSalesInvoice),
            ("PostedSalesInvoiceLine", PostedSalesInvoiceLine),
            ("CustomerLedgerEntry", CustomerLedgerEntry),
            ("DetailedCustomerLedgerEntry", DetailedCustomerLedgerEntry),
            ("SalesCreditMemo", SalesCreditMemo),
            ("SalesCreditMemoLine", SalesCreditMemoLine),
            ("GeneralLedgerEntry", GeneralLedgerEntry),
            ("BankAccountLedgerEntry", BankAccountLedgerEntry),
            ("ItemLedgerEntries", ItemLedgerEntries),
            ("ValueEntry", ValueEntry),
            ("ProductionOrderLine", ProductionOrderLine),
            ("Prepayment", Preayment),
            ("PrepaymentLine", PreaymentLine),
            ("Expense", Expense),
        ]
