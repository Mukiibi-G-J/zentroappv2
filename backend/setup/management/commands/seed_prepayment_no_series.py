from django.core.management.base import BaseCommand

from setup.models import NoSeries, NoSeriesLines


SERIES_DEFINITIONS = {
    "POSTPREPINV": {
        "description": "Posted Prepayment Invoice",
        "start_number": "POSTPREPINV-000001",
        "increment_by": 1,
    },
    "POSTPREPCM": {
        "description": "Posted Prepayment Credit Memo",
        "start_number": "POSTPREPCM-000001",
        "increment_by": 1,
    },
}


class Command(BaseCommand):
    help = "Ensure the posted prepayment invoice/credit memo number series exist."

    def handle(self, *args, **options):
        created = 0
        updated = 0

        for code, definition in SERIES_DEFINITIONS.items():
            no_series, ns_created = NoSeries.objects.get_or_create(
                code=code, defaults={"description": definition["description"]}
            )
            if ns_created:
                created += 1

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
                continue

            fields_to_update = []

            if not line.start_number:
                line.start_number = definition["start_number"]
                fields_to_update.append("start_number")

            if not line.increment_by:
                line.increment_by = definition["increment_by"]
                fields_to_update.append("increment_by")

            if fields_to_update:
                line.save(update_fields=fields_to_update)
                updated += 1

        summary = (
            f"Prepayment no. series seeded (created: {created}, updated: {updated})."
        )
        self.stdout.write(self.style.SUCCESS(summary))

