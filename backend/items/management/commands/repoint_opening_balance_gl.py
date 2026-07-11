"""Repoint mis-classified inventory adjustment G/L lines to the Opening Balance account.

Background
----------
In primewise (Mwanjari branch), the bookkeeper posted item journal entries that
were meant to be opening balances but used ``adjustment_type='operational'``.
With ``operational`` the balancing leg goes to ``Inventory Adjmt., Retail``
(``general_posting_setup.inventory_adjustment_account``) instead of the dedicated
Opening Balance account ``9999``.

What this command does
----------------------
For every posted ``ItemJournal`` with:
  * ``global_dimension_1`` = the requested branch (default: ``MWANJARI``),
  * ``adjustment_type='operational'``,
  * (optional) ``date`` between ``--from-date`` and ``--to-date``,
  * (optional) ``document_no`` in ``--document-no``,

it locates the matching ``GeneralLedgerEntry`` rows whose ``gl_account`` is the
operational inventory-adjustment account and whose branch matches, sums the
absolute amounts as a safety check, and (when ``--apply`` is passed) repoints
those G/L rows to account ``9999`` and flips the journals'
``adjustment_type`` to ``opening_balance``.

Usage
-----
Dry run (default) — only prints what would change::

    python manage.py tenant_command repoint_opening_balance_gl \\
        --schema=primewise

Verify the expected total then apply::

    python manage.py tenant_command repoint_opening_balance_gl \\
        --schema=primewise --expected-total=127576 --apply

Override defaults (e.g. another branch or account number)::

    python manage.py tenant_command repoint_opening_balance_gl \\
        --schema=primewise --branch-code=MWANJARI \\
        --to-account=9999 --apply
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Iterable, Optional

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Sum

try:
    from django_tenants.utils import schema_context
except ImportError:  # pragma: no cover - non-tenant fallback
    schema_context = None

from dimension.models import DimensionValue
from financials.models import G_LAccount, GeneralLedgerEntry
from items.models import ItemJournal
from postings.models import GeneralPostingSetup


DEFAULT_BRANCH_CODE = "MWANJARI"
DEFAULT_FROM_ACCOUNT_NAME = "Inventory Adjmt., Retail"
DEFAULT_TO_ACCOUNT_NO = "9999"
DEFAULT_EXPECTED_TOTAL = Decimal("127576")


def _parse_date(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%d").date()


class Command(BaseCommand):
    help = (
        "Repoint posted inventory-adjustment G/L entries (Mwanjari, operational) "
        "to the Opening Balance account and update the originating ItemJournals' "
        "adjustment_type to opening_balance. Defaults to dry-run."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--schema",
            help="Tenant schema name (e.g. 'primewise'). Required when running "
            "via 'manage.py' without 'tenant_command'.",
        )
        parser.add_argument(
            "--branch-code",
            default=DEFAULT_BRANCH_CODE,
            help=f"DimensionValue.code identifying the branch (default: '{DEFAULT_BRANCH_CODE}').",
        )
        parser.add_argument(
            "--from-account",
            help="G/L account no. currently used as balancing account on the affected "
            "entries. Defaults to the account named 'Inventory Adjmt., Retail' "
            "or the first GeneralPostingSetup.inventory_adjustment_account.",
        )
        parser.add_argument(
            "--to-account",
            default=DEFAULT_TO_ACCOUNT_NO,
            help=f"Target Opening Balance G/L account no. (default: '{DEFAULT_TO_ACCOUNT_NO}').",
        )
        parser.add_argument(
            "--from-date",
            help="Only consider ItemJournals with date >= this YYYY-MM-DD.",
        )
        parser.add_argument(
            "--to-date",
            help="Only consider ItemJournals with date <= this YYYY-MM-DD.",
        )
        parser.add_argument(
            "--document-no",
            action="append",
            default=[],
            help="Restrict to specific ItemJournal.document_no values. May be passed multiple times.",
        )
        parser.add_argument(
            "--expected-total",
            default=str(DEFAULT_EXPECTED_TOTAL),
            help=(
                f"Expected absolute sum of the G/L amounts to be repointed "
                f"(default: {DEFAULT_EXPECTED_TOTAL}). The command refuses to "
                "--apply when this does not match unless --force is set."
            ),
        )
        parser.add_argument(
            "--tolerance",
            default="0.01",
            help="Allowed difference between observed and expected totals (default: 0.01).",
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Persist changes. Without this flag the command runs in dry-run mode.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Apply even when the observed total does not match --expected-total.",
        )

    def handle(self, *args, **options):
        schema = options.get("schema")
        if schema and schema_context:
            with schema_context(schema):
                self._run(options)
        else:
            self._run(options)

    def _run(self, options):
        branch_code = options["branch_code"]
        to_account_no = options["to_account"]
        document_nos = options["document_no"]
        apply_changes = options["apply"]
        force = options["force"]

        try:
            expected_total = Decimal(str(options["expected_total"]))
        except Exception as exc:
            raise CommandError(f"Invalid --expected-total: {exc}") from exc
        try:
            tolerance = Decimal(str(options["tolerance"]))
        except Exception as exc:
            raise CommandError(f"Invalid --tolerance: {exc}") from exc

        from_date = _parse_date(options.get("from_date"))
        to_date = _parse_date(options.get("to_date"))

        branch = DimensionValue.objects.filter(code__iexact=branch_code).first()
        if not branch:
            raise CommandError(
                f"DimensionValue with code='{branch_code}' not found. "
                "Pass --branch-code to override."
            )

        from_account = self._resolve_from_account(options.get("from_account"))
        try:
            to_account = G_LAccount.objects.get(no=to_account_no)
        except G_LAccount.DoesNotExist as exc:
            raise CommandError(
                f"Target G/L account no='{to_account_no}' not found."
            ) from exc

        if from_account.no == to_account.no:
            raise CommandError(
                f"--from-account and --to-account are both '{to_account.no}'. Nothing to do."
            )

        journals = ItemJournal.objects.filter(
            global_dimension_1=branch,
            adjustment_type="operational",
            status="Posted",
        )
        if from_date:
            journals = journals.filter(date__gte=from_date)
        if to_date:
            journals = journals.filter(date__lte=to_date)
        if document_nos:
            journals = journals.filter(document_no__in=document_nos)

        journal_doc_nos = list(journals.values_list("document_no", flat=True))
        if not journal_doc_nos:
            self.stdout.write(
                self.style.WARNING(
                    "No matching posted operational ItemJournals on branch "
                    f"'{branch.code}' found."
                )
            )
            return

        gl_qs = GeneralLedgerEntry.objects.filter(
            document_no__in=journal_doc_nos,
            gl_account=from_account,
            global_dimension_1=branch,
            reversed=False,
        )

        agg = gl_qs.aggregate(total_amount=Sum("amount"))
        signed_total = Decimal(str(agg["total_amount"] or 0))
        absolute_total = abs(signed_total)
        gl_count = gl_qs.count()

        self._print_preview(
            branch=branch,
            from_account=from_account,
            to_account=to_account,
            journals=journals,
            gl_qs=gl_qs,
            signed_total=signed_total,
            absolute_total=absolute_total,
            gl_count=gl_count,
            expected_total=expected_total,
            tolerance=tolerance,
        )

        diff = (absolute_total - expected_total).copy_abs()
        totals_match = diff <= tolerance

        if not apply_changes:
            self.stdout.write(
                self.style.NOTICE(
                    "Dry-run: no changes written. Re-run with --apply to persist."
                )
            )
            return

        if not totals_match and not force:
            raise CommandError(
                f"Observed absolute total {absolute_total} does not match "
                f"--expected-total {expected_total} (tolerance {tolerance}). "
                "Narrow the scope (e.g. --from-date/--to-date or --document-no) "
                "or pass --force to override."
            )

        with transaction.atomic():
            gl_updated = gl_qs.update(
                gl_account=to_account,
                balance_account_no=to_account.no,
            )
            journal_updated = journals.update(adjustment_type="opening_balance")

        self.stdout.write(
            self.style.SUCCESS(
                f"Updated {gl_updated} G/L entries → account {to_account.no} "
                f"({to_account.name})."
            )
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Updated {journal_updated} ItemJournals → adjustment_type='opening_balance'."
            )
        )

    def _resolve_from_account(self, override: Optional[str]) -> G_LAccount:
        if override:
            try:
                return G_LAccount.objects.get(no=override)
            except G_LAccount.DoesNotExist as exc:
                raise CommandError(
                    f"--from-account='{override}' not found."
                ) from exc

        account = (
            G_LAccount.objects.filter(name__iexact=DEFAULT_FROM_ACCOUNT_NAME)
            .order_by("no")
            .first()
        )
        if account:
            return account

        setup = (
            GeneralPostingSetup.objects.filter(inventory_adjustment_account__isnull=False)
            .select_related("inventory_adjustment_account")
            .first()
        )
        if setup and setup.inventory_adjustment_account:
            return setup.inventory_adjustment_account

        raise CommandError(
            "Could not resolve the source 'Inventory Adjmt., Retail' account. "
            "Pass --from-account=<no> explicitly."
        )

    def _print_preview(
        self,
        *,
        branch: DimensionValue,
        from_account: G_LAccount,
        to_account: G_LAccount,
        journals,
        gl_qs,
        signed_total: Decimal,
        absolute_total: Decimal,
        gl_count: int,
        expected_total: Decimal,
        tolerance: Decimal,
    ) -> None:
        self.stdout.write(self.style.MIGRATE_HEADING("Repoint Opening Balance G/L"))
        self.stdout.write(f"  Branch:        {branch.code} (id={branch.id})")
        self.stdout.write(
            f"  From account:  {from_account.no} {from_account.name}"
        )
        self.stdout.write(
            f"  To account:    {to_account.no} {to_account.name}"
        )

        journal_count = journals.count()
        self.stdout.write(
            f"  ItemJournals:  {journal_count} posted operational rows"
        )
        self.stdout.write(f"  G/L entries:   {gl_count}")
        self.stdout.write(f"  Signed total:  {signed_total}")
        self.stdout.write(f"  Abs total:     {absolute_total}")
        self.stdout.write(
            f"  Expected:      {expected_total} (tolerance {tolerance})"
        )

        diff = (absolute_total - expected_total).copy_abs()
        if diff <= tolerance:
            self.stdout.write(
                self.style.SUCCESS(f"  ✓ Totals match (diff={diff}).")
            )
        else:
            self.stdout.write(
                self.style.WARNING(f"  ! Totals differ by {diff}.")
            )

        if not gl_count:
            return

        self.stdout.write("")
        self.stdout.write(
            self.style.MIGRATE_LABEL(
                "  Per-document breakdown (document_no, posting_date, amount):"
            )
        )
        rows: Iterable = (
            gl_qs.order_by("posting_date", "document_no")
            .values("document_no", "posting_date", "amount")
        )
        for row in rows:
            self.stdout.write(
                f"    {row['document_no']:<24} {row['posting_date']}  "
                f"{Decimal(str(row['amount'])):>14}"
            )
