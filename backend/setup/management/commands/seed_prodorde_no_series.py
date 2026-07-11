from django.core.management.base import BaseCommand

from setup.models import NoSeries, NoSeriesLines


SERIES_DEFINITIONS = {
    "PRODORDE": {
        "description": "Production Order Item Journal",
        "start_number": "PRODORDE-000001",
        "increment_by": 1,
    },
}


class Command(BaseCommand):
    help = "Ensure the Production Order Item Journal (PRODORDE) number series exists."

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
                    self.style.SUCCESS(f'Created NoSeries: {code} - {definition["description"]}')
                )
            else:
                # Update description if it exists but is different
                if no_series.description != definition["description"]:
                    no_series.description = definition["description"]
                    no_series.save(update_fields=["description"])
                    updated += 1
                    self.stdout.write(
                        self.style.WARNING(f'Updated NoSeries description: {code}')
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

            # Update start_number if it's different from definition
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

        # Link PRODORDE to PROD. ORDE template if it exists
        try:
            from items.models import ItemJournalTemplate
            
            template = ItemJournalTemplate.objects.filter(name="PROD. ORDE").first()
            if template:
                if not template.no_series or template.no_series.code != "PRODORDE":
                    prodorde_series = NoSeries.objects.get(code="PRODORDE")
                    template.no_series = prodorde_series
                    template.save(update_fields=["no_series"])
                    self.stdout.write(
                        self.style.SUCCESS(
                            'Linked PRODORDE no series to "PROD. ORDE" template'
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.SUCCESS(
                            '"PROD. ORDE" template already linked to PRODORDE no series'
                        )
                    )
        except ImportError:
            # Items app might not be available in some contexts
            pass
        except Exception as e:
            self.stdout.write(
                self.style.WARNING(f'Could not link template: {str(e)}')
            )

        summary = f"\nSummary: {created} created, {updated} updated"
        if created > 0 or updated > 0:
            self.stdout.write(self.style.SUCCESS(summary))
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"\nAll PRODORDE number series are already configured correctly."
                )
            )

