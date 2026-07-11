from django.core.management.base import BaseCommand
from django.db import transaction

from setup.enums import JournalType
from setup.models import JournalSetup, NoSeries, NoSeriesLines


SERIES_CODE = "EXP"
SERIES_DEFINITION = {
    "description": "Expense",
    "start_number": "EXP-000001",
    "increment_by": 1,
}


class Command(BaseCommand):
    help = (
        "Ensure expense number series (EXP) exists and is linked to JournalSetup "
        "for journal_type=expense."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--tenant",
            type=str,
            default=None,
            metavar="SCHEMA",
            help="Tenant schema name (e.g. primewise). If omitted, uses the current schema.",
        )

    def handle(self, *args, **options):
        tenant_schema = options.get("tenant")

        def run_seed():
            with transaction.atomic():
                series_line = self._ensure_number_series()
                setup, created = self._ensure_journal_setup(series_line)
            self.stdout.write(
                self.style.SUCCESS(
                    f"Expense no. series ready: {SERIES_CODE} / {series_line.start_number}. "
                    f"JournalSetup (expense) "
                    f"{'created' if created else 'already linked'}."
                )
            )

        if tenant_schema:
            from django_tenants.utils import schema_context

            with schema_context(tenant_schema):
                self.stdout.write(f"Seeding expense no. series in schema: {tenant_schema}")
                run_seed()
        else:
            run_seed()

    def _ensure_number_series(self):
        no_series, _ = NoSeries.objects.get_or_create(
            code=SERIES_CODE,
            defaults={"description": SERIES_DEFINITION["description"]},
        )
        if no_series.description != SERIES_DEFINITION["description"]:
            no_series.description = SERIES_DEFINITION["description"]
            no_series.save(update_fields=["description"])

        line = NoSeriesLines.objects.filter(no_series=no_series).order_by("id").first()
        if not line:
            line = NoSeriesLines.objects.create(
                no_series=no_series,
                start_number=SERIES_DEFINITION["start_number"],
                increment_by=SERIES_DEFINITION["increment_by"],
            )
        else:
            fields_to_update = []
            if not line.start_number:
                line.start_number = SERIES_DEFINITION["start_number"]
                fields_to_update.append("start_number")
            if not line.increment_by:
                line.increment_by = SERIES_DEFINITION["increment_by"]
                fields_to_update.append("increment_by")
            if fields_to_update:
                line.save(update_fields=fields_to_update)
        return line

    def _ensure_journal_setup(self, expense_series_line):
        setup, created = JournalSetup.objects.get_or_create(
            journal_type=JournalType.EXPENSE.value,
            defaults={"journal_no_series": expense_series_line.no_series},
        )
        if not created and setup.journal_no_series_id != expense_series_line.no_series_id:
            setup.journal_no_series = expense_series_line.no_series
            setup.save(update_fields=["journal_no_series"])
        elif not created and not setup.journal_no_series_id:
            setup.journal_no_series = expense_series_line.no_series
            setup.save(update_fields=["journal_no_series"])
        return setup, created
