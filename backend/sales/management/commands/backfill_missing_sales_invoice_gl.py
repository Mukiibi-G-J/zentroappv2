"""
Insert G/L lines that were never created for posted sales invoices (e.g. when
InventoryPostingSetup was missing). Skips Payment-type lines so existing Cash/AR
settlement is not duplicated.

Usage:
  python manage.py tenant_command backfill_missing_sales_invoice_gl --schema=primewise --dry-run
  python manage.py tenant_command backfill_missing_sales_invoice_gl --schema=primewise --branch-code=MWANJARI
  python manage.py tenant_command backfill_missing_sales_invoice_gl --schema=primewise --include-cogs

Default mode is revenue-only (Invoice document type only). Use --include-cogs for
COGS + inventory G/L (empty document type) - amounts use current FIFO in process().
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q
from django.test import RequestFactory

try:
    from django_tenants.utils import schema_context
except ImportError:
    schema_context = None

from authentication.models import CustomUser
from common.enums import DocumentType
from dimension.models import get_posting_dimension_payload
from dimension.utils import get_first_branch_dimension_value
from financials.enums import BalacingAccountType
from financials.models import GeneralLedgerEntry
from items.models import ItemLedgerEntries, ValueEntry
from items.enums import EntryType as ItemEntryType
from sales.admin import SalesInvoiceProcessor
from sales.models import SalesInvoice, CustomerLedgerEntry


def _filter_gl_entries(gl_entries, include_cogs):
    """Exclude Payment lines. If not include_cogs, keep only Invoice document type."""
    out = []
    for e in gl_entries:
        dt = e.get("document_type") or ""
        amount = e.get("amount") or 0
        # Avoid creating meaningless duplicate zero-value rows (0.0 / -0.0).
        # These can appear in COGS/inventory candidate entries when cost resolves to zero.
        if abs(float(amount)) < 1e-9:
            continue
        if dt == DocumentType.Payment.value:
            continue
        if not include_cogs and dt != DocumentType.Invoice.value:
            continue
        out.append(e)
    return out


def _gl_already_exists(gl_entry):
    acc = gl_entry.get("gl_account")
    if acc is None:
        return True
    dim1 = gl_entry.get("global_dimension_1")
    dim1_id = dim1.id if dim1 else None
    return GeneralLedgerEntry.objects.filter(
        document_no=gl_entry["document_no"],
        gl_account_id=getattr(acc, "pk", acc),
        posting_date=gl_entry["posting_date"],
        document_type=gl_entry.get("document_type"),
        amount=gl_entry["amount"],
        global_dimension_1_id=dim1_id,
        reversed=False,
    ).exists()


def _create_gl_row(gl_entry):
    dim_payload = get_posting_dimension_payload(
        global_dimension_1=gl_entry.get("global_dimension_1"),
        dimension_set=gl_entry.get("dimension_set"),
    )
    GeneralLedgerEntry.objects.create(
        posting_date=gl_entry["posting_date"],
        document_type=gl_entry["document_type"],
        document_no=gl_entry["document_no"],
        gl_account=gl_entry["gl_account"],
        description=gl_entry.get("description"),
        amount=gl_entry["amount"],
        general_posting_type=gl_entry.get("gen_posting_type") or "",
        dimension_set=dim_payload["dimension_set"],
        global_dimension_1=dim_payload["global_dimension_1"],
        global_dimension_2=dim_payload["global_dimension_2"],
        general_business_posting_group=gl_entry.get("gen_bus_posting_group"),
        general_product_posting_group=gl_entry.get("gen_prod_posting_group"),
        balancing_account_type=(
            BalacingAccountType.GLAccount.name
            if gl_entry.get("balance_account_type") == "G/L Account"
            else BalacingAccountType.Customer.value
        ),
        user=gl_entry["user"],
        transaction_no=gl_entry.get("transaction_no"),
    )


def _ile_already_exists(item_entry):
    return ItemLedgerEntries.objects.filter(
        document_no=item_entry["document_no"],
        item=item_entry["item"],
        transaction_no=item_entry.get("transaction_no"),
        posting_date=item_entry["posting_date"],
        quantity=item_entry["quantity"],
        total=item_entry["total"],
    ).exists()


def _create_subledger_rows(item_entry, value_entry, invoice):
    inv_dim_payload = get_posting_dimension_payload(
        global_dimension_1=item_entry.get("global_dimension_1")
        or getattr(invoice, "global_dimension_1", None),
        global_dimension_2=item_entry.get("global_dimension_2")
        or getattr(invoice, "global_dimension_2", None),
        dimension_set=item_entry.get("dimension_set")
        or value_entry.get("dimension_set")
        or getattr(invoice, "dimension_set", None),
    )

    item_ledger = ItemLedgerEntries.objects.create(
        posting_date=item_entry["posting_date"],
        entry_type=item_entry["entry_type"],
        item=item_entry["item"],
        document_no=item_entry["document_no"],
        description=item_entry["description"],
        location=item_entry["location"],
        quantity=item_entry["quantity"],
        remaining_quantity=item_entry["remaining_quantity"],
        total=item_entry["total"],
        unit_of_measure_code=item_entry["unit_of_measure"],
        global_dimension_1=inv_dim_payload.get("global_dimension_1")
        or item_entry.get("global_dimension_1"),
        global_dimension_2=inv_dim_payload.get("global_dimension_2")
        or item_entry.get("global_dimension_2"),
        dimension_set=inv_dim_payload.get("dimension_set"),
        user=item_entry["user"],
        receipt_no=item_entry["receipt_no"],
        date=item_entry["date"],
        document_type=DocumentType.Sales.value,
        transaction_no=item_entry["transaction_no"],
    )
    if item_entry.get("lot_no"):
        item_ledger.lot_no = item_entry["lot_no"]
    if item_entry.get("expiry_date"):
        item_ledger.expiry_date = item_entry["expiry_date"]
    if item_entry.get("serial_no"):
        item_ledger.serial_no = item_entry["serial_no"]
    item_ledger.save()

    ValueEntry.objects.create(
        posting_date=value_entry["posting_date"],
        document_no=value_entry["document_no"],
        item=value_entry["item"],
        cost_amount=value_entry["cost_amount"],
        cost_amount_non_invtbl=value_entry.get("cost_amount_non_invtbl") or 0,
        item_ledger_entry_quantity=value_entry["item_ledger_entry_quantity"],
        invoiced_quantity=value_entry["invoiced_quantity"],
        valued_quantity=value_entry["valued_quantity"],
        cost_per_unit=value_entry["cost_per_unit"],
        general_product_posting_group=value_entry["general_product_posting_group"],
        inventory_posting_group=value_entry["inventory_posting_group"],
        document_type=DocumentType.Sales.value,
        entry_type=ItemEntryType.DirectCost.value,
        sales_amount=value_entry["sales_amount"],
        item_ledger_entry_no=item_ledger,
        transaction_no=value_entry["transaction_no"],
        global_dimension_1=inv_dim_payload.get("global_dimension_1")
        or value_entry.get("global_dimension_1")
        or get_first_branch_dimension_value(),
        global_dimension_2=inv_dim_payload.get("global_dimension_2")
        or value_entry.get("global_dimension_2"),
        dimension_set=inv_dim_payload.get("dimension_set"),
    )


class Command(BaseCommand):
    help = (
        "Backfill missing sales invoice G/L entries (excludes Payment lines by default). "
        "Ensure InventoryPostingSetup exists before running. Uses SalesInvoiceProcessor.process() only "
        "(does not re-post subledgers or reduce inventory)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--schema",
            type=str,
            help="Tenant schema (use tenant_command).",
        )
        parser.add_argument(
            "--branch-code",
            type=str,
            default="",
            help="Filter by DimensionValue code or description (substring).",
        )
        parser.add_argument(
            "--from-date",
            type=str,
            default="",
            help="Filter posting_date >= YYYY-MM-DD (invoice posting_date).",
        )
        parser.add_argument(
            "--to-date",
            type=str,
            default="",
            help="Filter posting_date <= YYYY-MM-DD (invoice posting_date).",
        )
        parser.add_argument(
            "--invoice-no",
            type=str,
            default="",
            help="Process a single invoice number.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Max invoices to process (0 = no limit).",
        )
        parser.add_argument(
            "--user-id",
            type=int,
            default=0,
            help=(
                "CustomUser id override for SalesInvoiceProcessor. "
                "Default behavior uses each invoice.user, then first superuser, then first user."
            ),
        )
        parser.add_argument(
            "--include-cogs",
            action="store_true",
            help=(
                "Also backfill COGS/inventory G/L (non-Invoice document types). "
                "Costs use current FIFO from process() - may differ from historical values."
            ),
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be created without writing.",
        )
        parser.add_argument(
            "--include-subledger",
            action="store_true",
            help=(
                "Also backfill ItemLedgerEntries + ValueEntry from processor item/value "
                "entries. Does not reduce inventory quantities."
            ),
        )

    def handle(self, *args, **options):
        schema_name = options.get("schema")
        branch_code = (options.get("branch_code") or "").strip()
        from_date = (options.get("from_date") or "").strip()
        to_date = (options.get("to_date") or "").strip()
        invoice_no = (options.get("invoice_no") or "").strip()
        limit = int(options.get("limit") or 0)
        user_id = int(options.get("user_id") or 0)
        include_cogs = options.get("include_cogs", False)
        dry_run = options.get("dry_run", False)
        include_subledger = options.get("include_subledger", False)

        def _resolve_effective_user(inv, fallback_user):
            """
            Pick the best historical user for this invoice:
            1) existing Payment GL user (same doc + branch),
            2) existing CustomerLedgerEntry user (same doc + branch),
            3) invoice.user (if this schema has it),
            4) fallback user.
            """
            dim1_id = getattr(inv, "global_dimension_1_id", None)

            # Prefer user from existing payment G/L rows for this exact document.
            gl_user_id = (
                GeneralLedgerEntry.objects.filter(
                    document_no=inv.invoice_no,
                    document_type=DocumentType.Payment.value,
                    global_dimension_1_id=dim1_id,
                    reversed=False,
                    user__isnull=False,
                )
                .values_list("user_id", flat=True)
                .first()
            )
            if gl_user_id:
                u = CustomUser.objects.filter(pk=gl_user_id).first()
                if u:
                    return u

            # Then fall back to customer ledger user on the invoice document.
            cle_user_id = (
                CustomerLedgerEntry.objects.filter(
                    document_no=inv.invoice_no,
                    global_dimension_1_id=dim1_id,
                    user__isnull=False,
                )
                .values_list("user_id", flat=True)
                .first()
            )
            if cle_user_id:
                u = CustomUser.objects.filter(pk=cle_user_id).first()
                if u:
                    return u

            # Some schemas/models may include invoice.user.
            inv_user = getattr(inv, "user", None)
            if inv_user:
                return inv_user

            return fallback_user

        def run():
            fallback_user = None
            if user_id:
                fallback_user = CustomUser.objects.filter(pk=user_id).first()
            if not fallback_user:
                fallback_user = CustomUser.objects.filter(is_superuser=True).first()
            if not fallback_user:
                fallback_user = CustomUser.objects.order_by("id").first()
            if not fallback_user:
                self.stdout.write(self.style.ERROR("No user found for posting context."))
                return

            factory = RequestFactory()

            qs = SalesInvoice.objects.filter(status="Posted").order_by("posting_date", "id")
            if invoice_no:
                qs = qs.filter(invoice_no=invoice_no)
            if branch_code:
                from dimension.models import DimensionValue

                b_ids = DimensionValue.objects.filter(
                    Q(code__iexact=branch_code) | Q(description__icontains=branch_code)
                ).values_list("id", flat=True)
                qs = qs.filter(global_dimension_1_id__in=list(b_ids))
            if from_date:
                qs = qs.filter(posting_date__gte=from_date)
            if to_date:
                qs = qs.filter(posting_date__lte=to_date)
            if limit > 0:
                qs = list(qs[:limit])
            else:
                qs = list(qs)

            self.stdout.write(
                f"Invoices to scan: {len(qs)} | "
                f"mode={'full+cogs' if include_cogs else 'revenue-only (Invoice G/L)'} | "
                f"subledger={include_subledger} | dry_run={dry_run}\n"
            )

            total_created = 0
            total_skipped_dup = 0
            total_skip_no_lines = 0
            total_ile_created = 0
            total_ile_dup = 0
            errors = 0

            for inv in qs:
                effective_user = (
                    fallback_user if user_id else _resolve_effective_user(inv, fallback_user)
                )
                mock_request = factory.post("/")
                mock_request.user = effective_user
                receipt = f"RECON-BF-{inv.id}"
                proc = SalesInvoiceProcessor(inv, mock_request, receipt)
                result = proc.process()
                if isinstance(result, dict) and result.get("success") is False:
                    msg = result.get("message", "process failed")
                    if "Inventory Posting Setup is not configured" in msg:
                        self.stdout.write(
                            self.style.WARNING(
                                f"  SKIP {inv.invoice_no} (create InventoryPostingSetup first): {msg}"
                            )
                        )
                    else:
                        self.stdout.write(self.style.WARNING(f"  SKIP {inv.invoice_no}: {msg}"))
                        errors += 1
                    continue

                raw_entries = result.get("gl_entries") or []
                candidates = _filter_gl_entries(raw_entries, include_cogs)
                to_create = [e for e in candidates if not _gl_already_exists(e)]
                item_entries = result.get("item_entries") or []
                value_entries = result.get("value_entries") or []
                sub_pairs = list(zip(item_entries, value_entries))
                sub_to_create = [p for p in sub_pairs if not _ile_already_exists(p[0])]

                if not candidates and not (include_subledger and sub_pairs):
                    total_skip_no_lines += 1
                    continue

                if dry_run:
                    self.stdout.write(
                        f"  {inv.invoice_no}: would create {len(to_create)} / "
                        f"{len(candidates)} candidates ({len(raw_entries)} raw gl_entries)\n"
                    )
                    for e in to_create[:6]:
                        acc = e.get("gl_account")
                        acno = getattr(acc, "no", None)
                        self.stdout.write(
                            f"    + {e.get('document_type')} {acno} amt={e.get('amount')}\n"
                        )
                    if len(to_create) > 6:
                        self.stdout.write(f"    ... +{len(to_create) - 6} more\n")
                    if include_subledger:
                        self.stdout.write(
                            f"    subledger: would create {len(sub_to_create)} / {len(sub_pairs)} item/value pairs\n"
                        )
                    total_created += len(to_create)
                    total_skipped_dup += len(candidates) - len(to_create)
                    total_ile_created += len(sub_to_create)
                    total_ile_dup += len(sub_pairs) - len(sub_to_create)
                    continue

                created_here = 0
                ile_created_here = 0
                try:
                    with transaction.atomic():
                        for e in to_create:
                            _create_gl_row(e)
                            created_here += 1
                        if include_subledger:
                            for item_entry, value_entry in sub_to_create:
                                _create_subledger_rows(item_entry, value_entry, inv)
                                ile_created_here += 1
                except Exception as ex:
                    self.stdout.write(
                        self.style.ERROR(f"  FAIL {inv.invoice_no}: {ex}")
                    )
                    errors += 1
                    continue

                skipped = len(candidates) - created_here
                total_created += created_here
                total_skipped_dup += skipped
                total_ile_created += ile_created_here
                total_ile_dup += len(sub_pairs) - ile_created_here
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  OK {inv.invoice_no}: created {created_here}, skipped duplicate {skipped}"
                    )
                )
                if include_subledger:
                    self.stdout.write(
                        f"    subledger: created {ile_created_here}, skipped duplicate {len(sub_pairs) - ile_created_here}"
                    )

            self.stdout.write(
                f"\nDone. created={total_created} skip_dup={total_skipped_dup} "
                f"subledger_created={total_ile_created} subledger_skip_dup={total_ile_dup} "
                f"no_candidate_lines={total_skip_no_lines} errors={errors}\n"
            )
            if not include_cogs:
                self.stdout.write(
                    "Note: revenue-only mode; use --include-cogs for COGS/inventory G/L "
                    "(see help for FIFO risk).\n"
                )

        if schema_name and schema_context:
            with schema_context(schema_name):
                run()
        else:
            run()
