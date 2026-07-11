"""
Ensure number series SERV-MENU exists for auto-generated Menu.code.

Single tenant:
    python manage.py tenant_command seed_service_menu_no_series --schema=hardwareworld

All tenants:
    python manage.py migrate_schemas --command=seed_service_menu_no_series
"""

from django.core.management.base import BaseCommand

from setup.models import NoSeries, NoSeriesLines

SERIES_CODE = "SERV-MENU"
SERIES_DESCRIPTION = "POS menu codes"
START_NUMBER = "SERV-MENU-000001"


class Command(BaseCommand):
    help = "Ensure NoSeries SERV-MENU exists for POS menu code generation."

    def handle(self, *args, **options):
        created = 0
        updated = 0

        no_series, ns_created = NoSeries.objects.get_or_create(
            code=SERIES_CODE,
            defaults={"description": SERIES_DESCRIPTION},
        )
        if ns_created:
            created += 1
            self.stdout.write(
                self.style.SUCCESS(f"Created NoSeries: {SERIES_CODE}")
            )
        else:
            if no_series.description != SERIES_DESCRIPTION:
                no_series.description = SERIES_DESCRIPTION
                no_series.save(update_fields=["description"])
                updated += 1
                self.stdout.write(
                    self.style.WARNING(f"Updated NoSeries description: {SERIES_CODE}")
                )

        line = (
            NoSeriesLines.objects.filter(no_series=no_series).order_by("id").first()
        )

        if not line:
            NoSeriesLines.objects.create(
                no_series=no_series,
                start_number=START_NUMBER,
                increment_by=1,
            )
            created += 1
            self.stdout.write(
                self.style.SUCCESS(
                    f"Created NoSeriesLines: {SERIES_CODE} - Start: {START_NUMBER}"
                )
            )
        else:
            fields_to_update = []
            if not line.start_number:
                line.start_number = START_NUMBER
                fields_to_update.append("start_number")
            if not line.increment_by:
                line.increment_by = 1
                fields_to_update.append("increment_by")
            if line.start_number != START_NUMBER and not line.last_used_number:
                line.start_number = START_NUMBER
                fields_to_update.append("start_number")
            if fields_to_update:
                line.save(update_fields=fields_to_update)
                updated += 1
                self.stdout.write(
                    self.style.WARNING(
                        f"Updated NoSeriesLines: {SERIES_CODE} - {fields_to_update}"
                    )
                )

        if created or updated:
            self.stdout.write(self.style.SUCCESS(f"\nSummary: {created} created, {updated} updated"))
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    "\nMenu number series is already configured correctly."
                )
            )
