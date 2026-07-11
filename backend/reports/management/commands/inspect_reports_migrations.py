from django.core.management.base import BaseCommand
from django.db import connection
from django_tenants.utils import schema_context


class Command(BaseCommand):
    help = "Inspect reports migrations vs tables for one tenant."

    def add_arguments(self, parser):
        parser.add_argument("--schema", type=str, required=True)

    def handle(self, *args, **options):
        schema = options["schema"]
        with schema_context(schema):
            with connection.cursor() as cur:
                cur.execute(
                    "SELECT app, name FROM django_migrations WHERE app = 'reports' ORDER BY id"
                )
                rows = cur.fetchall()
                cur.execute("SELECT to_regclass('reports_reportlog')")
                reg = cur.fetchone()[0]
                cur.execute("SELECT to_regclass('reports_scheduledreport')")
                sched = cur.fetchone()[0]
        self.stdout.write(f"Schema: {schema}")
        self.stdout.write(f"reports_reportlog: {reg}")
        self.stdout.write(f"reports_scheduledreport: {sched}")
        self.stdout.write("django_migrations reports:")
        for app, name in rows:
            self.stdout.write(f"  {app} {name}")
