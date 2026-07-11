from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from sales.models import SalesReceivable
from setup.models import NoSeries, NoSeriesLines


SERIES_DEFINITIONS = {
    "CM": {
        "description": "Credit Memo",
        "start_number": "CM-000001",
        "increment_by": 1,
    },
    "POSTCM": {
        "description": "Posted Credit Memo",
        "start_number": "POSTCM-000001",
        "increment_by": 1,
    },
}


class Command(BaseCommand):
    help = (
        "Ensure Sales & Receivables setup has credit memo number series configured and linked."
    )

    @transaction.atomic
    def handle(self, *args, **options):
        series_lines = self._ensure_number_series()
        sales_setup = SalesReceivable.objects.first()

        if not sales_setup:
            raise CommandError(
                "SalesReceivable configuration not found. "
                "Please create it via the admin before seeding credit memo series."
            )

        updated_fields = []

        if not sales_setup.credit_memo_no_id:
            sales_setup.credit_memo_no = series_lines["CM"]
            updated_fields.append("credit_memo_no")

        if not sales_setup.posted_credit_memo_no_id:
            sales_setup.posted_credit_memo_no = series_lines["POSTCM"]
            updated_fields.append("posted_credit_memo_no")

        if updated_fields:
            sales_setup.save(update_fields=updated_fields)
            self.stdout.write(
                self.style.SUCCESS(
                    "SalesReceivable setup updated with credit memo number series."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    "SalesReceivable already has credit memo number series configured."
                )
            )

    def _ensure_number_series(self):
        """
        Ensure the required NoSeries/NoSeriesLines exist for credit memo numbers.
        Returns a dict of code -> NoSeriesLines instances.
        """

        series_lines = {}

        for code, definition in SERIES_DEFINITIONS.items():
            no_series, _ = NoSeries.objects.get_or_create(
                code=code, defaults={"description": definition["description"]}
            )

            line = (
                NoSeriesLines.objects.filter(no_series=no_series)
                .order_by("id")
                .first()
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

