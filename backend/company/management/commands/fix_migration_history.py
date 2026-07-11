"""Fix inconsistent migration history: add missing bank_account.0002_initial record."""
from django.core.management.base import BaseCommand
from django.db import connection
from django.utils import timezone


class Command(BaseCommand):
    help = "Fix migration history: add bank_account.0002_initial if missing (required before financials.0003)"

    def handle(self, *args, **options):
        fixed = 0
        # Get all schemas that have django_migrations table (public + tenant schemas)
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT s.schema_name FROM information_schema.schemata s
                WHERE s.schema_name NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
                AND EXISTS (
                    SELECT 1 FROM information_schema.tables t
                    WHERE t.table_schema = s.schema_name AND t.table_name = 'django_migrations'
                )
            """)
            schemas = [row[0] for row in cursor.fetchall()]

        for schema_name in schemas:
            with connection.cursor() as cursor:
                cursor.execute("SET search_path TO %s", [schema_name])
                cursor.execute(
                    "SELECT id FROM django_migrations WHERE app = %s AND name = %s",
                    ["bank_account", "0002_initial"],
                )
                if cursor.fetchone():
                    continue

                cursor.execute(
                    """
                    INSERT INTO django_migrations (app, name, applied)
                    VALUES (%s, %s, %s)
                    """,
                    ["bank_account", "0002_initial", timezone.now()],
                )
                fixed += 1
                self.stdout.write(f"  Fixed schema: {schema_name}")

        self.stdout.write(
            self.style.SUCCESS(f"Done. Fixed {fixed} schema(s).")
        )
