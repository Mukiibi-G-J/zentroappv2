"""
Create reports tables on tenant schemas where django_migrations says applied but tables are missing.
"""

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import connection
from django_tenants.utils import schema_context

from company.models import Company


class Command(BaseCommand):
    help = "Re-apply reports migrations on tenants missing reports_reportlog."

    def add_arguments(self, parser):
        parser.add_argument("--schema", type=str, help="Single tenant schema only.")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        schemas = []
        qs = Company.objects.exclude(schema_name="public").order_by("schema_name")
        if options.get("schema"):
            qs = qs.filter(schema_name=options["schema"])

        for company in qs:
            with schema_context(company.schema_name):
                with connection.cursor() as cur:
                    cur.execute("SELECT to_regclass('reports_reportlog')")
                    if not cur.fetchone()[0]:
                        schemas.append(company.schema_name)

        if not schemas:
            self.stdout.write(self.style.SUCCESS("No tenants missing reports_reportlog."))
            return

        self.stdout.write(f"Tenants missing table: {', '.join(schemas)}")
        if options.get("dry_run"):
            return

        for schema in schemas:
            self.stdout.write(f"Fixing reports tables on {schema}...")
            with schema_context(schema):
                with connection.cursor() as cur:
                    cur.execute("DELETE FROM django_migrations WHERE app = %s", ["reports"])
                call_command(
                    "migrate",
                    "reports",
                    verbosity=1,
                    interactive=False,
                )

        self.stdout.write(self.style.SUCCESS("Done. Re-run check_reportlog_table to verify."))
