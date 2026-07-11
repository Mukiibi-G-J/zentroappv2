from django.core.management.base import BaseCommand
from django.core.management import call_command
import os


class Command(BaseCommand):
    help = "Load pricing plans data from JSON file"

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            type=str,
            default="data/pricing_plans.json",
            help="Path to the JSON file (default: data/pricing_plans.json)",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Clear existing pricing plans before loading",
        )

    def handle(self, *args, **options):
        file_path = options["file"]
        clear_existing = options["clear"]

        # Check if file exists
        if not os.path.exists(file_path):
            self.stdout.write(self.style.ERROR(f"File {file_path} does not exist"))
            return

        try:
            if clear_existing:
                self.stdout.write("Clearing existing pricing plans...")
                from company.models import Pricing

                Pricing.objects.all().delete()
                self.stdout.write(self.style.SUCCESS("Existing pricing plans cleared"))

            # Load the data
            self.stdout.write(f"Loading pricing plans from {file_path}...")
            call_command("loaddata", file_path, verbosity=0)

            self.stdout.write(self.style.SUCCESS("Pricing plans loaded successfully!"))

            # Display loaded plans
            from company.models import Pricing

            plans = Pricing.objects.all().order_by("order")
            self.stdout.write("\nLoaded plans:")
            for plan in plans:
                self.stdout.write(f"  - {plan.name}: UGX {plan.price:,}/month")

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"Error loading pricing plans: {str(e)}")
            )
