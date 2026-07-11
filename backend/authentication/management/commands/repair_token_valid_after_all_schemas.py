"""
Add authentication_customuser.token_valid_after (and index) in every PostgreSQL schema
that has that table, when migration drift left the column missing.

Same logic as docs/general/TOKEN_VALID_AFTER_PRODUCTION_RUNBOOK.md — use this instead of
a fragile shell one-liner.

Production:
  python manage.py repair_token_valid_after_all_schemas --settings=core.settingsprod

Dry-run (list schemas missing the column):
  python manage.py repair_token_valid_after_all_schemas --settings=core.settingsprod --dry-run
"""

from django.core.management.base import BaseCommand
from django.db import connection


REPAIR_SQL = """
DO $$
DECLARE
  r record;
BEGIN
  FOR r IN
    SELECT n.nspname AS schema_name
    FROM pg_namespace n
    JOIN pg_class c ON c.relnamespace = n.oid
    WHERE c.relname = 'authentication_customuser'
      AND n.nspname NOT IN ('pg_catalog', 'information_schema')
  LOOP
    EXECUTE format(
      'ALTER TABLE %I.authentication_customuser '
      'ADD COLUMN IF NOT EXISTS token_valid_after timestamptz NULL',
      r.schema_name
    );
    EXECUTE format(
      'CREATE INDEX IF NOT EXISTS %I ON %I.authentication_customuser (token_valid_after)',
      'authentication_customuser_token_valid_after',
      r.schema_name
    );
  END LOOP;
END $$;
"""

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
      AND a.attname = 'token_valid_after'
      AND a.attnum > 0
      AND NOT a.attisdropped
  )
ORDER BY n.nspname;
"""


class Command(BaseCommand):
    help = (
        "Repair missing token_valid_after column on authentication_customuser "
        "across all PostgreSQL schemas (public + tenants)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Only list schemas where the column is missing; do not change the database.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        with connection.cursor() as cursor:
            cursor.execute(LIST_MISSING_SQL)
            missing = [row[0] for row in cursor.fetchall()]

        if not missing:
            self.stdout.write(
                self.style.SUCCESS(
                    "All schemas with authentication_customuser already have token_valid_after."
                )
            )
            return

        self.stdout.write(
            self.style.WARNING(
                "Schemas missing token_valid_after: " + ", ".join(missing)
            )
        )
        if dry_run:
            self.stdout.write(self.style.NOTICE("Dry-run: no changes applied."))
            return

        with connection.cursor() as cursor:
            cursor.execute(REPAIR_SQL)
        self.stdout.write(self.style.SUCCESS("repair-complete"))

        with connection.cursor() as cursor:
            cursor.execute(LIST_MISSING_SQL)
            still = [row[0] for row in cursor.fetchall()]
        if still:
            self.stdout.write(
                self.style.ERROR(
                    "After repair, these schemas still miss the column: "
                    + ", ".join(still)
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    "Verified: every schema with authentication_customuser has token_valid_after."
                )
            )
