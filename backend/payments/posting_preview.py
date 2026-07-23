"""Shared helpers for payment / journal posting preview (BC-style related entries)."""

from __future__ import annotations

from datetime import date, datetime


def format_preview_account(obj) -> str:
    if obj is None:
        return '—'
    if hasattr(obj, 'no') and getattr(obj, 'name', None):
        return f'{obj.no} - {obj.name}'
    if hasattr(obj, 'no'):
        return str(obj.no)
    if hasattr(obj, 'code'):
        return str(obj.code)
    return str(obj)


def _preview_date(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)[:10] if value else None


def _account_no(obj) -> str | None:
    if obj is None:
        return None
    if hasattr(obj, 'no'):
        return str(obj.no)
    if hasattr(obj, 'code'):
        return str(obj.code)
    return str(obj)


def _dimension_code(value) -> str | None:
    if value is None:
        return None
    if hasattr(value, 'code'):
        return str(value.code)
    return str(value)


def _nonzero_entries(entries, *, source_key: str | None = None) -> list:
    """Keep rows that affect posting; item/value ledgers use quantity/cost, not amount."""
    result = []
    for entry in entries or []:
        if source_key in ('item_ledger_entries', 'item_entries'):
            qty = float(entry.get('quantity') or 0)
            total = float(entry.get('total') or entry.get('amount') or 0)
            if qty != 0 or total != 0:
                result.append(entry)
        elif source_key == 'value_entries':
            if any(
                float(entry.get(key) or 0) != 0
                for key in (
                    'cost_amount',
                    'sales_amount',
                    'valued_quantity',
                    'item_ledger_entry_quantity',
                    'amount',
                )
            ):
                result.append(entry)
        elif float(entry.get('amount') or 0) != 0:
            result.append(entry)
    return result


def normalize_processor_entries(entries: dict | None) -> dict:
    """Map processor keys (item_entries, bank_entries, …) to preview/find-entries keys."""
    if not entries:
        return {}
    out = dict(entries)
    for src, dest in (
        ('item_entries', 'item_ledger_entries'),
        ('bank_entries', 'bank_account_entries'),
        ('reversal_vat_entries', 'vat_entries'),
    ):
        if out.get(src) and not out.get(dest):
            out[dest] = out[src]
    return out


def _gl_balance_cache(account_nos: set[str]) -> dict[str, float]:
    if not account_nos:
        return {}
    from django.db.models import Sum
    from financials.models import GeneralLedgerEntry

    return {
        str(row['gl_account_id']): float(row['total'] or 0)
        for row in GeneralLedgerEntry.objects.filter(gl_account_id__in=account_nos)
        .values('gl_account_id')
        .annotate(total=Sum('amount'))
    }


def _vendor_balance_cache(vendor_nos: set[str]) -> dict[str, float]:
    if not vendor_nos:
        return {}
    from purchases.models import VendorLedger

    balances = {no: 0.0 for no in vendor_nos}
    for entry in VendorLedger.objects.filter(vendor__no__in=vendor_nos, open=True).select_related('vendor'):
        vendor_no = entry.vendor.no
        balances[vendor_no] = balances.get(vendor_no, 0.0) + float(entry.remaining_amount or 0)
    return balances


def _bank_balance_cache(bank_nos: set[str]) -> dict[str, float]:
    if not bank_nos:
        return {}
    from django.db.models import Sum
    from bank_account.models import BankAccountLedgerEntry

    return {
        str(row['bank_account_no_id']): float(row['total'] or 0)
        for row in BankAccountLedgerEntry.objects.filter(
            bank_account_no_id__in=bank_nos,
            reversed=False,
        )
        .values('bank_account_no_id')
        .annotate(total=Sum('amount'))
    }


def _customer_balance_cache(customer_nos: set[str]) -> dict[str, float]:
    if not customer_nos:
        return {}
    from sales.models import CustomerLedgerEntry

    balances = {no: 0.0 for no in customer_nos}
    for entry in CustomerLedgerEntry.objects.filter(customer__no__in=customer_nos, open=True).select_related('customer'):
        customer_no = entry.customer.no
        balances[customer_no] = balances.get(customer_no, 0.0) + float(entry.remaining_amount or 0)
    return balances


