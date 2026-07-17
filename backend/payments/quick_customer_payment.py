"""POS / cashier one-shot: create customer payment, apply oldest open invoice, post."""

from __future__ import annotations

import uuid
from decimal import Decimal, InvalidOperation

from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.utils import timezone

from financials.models import PaymentMethod
from payments.admin import PaymentJournalPostingProcessor
from payments.enums import AccountType, DocumentType, PaymentStatus
from payments.journal_application import (
    applying_document_no,
    applying_party_no,
    clear_applies_to_stamps_for_document,
    ledger_entry_allows_applies_to_stamp,
    set_customer_application,
)
from payments.models import PaymentJournal, PaymentLine
from payments.posting_prepare import prepare_payment_journal_for_posting
from sales.models import Customer, CustomerLedgerEntry


class QuickCustomerPaymentError(Exception):
    """Validation or business-rule failure for quick customer payment."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


def _coerce_amount(raw) -> int:
    if raw is None or raw == "":
        raise QuickCustomerPaymentError("amount is required")
    try:
        value = Decimal(str(raw).replace(",", "").strip())
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise QuickCustomerPaymentError("amount must be a valid number") from exc
    if value <= 0:
        raise QuickCustomerPaymentError("amount must be greater than zero")
    return int(value)


def _open_ledger_qs(customer: Customer, request=None):
    qs = CustomerLedgerEntry.objects.filter(customer=customer, open=True)
    if request is not None:
        try:
            from dimension.branch_filter import filter_queryset_by_branch

            qs = filter_queryset_by_branch(qs, request.user, request=request)
        except Exception:
            pass
    return qs


def _customer_outstanding(customer: Customer, request=None) -> int:
    total = 0
    for entry in _open_ledger_qs(customer, request):
        total += entry.remaining_amount or 0
    return abs(int(total))


def _oldest_open_invoice(customer: Customer, request=None) -> CustomerLedgerEntry | None:
    qs = (
        _open_ledger_qs(customer, request)
        .filter(document_type="Invoice")
        .order_by("posting_date", "id")
    )
    for entry in qs:
        remaining = entry.remaining_amount or 0
        if remaining != 0:
            return entry
    return None


def _stamp_applies_to(journal: PaymentJournal, customer_ledger: CustomerLedgerEntry) -> None:
    try:
        applies_to_id = applying_document_no(journal)
        customer_no = applying_party_no(journal, "customer")
        if customer_no:
            clear_applies_to_stamps_for_document(
                applies_to_id,
                customer_no=customer_no,
                except_ledger_id=customer_ledger.id,
            )
        if ledger_entry_allows_applies_to_stamp(customer_ledger):
            customer_ledger.applies_to_id = applies_to_id
            customer_ledger.save(update_fields=["applies_to_id", "updated_at"])
    except ValueError:
        pass


def _journal_debug_snapshot(journal: PaymentJournal, invoice: CustomerLedgerEntry) -> dict:
    """Temporary debug payload so POS can inspect apply/dimension state without posting."""
    bal = getattr(journal, "bal_account_no", None)
    user = getattr(journal, "_request_user", None)
    return {
        "status": journal.status,
        "application_status": getattr(journal, "application_status", None),
        "applies_to_doc_type": getattr(journal, "applies_to_doc_type", None),
        "applies_to_object_id": getattr(journal, "applies_to_object_id", None),
        "applies_to_doc_name": getattr(journal, "applies_to_doc_name", None),
        "external_document_no": journal.external_document_no,
        "description": journal.description,
        "bal_account_type": journal.bal_account_type,
        "bal_account_object_id": journal.bal_account_object_id,
        "bal_account_no": str(bal) if bal is not None else None,
        "journal_dimension_set_id": getattr(journal, "dimension_set_id", None),
        "invoice_document_no": invoice.document_no,
        "invoice_ledger_id": invoice.id,
        "invoice_dimension_set_id": getattr(invoice, "dimension_set_id", None),
        "invoice_global_dimension_1_id": getattr(invoice, "global_dimension_1_id", None),
        "invoice_applies_to_id": getattr(invoice, "applies_to_id", None) or "",
        "user_global_dimension_1_id": (
            getattr(user, "global_dimension_1_id", None) if user else None
        ),
        "user_dimension_set_id": (
            getattr(user, "dimension_set_id", None) if user else None
        ),
    }


def quick_customer_payment(
    *,
    customer_id,
    amount,
    payment_method_id,
    request,
    create_only: bool = False,
) -> dict:
    """
    Create PaymentJournal + PaymentLine, apply to oldest open invoice, and post.

    When create_only=True (temporary debug), stop after apply/prepare and leave
    the journal Open so the UI can inspect background state.
    """
    if not customer_id:
        raise QuickCustomerPaymentError("customer_id is required")
    if not payment_method_id:
        raise QuickCustomerPaymentError("payment_method_id is required")

    amount_int = _coerce_amount(amount)

    try:
        customer = Customer.objects.get(pk=customer_id)
    except Customer.DoesNotExist as exc:
        raise QuickCustomerPaymentError("Customer not found") from exc

    try:
        payment_method = PaymentMethod.objects.get(pk=payment_method_id)
    except PaymentMethod.DoesNotExist as exc:
        raise QuickCustomerPaymentError("Payment method not found") from exc

    outstanding = _customer_outstanding(customer, request)
    if outstanding <= 0:
        raise QuickCustomerPaymentError(
            "This customer has no open balance to settle."
        )

    invoice = _oldest_open_invoice(customer, request)
    if invoice is None:
        raise QuickCustomerPaymentError(
            "This customer has no open invoices to apply the payment to."
        )

    customer_ct = ContentType.objects.get_for_model(Customer)
    description = f"POS payment — {customer.name} ({customer.no})"

    with transaction.atomic():
        journal = PaymentJournal(
            posting_date=timezone.now().date(),
            document_type=DocumentType.PAYMENT.value,
            account_type=AccountType.CUSTOMER.value,
            account_content_type=customer_ct,
            account_object_id=customer.pk,
            description=description,
            payment_method=payment_method,
            amount=amount_int,
            status=PaymentStatus.OPEN.value,
        )
        journal.save()

        PaymentLine.objects.create(
            payment=journal,
            line_no=10000,
            account_type=AccountType.CUSTOMER.value,
            account_no=customer.no,
            description=description,
            amount=amount_int,
            payment_method=payment_method,
        )
        journal.recalculate_amount()

        set_customer_application(journal, invoice)
        _stamp_applies_to(journal, invoice)

        prepare_payment_journal_for_posting(journal)
        journal.refresh_from_db()
        journal.full_clean()
        journal.clean()
        invoice.refresh_from_db()

        if create_only:
            journal._request_user = getattr(request, "user", None)
            remaining_balance = _customer_outstanding(customer, request)
            return {
                "document_no": journal.document_no,
                "system_id": str(journal.system_id),
                "amount": amount_int,
                "customer_id": customer.pk,
                "customer_no": customer.no,
                "customer_name": customer.name,
                "applied_document_no": invoice.document_no,
                "applied_ledger_id": invoice.id,
                "remaining_balance": remaining_balance,
                "payment_method_id": payment_method.pk,
                "payment_method_code": payment_method.code,
                "posted": False,
                "create_only": True,
                "debug": _journal_debug_snapshot(journal, invoice),
            }

        receipt_no = (
            f"RCP-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
        )
        processor = PaymentJournalPostingProcessor(journal, request, receipt_no)
        result = processor.post()
        if not result.get("success"):
            raise QuickCustomerPaymentError(
                result.get("message", "Unknown error during posting")
            )

        journal.status = PaymentStatus.POSTED.value
        journal.save(update_fields=["status", "updated_at"])
        journal.refresh_from_db()

    remaining_balance = _customer_outstanding(customer, request)

    return {
        "document_no": journal.document_no,
        "system_id": str(journal.system_id),
        "amount": amount_int,
        "customer_id": customer.pk,
        "customer_no": customer.no,
        "customer_name": customer.name,
        "applied_document_no": invoice.document_no,
        "applied_ledger_id": invoice.id,
        "remaining_balance": remaining_balance,
        "payment_method_id": payment_method.pk,
        "payment_method_code": payment_method.code,
        "posted": True,
        "create_only": False,
    }
