from django.core.management.base import BaseCommand
from django_tenants.utils import schema_context
from sales.models import SalesInvoice
from datetime import date


class Command(BaseCommand):
    help = "Verify sales history for specific dates"

    def add_arguments(self, parser):
        parser.add_argument(
            "--schema",
            type=str,
            default="hardwareworld",
            help="Tenant schema name",
        )
        parser.add_argument(
            "--start-date",
            type=str,
            default="2025-11-03",
            help="Start date in YYYY-MM-DD format",
        )
        parser.add_argument(
            "--end-date",
            type=str,
            default="2025-11-07",
            help="End date in YYYY-MM-DD format",
        )

    def handle(self, *args, **options):
        schema = options.get("schema", "hardwareworld")
        start_date_str = options.get("start_date", "2025-11-03")
        end_date_str = options.get("end_date", "2025-11-07")

        start_date = date.fromisoformat(start_date_str)
        end_date = date.fromisoformat(end_date_str)

        with schema_context(schema):
            self.stdout.write("\n" + "=" * 60)
            self.stdout.write("Sales History Verification")
            self.stdout.write("=" * 60)

            current_date = start_date
            total_count = 0
            total_amount = 0

            while current_date <= end_date:
                invoices = SalesInvoice.objects.filter(
                    posting_date=current_date, status="Posted"
                ).prefetch_related("lines")

                count = invoices.count()
                amount = sum(
                    sum(line.total_amount for line in inv.lines.all())
                    for inv in invoices
                )

                total_count += count
                total_amount += amount

                avg = amount // count if count > 0 else 0
                self.stdout.write(
                    f"{current_date}: {count:2d} sales | Total: {amount:>12,} | Avg: {avg:>8,}"
                )

                current_date = current_date.replace(day=current_date.day + 1) if current_date.day < 28 else current_date.replace(month=current_date.month + 1, day=1)

            self.stdout.write("=" * 60)
            self.stdout.write(
                f"GRAND TOTAL: {total_count} sales | Total Amount: {total_amount:>12,}"
            )
            self.stdout.write("=" * 60)










