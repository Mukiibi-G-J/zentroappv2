"""
Backfill ItemLedgerEntries.posting_date when null.

Legacy item-journal posting wrote ``date`` but omitted ``posting_date``, so the
Item Ledger Entries list shows "—" for Posting Date.

Usage:
  python manage.py tenant_command backfill_item_ledger_posting_dates --schema=primewise
  python manage.py tenant_command backfill_item_ledger_posting_dates --schema=primewise --dry-run
"""

from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction

from financials.models import GeneralLedgerEntry
from items.models import ItemLedgerEntries, ValueEntry


def resolve_posting_date(ile: ItemLedgerEntries):
    if ile.date is not None:
        return ile.date, "date"

    ve = (
        ValueEntry.objects.filter(item_ledger_entry_no=ile.pk)
        .exclude(posting_date__isnull=True)
        .order_by("id")
        .first()
    )
    if ve and ve.posting_date is not None:
        return ve.posting_date, "value_entry"

    if ile.document_no:
        gl = (
            GeneralLedgerEntry.objects.filter(document_no=ile.document_no)
            .exclude(posting_date__isnull=True)
            .order_by("id")
            .first()
        )
        if gl and gl.posting_date is not None:
            return gl.posting_date, "general_ledger"

    if ile.created_at is not None:
        return ile.created_at.date(), "created_at"

    return None, None


class Command(BaseCommand):
    help = (
        "Backfill null ItemLedgerEntries.posting_date from date / ValueEntry / "
        "G/L / created_at so the Item Ledger Entries list shows Posting Date."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report how many rows would be updated without writing.",
        )
        parser.add_argument(
            "--document-prefix",
            default="",
            help="Optional document_no prefix filter (e.g. ITMJ).",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        prefix = (options.get("document_prefix") or "").strip()

        qs = ItemLedgerEntries.objects.filter(posting_date__isnull=True).order_by("id")
        if prefix:
            qs = qs.filter(document_no__startswith=prefix)

        total = qs.count()
        if total == 0:
            self.stdout.write(self.style.SUCCESS("No Item Ledger Entries with null posting_date."))
            return

        updated = 0
        skipped = 0
        sources = {}

        with transaction.atomic():
            for ile in qs.iterator(chunk_size=500):
                resolved, source = resolve_posting_date(ile)
                if resolved is None:
                    skipped += 1
                    continue
                sources[source] = sources.get(source, 0) + 1
                if not dry_run:
                    ItemLedgerEntries.objects.filter(pk=ile.pk).update(
                        posting_date=resolved
                    )
                updated += 1

            if dry_run:
                transaction.set_rollback(True)

        verb = "Would update" if dry_run else "Updated"
        self.stdout.write(
            self.style.SUCCESS(
                f"{verb} {updated} of {total} null posting_date row(s); "
                f"skipped={skipped}; sources={sources}"
            )
        )
