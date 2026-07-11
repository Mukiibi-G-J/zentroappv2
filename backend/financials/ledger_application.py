"""BC Applies-to ID on customer/vendor ledger entries."""

from __future__ import annotations

from typing import Any, Iterator

from django.db import connections


def set_ledger_applies_to(ledger_entry: Any, target_entry: Any) -> None:
    """Set Applies-to ID to the target entry number (BC field 47, Code[50])."""
    ledger_entry.applies_to_id = str(target_entry.pk)


def clear_ledger_applies_to(ledger_entry: Any) -> None:
    """Clear Applies-to ID."""
    ledger_entry.applies_to_id = ""


def collect_applied_vendor_ledger_entry_ids(
    entry_id: int,
    *,
    using: str = "default",
) -> set[int]:
    """
    Resolve vendor ledger rows shown on BC page 62 Applied Vendor Entries.

    Mirrors FindApplnEntriesDtldtLedgEntry plus applies_to_id links.
    Returns counterpart entries only (excludes the source entry_id).
    """
    from purchases.models import DetailedVendorLedgerEntry, VendorLedger

    linked_ids: set[int] = set()

    linked_ids.update(
        VendorLedger.objects.using(using)
        .filter(applies_to_id=str(entry_id))
        .values_list("id", flat=True)
    )

    applies_to = (
        VendorLedger.objects.using(using)
        .filter(pk=entry_id)
        .values_list("applies_to_id", flat=True)
        .first()
    )
    if applies_to:
        try:
            linked_ids.add(int(applies_to))
        except (TypeError, ValueError):
            pass

    for dtld in DetailedVendorLedgerEntry.objects.using(using).filter(
        vendor_ledger_entry_id=entry_id,
        unapplied=False,
    ):
        if dtld.vendor_ledger_entry_id == dtld.applied_vendor_ledger_entry_no:
            related = DetailedVendorLedgerEntry.objects.using(using).filter(
                applied_vendor_ledger_entry_no=dtld.applied_vendor_ledger_entry_no,
                entry_type="Application",
                unapplied=False,
            )
            for dtld2 in related:
                if dtld2.vendor_ledger_entry_id != dtld2.applied_vendor_ledger_entry_no:
                    linked_ids.add(dtld2.vendor_ledger_entry_id)
        else:
            linked_ids.add(dtld.applied_vendor_ledger_entry_no)

    linked_ids.discard(entry_id)
    return linked_ids


def collect_applied_customer_ledger_entry_ids(
    entry_id: int,
    *,
    using: str = "default",
) -> set[int]:
    """BC Applied Customer Entries — same algorithm as vendor (counterparts only)."""
    from sales.models import CustomerLedgerEntry, DetailedCustomerLedgerEntry

    linked_ids: set[int] = set()

    linked_ids.update(
        CustomerLedgerEntry.objects.using(using)
        .filter(applies_to_id=str(entry_id))
        .values_list("id", flat=True)
    )

    applies_to = (
        CustomerLedgerEntry.objects.using(using)
        .filter(pk=entry_id)
        .values_list("applies_to_id", flat=True)
        .first()
    )
    if applies_to:
        try:
            linked_ids.add(int(applies_to))
        except (TypeError, ValueError):
            pass

    for dtld in DetailedCustomerLedgerEntry.objects.using(using).filter(
        customer_ledger_entry_id=entry_id,
        unapplied=False,
    ):
        if dtld.customer_ledger_entry_id == dtld.applied_customer_ledger_entry_no:
            related = DetailedCustomerLedgerEntry.objects.using(using).filter(
                applied_customer_ledger_entry_no=dtld.applied_customer_ledger_entry_no,
                entry_type="Application",
                unapplied=False,
            )
            for dtld2 in related:
                if (
                    dtld2.customer_ledger_entry_id
                    != dtld2.applied_customer_ledger_entry_no
                ):
                    linked_ids.add(dtld2.customer_ledger_entry_id)
        else:
            linked_ids.add(dtld.applied_customer_ledger_entry_no)

    linked_ids.discard(entry_id)
    return linked_ids


