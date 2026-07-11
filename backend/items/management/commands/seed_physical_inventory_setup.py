from django.core.management.base import BaseCommand
from items.models import ItemJournalTemplate, ItemJournalBatch
from setup.models import NoSeries
from django_tenants.utils import schema_context


class Command(BaseCommand):
    help = "Seed Physical Inventory Journal Template and Default Batch"

    def add_arguments(self, parser):
        parser.add_argument(
            "--tenant",
            type=str,
            help="Tenant schema name (optional, defaults to current schema)",
        )

    def handle(self, *args, **options):
        tenant_schema = options.get("tenant")

        def seed_physical_inventory():
            # Get or create ITEM template and DEFAULT batch
            item_template, created = ItemJournalTemplate.objects.get_or_create(
                name="ITEM",
                defaults={
                    "description": "Item Journal",
                    "type": "item",
                },
            )

            if created:
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Successfully created journal template: "{item_template.name}"'
                    )
                )
            else:
                self.stdout.write(
                    f'Journal template "{item_template.name}" already exists'
                )

            item_batch, created = ItemJournalBatch.objects.get_or_create(
                journal_template=item_template,
                name="DEFAULT",
                defaults={"description": "Default Journal"},
            )

            if created:
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Successfully created journal batch: "{item_batch.name}" for template "{item_template.name}"'
                    )
                )
            else:
                self.stdout.write(
                    f'Journal batch "{item_batch.name}" already exists for template "{item_template.name}"'
                )
            # Get or create PHYS. INV. template
            template, created = ItemJournalTemplate.objects.get_or_create(
                name="PHYS. INV.",
                defaults={
                    "description": "Physical Inventory",
                    "type": "phys_inventory",
                },
            )

            if created:
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Successfully created journal template: "{template.name}"'
                    )
                )
            else:
                self.stdout.write(f'Journal template "{template.name}" already exists')

            # Get or create DEFAULT batch for the template
            batch, created = ItemJournalBatch.objects.get_or_create(
                journal_template=template,
                name="DEFAULT",
                defaults={"description": "Default Journal"},
            )

            if created:
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Successfully created journal batch: "{batch.name}" for template "{template.name}"'
                    )
                )
            else:
                self.stdout.write(
                    f'Journal batch "{batch.name}" already exists for template "{template.name}"'
                )

            # Link PHYSINVJNL number series to template if it exists
            try:
                physinv_series = NoSeries.objects.filter(code="PHYSINVJNL").first()
                if physinv_series:
                    if (
                        not template.no_series
                        or template.no_series.code != "PHYSINVJNL"
                    ):
                        template.no_series = physinv_series
                        template.save(update_fields=["no_series"])
                        self.stdout.write(
                            self.style.SUCCESS(
                                'Linked PHYSINVJNL number series to "PHYS. INV." template'
                            )
                        )
                    else:
                        self.stdout.write(
                            self.style.SUCCESS(
                                '"PHYS. INV." template already linked to PHYSINVJNL number series'
                            )
                        )
                else:
                    self.stdout.write(
                        self.style.WARNING(
                            'PHYSINVJNL number series not found. Please run "seed_no_series_from_json" command first.'
                        )
                    )
            except Exception as e:
                self.stdout.write(
                    self.style.WARNING(f"Could not link number series: {str(e)}")
                )

        if tenant_schema:
            with schema_context(tenant_schema):
                seed_physical_inventory()
        else:
            seed_physical_inventory()

        self.stdout.write(
            self.style.SUCCESS("Physical inventory setup completed successfully!")
        )
