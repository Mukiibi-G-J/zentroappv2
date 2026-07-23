"""BC Page 344 Find Entries / Navigate — related ledger lookup for posted documents."""

from __future__ import annotations

from django.db.models import Q


def resolve_posted_purchase_document_nos(posted) -> set[str]:
    """Ledger document_no is usually PurchaseInvoice.invoice_no, not PostedPurchaseInvoice.no."""
    from purchases.models import PurchaseInvoice

    doc_nos: set[str] = set()
    if getattr(posted, 'no', None):
        doc_nos.add(posted.no)
    vendor_invoice_no = getattr(posted, 'vendor_invoice_no', None)
    vendor_id = getattr(posted, 'vendor_id', None)
    if vendor_invoice_no and vendor_id:
        purchase_invoice_no = (
            PurchaseInvoice.objects.filter(
                vendor_invoice_no=vendor_invoice_no,
                vendor_id=vendor_id,
            )
            .values_list('invoice_no', flat=True)
            .first()
        )
        if purchase_invoice_no:
            doc_nos.add(purchase_invoice_no)
    doc_nos.discard(None)
    doc_nos.discard('')
    return doc_nos


def resolve_posted_sales_document_nos(posted) -> set[str]:
    """Ledger document_no is usually SalesInvoice.invoice_no, not PostedSalesInvoice.no."""
    from sales.models import SalesInvoice

    doc_nos: set[str] = set()
    if getattr(posted, 'no', None):
        doc_nos.add(posted.no)
    customer_invoice_no = getattr(posted, 'customer_invoice_no', None)
    customer_id = getattr(posted, 'customer_id', None)
    if customer_invoice_no and customer_id:
        sales_invoice_no = (
            SalesInvoice.objects.filter(
                customer_invoice_no=customer_invoice_no,
                customer_id=customer_id,
            )
            .values_list('invoice_no', flat=True)
            .first()
        )
        if sales_invoice_no:
            doc_nos.add(sales_invoice_no)
    doc_nos.discard(None)
    doc_nos.discard('')
    return doc_nos


def _doc_filter(doc_nos: set[str], posting_date=None) -> Q:
    q = Q(document_no__in=doc_nos)
    if posting_date is not None:
        q &= Q(posting_date=posting_date)
    return q


def _item_doc_filter(doc_nos: set[str], posting_date=None) -> Q:
    """Item ledger may use posting_date or date."""
    q = Q(document_no__in=doc_nos)
    if posting_date is not None:
        q &= Q(posting_date=posting_date) | Q(date=posting_date)
    return q


