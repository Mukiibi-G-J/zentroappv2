"""Post General Journal batches using the payment journal posting pipeline."""

from __future__ import annotations

import uuid
from typing import Any

from django.db import transaction
from django.utils import timezone

from financials.models import GeneralJournalLine, G_LAccount
from payments.enums import DocumentType, PaymentStatus


def resolve_journal_account(account_type: str | None, account_no: str | None):
    if not account_type or not account_no:
        return None
    if account_type == "G/L Account":
        return G_LAccount.objects.filter(no=account_no).first()
    if account_type == "Customer":
        from sales.models import Customer

        return Customer.objects.filter(no=account_no).first()
    if account_type == "Vendor":
        from purchases.models import Vendor

        return Vendor.objects.filter(no=account_no).first()
    if account_type == "Bank Account":
        from bank_account.models import BankAccount

        return BankAccount.objects.filter(no=account_no).first()
    return None


class GeneralJournalLinePostingAdapter:
    """Adapt GeneralJournalLine for PaymentJournalProcessor."""

    def __init__(self, line: GeneralJournalLine):
        self._line = line
        self.id = line.pk
        self.document_no = line.document_no
        self.posting_date = line.posting_date
        self.document_type = line.document_type or DocumentType.PAYMENT.value
        self.external_document_no = line.external_document_no
        self.account_type = line.account_type
        self.account_no = resolve_journal_account(line.account_type, line.account_no)
        self.description = line.description
        self.payment_method = line.payment_method
        self.amount = abs(int(line.effective_amount() or 0))
        self.bal_account_type = line.bal_account_type
        self.bal_account_no = resolve_journal_account(line.bal_account_type, line.bal_account_no)
        self.applies_to_object_id = line.applies_to_object_id
        self.dimension_set = None
        self.status = line.status

    def full_clean(self):
        return None

    def clean(self):
        return None


def _open_lines(batch_name: str):
    return (
        GeneralJournalLine.objects.filter(batch_name=batch_name.upper())
        .exclude(status=PaymentStatus.POSTED.value)
        .order_by("line_no")
    )


def _validate_line(line: GeneralJournalLine) -> None:
    if not line.posting_date:
        raise ValueError(f"Line {line.line_no}: posting date is required.")
    if not line.document_no:
        raise ValueError(f"Line {line.line_no}: document number is required.")
    if not line.account_type:
        raise ValueError(f"Line {line.line_no}: account type is required.")
    if not line.account_no:
        raise ValueError(f"Line {line.line_no}: account number is required.")
    if not line.bal_account_type:
        raise ValueError(f"Line {line.line_no}: balancing account type is required.")
    if not line.bal_account_no:
        raise ValueError(f"Line {line.line_no}: balancing account number is required.")
    if not line.effective_amount():
        raise ValueError(f"Line {line.line_no}: amount is required.")
    adapter = GeneralJournalLinePostingAdapter(line)
    if adapter.account_no is None:
        raise ValueError(
            f"Line {line.line_no}: account {line.account_type} {line.account_no} was not found.",
        )
    if adapter.bal_account_no is None:
        raise ValueError(
            f"Line {line.line_no}: balancing account "
            f"{line.bal_account_type} {line.bal_account_no} was not found.",
        )


def batch_balance(lines) -> int:
    return sum(line.effective_amount() for line in lines)


def preview_general_journal_batch(batch_name: str, request) -> dict[str, Any]:
    from payments.admin import PaymentJournalProcessor
    from payments.posting_preview import (
        build_batch_posting_preview_content,
        processor_entries_have_rows,
    )

    lines = list(_open_lines(batch_name))
    if not lines:
        raise ValueError("No open lines in this batch.")

    for line in lines:
        _validate_line(line)

    if not all(line.bal_account_no for line in lines):
        balance = batch_balance(lines)
        if balance != 0:
            raise ValueError(
                f"Journal is not balanced. Total balance is {balance:,.2f}. "
                "Debit and credit amounts must net to zero before posting.",
            )

    processor_results: list[dict] = []
    for line in lines:
        adapter = GeneralJournalLinePostingAdapter(line)
        receipt_no = f"PREVIEW-{uuid.uuid4().hex[:8].upper()}"
        processor = PaymentJournalProcessor(adapter, request, receipt_no)
        entries = processor.process()
        if isinstance(entries, dict) and entries.get("success") is False:
            raise ValueError(entries.get("message", f"Preview failed on line {line.line_no}"))

        if not processor_entries_have_rows(entries):
            raise ValueError(f"Preview returned no entries for line {line.line_no}")

        processor_results.append(entries)

    content = build_batch_posting_preview_content(
        processor_results,
        message=f"Preview posting for batch {batch_name.upper()}",
        batch_name=batch_name.upper(),
    )
    return {"command": "PREVIEW", "content": content}


def post_general_journal_batch(batch_name: str, request) -> dict[str, Any]:
    from payments.admin import PaymentJournalPostingProcessor

    lines = list(_open_lines(batch_name))
    if not lines:
        raise ValueError("No open lines in this batch.")

    for line in lines:
        _validate_line(line)

    if not all(line.bal_account_no for line in lines):
        balance = batch_balance(lines)
        if balance != 0:
            raise ValueError(
                f"Journal is not balanced. Total balance is {balance:,.2f}. "
                "Debit and credit amounts must net to zero before posting.",
            )

    posted_count = 0
    receipt_no = f"GJ-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"

    with transaction.atomic():
        for line in lines:
            adapter = GeneralJournalLinePostingAdapter(line)
            processor = PaymentJournalPostingProcessor(adapter, request, receipt_no)
            result = processor.post()
            if not result.get("success"):
                raise ValueError(
                    result.get("message", f"Posting failed on line {line.line_no}"),
                )
            line.status = PaymentStatus.POSTED.value
            line.save(update_fields=["status", "updated_at"])
            posted_count += 1

    return {
        "command": "REFRESH",
        "content": {
            "Message": f"Posted {posted_count} line(s) from batch {batch_name.upper()}.",
        },
    }
