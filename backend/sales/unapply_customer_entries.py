"""
BC CustEntry-Apply Posted Entries — Unapply Customer Entries.

Reverses posted Application DetailedCustomerLedgerEntry rows, reopens CLE
Remaining/Open, and clears Applies-to ID stamps. No G/L is written (same as
standard BC unapply for LCY applications without FX gain/loss).
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from django.db import transaction
from django.db.models import Q, QuerySet
from django.utils import timezone


def _parse_date(value) -> date:
    if value is None or value == '':
        return timezone.localdate()
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()[:10]
    return date.fromisoformat(text)


def find_application_entries_to_unapply(cle) -> QuerySet:
    """
    Application detailed rows that will be reversed for this CLE.

    Groups by transaction_no of Application rows on (or linked to) the CLE,
    matching BC Unapply Customer Entries line set.
    """
    from common.enums import EntryType
    from sales.models import DetailedCustomerLedgerEntry

    app_type = EntryType.application.value
    direct = DetailedCustomerLedgerEntry.objects.filter(
        customer_ledger_entry_id=cle.pk,
        entry_type=app_type,
        unapplied=False,
    )
    txn_nos = {
        t for t in direct.values_list('transaction_no', flat=True).distinct() if t
    }

    if not txn_nos:
        linked = DetailedCustomerLedgerEntry.objects.filter(
            applied_customer_ledger_entry_no=cle.pk,
            entry_type=app_type,
            unapplied=False,
        )
        txn_nos = {
            t for t in linked.values_list('transaction_no', flat=True).distinct() if t
        }

    if not txn_nos:
        # Fallback: applications on this CLE without shared transaction_no
        if direct.exists():
            return direct.select_related(
                'customer',
                'customer_ledger_entry',
                'global_dimension_1',
                'dimension_set',
            ).order_by('entry_no')
        return DetailedCustomerLedgerEntry.objects.none()

    return (
        DetailedCustomerLedgerEntry.objects.filter(
            entry_type=app_type,
            unapplied=False,
            customer_id=cle.customer_id,
            transaction_no__in=txn_nos,
        )
        .select_related(
            'customer',
            'customer_ledger_entry',
            'global_dimension_1',
            'dimension_set',
        )
        .order_by('entry_no')
    )


def serialize_unapply_line(dtld) -> dict[str, Any]:
    return {
        'EntryNo': dtld.entry_no,
        'PostingDate': dtld.posting_date.isoformat() if dtld.posting_date else None,
        'EntryType': dtld.entry_type,
        'DocumentType': dtld.document_type,
        'DocumentNo': dtld.document_no,
        'CustomerNo': getattr(dtld.customer, 'no', None),
        'InitialDocumentType': dtld.initial_document_type,
        'InitialDocumentNo': (
            getattr(dtld.customer_ledger_entry, 'document_no', None)
            if dtld.customer_ledger_entry_id
            else None
        ),
        'InitialEntryDueDate': (
            dtld.initial_entry_due_date.isoformat()
            if dtld.initial_entry_due_date
            else None
        ),
        'Amount': int(dtld.amount or 0),
        'DebitAmount': int(dtld.debit_amount or 0),
        'CreditAmount': int(dtld.credit_amount or 0),
        'CurrencyCode': '',
        'CustomerLedgerEntryNo': dtld.customer_ledger_entry_id,
        'AppliedCustomerLedgerEntryNo': dtld.applied_customer_ledger_entry_no,
        'TransactionNo': dtld.transaction_no,
    }


def build_unapply_dialog_content(cle, *, document_no: str | None = None, posting_date=None) -> dict:
    apps = list(find_application_entries_to_unapply(cle))
    if not apps:
        raise ValueError(
            'This customer ledger entry has no applied entries to unapply.'
        )

    doc_no = (document_no or '').strip() or (cle.document_no or '')
    post_date = _parse_date(posting_date or cle.posting_date)
    customer = cle.customer
    return {
        'EntryNo': cle.pk,
        'SystemId': str(cle.system_id),
        'CustomerNo': getattr(customer, 'no', ''),
        'CustomerName': getattr(customer, 'name', '') or '',
        'DocumentNo': doc_no,
        'PostingDate': post_date.isoformat(),
        'DialogTitle': (
            f'Unapply Customer Entries - '
            f'{getattr(customer, "no", "")} {getattr(customer, "name", "") or ""} '
            f'Entry No. {cle.pk}'
        ).strip(),
        'Lines': [serialize_unapply_line(a) for a in apps],
    }


def _build_reversing_dicts(
    apps,
    *,
    document_no: str,
    posting_date: date,
    transaction_no: str,
) -> list[dict]:
    rows: list[dict] = []
    for app in apps:
        amount = int(app.amount or 0)
        debit = int(app.debit_amount or 0)
        credit = int(app.credit_amount or 0)
        rows.append(
            {
                'posting_date': posting_date,
                'entry_type': app.entry_type,
                'document_type': app.document_type,
                'document_no': document_no,
                'customer': app.customer,
                'amount': -amount,
                'debit_amount': credit,
                'credit_amount': debit,
                'initial_entry_due_date': app.initial_entry_due_date or posting_date,
                'initial_document_type': app.initial_document_type,
                'customer_ledger_entry': app.customer_ledger_entry,
                'applied_customer_ledger_entry_no': app.applied_customer_ledger_entry_no,
                'unapplied_by_entry_no': 0,
                'unapplied': False,
                'global_dimension_1': app.global_dimension_1,
                'dimension_set': app.dimension_set,
                'transaction_no': transaction_no,
                'source_entry_no': app.entry_no,
            }
        )
    return rows


def build_unapply_preview_entries(
    cle,
    *,
    document_no: str | None = None,
    posting_date=None,
) -> dict:
    apps = list(find_application_entries_to_unapply(cle))
    if not apps:
        raise ValueError(
            'This customer ledger entry has no applied entries to unapply.'
        )

    doc_no = (document_no or '').strip() or (cle.document_no or '')
    post_date = _parse_date(posting_date or cle.posting_date)
    txn = f'UNAPPLY-PREVIEW-{uuid.uuid4().hex[:8].upper()}'
    reversing = _build_reversing_dicts(
        apps,
        document_no=doc_no,
        posting_date=post_date,
        transaction_no=txn,
    )
    # Preview should not expose internal source_entry_no; BC masks Document No. as ***.
    for row in reversing:
        row.pop('source_entry_no', None)
        row['document_no'] = '***'
    return {'detailed_customer_entries': reversing}


def post_unapply_customer_entries(
    cle,
    *,
    document_no: str | None = None,
    posting_date=None,
    user=None,
) -> dict:
    from common.enums import EntryType
    from sales.models import CustomerLedgerEntry, DetailedCustomerLedgerEntry

    apps = list(find_application_entries_to_unapply(cle))
    if not apps:
        raise ValueError(
            'This customer ledger entry has no applied entries to unapply.'
        )

    doc_no = (document_no or '').strip() or (cle.document_no or '')
    if not doc_no:
        raise ValueError('Document No. is required to unapply.')
    post_date = _parse_date(posting_date or cle.posting_date)
    txn = f'UNAPPLY-{uuid.uuid4().hex[:10].upper()}'
    reversing = _build_reversing_dicts(
        apps,
        document_no=doc_no,
        posting_date=post_date,
        transaction_no=txn,
    )

    affected_cle_ids: set[int] = set()
    created_count = 0

    with transaction.atomic():
        for row in reversing:
            source_entry_no = row.pop('source_entry_no')
            source = next(a for a in apps if a.entry_no == source_entry_no)
            created = DetailedCustomerLedgerEntry.objects.create(
                posting_date=row['posting_date'],
                entry_type=EntryType.application.value,
                document_type=row['document_type'],
                document_no=row['document_no'],
                customer=row['customer'],
                amount=row['amount'],
                debit_amount=row['debit_amount'],
                credit_amount=row['credit_amount'],
                initial_entry_due_date=row['initial_entry_due_date'],
                initial_document_type=row['initial_document_type'],
                customer_ledger_entry=row['customer_ledger_entry'],
                applied_customer_ledger_entry_no=row['applied_customer_ledger_entry_no'],
                unapplied_by_entry_no=0,
                unapplied=False,
                global_dimension_1=row['global_dimension_1'],
                dimension_set=row['dimension_set'],
                transaction_no=row['transaction_no'],
            )
            source.unapplied = True
            source.unapplied_by_entry_no = created.entry_no
            source.save(update_fields=['unapplied', 'unapplied_by_entry_no', 'updated_at'])
            created_count += 1
            if created.customer_ledger_entry_id:
                affected_cle_ids.add(created.customer_ledger_entry_id)
            if created.applied_customer_ledger_entry_no:
                affected_cle_ids.add(int(created.applied_customer_ledger_entry_no))

        for cle_id in affected_cle_ids:
            entry = CustomerLedgerEntry.objects.filter(pk=cle_id).first()
            if not entry:
                continue
            remaining = entry.remaining_amount
            entry.open = remaining != 0
            if entry.applies_to_id:
                entry.applies_to_id = ''
                entry.save(update_fields=['open', 'applies_to_id', 'updated_at'])
            else:
                entry.save(update_fields=['open', 'updated_at'])

    return {
        'Message': (
            f'Unapplied {created_count} application '
            f'{"entry" if created_count == 1 else "entries"} '
            f'for customer ledger entry {cle.pk}.'
        ),
        'CreatedCount': created_count,
        'TransactionNo': txn,
        'AffectedEntryIds': sorted(affected_cle_ids),
    }


def assert_customer_ledger_entry_can_apply(cle) -> None:
    """
    BC CustEntry-Apply Posted Entries guard before opening Apply Customer Entries.

    Message matches Business Central when the selected CLE is already closed.
    """
    if not getattr(cle, 'open', True):
        raise ValueError(
            'One or more of the entries that you selected is closed. '
            'You cannot apply closed entries.'
        )


def build_apply_customer_ledger_dialog_content(cle) -> dict[str, Any]:
    """Payload for opening Apply Customer Entries from a CLE (open entries only)."""
    assert_customer_ledger_entry_can_apply(cle)
    customer = getattr(cle, 'customer', None)
    return {
        'EntryNo': cle.pk,
        'SystemId': str(cle.system_id),
        'CustomerNo': getattr(customer, 'no', '') or '',
        'CustomerName': getattr(customer, 'name', '') or '',
        'DocumentNo': cle.document_no or '',
        'DocumentType': cle.document_type or '',
        'PostingDate': (
            cle.posting_date.isoformat() if cle.posting_date else ''
        ),
        'Open': bool(cle.open),
        'RemainingAmount': int(cle.remaining_amount or 0),
    }


def customer_ledger_entry_is_paid_or_partially_applied(cle) -> bool:
    """True when Application detailed rows exist (fully or partially applied)."""
    from common.enums import EntryType
    from sales.models import DetailedCustomerLedgerEntry

    if find_application_entries_to_unapply(cle).exists():
        return True
    return DetailedCustomerLedgerEntry.objects.filter(
        customer_ledger_entry_id=cle.pk,
        entry_type=EntryType.application.value,
        unapplied=False,
    ).exists()


def assert_posted_sales_invoice_not_applied(posted) -> None:
    """
    BC Correct guard: block Correct / corrective CM when invoice CLE is applied.

    Message mirrors Business Central paid-invoice correct dialog.
    """
    from pages.find_entries import resolve_posted_sales_document_nos
    from sales.models import CustomerLedgerEntry

    doc_nos = resolve_posted_sales_document_nos(posted)
    if not doc_nos:
        return

    q = Q(document_no__in=doc_nos, document_type='Invoice')
    if getattr(posted, 'customer_id', None):
        q &= Q(customer_id=posted.customer_id)

    for cle in CustomerLedgerEntry.objects.filter(q):
        if customer_ledger_entry_is_paid_or_partially_applied(cle):
            raise ValueError(
                'You cannot correct this posted sales invoice because it is '
                'fully or partially paid.\n\n'
                'To reverse a paid sales invoice, unapply the payment from '
                'Customer Ledger Entries (Find entries → Cust. Ledger Entry → '
                'Unapply Entries), then create a sales credit memo.'
            )
        # Closed with zero remaining even without Application rows (e.g. cash)
        if not cle.open and int(cle.remaining_amount or 0) == 0:
            raise ValueError(
                'You cannot correct this posted sales invoice because it is '
                'fully or partially paid.\n\n'
                'To reverse a paid sales invoice, you must manually create a '
                'sales credit memo.'
            )
