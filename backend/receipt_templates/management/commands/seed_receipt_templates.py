from django.core.management.base import BaseCommand
from django_tenants.utils import schema_context

from receipt_templates.seed import seed_receipt_templates


class Command(BaseCommand):
    help = "Seed system receipt templates and default assignments for a tenant schema"

    def add_arguments(self, parser):
        parser.add_argument(
            "--tenant",
            type=str,
            help="Tenant schema name (required unless --all-tenants)",
        )
        parser.add_argument(
            "--all-tenants",
            action="store_true",
            help="Seed every tenant schema (excludes public)",
        )
        parser.add_argument(
            "--clear-assignments",
            action="store_true",
            help="Remove non-branch-specific assignments before re-seeding",
        )

    def handle(self, *args, **options):
        if options["all_tenants"]:
            from company.models import Company

            for company in Company.objects.exclude(schema_name="public"):
                self._seed_schema(company.schema_name, options)
            return

        schema = options.get("tenant")
        if not schema:
            self.stderr.write(self.style.ERROR("Provide --tenant or --all-tenants"))
            return
        self._seed_schema(schema, options)

    def _seed_schema(self, schema_name: str, options):
        self.stdout.write(f"Seeding receipt templates for schema: {schema_name}")
        with schema_context(schema_name):
            seed_receipt_templates(
                self.stdout,
                self.style,
                clear_assignments=options.get("clear_assignments", False),
            )
