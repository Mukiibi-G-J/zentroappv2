from django.core.management.base import BaseCommand
from django.db import connection
from django_tenants.utils import schema_context

from company.models import Company


class Command(BaseCommand):
    help = "List tenant schemas missing reports_reportlog table."

    def handle(self, *args, **options):
        missing = []
        for company in Company.objects.exclude(schema_name="public").order_by("schema_name"):
            with schema_context(company.schema_name):
                with connection.cursor() as cur:
                    cur.execute("SELECT to_regclass('reports_reportlog')")
                    reg = cur.fetchone()[0]
            if not reg:
                missing.append(company.schema_name)
                self.stdout.write(self.style.WARNING(f"{company.schema_name}: MISSING"))
            else:
                self.stdout.write(f"{company.schema_name}: ok")
        if missing:
            self.stdout.write(
                self.style.ERROR(
                    f"\n{len(missing)} schema(s) missing reports_reportlog. "
                    "Run: python manage.py migrate_schemas"
                )
            )
        else:
            self.stdout.write(self.style.SUCCESS("\nAll checked schemas have reports_reportlog."))