def collect_ledger_entries_by_document_nos(
    doc_nos: set[str],
    *,
    posting_date=None,
) -> dict:
    """Load related ledger rows keyed for BC-style preview serializers."""
    if not doc_nos:
        return {}

    from bank_account.models import BankAccountLedgerEntry
    from financials.models import GeneralLedgerEntry, VatEntry
    from items.models import ItemLedgerEntries, ValueEntry
    from purchases.models import DetailedVendorLedgerEntry, VendorLedger
    from sales.models import CustomerLedgerEntry, DetailedCustomerLedgerEntry

    doc_q = _doc_filter(doc_nos, posting_date)
    item_q = _item_doc_filter(doc_nos, posting_date)

    gl_qs = (
        GeneralLedgerEntry.objects.filter(doc_q)
        .select_related('gl_account', 'global_dimension_1')
        .order_by('posting_date', 'id')
    )
    vat_qs = (
        VatEntry.objects.filter(doc_q)
        .select_related('vat_account', 'vat_business_posting_group', 'vat_product_posting_group')
        .order_by('posting_date', 'id')
    )
    vendor_qs = (
        VendorLedger.objects.filter(doc_q)
        .select_related('vendor', 'global_dimension_1')
        .order_by('posting_date', 'id')
    )
    detailed_vendor_qs = (
        DetailedVendorLedgerEntry.objects.filter(doc_q)
        .select_related('vendor', 'global_dimension_1')
        .order_by('posting_date', 'entry_no')
    )
    customer_qs = (
        CustomerLedgerEntry.objects.filter(doc_q)
        .select_related('customer', 'global_dimension_1')
        .order_by('posting_date', 'id')
    )
    detailed_customer_qs = (
        DetailedCustomerLedgerEntry.objects.filter(doc_q)
        .select_related('customer', 'global_dimension_1')
        .order_by('posting_date', 'entry_no')
    )
    bank_qs = (
        BankAccountLedgerEntry.objects.filter(doc_q)
        .select_related('bank_account_no', 'global_dimension_1')
        .order_by('posting_date', 'entry_no')
    )
    item_qs = (
        ItemLedgerEntries.objects.filter(item_q)
        .select_related('item', 'location', 'global_dimension_1')
        .order_by('date', 'id')
    )
    value_qs = (
        ValueEntry.objects.filter(doc_q)
        .select_related('item', 'location_code', 'global_dimension_1')
        .order_by('posting_date', 'id')
    )

    return {
        'gl_entries': [_gl_row(e) for e in gl_qs],
        'vat_entries': [_vat_row(e) for e in vat_qs],
        'vendor_entries': [_vendor_row(e) for e in vendor_qs],
        'detailed_vendor_entries': [_detailed_vendor_row(e) for e in detailed_vendor_qs],
        'customer_entries': [_customer_row(e) for e in customer_qs],
        'detailed_customer_entries': [_detailed_customer_row(e) for e in detailed_customer_qs],
        'bank_account_entries': [_bank_row(e) for e in bank_qs],
        'item_ledger_entries': [_item_ledger_row(e) for e in item_qs],
        'value_entries': [_value_entry_row(e) for e in value_qs],
    }


def _gl_row(e) -> dict:
    return {
        'posting_date': e.posting_date,
        'document_type': e.document_type,
        'document_no': e.document_no,
        'gl_account': e.gl_account,
        'description': e.description,
        'gen_posting_type': e.general_posting_type,
        'global_dimension_1': e.global_dimension_1,
        'amount': e.amount,
    }


def _vat_row(e) -> dict:
    return {
        'posting_date': e.posting_date,
        'document_type': e.document_type,
        'document_no': e.document_no,
        'type': e.type,
        'base': e.base,
        'amount': e.amount,
        'vat_percent': e.vat_percent,
        'vat_bus_posting_group': getattr(e.vat_business_posting_group, 'code', None),
        'vat_prod_posting_group': getattr(e.vat_product_posting_group, 'code', None),
        'vat_account': e.vat_account,
    }


def _vendor_row(e) -> dict:
    return {
        'posting_date': e.posting_date,
        'document_date': e.document_date,
        'document_type': e.document_type,
        'document_no': e.document_no,
        'vendor': e.vendor,
        'description': e.description,
        'amount': e.amount,
        'remaining_amount': e.remaining_amount,
        'global_dimension_1': e.global_dimension_1,
    }


def _detailed_vendor_row(e) -> dict:
    return {
        'posting_date': e.posting_date,
        'entry_type': e.entry_type,
        'document_type': e.document_type,
        'document_no': e.document_no,
        'vendor': e.vendor,
        'amount': e.amount,
        'debit_amount': e.debit_amount,
        'credit_amount': e.credit_amount,
        'global_dimension_1': e.global_dimension_1,
    }


def _customer_row(e) -> dict:
    return {
        'posting_date': e.posting_date,
        'document_date': e.document_date,
        'document_type': e.document_type,
        'document_no': e.document_no,
        'customer': e.customer,
        'description': e.description,
        'amount': e.amount,
        'remaining_amount': getattr(e, 'remaining_amount', None),
        'global_dimension_1': getattr(e, 'global_dimension_1', None),
    }


def _detailed_customer_row(e) -> dict:
    return {
        'posting_date': e.posting_date,
        'entry_type': e.entry_type,
        'document_type': e.document_type,
        'document_no': e.document_no,
        'customer': e.customer,
        'amount': e.amount,
        'debit_amount': e.debit_amount,
        'credit_amount': e.credit_amount,
        'global_dimension_1': getattr(e, 'global_dimension_1', None),
    }