def _account_hover_info(
    obj,
    *,
    balance: float | None = None,
    category: str | None = None,
) -> dict | None:
    if obj is None:
        return None
    no = _account_no(obj)
    name = getattr(obj, 'name', None)
    if not no and not name:
        return None
    info = {
        'No': no,
        'Name': name,
        'Blocked': bool(getattr(obj, 'blocked', False)),
    }
    if balance is not None:
        info['Balance'] = balance
    if category:
        info['Category'] = category
    return info


def _collect_account_nos(entries: list[dict], key: str) -> set[str]:
    nos: set[str] = set()
    for entry in entries:
        obj = entry.get(key)
        no = _account_no(obj)
        if no:
            nos.add(no)
    return nos


def _serialize_gl_entry(entry: dict, *, gl_balances: dict[str, float] | None = None) -> dict:
    gl = entry.get('gl_account')
    no = _account_no(gl)
    return {
        'PostingDate': _preview_date(entry.get('posting_date')),
        'DocumentType': entry.get('document_type'),
        'DocumentNo': entry.get('document_no'),
        'GLAccountNo': no,
        'GLAccountName': getattr(gl, 'name', None) if gl else None,
        'AccountInfo': _account_hover_info(
            gl,
            balance=gl_balances.get(no, 0.0) if gl_balances is not None and no else None,
            category=getattr(gl, 'income_balance', None) if gl else None,
        ),
        'Description': entry.get('description'),
        'GenPostingType': entry.get('gen_posting_type'),
        'GlobalDimension1': _dimension_code(entry.get('global_dimension_1')),
        'Amount': float(entry.get('amount') or 0),
    }


def _serialize_vendor_entry(entry: dict, *, vendor_balances: dict[str, float] | None = None) -> dict:
    vendor = entry.get('vendor')
    amount = float(entry.get('amount') or 0)
    no = _account_no(vendor)
    return {
        'PostingDate': _preview_date(entry.get('posting_date')),
        'DocumentDate': _preview_date(entry.get('document_date')),
        'DocumentType': entry.get('document_type'),
        'DocumentNo': entry.get('document_no'),
        'VendorNo': no,
        'VendorName': getattr(vendor, 'name', None) if vendor else None,
        'AccountInfo': _account_hover_info(
            vendor,
            balance=vendor_balances.get(no, 0.0) if vendor_balances is not None and no else None,
            category='Vendor',
        ),
        'Description': entry.get('description'),
        'Amount': amount,
        'RemainingAmount': float(entry.get('remaining_amount') or amount),
        'GlobalDimension1': _dimension_code(entry.get('global_dimension_1')),
    }


def _serialize_customer_entry(entry: dict, *, customer_balances: dict[str, float] | None = None) -> dict:
    customer = entry.get('customer')
    amount = float(entry.get('amount') or 0)
    no = _account_no(customer)
    return {
        'PostingDate': _preview_date(entry.get('posting_date')),
        'DocumentDate': _preview_date(entry.get('document_date')),
        'DocumentType': entry.get('document_type'),
        'DocumentNo': entry.get('document_no'),
        'CustomerNo': no,
        'CustomerName': getattr(customer, 'name', None) if customer else None,
        'AccountInfo': _account_hover_info(
            customer,
            balance=customer_balances.get(no, 0.0) if customer_balances is not None and no else None,
            category='Customer',
        ),
        'Description': entry.get('description'),
        'Amount': amount,
        'RemainingAmount': float(entry.get('remaining_amount') or amount),
        'GlobalDimension1': _dimension_code(entry.get('global_dimension_1')),
    }


def _serialize_detailed_vendor_entry(entry: dict, *, vendor_balances: dict[str, float] | None = None) -> dict:
    vendor = entry.get('vendor')
    no = _account_no(vendor)
    return {
        'PostingDate': _preview_date(entry.get('posting_date')),
        'EntryType': entry.get('entry_type'),
        'DocumentType': entry.get('document_type'),
        'DocumentNo': entry.get('document_no'),
        'VendorNo': no,
        'VendorName': getattr(vendor, 'name', None) if vendor else None,
        'AccountInfo': _account_hover_info(
            vendor,
            balance=vendor_balances.get(no, 0.0) if vendor_balances is not None and no else None,
            category='Vendor',
        ),
        'Amount': float(entry.get('amount') or 0),
        'DebitAmount': float(entry.get('debit_amount') or 0),
        'CreditAmount': float(entry.get('credit_amount') or 0),
        'GlobalDimension1': _dimension_code(entry.get('global_dimension_1')),
    }


