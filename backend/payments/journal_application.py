"""Resolve applying journal documents for vendor/customer entry application."""

from __future__ import annotations

from django.contrib.contenttypes.models import ContentType

from financials.models import GeneralJournalLine
from payments.models import PaymentJournal

JOURNAL_SOURCE_PAYMENT = "payment_journal"
JOURNAL_SOURCE_GENERAL = "general_journal_line"


class ApplyingDocumentNotFound(Exception):
    pass


def resolve_applying_document(system_id, journal_source: str = JOURNAL_SOURCE_PAYMENT):
    """Load PaymentJournal or GeneralJournalLine by system_id."""
    if journal_source == JOURNAL_SOURCE_GENERAL:
        try:
            return GeneralJournalLine.objects.get(system_id=system_id)
        except GeneralJournalLine.DoesNotExist as exc:
            raise ApplyingDocumentNotFound("General journal line not found") from exc
    try:
        return PaymentJournal.objects.get(system_id=system_id)
    except PaymentJournal.DoesNotExist as exc:
        raise ApplyingDocumentNotFound("Payment journal not found") from exc


def applying_document_no(document) -> str:
    doc_no = (document.document_no or "").strip()
    if not doc_no:
        raise ValueError("Save the document number before setting Applies-to ID.")
    return doc_no


def is_applying_document_posted(document) -> bool:
    return (document.status or "").strip().lower() == "posted"


def clear_application(document, *, linked_ledger_id, applies_to_id: str) -> None:
    from payments.enums import ApplicationStatus

    document.application_status = ApplicationStatus.UNAPPLIED.value
    document.applies_to_doc_type = None
    document.applies_to_content_type = None
    document.applies_to_object_id = None
    document.save(
        update_fields=[
            "application_status",
            "applies_to_doc_type",
            "applies_to_content_type",
            "applies_to_object_id",
            "updated_at",
        ]
    )


def set_vendor_application(document, vendor_ledger) -> None:
    from payments.enums import ApplicationStatus

    vendor_ct = ContentType.objects.get_for_model(vendor_ledger.__class__)
    document.applies_to_content_type = vendor_ct
    document.applies_to_object_id = vendor_ledger.id
    document.applies_to_doc_type = vendor_ledger.document_type
    document.application_status = ApplicationStatus.APPLIED.value
    document.save(
        update_fields=[
            "applies_to_content_type",
            "applies_to_object_id",
            "applies_to_doc_type",
            "application_status",
            "updated_at",
        ]
    )


def set_customer_application(document, customer_ledger) -> None:
    from payments.enums import ApplicationStatus

    customer_ct = ContentType.objects.get_for_model(customer_ledger.__class__)
    document.applies_to_content_type = customer_ct
    document.applies_to_object_id = customer_ledger.id
    document.applies_to_doc_type = customer_ledger.document_type
    document.application_status = ApplicationStatus.APPLIED.value
    document.save(
        update_fields=[
            "applies_to_content_type",
            "applies_to_object_id",
            "applies_to_doc_type",
            "application_status",
            "updated_at",
        ]
    )


# BC: Applies-to ID staging stamps belong on invoices/credits — never on Payment rows.
_APPLIES_TO_STAMP_BLOCKED_DOC_TYPES = frozenset({"Payment", "Refund"})


def ledger_entry_allows_applies_to_stamp(entry) -> bool:
    doc_type = (getattr(entry, "document_type", None) or "").strip()
    return doc_type not in _APPLIES_TO_STAMP_BLOCKED_DOC_TYPES


def applying_party_no(document, party: str) -> str:
    account_type = (getattr(document, "account_type", None) or "").strip()
    if party == "customer":
        if account_type != "Customer":
            return ""
        account_no = getattr(document, "account_no", None)
        if account_no is not None and hasattr(account_no, "no"):
            return str(account_no.no).strip()
        return str(account_no or "").strip()
    if account_type != "Vendor":
        return ""
    account_no = getattr(document, "account_no", None)
    if account_no is not None and hasattr(account_no, "no"):
        return str(account_no.no).strip()
    return str(account_no or "").strip()


def clear_applies_to_stamps_for_document(
    document_no: str,
    *,
    vendor_no: str | None = None,
    customer_no: str | None = None,
    except_ledger_id: int | None = None,
) -> int:
    """Remove temporary Applies-to ID stamps (payment document no.) from open ledger rows."""
    from django.utils import timezone

    stamp = (document_no or "").strip()
    if not stamp:
        return 0

    cleared = 0
    now = timezone.now()

    if vendor_no:
        from purchases.models import VendorLedger

        qs = VendorLedger.objects.filter(
                vendor__no=vendor_no,
                applies_to_id=stamp,
                open=True,
            )
        if except_ledger_id:
            qs = qs.exclude(pk=except_ledger_id)
        cleared += qs.update(applies_to_id="", updated_at=now)

    if customer_no:
        from sales.models import CustomerLedgerEntry

        qs = CustomerLedgerEntry.objects.filter(
            customer__no=customer_no,
            applies_to_id=stamp,
            open=True,
        )
        if except_ledger_id:
            qs = qs.exclude(pk=except_ledger_id)
        cleared += qs.update(applies_to_id="", updated_at=now)

    return cleared


def clear_invalid_payment_ledger_applies_to_ids() -> int:
    """Remove applies_to_id wrongly stored on posted payment ledger rows."""
    from django.utils import timezone

    from purchases.models import VendorLedger
    from sales.models import CustomerLedgerEntry

    now = timezone.now()
    cleared = VendorLedger.objects.filter(document_type="Payment").exclude(
        applies_to_id="",
    ).update(applies_to_id="", updated_at=now)
    cleared += CustomerLedgerEntry.objects.filter(document_type="Payment").exclude(
        applies_to_id="",
    ).update(applies_to_id="", updated_at=now)
    return cleared
