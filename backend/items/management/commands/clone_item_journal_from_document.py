"""
Clone an item journal (open status) from a source document, including tracking specs.

Usage:
  python manage.py tenant_command clone_item_journal_from_document \\
      --schema=primewise --source-document-no=ITMJ-003282
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from items.models import ItemJournal, TrackingSpecification
from items.services.item_journal_reversal import clone_item_journal_from_source

try:
    from django_tenants.utils import schema_context
except ImportError:
    schema_context = None


class Command(BaseCommand):
    help = "Populate a new open item journal from an existing document (same dates and lines)."

    def add_arguments(self, parser):
        parser.add_argument("--schema", type=str, help="Tenant schema name.")
        parser.add_argument(
            "--source-document-no",
            type=str,
            required=True,
            help="Source posted journal document (e.g. ITMJ-003282).",
        )
        parser.add_argument(
            "--user-id",
            type=int,
            default=None,
            help="User for the new journal (defaults to source journal user).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print what would be created without saving.",
        )

    def handle(self, *args, **options):
        def run():
            source = ItemJournal.objects.filter(
                document_no=options["source_document_no"]
            ).first()
            if not source:
                self.stderr.write(
                    self.style.ERROR(
                        f"Source journal {options['source_document_no']!r} not found."
                    )
                )
                return

            User = get_user_model()
            user = source.user
            if options.get("user_id"):
                user = User.objects.filter(id=options["user_id"]).first() or user

            specs = list(
                TrackingSpecification.objects.filter(item_journal=source).order_by("id")
            )
            self.stdout.write(
                f"\nSource journal id={source.id} doc={source.document_no!r}\n"
                f"  date={source.date} item={source.item.no} qty={source.quantity} "
                f"amount={source.amount} entry_type={source.entry_type}\n"
                f"  tracking specs: {len(specs)}\n"
            )
            for spec in specs:
                self.stdout.write(
                    f"    lot={spec.lot_no!r} qty_base={spec.quantity_base} "
                    f"expiry={spec.expiry_date}"
                )

            if options.get("dry_run"):
                self.stdout.write(
                    self.style.WARNING(
                        "\nDry-run: no journal created. Omit --dry-run to clone.\n"
                    )
                )
                return

            clone = clone_item_journal_from_source(source=source, user=user)
            self.stdout.write(
                self.style.SUCCESS(
                    f"\nCreated open journal id={clone.id} document_no={clone.document_no!r} "
                    f"(date={clone.date}). Preview/post from admin when ready.\n"
                )
            )

        if schema_context and options.get("schema"):
            with schema_context(options["schema"]):
                run()
        else:
            run()
