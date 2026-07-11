from django.core.management.base import BaseCommand
from django.db import transaction

from setup.models import NoSeries, NoSeriesLines, ManufacturingSetup


SERIES_DEFINITIONS = {
    "PRODBOM": {
        "description": "Production BOM (PRODBOM)",
        "start_number": "PRODBOM-000001",
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
    "ROUTING": {
        "description": "Routing",
        "start_number": "ROUTING-000001",
        "increment_by": 1,
    },
    "RESOURCE": {
        "description": "Resource",
        "start_number": "RES-000001",
        "increment_by": 1,
    },
}


class Command(BaseCommand):
    help = "Seed Manufacturing Setup with all required number series (BOM, Production Order, Work Center, Machine Center, Routing, and Resource)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Clear existing Manufacturing Setup before seeding",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        clear_existing = options.get("clear", False)

        self.stdout.write("=" * 80)
        self.stdout.write(
            self.style.SUCCESS("SEEDING MANUFACTURING SETUP NUMBER SERIES")
        )
        self.stdout.write("=" * 80 + "\n")

        # Clear existing setup if requested
        if clear_existing:
            ManufacturingSetup.objects.all().delete()
            self.stdout.write(
                self.style.WARNING("Cleared existing Manufacturing Setup")
            )

        # Ensure all number series exist
        series_lines = self._ensure_number_series()

        # Get or create ManufacturingSetup
        manufacturing_setup = ManufacturingSetup.objects.first()

        if not manufacturing_setup:
            # Create ManufacturingSetup with all series (excluding Resource, which now uses ResourceSetup)
            manufacturing_setup = ManufacturingSetup.objects.create(
                bom_no_series=series_lines["PRODBOM"].no_series,
                production_order_no_series=series_lines["PROD"].no_series,
                work_center_no_series=series_lines["WORKCTR"].no_series,
                machine_center_no_series=series_lines["MACHCTR"].no_series,
                routing_no_series=series_lines["ROUTING"].no_series,
            )
            self.stdout.write(
                self.style.SUCCESS(
                    "✓ Created ManufacturingSetup and linked all number series"
                )
            )
        else:
            # Update ManufacturingSetup with missing series
            updated_fields = []
            updates_made = False

            # Update BOM series (prefer PRODBOM over BOM if exists)
            if series_lines.get("PRODBOM"):
                if (
                    not manufacturing_setup.bom_no_series_id
                    or manufacturing_setup.bom_no_series.code == "BOM"
                ):
                    manufacturing_setup.bom_no_series = series_lines["PRODBOM"].no_series
                    updated_fields.append("bom_no_series")
                    updates_made = True
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"  ✓ Linked BOM No's.: {series_lines['PRODBOM'].no_series.code}"
                        )
                    )

            # Update Production Order series
            if series_lines.get("PROD"):
                if not manufacturing_setup.production_order_no_series_id:
                    manufacturing_setup.production_order_no_series = (
                        series_lines["PROD"].no_series
                    )
                    updated_fields.append("production_order_no_series")
                    updates_made = True
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"  ✓ Linked Production Order No's.: {series_lines['PROD'].no_series.code}"
                        )
                    )

            # Update Work Center series
            if series_lines.get("WORKCTR"):
                if not manufacturing_setup.work_center_no_series_id:
                    manufacturing_setup.work_center_no_series = (
                        series_lines["WORKCTR"].no_series
                    )
                    updated_fields.append("work_center_no_series")
                    updates_made = True
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"  ✓ Linked Work Center No's.: {series_lines['WORKCTR'].no_series.code}"
                        )
                    )

            # Update Machine Center series
            if series_lines.get("MACHCTR"):
                if not manufacturing_setup.machine_center_no_series_id:
                    manufacturing_setup.machine_center_no_series = (
                        series_lines["MACHCTR"].no_series
                    )
                    updated_fields.append("machine_center_no_series")
                    updates_made = True
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"  ✓ Linked Machine Center No's.: {series_lines['MACHCTR'].no_series.code}"
                        )
                    )

            # Update Routing series
            if series_lines.get("ROUTING"):
                if not manufacturing_setup.routing_no_series_id:
                    manufacturing_setup.routing_no_series = (
                        series_lines["ROUTING"].no_series
                    )
                    updated_fields.append("routing_no_series")
                    updates_made = True
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"  ✓ Linked Routing No's.: {series_lines['ROUTING'].no_series.code}"
                        )
                    )

            if updated_fields:
                manufacturing_setup.save(update_fields=updated_fields)
                self.stdout.write(
                    self.style.SUCCESS(
                        f"\n✓ Updated ManufacturingSetup with {len(updated_fields)} field(s)"
                    )
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS(
                        "\n✓ ManufacturingSetup already has all number series configured"
                    )
                )

        # Display summary
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write(self.style.SUCCESS("MANUFACTURING SETUP SUMMARY"))
        self.stdout.write("=" * 80)
        self.stdout.write(
            f"  BOM No's.: {manufacturing_setup.bom_no_series.code if manufacturing_setup.bom_no_series else 'Not set'}"
        )
        self.stdout.write(
            f"  Production Order No's.: {manufacturing_setup.production_order_no_series.code if manufacturing_setup.production_order_no_series else 'Not set'}"
        )
        self.stdout.write(
            f"  Work Center No's.: {manufacturing_setup.work_center_no_series.code if manufacturing_setup.work_center_no_series else 'Not set'}"
        )
        self.stdout.write(
            f"  Machine Center No's.: {manufacturing_setup.machine_center_no_series.code if manufacturing_setup.machine_center_no_series else 'Not set'}"
        )
        self.stdout.write(
            f"  Routing No's.: {manufacturing_setup.routing_no_series.code if manufacturing_setup.routing_no_series else 'Not set'}"
        )
        self.stdout.write("=" * 80 + "\n")

    def _ensure_number_series(self):
        """
        Ensure all required NoSeries and NoSeriesLines exist.
        Returns a dict of code -> NoSeriesLines instances.
        """
        series_lines = {}
        created_count = 0
        updated_count = 0

        for code, definition in SERIES_DEFINITIONS.items():
            # Create or get NoSeries
            no_series, ns_created = NoSeries.objects.get_or_create(
                code=code, defaults={"description": definition["description"]}
            )

            if ns_created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  ✓ Created NoSeries: {code} - {definition['description']}"
                    )
                )
            else:
                # Update description if it exists but is different
                if no_series.description != definition["description"]:
                    try:
                        no_series.description = definition["description"]
                        no_series.save(update_fields=["description"])
                        updated_count += 1
                        self.stdout.write(
                            self.style.WARNING(
                                f"  ↻ Updated NoSeries description: {code}"
                            )
                        )
                    except Exception as e:
                        # Handle unique constraint violation on description
                        if "description" in str(e).lower() or "unique" in str(e).lower():
                            self.stdout.write(
                                self.style.ERROR(
                                    f"  ✗ Could not update description for {code}: {definition['description']} already exists. "
                                    f"Current description: {no_series.description}"
                                )
                            )
                        else:
                            raise

            # Get or create NoSeriesLines
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
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  ✓ Created NoSeriesLines: {code} - Start: {definition['start_number']}"
                    )
                )
            else:
                fields_to_update = []

                if not line.start_number:
                    line.start_number = definition["start_number"]
                    fields_to_update.append("start_number")

                if not line.increment_by:
                    line.increment_by = definition["increment_by"]
                    fields_to_update.append("increment_by")

                # Update start_number if it's different from definition
                if line.start_number != definition["start_number"]:
                    line.start_number = definition["start_number"]
                    fields_to_update.append("start_number")

                if fields_to_update:
                    line.save(update_fields=fields_to_update)
                    updated_count += 1
                    self.stdout.write(
                        self.style.WARNING(
                            f"  ↻ Updated NoSeriesLines: {code} - Fields: {', '.join(fields_to_update)}"
                        )
                    )

            series_lines[code] = line

        if created_count > 0 or updated_count > 0:
            self.stdout.write(
                self.style.SUCCESS(
                    f"\n  Number Series Summary: {created_count} created, {updated_count} updated"
                )
            )

        return series_lines