def _table_columns(using: str, table: str) -> set[str]:
    with connections[using].cursor() as cursor:
        cursor.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = current_schema()
              AND table_name = %s
            """,
            [table],
        )
        return {row[0] for row in cursor.fetchall()}


def _vendor_payment_fk_column(using: str) -> str | None:
    cols = _table_columns(using, "purchases_vendorledger")
    if "payment_id" in cols:
        return "payment_id"
    if "applies_to_id_id" in cols:
        return "applies_to_id_id"
    return None


def _iter_legacy_payment_invoice_links(
    using: str,
) -> Iterator[tuple[int, str, int]]:
    """Invoice vendor ledger rows linked to financials.Payment (any FK column name)."""
    fk_col = _vendor_payment_fk_column(using)
    if not fk_col:
        return

    with connections[using].cursor() as cursor:
        cursor.execute(
            f"""
            SELECT vl.id, fp.document_no, vl.vendor_id
            FROM purchases_vendorledger vl
            INNER JOIN financials_payment fp ON vl.{fk_col} = fp.id
            WHERE vl.{fk_col} IS NOT NULL
              AND fp.document_no IS NOT NULL
              AND TRIM(fp.document_no) <> ''
            """
        )
        for invoice_id, document_no, vendor_id in cursor.fetchall():
            yield int(invoice_id), str(document_no), int(vendor_id)


def _ledger_allows_applies_to_stamp(entry) -> bool:
    doc_type = (getattr(entry, "document_type", None) or "").strip()
    return doc_type not in ("Payment", "Refund")


def backfill_vendor_ledger_applies_to_ids(*, using: str = "default") -> int:
    """
    Backfill applies_to_id on invoice/credit vendor ledger rows from legacy links.

    Sources:
    1. Invoice rows still linked via payment FK (financials.Payment)
    2. Payment journal applies_to_object_id (payment document no. as stamp)
    """
    from purchases.models import VendorLedger

    if "applies_to_id" not in _table_columns(using, "purchases_vendorledger"):
        return 0

    updated = 0

    # Legacy invoice→payment FK links: stamp the invoice, not the payment row.
    for invoice_id, payment_document_no, vendor_id in _iter_legacy_payment_invoice_links(
        using
    ):
        invoice_vl = VendorLedger.objects.using(using).filter(pk=invoice_id).first()
        if not invoice_vl or not _ledger_allows_applies_to_stamp(invoice_vl):
            continue
        if not invoice_vl.applies_to_id:
            invoice_vl.applies_to_id = payment_document_no
            invoice_vl.save(update_fields=["applies_to_id", "updated_at"])
            updated += 1

    # Do not backfill applies_to_id onto Payment vendor ledger rows — BC uses invoices only.

    try:
        from payments.models import PaymentJournal
    except ImportError:
        return updated

    for pj in (
        PaymentJournal.objects.using(using)
        .filter(applies_to_object_id__isnull=False)
        .exclude(document_no="")
        .iterator()
    ):
        invoice_vl = VendorLedger.objects.using(using).filter(pk=pj.applies_to_object_id).first()
        if not invoice_vl or not _ledger_allows_applies_to_stamp(invoice_vl):
            continue
        stamp = (pj.document_no or "").strip()
        if stamp and not invoice_vl.applies_to_id:
            invoice_vl.applies_to_id = stamp
            invoice_vl.save(update_fields=["applies_to_id", "updated_at"])
            updated += 1

    return updated


def backfill_customer_ledger_applies_to_ids(*, using: str = "default") -> int:
    """Backfill applies_to_id on invoice customer ledger rows from payment journal links."""
    from sales.models import CustomerLedgerEntry

    if "applies_to_id" not in _table_columns(using, "sales_customerledgerentry"):
        return 0

    updated = 0

    try:
        from payments.models import PaymentJournal
    except ImportError:
        return updated

    for pj in (
        PaymentJournal.objects.using(using)
        .filter(applies_to_object_id__isnull=False)
        .exclude(document_no="")
        .iterator()
    ):
        invoice_cle = (
            CustomerLedgerEntry.objects.using(using)
            .filter(pk=pj.applies_to_object_id)
            .first()
        )
        if not invoice_cle or not _ledger_allows_applies_to_stamp(invoice_cle):
            continue
        stamp = (pj.document_no or "").strip()
        if stamp and not invoice_cle.applies_to_id:
            invoice_cle.applies_to_id = stamp
            invoice_cle.save(update_fields=["applies_to_id", "updated_at"])
            updated += 1

    return updated

