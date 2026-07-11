"""
Seed pricing plans (app packages) from JSON.
Discovered by Seed Manager via seed_ prefix.
"""
from django.core.management.base import BaseCommand
from django.core.management import call_command
import os


class Command(BaseCommand):
    help = "Seed pricing plans (app packages) from JSON file"

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
            help="Clear existing pricing plans before seeding",
        )

    def handle(self, *args, **options):
        file_path = options["file"]
        clear_existing = options["clear"]

        if not os.path.exists(file_path):
            self.stdout.write(self.style.ERROR(f"File {file_path} does not exist"))
            return

        try:
            if clear_existing:
                self.stdout.write("Clearing existing pricing plans...")
                from company.models import Pricing

                Pricing.objects.all().delete()
                self.stdout.write(self.style.SUCCESS("Existing pricing plans cleared"))

            self.stdout.write(f"Seeding pricing plans from {file_path}...")
            call_command("loaddata", file_path, verbosity=0)
            self.stdout.write(self.style.SUCCESS("Pricing plans seeded successfully!"))

            from company.models import Pricing

            plans = Pricing.objects.all().order_by("order")
            for plan in plans:
                self.stdout.write(f"  - {plan.name}: UGX {plan.price:,}/month")

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error seeding pricing plans: {str(e)}"))
