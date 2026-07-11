from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from setup.models import NoSeries, NoSeriesLines, JournalSetup
from setup.enums import JournalType


SERIES_DEFINITIONS = {
    "LOAN": {
        "description": "Loan Numbers",
        "start_number": "LOAN-00001",
        "increment_by": 1,
    },
    "LOANREP": {
        "description": "Loan Repayment Numbers",
        "start_number": "LOANREP-00001",
        "increment_by": 1,
    },
}


class Command(BaseCommand):
    help = "Ensure loan number series (LOAN and LOANREP) exist and are linked to JournalSetup."

    @transaction.atomic
    def handle(self, *args, **options):
        series_lines = self._ensure_number_series()
        loan_setup = self._ensure_journal_setup(series_lines["LOAN"])

        self.stdout.write(
            self.style.SUCCESS(
                f"Loan number series ready: LOAN and LOANREP configured. "
                f"JournalSetup {'created' if loan_setup[1] else 'already exists'}."
            )
        )

    def _ensure_number_series(self):
        """
        Ensure the required NoSeries/NoSeriesLines exist for loan numbers.
        Returns a dict of code -> NoSeriesLines instances.
        """
        series_lines = {}

        for code, definition in SERIES_DEFINITIONS.items():
            no_series, _ = NoSeries.objects.get_or_create(
                code=code, defaults={"description": definition["description"]}
            )

            line = (
                NoSeriesLines.objects.filter(no_series=no_series).order_by("id").first()
            )

            if not line:
                line = NoSeriesLines.objects.create(
                    no_series=no_series,
                    start_number=definition["start_number"],
                    increment_by=definition["increment_by"],
                )
            else:
                fields_to_update = []
                if not line.start_number:
                    line.start_number = definition["start_number"]
                    fields_to_update.append("start_number")
                if not line.increment_by:
                    line.increment_by = definition["increment_by"]
                    fields_to_update.append("increment_by")
                if fields_to_update:
                    line.save(update_fields=fields_to_update)

            series_lines[code] = line

        return series_lines

    def _ensure_journal_setup(self, loan_series_line):
        """
        Ensure JournalSetup exists for LOAN journal type.
        Returns tuple (JournalSetup instance, created boolean).
        """
        loan_setup, created = JournalSetup.objects.get_or_create(
            journal_type=JournalType.LOAN.value,
            defaults={"journal_no_series": loan_series_line.no_series},
        )

        # Update if journal_no_series is not set
        if not created and not loan_setup.journal_no_series:
            loan_setup.journal_no_series = loan_series_line.no_series
            loan_setup.save(update_fields=["journal_no_series"])

        return loan_setup, created
