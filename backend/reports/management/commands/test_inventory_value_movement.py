from datetime import date

from django.core.management.base import BaseCommand
from django_tenants.utils import schema_context

from reports.services.inventory_value_movement_service import InventoryValueMovementService


class Command(BaseCommand):
    help = "Debug inventory value movement report generation."

    def add_arguments(self, parser):
        parser.add_argument("--schema", type=str, default="primewise")
        parser.add_argument("--start", type=str, default="2026-05-01")
        parser.add_argument("--end", type=str, default="2026-05-22")

    def handle(self, *args, **options):
        schema = options["schema"]
        start = date.fromisoformat(options["start"])
        end = date.fromisoformat(options["end"])
        self.stdout.write(f"Schema: {schema}")
        with schema_context(schema):
            svc = InventoryValueMovementService()
            try:
                data = svc.generate_report(start, end, period_type="daily", branch=None)
                summary = data.get("summary", {})
                self.stdout.write(
                    self.style.SUCCESS(
                        f"OK closing={summary.get('closing_value')} "
                        f"source={summary.get('valuation_source')}"
                    )
                )
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"FAILED: {type(e).__name__}: {e}"))
                raise
