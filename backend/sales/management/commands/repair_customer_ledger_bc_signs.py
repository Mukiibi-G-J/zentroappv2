"""
Repair CLE detailed amounts that used inverted BC signs.

Business Central pattern (customer):
  Invoice Initial Entry:  +amount
  Payment Initial Entry:  -amount
  Application on invoice: -amount
  Application on payment: +amount
  Remaining Amount = Sum(detailed.amount) → 0 when fully applied

Legacy cash sales invoices posted Invoice Initial as -amount. With the cash
Application also -amount, Remaining became -2×amount (e.g. -180,000).

Usage:
  python manage.py tenant_command repair_customer_ledger_bc_signs --schema=YOUR_SCHEMA --dry-run
  python manage.py tenant_command repair_customer_ledger_bc_signs --schema=YOUR_SCHEMA
  python manage.py tenant_command repair_customer_ledger_bc_signs --schema=YOUR_SCHEMA --document-no=SIN-015198
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q, Sum

from common.enums import EntryType
from sales.models import CustomerLedgerEntry, DetailedCustomerLedgerEntry


def _flip_detailed(entry: DetailedCustomerLedgerEntry) -> None:
    amt = int(entry.amount or 0)
    entry.amount = -amt
    debit = int(entry.debit_amount or 0)
    credit = int(entry.credit_amount or 0)
    entry.debit_amount = credit
    entry.credit_amount = debit
    entry.save(
        update_fields=["amount", "debit_amount", "credit_amount", "updated_at"]
    )


def _sync_cle_open_and_header(cle: CustomerLedgerEntry) -> None:
    remaining = cle.remaining_amount
    updates = []
    # Header amount should match Initial Entry sign/magnitude when present.
    initial = (
        DetailedCustomerLedgerEntry.objects.filter(
            customer_ledger_entry=cle,
            entry_type=EntryType.initial.value,
        )
        .order_by("entry_no")
        .first()
    )
    if initial is not None:
        init_amt = int(initial.amount or 0)
        if cle.amount != init_amt:
            cle.amount = init_amt
            updates.append("amount")
        if cle.original_amount != init_amt:
            cle.original_amount = init_amt
            updates.append("original_amount")
    should_open = remaining != 0
    if cle.open != should_open:
        cle.open = should_open
        updates.append("open")
    if updates:
        cle.save(update_fields=[*updates, "updated_at"])


class Command(BaseCommand):
    help = (
        "Repair inverted Customer Ledger detailed entry signs so Remaining "
        "Amount matches Business Central (sum of detailed amounts)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would change without writing",
        )
        parser.add_argument(
            "--document-no",
            type=str,
            default="",
            help="Limit repair to a single document number",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        document_no = (options.get("document_no") or "").strip()

        qs = DetailedCustomerLedgerEntry.objects.all()
        if document_no:
            qs = qs.filter(document_no=document_no)

        # 1) Invoice Initial Entries must be positive receivables.
        bad_invoice_initials = qs.filter(
            entry_type=EntryType.initial.value,
            document_type="Invoice",
            amount__lt=0,
        )

        # 2) Payment Initial Entries must be negative.
        bad_payment_initials = qs.filter(
            entry_type=EntryType.initial.value,
            document_type="Payment",
            amount__gt=0,
        )

        # 3) Application rows on invoice CLEs that increase remaining (wrong +).
        #    Only untouched applications (not unapplied).
        bad_invoice_apps = qs.filter(
            entry_type=EntryType.application.value,
            initial_document_type="Invoice",
            amount__gt=0,
            unapplied=False,
        ).filter(
            Q(customer_ledger_entry__document_type="Invoice")
            | Q(initial_document_type="Invoice")
        )

        # Narrow (3) to apps whose CLE is an Invoice entry.
        bad_invoice_apps = bad_invoice_apps.filter(
            customer_ledger_entry__document_type="Invoice"
        )

        # 4) Application on payment CLE that decreases remaining wrongly (-).
        bad_payment_apps = qs.filter(
            entry_type=EntryType.application.value,
            customer_ledger_entry__document_type="Payment",
            amount__lt=0,
            unapplied=False,
        )

        flip_ids = set(
            list(bad_invoice_initials.values_list("pk", flat=True))
            + list(bad_payment_initials.values_list("pk", flat=True))
            + list(bad_invoice_apps.values_list("pk", flat=True))
            + list(bad_payment_apps.values_list("pk", flat=True))
        )
        to_flip = list(
            DetailedCustomerLedgerEntry.objects.filter(pk__in=flip_ids).order_by(
                "entry_no"
            )
        )

        if not to_flip:
            self.stdout.write(self.style.SUCCESS("No inverted detailed entries found."))
            return

        self.stdout.write(f"Found {len(to_flip)} detailed entr(y/ies) to flip:")
        affected_cle_ids: set[int] = set()
        for row in to_flip:
            cle_id = row.customer_ledger_entry_id
            affected_cle_ids.add(cle_id)
            self.stdout.write(
                f"  Dtld {row.entry_no} CLE {cle_id} {row.entry_type} "
                f"{row.document_type}/{row.document_no} amount {row.amount} -> {-int(row.amount or 0)}"
            )

        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run — no changes written."))
            return

        with transaction.atomic():
            for row in to_flip:
                _flip_detailed(row)
            for cle in CustomerLedgerEntry.objects.filter(id__in=affected_cle_ids):
                _sync_cle_open_and_header(cle)

        # Report remaining after repair
        for cle in CustomerLedgerEntry.objects.filter(id__in=affected_cle_ids):
            total = (
                DetailedCustomerLedgerEntry.objects.filter(customer_ledger_entry=cle)
                .aggregate(t=Sum("amount"))["t"]
                or 0
            )
            self.stdout.write(
                f"CLE {cle.id} {cle.document_type} {cle.document_no}: "
                f"remaining={total} open={cle.open}"
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Repaired {len(to_flip)} detailed entr(y/ies) across "
                f"{len(affected_cle_ids)} customer ledger entr(y/ies)."
            )
        )