def _bank_row(e) -> dict:
    return {
        'posting_date': e.posting_date,
        'document_date': getattr(e, 'document_date', None) or e.posting_date,
        'document_type': e.document_type,
        'document_no': e.document_no,
        'bank_account': e.bank_account_no,
        'description': e.description,
        'amount': e.amount,
        'bal_account_type': getattr(e, 'bal_account_type', None),
        'bal_account_no': getattr(e, 'bal_account_no', None),
        'global_dimension_1': getattr(e, 'global_dimension_1', None),
    }


def _item_ledger_row(e) -> dict:
    return {
        'posting_date': e.posting_date or e.date,
        'entry_type': e.entry_type,
        'document_type': e.document_type,
        'document_no': e.document_no,
        'item': e.item,
        'description': e.description,
        'quantity': e.quantity,
        'location': e.location,
        'amount': e.cost_amount or e.sales_amount or e.purchase_amount or 0,
        'lot_no': e.lot_no,
        'serial_no': e.serial_no,
    }


def _value_entry_row(e) -> dict:
    cost = e.cost_amount
    sales = e.sales_amount
    try:
        cost_f = float(cost) if cost not in (None, '') else 0.0
    except (TypeError, ValueError):
        cost_f = 0.0
    try:
        sales_f = float(sales) if sales not in (None, '') else 0.0
    except (TypeError, ValueError):
        sales_f = 0.0
    return {
        'posting_date': e.posting_date,
        'entry_type': e.entry_type,
        'document_type': e.document_type,
        'document_no': e.document_no,
        'item': e.item,
        'description': e.description,
        'valued_quantity': e.valued_quantity,
        'cost_amount': cost_f,
        'sales_amount': sales_f,
        'amount': cost_f or sales_f,
        'location': e.location_code,
    }


def build_find_entries_for_posted_purchase(record) -> dict:
    from payments.posting_preview import build_find_entries_preview_content

    doc_nos = resolve_posted_purchase_document_nos(record)
    if not doc_nos:
        raise ValueError('No document number available to find entries.')

    entries = collect_ledger_entries_by_document_nos(
        doc_nos,
        posting_date=getattr(record, 'posting_date', None),
    )
    # If posting_date filter yields nothing, retry without date (external docs / date drift).
    if not any(entries.values()):
        entries = collect_ledger_entries_by_document_nos(doc_nos)

    batch = next(iter(doc_nos))
    posting_date = getattr(record, 'posting_date', None)
    posting_date_s = (
        posting_date.isoformat()
        if hasattr(posting_date, 'isoformat')
        else (str(posting_date)[:10] if posting_date else None)
    )
    return build_find_entries_preview_content(
        entries,
        message=f'Find entries for document {", ".join(sorted(doc_nos))}',
        batch_name=batch,
        source_table_name='Posted Purchase Invoice',
        document_nos=sorted(doc_nos),
        posting_date=posting_date_s,
    )


def build_find_entries_for_posted_sales(record) -> dict:
    from payments.posting_preview import build_find_entries_preview_content

    doc_nos = resolve_posted_sales_document_nos(record)
    if not doc_nos:
        raise ValueError('No document number available to find entries.')

    entries = collect_ledger_entries_by_document_nos(
        doc_nos,
        posting_date=getattr(record, 'posting_date', None),
    )
    if not any(entries.values()):
        entries = collect_ledger_entries_by_document_nos(doc_nos)

    batch = next(iter(doc_nos))
    posting_date = getattr(record, 'posting_date', None)
    posting_date_s = (
        posting_date.isoformat()
        if hasattr(posting_date, 'isoformat')
        else (str(posting_date)[:10] if posting_date else None)
    )
    return build_find_entries_preview_content(
        entries,
        message=f'Find entries for document {", ".join(sorted(doc_nos))}',
        batch_name=batch,
        source_table_name='Posted Sales Invoice',
        document_nos=sorted(doc_nos),
        posting_date=posting_date_s,
    )