def _serialize_detailed_customer_entry(entry: dict, *, customer_balances: dict[str, float] | None = None) -> dict:
    customer = entry.get('customer')
    no = _account_no(customer)
    return {
        'PostingDate': _preview_date(entry.get('posting_date')),
        'EntryType': entry.get('entry_type'),
        'DocumentType': entry.get('document_type'),
        'DocumentNo': entry.get('document_no'),
        'CustomerNo': no,
        'CustomerName': getattr(customer, 'name', None) if customer else None,
        'AccountInfo': _account_hover_info(
            customer,
            balance=customer_balances.get(no, 0.0) if customer_balances is not None and no else None,
            category='Customer',
        ),
        'Amount': float(entry.get('amount') or 0),
        'AmountLCY': float(entry.get('amount') or 0),
        'DebitAmount': float(entry.get('debit_amount') or 0),
        'CreditAmount': float(entry.get('credit_amount') or 0),
        'InitialDocumentType': entry.get('initial_document_type'),
        'InitialEntryDueDate': _preview_date(entry.get('initial_entry_due_date')),
        'CurrencyCode': entry.get('currency_code') or '',
        'GlobalDimension1': _dimension_code(entry.get('global_dimension_1')),
    }


def _serialize_bank_entry(entry: dict, *, bank_balances: dict[str, float] | None = None) -> dict:
    bank = entry.get('bank_account')
    no = _account_no(bank)
    return {
        'PostingDate': _preview_date(entry.get('posting_date')),
        'DocumentDate': _preview_date(entry.get('document_date') or entry.get('posting_date')),
        'DocumentType': entry.get('document_type'),
        'DocumentNo': entry.get('document_no'),
        'BankAccountNo': no,
        'BankAccountName': getattr(bank, 'name', None) if bank else None,
        'AccountInfo': _account_hover_info(
            bank,
            balance=bank_balances.get(no, 0.0) if bank_balances is not None and no else None,
            category='Bank Account',
        ),
        'Description': entry.get('description'),
        'Amount': float(entry.get('amount') or 0),
        'BalAccountType': entry.get('bal_account_type'),
        'BalAccountNo': entry.get('bal_account_no'),
        'GlobalDimension1': _dimension_code(entry.get('global_dimension_1')),
    }


def _serialize_vat_entry(entry: dict) -> dict:
    vat_account = entry.get('vat_account')
    return {
        'PostingDate': _preview_date(entry.get('posting_date')),
        'DocumentType': entry.get('document_type'),
        'DocumentNo': entry.get('document_no'),
        'Type': entry.get('type'),
        'VatBusPostingGroup': entry.get('vat_bus_posting_group'),
        'VatProdPostingGroup': entry.get('vat_prod_posting_group'),
        'Base': float(entry.get('base') or 0),
        'Amount': float(entry.get('amount') or 0),
        'VatPercent': float(entry.get('vat_percent') or 0),
        'VatAccountNo': _account_no(vat_account),
    }


def _item_display_name(item) -> str | None:
    if item is None:
        return None
    return (
        getattr(item, 'item_name', None)
        or getattr(item, 'name', None)
        or getattr(item, 'description', None)
    )


def _serialize_item_ledger_entry(entry: dict) -> dict:
    item = entry.get('item')
    location = entry.get('location')
    return {
        'PostingDate': _preview_date(entry.get('posting_date')),
        'EntryType': entry.get('entry_type'),
        'DocumentType': entry.get('document_type'),
        'DocumentNo': entry.get('document_no'),
        'ItemNo': _account_no(item),
        'ItemName': _item_display_name(item),
        'Description': entry.get('description'),
        'Quantity': float(entry.get('quantity') or 0),
        'LocationCode': _account_no(location) if location else None,
        'LotNo': entry.get('lot_no'),
        'SerialNo': entry.get('serial_no'),
        'Amount': float(entry.get('amount') or entry.get('total') or 0),
    }


