from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from setup.models import NoSeries, NoSeriesLines, ManufacturingSetup


SERIES_DEFINITIONS = {
    "BOM": {
        "description": "Production BOM",
        "start_number": "BOM-000001",
        "increment_by": 1,
    },
    "PROD": {
        "description": "Production Order",
        "start_number": "PROD-000001",
        "increment_by": 1,
    },
    "WORKCTR": {
        "description": "Work Center",
        "start_number": "WORKCTR-000001",
        "increment_by": 1,
    },
    "MACHCTR": {
        "description": "Machine Center",
        "start_number": "MACHCTR-000001",
        "increment_by": 1,
    },
    "PRODBOM": {
        "description": "Production BOM",
        "start_number": "PRODBOM-000001",
        "increment_by": 1,
    },
    "ROUTING": {
        "description": "Routing",
        "start_number": "ROUTING-000001",
        "increment_by": 1,
    },
}


class Command(BaseCommand):
    help = (
        "Ensure Manufacturing Setup has BOM, Production Order, Work Center, Machine Center, and Routing number series configured and linked.\n"
        "Usage: python manage.py tenant_command seed_production_bom_numbers --schema=<tenant_schema>\n"
        "Example: python manage.py tenant_command seed_production_bom_numbers --schema=ekk"
    )

    @transaction.atomic
    def handle(self, *args, **options):
        series_lines = self._ensure_number_series()
        manufacturing_setup = ManufacturingSetup.objects.first()

        if not manufacturing_setup:
            # Create ManufacturingSetup if it doesn't exist
            manufacturing_setup = ManufacturingSetup.objects.create(
                bom_no_series=series_lines.get("BOM").no_series if series_lines.get("BOM") else None,
                production_order_no_series=(
                    series_lines.get("PROD").no_series
                    if series_lines.get("PROD")
                    else None
                ),
                work_center_no_series=(
                    series_lines.get("WORKCTR").no_series
                    if series_lines.get("WORKCTR")
                    else None
                ),
                machine_center_no_series=(
                    series_lines.get("MACHCTR").no_series
                    if series_lines.get("MACHCTR")
                    else None
                ),
                routing_no_series=(
                    series_lines.get("ROUTING").no_series
                    if series_lines.get("ROUTING")
                    else None
                ),
            )
            self.stdout.write(
                self.style.SUCCESS(
                    "ManufacturingSetup created and linked with number series."
                )
            )
        else:
            updated_fields = []

            if series_lines.get("BOM") and not manufacturing_setup.bom_no_series_id:
                manufacturing_setup.bom_no_series = series_lines["BOM"].no_series
                updated_fields.append("bom_no_series")

            if (
                series_lines.get("PROD")
                and not manufacturing_setup.production_order_no_series_id
            ):
                manufacturing_setup.production_order_no_series = series_lines[
                    "PROD"
                ].no_series
                updated_fields.append("production_order_no_series")

            if (
                series_lines.get("WORKCTR")
                and not manufacturing_setup.work_center_no_series_id
            ):
                manufacturing_setup.work_center_no_series = series_lines[
                    "WORKCTR"
                ].no_series
                updated_fields.append("work_center_no_series")

            if (
                series_lines.get("MACHCTR")
                and not manufacturing_setup.machine_center_no_series_id
            ):
                manufacturing_setup.machine_center_no_series = series_lines[
                    "MACHCTR"
                ].no_series
                updated_fields.append("machine_center_no_series")

            if (
                series_lines.get("ROUTING")
                and not manufacturing_setup.routing_no_series_id
            ):
                manufacturing_setup.routing_no_series = series_lines[
                    "ROUTING"
                ].no_series
                updated_fields.append("routing_no_series")

            if updated_fields:
                manufacturing_setup.save(update_fields=updated_fields)
                self.stdout.write(
                    self.style.SUCCESS("ManufacturingSetup updated with number series.")
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS(
                        "ManufacturingSetup already has number series configured."
                    )
                )

    def _ensure_number_series(self):
        """
        Ensure the required NoSeries/NoSeriesLines exist for BOM and Production Order numbers.
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
