"""
Ensure hotel number series (ROOM-TYPE, ROOM, ROOM-AMENITY) exist for RoomType, Room, and RoomAmenity models.

Run single tenant:
    python manage.py tenant_command seed_hotel_no_series --schema=hardwareworld

Run all tenants:
    python manage.py migrate_schemas --command=seed_hotel_no_series
"""

from django.core.management.base import BaseCommand

from setup.models import NoSeries, NoSeriesLines


SERIES_DEFINITIONS = {
    "ROOM-TYPE": {
        "description": "Room Type",
        "start_number": "RT-000001",
        "increment_by": 1,
    },
    "ROOM": {
        "description": "Room",
        "start_number": "RM-000001",
        "increment_by": 1,
    },
    "ROOM-AMENITY": {
        "description": "Room Amenity",
        "start_number": "AM-000001",
        "increment_by": 1,
    },
}


class Command(BaseCommand):
    help = "Ensure hotel number series (ROOM-TYPE, ROOM, ROOM-AMENITY) exist for RoomType, Room, and RoomAmenity models."

    def handle(self, *args, **options):
        created = 0
        updated = 0

        for code, definition in SERIES_DEFINITIONS.items():
            no_series, ns_created = NoSeries.objects.get_or_create(
                code=code, defaults={"description": definition["description"]}
            )
            if ns_created:
                created += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Created NoSeries: {code} - {definition["description"]}'
                    )
                )
            else:
                if no_series.description != definition["description"]:
                    no_series.description = definition["description"]
                    no_series.save(update_fields=["description"])
                    updated += 1
                    self.stdout.write(
                        self.style.WARNING(f"Updated NoSeries description: {code}")
                    )

            line = (
                NoSeriesLines.objects.filter(no_series=no_series)
                .order_by("id")
                .first()
            )

            if not line:
                NoSeriesLines.objects.create(
                    no_series=no_series,
                    start_number=definition["start_number"],
                    increment_by=definition["increment_by"],
                )
                created += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Created NoSeriesLines: {code} - Start: {definition["start_number"]}'
                    )
                )
                continue

            fields_to_update = []

            if not line.start_number:
                line.start_number = definition["start_number"]
                fields_to_update.append("start_number")

            if not line.increment_by:
                line.increment_by = definition["increment_by"]
                fields_to_update.append("increment_by")

            if line.start_number != definition["start_number"]:
                line.start_number = definition["start_number"]
                fields_to_update.append("start_number")

            if fields_to_update:
                line.save(update_fields=fields_to_update)
                updated += 1
                self.stdout.write(
                    self.style.WARNING(
                        f'Updated NoSeriesLines: {code} - Fields: {", ".join(fields_to_update)}'
                    )
                )

        summary = f"\nSummary: {created} created, {updated} updated"
        if created > 0 or updated > 0:
            self.stdout.write(self.style.SUCCESS(summary))
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    "\nAll hotel number series are already configured correctly."
                )
            )