def _serialize_value_entry(entry: dict) -> dict:
    item = entry.get('item')
    location = entry.get('location')
    cost_amount = float(entry.get('cost_amount') or 0)
    sales_amount = float(entry.get('sales_amount') or 0)
    return {
        'PostingDate': _preview_date(entry.get('posting_date')),
        'EntryType': entry.get('entry_type'),
        'DocumentType': entry.get('document_type'),
        'DocumentNo': entry.get('document_no'),
        'ItemNo': _account_no(item),
        'ItemName': _item_display_name(item),
        'Description': entry.get('description'),
        'ValuedQuantity': float(entry.get('valued_quantity') or 0),
        'CostAmount': cost_amount,
        'SalesAmount': sales_amount,
        'LocationCode': _account_no(location) if location else None,
        'Amount': float(entry.get('amount') or cost_amount or sales_amount or 0),
    }


PREVIEW_TABLE_SPECS: tuple[tuple[str, str, str, callable], ...] = (
    ('gl_entries', 'G/L Entry', 'gl_entry', _serialize_gl_entry),
    ('vendor_entries', 'Vendor Ledger Entry', 'vendor_ledger_entry', _serialize_vendor_entry),
    (
        'bank_account_entries',
        'Bank Account Ledger Entry',
        'bank_account_ledger_entry',
        _serialize_bank_entry,
    ),
    (
        'detailed_vendor_entries',
        'Detailed Vendor Ledg. Entry',
        'detailed_vendor_ledger_entry',
        _serialize_detailed_vendor_entry,
    ),
    ('customer_entries', 'Customer Ledger Entry', 'customer_ledger_entry', _serialize_customer_entry),
    (
        'detailed_customer_entries',
        'Detailed Cust. Ledg. Entry',
        'detailed_customer_ledger_entry',
        _serialize_detailed_customer_entry,
    ),
    (
        'item_ledger_entries',
        'Item Ledger Entry',
        'item_ledger_entry',
        _serialize_item_ledger_entry,
    ),
    ('value_entries', 'Value Entry', 'value_entry', _serialize_value_entry),
)

# Find Entries (BC Navigate) — same ledgers plus VAT.
FIND_ENTRIES_TABLE_SPECS: tuple[tuple[str, str, str, callable], ...] = (
    ('gl_entries', 'G/L Entry', 'gl_entry', _serialize_gl_entry),
    ('vat_entries', 'VAT Entry', 'vat_entry', _serialize_vat_entry),
    ('vendor_entries', 'Vendor Ledger Entry', 'vendor_ledger_entry', _serialize_vendor_entry),
    (
        'detailed_vendor_entries',
        'Detailed Vendor Ledg. Entry',
        'detailed_vendor_ledger_entry',
        _serialize_detailed_vendor_entry,
    ),
    ('customer_entries', 'Customer Ledger Entry', 'customer_ledger_entry', _serialize_customer_entry),
    (
        'detailed_customer_entries',
        'Detailed Cust. Ledg. Entry',
        'detailed_customer_ledger_entry',
        _serialize_detailed_customer_entry,
    ),
    (
        'bank_account_entries',
        'Bank Account Ledger Entry',
        'bank_account_ledger_entry',
        _serialize_bank_entry,
    ),
    (
        'item_ledger_entries',
        'Item Ledger Entry',
        'item_ledger_entry',
        _serialize_item_ledger_entry,
    ),
    ('value_entries', 'Value Entry', 'value_entry', _serialize_value_entry),
)

# BC Navigate Show — open the matching list page filtered by document no(s).
FIND_ENTRIES_NAVIGATE_PAGES: dict[str, str] = {
    'gl_entry': 'GeneralLedgerEntryList',
    'vendor_ledger_entry': 'VendorLedgerEntryList',
    'detailed_vendor_ledger_entry': 'DetailedVendorLedgerEntryList',
    'customer_ledger_entry': 'CustomerLedgerEntryList',
    'detailed_customer_ledger_entry': 'DetailedCustomerLedgerEntryList',
    'bank_account_ledger_entry': 'BankAccountLedgerEntryList',
    'item_ledger_entry': 'ItemLedgerEntryList',
    'source_document_posted_sales_invoice': 'PostedSalesInvoiceList',
    'source_document_posted_purchase_invoice': 'PostedPurchaseInvoiceList',
}


