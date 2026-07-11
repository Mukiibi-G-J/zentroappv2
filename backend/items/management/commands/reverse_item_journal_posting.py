"""
Dry-run or apply reversal of a posted item journal document.

Usage:
  python manage.py tenant_command reverse_item_journal_posting \\
      --schema=primewise --document-no=ITMJ-003282 --dry-run
  python manage.py tenant_command reverse_item_journal_posting \\
      --schema=primewise --document-no=ITMJ-003282 --apply

Default --apply creates reversing G/L, item ledger, and value entries (not VE-only).
Use --mark-only only to flag rows reversed without posting reversing documents.
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from items.models import ItemJournal
from items.services.item_journal_reversal import ItemJournalPostingReversal

try:
    from django_tenants.utils import schema_context
except ImportError:
    schema_context = None


class Command(BaseCommand):
    help = "Reverse posted G/L, item ledger, and value entries for an item journal document."

    def add_arguments(self, parser):
        parser.add_argument("--schema", type=str, help="Tenant schema name.")
        parser.add_argument(
            "--document-no",
            type=str,
            required=True,
            help="Posted item journal document number (e.g. ITMJ-003282).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show reversal plan without writing (default).",
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            help=(
                "Post full reversal: reversing G/L, item ledger, and value entries "
                "(default; do not use --mark-only unless you only want flags)."
            ),
        )
        parser.add_argument(
            "--user-id",
            type=int,
            default=None,
            help="User id for reversal audit fields (defaults to journal user).",
        )
        parser.add_argument(
            "--reversal-document-no",
            type=str,
            default=None,
            help="Optional reversing document number (default: <doc>-REV).",
        )
        parser.add_argument(
            "--mark-only",
            action="store_true",
            help=(
                "Only mark existing ledger rows reversed (no reversing entries). "
                "Use when reports already exclude reversed rows."
            ),
        )

    def handle(self, *args, **options):
        if options.get("apply") and options.get("dry_run"):
            self.stderr.write(self.style.ERROR("Use either --dry-run or --apply."))
            return
        apply_changes = bool(options.get("apply"))

        def run():
            journal = ItemJournal.objects.filter(
                document_no=options["document_no"]
            ).first()
            if not journal:
                self.stderr.write(
                    self.style.ERROR(
                        f"Item journal {options['document_no']!r} not found."
                    )
                )
                return

            User = get_user_model()
            user = journal.user
            if options.get("user_id"):
                user = User.objects.filter(id=options["user_id"]).first() or user

            reverser = ItemJournalPostingReversal(
                journal=journal,
                user=user,
                reversal_document_no=options.get("reversal_document_no"),
            )
            plan = reverser.dry_run_plan()

            self.stdout.write(
                f"\nJournal id={plan['journal_id']} doc={plan['document_no']!r} "
                f"reversal_doc={plan['reversal_document_no']!r}\n"
            )
            if not plan["can_reverse"]:
                already = (
                    journal.status == "Posted"
                    and not plan["gl_entries"]
                    and not plan["item_ledger_entries"]
                    and not plan["value_entries"]
                )
                if already:
                    self.stdout.write(
                        self.style.SUCCESS(
                            "All ledger rows are reversed and reversing entries already exist. "
                            "Nothing to do."
                        )
                    )
                else:
                    self.stderr.write(
                        self.style.ERROR(
                            "Journal is not Posted or has no unreversed ledger rows."
                        )
                    )
                return

            for row in plan["gl_entries"]:
                self.stdout.write(
                    f"  G/L {row['id']} {row['account']}: {row['amount']} -> {row['reversal_amount']}"
                )
            for row in plan["item_ledger_entries"]:
                self.stdout.write(
                    f"  ILE {row['id']} lot={row['lot_no']!r}: qty {row['quantity']} "
                    f"total {row['total']} -> qty {row['reversal_quantity']}"
                )
            for row in plan["value_entries"]:
                self.stdout.write(
                    f"  VE {row['id']}: qty {row['qty']} cost {row['cost']} -> "
                    f"type {row.get('reversal_entry_type')} "
                    f"qty {row['reversal_qty']} cost {row['reversal_cost']}"
                )
            if plan.get("mode") == "create_reversing_entries":
                self.stdout.write(
                    self.style.NOTICE(
                        "\nFull reversal will post reversing G/L, item ledger, and value entries.\n"
                    )
                )
            for row in plan["fifo_restore"]:
                self.stdout.write(f"  FIFO restore: {row}")

            if not apply_changes:
                self.stdout.write(
                    self.style.WARNING(
                        "\nDry-run only. Re-run with --apply to post reversals.\n"
                    )
                )
                return

            result = reverser.apply(mark_only=bool(options.get("mark_only")))
            self.stdout.write(self.style.SUCCESS("\nReversal applied:"))
            for key, val in result.items():
                self.stdout.write(f"  {key}: {val}")
            if result.get("mode") == "create_reversing_entries":
                if not result.get("created_gl"):
                    self.stdout.write(
                        self.style.NOTICE(
                            "  (G/L reversing entries were already posted — skipped)"
                        )
                    )
                if not result.get("created_item_ledger"):
                    self.stdout.write(
                        self.style.NOTICE(
                            "  (Item ledger reversing entries were already posted — skipped)"
                        )
                    )
                if not result.get("created_value_entries"):
                    self.stdout.write(
                        self.style.NOTICE(
                            "  (Value entry reversing rows were already posted — skipped)"
                        )
                    )
            self.stdout.write("")

        if schema_context and options.get("schema"):
            with schema_context(options["schema"]):
                run()
        else:
            run()
