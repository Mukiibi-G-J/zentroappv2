from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from sales.models import SalesReceivable
from setup.models import NoSeries, NoSeriesLines


SERIES_DEFINITIONS = {
    "SO": {
        "description": "Sales Order",
        "start_number": "SO-000001",
        "increment_by": 1,
    },
}


class Command(BaseCommand):
    help = (
        "Ensure Sales & Receivables setup has sales order number series configured and linked."
    )

    @transaction.atomic
    def handle(self, *args, **options):
        series_lines = self._ensure_number_series()
        sales_setup = SalesReceivable.objects.first()

        if not sales_setup:
            raise CommandError(
                "SalesReceivable configuration not found. "
                "Please create it via the admin before seeding sales order series."
            )

        updated_fields = []

        if not sales_setup.sales_order_no_id:
            sales_setup.sales_order_no = series_lines["SO"]
            updated_fields.append("sales_order_no")

        if updated_fields:
            sales_setup.save(update_fields=updated_fields)
            self.stdout.write(
                self.style.SUCCESS(
                    "SalesReceivable setup updated with sales order number series."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    "SalesReceivable already has sales order number series configured."
                )
            )

    def _ensure_number_series(self):
        """
        Ensure the required NoSeries/NoSeriesLines exist for sales order numbers.
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