def append_preview_ledger_rows(rows, entries, ledger_type, account_key, line_no):
    for entry in entries or []:
        amount = float(entry.get('amount') or 0)
        if amount == 0:
            continue
        account = format_preview_account(entry.get(account_key) or entry.get('gl_account'))
        rows.append({
            'Line': line_no,
            'Side': 'Debit' if amount > 0 else 'Credit',
            'LedgerType': ledger_type,
            'Account': account,
            'Amount': amount,
        })
        line_no += 1
    return line_no


def merge_processor_preview_entries(rows, entries, line_no: int = 1) -> int:
    """Append flat preview rows (legacy list view)."""
    line_no = append_preview_ledger_rows(
        rows, entries.get('gl_entries'), 'G/L', 'gl_account', line_no,
    )
    line_no = append_preview_ledger_rows(
        rows, entries.get('vendor_entries'), 'Vendor', 'vendor', line_no,
    )
    line_no = append_preview_ledger_rows(
        rows, entries.get('customer_entries'), 'Customer', 'customer', line_no,
    )
    line_no = append_preview_ledger_rows(
        rows,
        entries.get('detailed_vendor_entries'),
        'Vendor Detail',
        'vendor',
        line_no,
    )
    line_no = append_preview_ledger_rows(
        rows,
        entries.get('detailed_customer_entries'),
        'Customer Detail',
        'customer',
        line_no,
    )
    return append_preview_ledger_rows(
        rows,
        entries.get('bank_account_entries'),
        'Bank',
        'bank_account',
        line_no,
    )


def _serialize_preview_rows(source_key: str, raw: list[dict], serializer) -> list[dict]:
    if source_key == 'gl_entries':
        balances = _gl_balance_cache(_collect_account_nos(raw, 'gl_account'))
        return [serializer(entry, gl_balances=balances) for entry in raw]
    if source_key == 'vendor_entries':
        balances = _vendor_balance_cache(_collect_account_nos(raw, 'vendor'))
        return [serializer(entry, vendor_balances=balances) for entry in raw]
    if source_key == 'customer_entries':
        balances = _customer_balance_cache(_collect_account_nos(raw, 'customer'))
        return [serializer(entry, customer_balances=balances) for entry in raw]
    if source_key == 'detailed_vendor_entries':
        balances = _vendor_balance_cache(_collect_account_nos(raw, 'vendor'))
        return [serializer(entry, vendor_balances=balances) for entry in raw]
    if source_key == 'detailed_customer_entries':
        balances = _customer_balance_cache(_collect_account_nos(raw, 'customer'))
        return [serializer(entry, customer_balances=balances) for entry in raw]
    if source_key == 'bank_account_entries':
        balances = _bank_balance_cache(_collect_account_nos(raw, 'bank_account'))
        return [serializer(entry, bank_balances=balances) for entry in raw]
    return [serializer(entry) for entry in raw]


def build_bc_preview_sets(entries: dict) -> tuple[list[dict], dict[str, list[dict]]]:
    """BC-style related entry summary + per-table detail rows."""
    related: list[dict] = []
    entry_sets: dict[str, list[dict]] = {}
    entries = normalize_processor_entries(entries)

    for source_key, table_name, table_key, serializer in PREVIEW_TABLE_SPECS:
        raw = _nonzero_entries(entries.get(source_key), source_key=source_key)
        if not raw:
            continue
        rows = _serialize_preview_rows(source_key, raw, serializer)
        related.append({
            'TableKey': table_key,
            'TableName': table_name,
            'NoOfEntries': len(rows),
        })
        entry_sets[table_key] = rows

    return related, entry_sets


