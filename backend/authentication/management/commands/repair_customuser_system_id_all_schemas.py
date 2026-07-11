"""
Add authentication_customuser.system_id (and unique index) in every PostgreSQL schema
that has that table when migration drift left the column missing.

Production:
  python manage.py repair_customuser_system_id_all_schemas --settings=core.settingsprod

Dry-run:
  python manage.py repair_customuser_system_id_all_schemas --dry-run
"""

from django.core.management.base import BaseCommand
from django.db import connection

LIST_MISSING_SQL = """
SELECT n.nspname
FROM pg_namespace n
JOIN pg_class c ON c.relnamespace = n.oid
WHERE c.relname = 'authentication_customuser'
  AND n.nspname NOT IN ('pg_catalog', 'information_schema')
  AND NOT EXISTS (
    SELECT 1
    FROM pg_attribute a
    WHERE a.attrelid = c.oid
      AND a.attname = 'system_id'
      AND a.attnum > 0
      AND NOT a.attisdropped
  )
ORDER BY n.nspname;
"""

REPAIR_SCHEMA_SQL = """
ALTER TABLE {schema}.authentication_customuser
  ADD COLUMN IF NOT EXISTS system_id varchar(36) NULL;

UPDATE {schema}.authentication_customuser
SET system_id = gen_random_uuid()::text
WHERE system_id IS NULL OR system_id = '';

CREATE UNIQUE INDEX IF NOT EXISTS authentication_customuser_system_id_key
  ON {schema}.authentication_customuser (system_id);
"""


class Command(BaseCommand):
    help = (
        "Repair missing system_id column on authentication_customuser "
        "across all PostgreSQL schemas (public + tenants)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Only list schemas where the column is missing.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        with connection.cursor() as cursor:
            cursor.execute(LIST_MISSING_SQL)
            missing = [row[0] for row in cursor.fetchall()]

        if not missing:
            self.stdout.write(
                self.style.SUCCESS(
                    "All schemas with authentication_customuser already have system_id."
                )
            )
            return

        self.stdout.write(
            self.style.WARNING(
                "Schemas missing system_id: " + ", ".join(missing)
            )
        )
        if dry_run:
            self.stdout.write(self.style.NOTICE("Dry-run: no changes applied."))
            return

        with connection.cursor() as cursor:
            for schema in missing:
                sql = REPAIR_SCHEMA_SQL.format(schema=f'"{schema}"')
                cursor.execute(sql)

        self.stdout.write(self.style.SUCCESS("repair-complete"))

        with connection.cursor() as cursor:
            cursor.execute(LIST_MISSING_SQL)
            still = [row[0] for row in cursor.fetchall()]
        if still:
            self.stdout.write(
                self.style.ERROR(
                    "After repair, these schemas still miss system_id: "
                    + ", ".join(still)
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    "Verified: every schema with authentication_customuser has system_id."
                )
            )
