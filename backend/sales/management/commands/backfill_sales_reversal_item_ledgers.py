"""
Create missing item/value ledger reversal rows for a posted sales credit memo.

Use when a reversal created the credit memo and financial entries but skipped
inventory because ledger rows were stored under SalesInvoice.invoice_no while the
reversal lookup used PostedSalesInvoice.no.

Usage:
  python manage.py tenant_command backfill_sales_reversal_item_ledgers --schema=hotbarmutungo --credit-memo-id=1
  python manage.py tenant_command backfill_sales_reversal_item_ledgers --schema=hotbarmutungo --invoice-no=SIN-000007
  python manage.py tenant_command backfill_sales_reversal_item_ledgers --schema=hotbarmutungo --credit-memo-id=1 --dry-run

  # --schema is consumed by tenant_command; the inner command uses the active tenant schema.
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.test import RequestFactory
from django.utils import timezone

try:
    from django_tenants.utils import schema_context
except ImportError:
    schema_context = None

from authentication.models import CustomUser
from dimension.models import get_posting_dimension_payload
from dimension.utils import get_first_branch_dimension_value
from items.models import ItemLedgerEntries, ValueEntry
from sales.admin import (
    SalesInvoiceReversalProcessor,
    resolve_sales_ledger_document_nos,
    sales_ledger_document_filter,
)
from sales.models import SalesCreditMemo, SalesInvoice, PostedSalesInvoice


def _build_reversal_wrapper(credit_memo):
    posted_invoice = credit_memo.original_invoice
    sales_invoice = SalesInvoice.objects.filter(
        customer_invoice_no=posted_invoice.customer_invoice_no,
        customer=posted_invoice.customer,
    ).first()
    if not sales_invoice:
        sales_invoice = SalesInvoice.objects.filter(
            invoice_no=credit_memo.original_invoice_no,
            customer=posted_invoice.customer,
        ).first()

    doc_nos = resolve_sales_ledger_document_nos(posted_invoice)
    invoice_no = (
        sales_invoice.invoice_no
        if sales_invoice and sales_invoice.invoice_no
        else next(iter(doc_nos), posted_invoice.no)
    )

    class ReversalInvoiceWrapper:
        def __init__(self):
            self.no = invoice_no
            self.invoice_no = invoice_no
            self.customer = posted_invoice.customer
            self.document_date = posted_invoice.document_date
            self.posting_date = posted_invoice.posting_date
            self.vat_date = posted_invoice.vat_date
            self.due_date = posted_invoice.due_date
            self.customer_invoice_no = posted_invoice.customer_invoice_no
            self.status = "Posted"
            self.reversed = True
            self.posted_sales_invoice_lines = (
                posted_invoice.posted_sales_invoice_lines.all()
            )
            self.credit_memos = SalesCreditMemo.objects.filter(pk=credit_memo.pk)

    return ReversalInvoiceWrapper()


def backfill_credit_memo_item_ledgers(credit_memo, user, dry_run=False):
    credit_memo_no = credit_memo.credit_memo_no
    existing_items = ItemLedgerEntries.objects.filter(document_no=credit_memo_no).count()
    existing_values = ValueEntry.objects.filter(document_no=credit_memo_no).count()
    if existing_items and existing_values:
        return {
            "created_items": 0,
            "created_values": 0,
            "message": (
                f"Credit memo {credit_memo_no} already has {existing_items} item "
                f"ledger row(s) and {existing_values} value row(s)."
            ),
        }

    wrapper = _build_reversal_wrapper(credit_memo)
    doc_filter = sales_ledger_document_filter(wrapper)
    original_items = list(ItemLedgerEntries.objects.filter(doc_filter))
    original_values = list(ValueEntry.objects.filter(doc_filter))

    if not original_items and not original_values:
        doc_nos = ", ".join(sorted(resolve_sales_ledger_document_nos(wrapper)))
        return {
            "created_items": 0,
            "created_values": 0,
            "message": f"No original item/value ledger rows found for document number(s): {doc_nos}",
        }

    request = RequestFactory().get("/")
    request.user = user
    preview = SalesInvoiceReversalProcessor(wrapper, request)
    preview._find_and_reverse_item_entries()
    preview._find_and_reverse_value_entries()

    if not preview.reversal_item_entries and not preview.reversal_value_entries:
        return {
            "created_items": 0,
            "created_values": 0,
            "message": "Preview produced no reversing item/value rows.",
        }

    if dry_run:
        return {
            "created_items": len(preview.reversal_item_entries),
            "created_values": len(preview.reversal_value_entries),
            "message": "Dry run only — no database changes made.",
        }

    import uuid

    transaction_no = (
        f"REV-{credit_memo_no}-"
        f"{timezone.now().date().strftime('%Y%m%d')}-"
        f"{uuid.uuid4().hex[:6].upper()}"
    )

    created_items = []
    items_only = existing_items > 0 and existing_values == 0
    with transaction.atomic():
        if not items_only:
            for idx, item_entry in enumerate(preview.reversal_item_entries):
                original_item = (
                    original_items[idx] if idx < len(original_items) else None
                )
                inv_dim_payload = get_posting_dimension_payload(
                    global_dimension_1=item_entry.get("global_dimension_1")
                    or getattr(original_item, "global_dimension_1", None),
                    global_dimension_2=item_entry.get("global_dimension_2")
                    or getattr(original_item, "global_dimension_2", None),
                    dimension_set=item_entry.get("dimension_set")
                    or getattr(original_item, "dimension_set", None),
                )
                reversing_item = ItemLedgerEntries.objects.create(
                    posting_date=item_entry["posting_date"],
                    entry_type=item_entry["entry_type"],
                    item=item_entry["item"],
                    document_no=credit_memo_no,
                    description=item_entry["description"],
                    location=item_entry["location"],
                    quantity=item_entry["quantity"],
                    remaining_quantity=item_entry["remaining_quantity"],
                    total=item_entry["total"],
                    unit_of_measure_code=item_entry["unit_of_measure_code"],
                    global_dimension_1=inv_dim_payload.get("global_dimension_1"),
                    global_dimension_2=inv_dim_payload.get("global_dimension_2"),
                    dimension_set=inv_dim_payload.get("dimension_set"),
                    user=item_entry["user"],
                    date=item_entry["date"],
                    document_type=item_entry["document_type"],
                    transaction_no=transaction_no,
                    reverses_entry_no=original_item.id if original_item else None,
                )
                created_items.append(reversing_item)
                if original_item and not original_item.reversed:
                    original_item.reversed = True
                    original_item.reversed_by_document_no = credit_memo_no
                    original_item.reversed_date = timezone.now().date()
                    original_item.reversed_by_user = user
                    original_item.save()

        if items_only:
            created_items = list(
                ItemLedgerEntries.objects.filter(document_no=credit_memo_no).order_by(
                    "id"
                )
            )

        created_values = 0
        for idx, value_entry in enumerate(preview.reversal_value_entries):
            original_val = (
                original_values[idx] if idx < len(original_values) else None
            )
            reversing_item_entry = (
                created_items[idx] if idx < len(created_items) else None
            )
            val_dim_payload = get_posting_dimension_payload(
                global_dimension_1=value_entry.get("global_dimension_1")
                or getattr(original_val, "global_dimension_1", None)
                or getattr(reversing_item_entry, "global_dimension_1", None),
                global_dimension_2=value_entry.get("global_dimension_2")
                or getattr(original_val, "global_dimension_2", None)
                or getattr(reversing_item_entry, "global_dimension_2", None),
                dimension_set=value_entry.get("dimension_set")
                or getattr(original_val, "dimension_set", None)
                or getattr(reversing_item_entry, "dimension_set", None),
            )
            ValueEntry.objects.create(
                posting_date=value_entry["posting_date"],
                document_no=credit_memo_no,
                item=value_entry["item"],
                cost_amount=value_entry["cost_amount"],
                cost_amount_non_invtbl=value_entry.get("cost_amount_non_invtbl")
                or 0,
                item_ledger_entry_quantity=value_entry[
                    "item_ledger_entry_quantity"
                ],
                invoiced_quantity=value_entry["invoiced_quantity"],
                valued_quantity=value_entry["valued_quantity"],
                cost_per_unit=value_entry["cost_per_unit"],
                general_product_posting_group=value_entry[
                    "general_product_posting_group"
                ],
                inventory_posting_group=value_entry["inventory_posting_group"],
                document_type=value_entry["document_type"],
                entry_type=value_entry["entry_type"],
                sales_amount=value_entry["sales_amount"],
                transaction_no=transaction_no,
                item_ledger_entry_no=reversing_item_entry,
                reverses_value_entry_no=original_val.id if original_val else None,
                global_dimension_1=val_dim_payload.get("global_dimension_1")
                or get_first_branch_dimension_value(),
                global_dimension_2=val_dim_payload.get("global_dimension_2"),
                dimension_set=val_dim_payload.get("dimension_set"),
            )
            created_values += 1
            if original_val and not original_val.reversed:
                original_val.reversed = True
                original_val.reversed_by_document_no = credit_memo_no
                original_val.reversed_date = timezone.now().date()
                original_val.reversed_by_user = user
                original_val.save()

    return {
        "created_items": len(created_items),
        "created_values": created_values,
        "message": (
            f"Created {len(created_items)} item ledger and {created_values} value "
            f"reversal row(s) for credit memo {credit_memo_no}."
        ),
    }


class Command(BaseCommand):
    help = (
        "Backfill missing item/value ledger reversal entries for a posted sales credit memo"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--schema",
            type=str,
            help="Tenant schema (optional; tenant_command sets the active schema).",
        )
        parser.add_argument("--credit-memo-id", type=int, help="SalesCreditMemo primary key")
        parser.add_argument("--invoice-no", help="Original sales invoice number (SIN-...)")
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview rows to create without saving",
        )
        parser.add_argument(
            "--user-email",
            default="",
            help="User email for reversed_by_user (defaults to first superuser)",
        )

    def handle(self, *args, **options):
        schema_name = options.get("schema")
        credit_memo_id = options.get("credit_memo_id")
        invoice_no = options.get("invoice_no")
        dry_run = options.get("dry_run", False)

        if not credit_memo_id and not invoice_no:
            raise CommandError("Provide --credit-memo-id or --invoice-no")

        def run():
            credit_memo = None
            if credit_memo_id:
                credit_memo = SalesCreditMemo.objects.filter(pk=credit_memo_id).first()
            elif invoice_no:
                sales_invoice = SalesInvoice.objects.filter(
                    invoice_no=invoice_no
                ).first()
                if not sales_invoice:
                    raise CommandError(f"Sales invoice {invoice_no} not found")
                posted = PostedSalesInvoice.objects.filter(
                    customer_invoice_no=sales_invoice.customer_invoice_no,
                    customer=sales_invoice.customer,
                ).first()
                if posted:
                    credit_memo = (
                        SalesCreditMemo.objects.filter(
                            original_invoice=posted, status="Posted"
                        )
                        .order_by("-id")
                        .first()
                    )
                if not credit_memo:
                    credit_memo = (
                        SalesCreditMemo.objects.filter(
                            original_invoice_no__in=[
                                invoice_no,
                                posted.no if posted else "",
                            ],
                            status="Posted",
                        )
                        .order_by("-id")
                        .first()
                    )

            if not credit_memo:
                raise CommandError("Posted sales credit memo not found")

            user_email = options.get("user_email") or ""
            user = None
            if user_email:
                user = CustomUser.objects.filter(email=user_email).first()
            if not user:
                user = CustomUser.objects.filter(is_superuser=True).first()
            if not user:
                raise CommandError("No user found for reversed_by_user")

            result = backfill_credit_memo_item_ledgers(
                credit_memo, user, dry_run=dry_run
            )
            self.stdout.write(result["message"])
            if result["created_items"] or result["created_values"]:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Items: {result['created_items']}, Values: {result['created_values']}"
                    )
                )

        if schema_name and schema_context:
            with schema_context(schema_name):
                run()
        else:
            active_schema = getattr(connection, "schema_name", None)
            if active_schema in (None, "public"):
                raise CommandError(
                    "No tenant schema active. Run via tenant_command, e.g.\n"
                    "  python manage.py tenant_command backfill_sales_reversal_item_ledgers "
                    "--schema=hotbarmutungo --invoice-no=SIN-000007"
                )
            run()