def build_find_entries_sets(
    entries: dict,
    *,
    source_table_name: str | None = None,
    document_nos: list[str] | None = None,
    posting_date: str | None = None,  # noqa: ARG001 — kept for API / future date scope
) -> tuple[list[dict], dict[str, list[dict]]]:
    """BC Navigate / Find Entries summary — include zero-amount and item/VAT ledgers."""
    related: list[dict] = []
    entry_sets: dict[str, list[dict]] = {}
    entries = normalize_processor_entries(entries)
    _ = posting_date

    def _nav_filters(page_name: str | None) -> dict | None:
        if not page_name or not document_nos:
            return None
        if page_name in ('PostedSalesInvoiceList', 'PostedPurchaseInvoiceList'):
            return {'no': ','.join(document_nos)}
        # Document No. alone matches BC Navigate Show for ledger lists.
        return {'document_no': ','.join(document_nos)}

    if source_table_name:
        source_key = (
            'source_document_posted_sales_invoice'
            if 'Sales' in source_table_name
            else 'source_document_posted_purchase_invoice'
            if 'Purchase' in source_table_name
            else 'source_document'
        )
        source_page = FIND_ENTRIES_NAVIGATE_PAGES.get(source_key)
        related.append({
            'TableKey': 'source_document',
            'TableName': source_table_name,
            'NoOfEntries': 1,
            'NavigatePageName': source_page,
            'NavigateFilters': _nav_filters(source_page),
        })

    for source_key, table_name, table_key, serializer in FIND_ENTRIES_TABLE_SPECS:
        raw = list(entries.get(source_key) or [])
        if not raw:
            continue
        rows = _serialize_preview_rows(source_key, raw, serializer)
        page_name = FIND_ENTRIES_NAVIGATE_PAGES.get(table_key)
        related.append({
            'TableKey': table_key,
            'TableName': table_name,
            'NoOfEntries': len(rows),
            'NavigatePageName': page_name,
            'NavigateFilters': _nav_filters(page_name),
        })
        entry_sets[table_key] = rows

    return related, entry_sets


def build_find_entries_preview_content(
    entries: dict,
    *,
    message: str = '',
    batch_name: str | None = None,
    source_table_name: str | None = None,
    document_nos: list[str] | None = None,
    posting_date: str | None = None,
) -> dict:
    """Map posted-document ledger lookup to BC Find Entries preview payload."""
    related, entry_sets = build_find_entries_sets(
        entries,
        source_table_name=source_table_name,
        document_nos=document_nos,
        posting_date=posting_date,
    )
    content: dict = {
        'Entries': [],
        'RelatedEntries': related,
        'EntrySets': entry_sets,
        'Message': message or 'Find entries',
        'DialogTitle': 'Find Entries',
        'DocumentNos': list(document_nos or []),
    }
    if batch_name:
        content['BatchName'] = batch_name
    if posting_date:
        content['PostingDate'] = posting_date
    return content


def merge_bc_preview_sets(
    related: list[dict],
    entry_sets: dict[str, list[dict]],
    entries: dict,
) -> None:
    """Merge processor entries into accumulated BC preview sets."""
    new_related, new_sets = build_bc_preview_sets(entries)
    index = {item['TableKey']: item for item in related}
    for item in new_related:
        key = item['TableKey']
        if key in index:
            index[key]['NoOfEntries'] += item['NoOfEntries']
            entry_sets.setdefault(key, []).extend(new_sets.get(key, []))
        else:
            related.append(item)
            entry_sets[key] = list(new_sets.get(key, []))


def build_posting_preview_content(
    entries: dict,
    *,
    message: str = '',
    batch_name: str | None = None,
) -> dict:
    """Map PaymentJournalProcessor output to BC-style preview payload."""
    entries = normalize_processor_entries(entries)
    preview_rows: list[dict] = []
    merge_processor_preview_entries(preview_rows, entries)
    related, entry_sets = build_bc_preview_sets(entries)

    content: dict = {
        'Entries': preview_rows,
        'RelatedEntries': related,
        'EntrySets': entry_sets,
        'Message': message,
    }
    if batch_name:
        content['BatchName'] = batch_name
    return content


def build_batch_posting_preview_content(
    entry_list: list[dict],
    *,
    message: str = '',
    batch_name: str | None = None,
) -> dict:
    """Merge multiple processor result dicts into one BC-style preview."""
    preview_rows: list[dict] = []
    line_no = 1
    related: list[dict] = []
    entry_sets: dict[str, list[dict]] = {}

    for entries in entry_list:
        line_no = merge_processor_preview_entries(preview_rows, entries, line_no)
        merge_bc_preview_sets(related, entry_sets, entries)

    content: dict = {
        'Entries': preview_rows,
        'RelatedEntries': related,
        'EntrySets': entry_sets,
        'Message': message,
    }
    if batch_name:
        content['BatchName'] = batch_name
    return content


def processor_entries_have_rows(entries: dict) -> bool:
    return any(
        entries.get(key)
        for key in (
            'gl_entries',
            'vendor_entries',
            'customer_entries',
            'detailed_vendor_entries',
            'detailed_customer_entries',
            'bank_account_entries',
        )
    )
