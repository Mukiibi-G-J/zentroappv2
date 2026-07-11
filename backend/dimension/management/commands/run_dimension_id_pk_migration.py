"""
Run dimension 0003 (code PK -> id PK) on all schemas.
Use when the migration was faked and the DB still has code as PK (causes 500 in admin).
"""
import importlib.util
import os

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import connection


def _get_schemas_with_dimension_table(cursor):
    """Return list of schema names that have dimension_dimension table."""
    cursor.execute("""
        SELECT DISTINCT table_schema
        FROM information_schema.tables
        WHERE table_name = 'dimension_dimension'
        AND table_schema NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
    """)
    return [row[0] for row in cursor.fetchall()]


def _schema_already_has_id_pk(cursor):
    """Return True if dimension_dimension already has id as primary key."""
    cursor.execute("""
        SELECT a.attname
        FROM pg_constraint c
        JOIN pg_class t ON c.conrelid = t.oid
        JOIN pg_namespace n ON t.relnamespace = n.oid
        JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = ANY(c.conkey) AND a.attisdropped = false
        WHERE n.nspname = current_schema()
        AND t.relname = 'dimension_dimension'
        AND c.contype = 'p'
    """)
    pk_cols = [row[0] for row in cursor.fetchall()]
    return "id" in pk_cols


class Command(BaseCommand):
    help = "Run dimension code->id PK migration on all schemas (for when migration was faked)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Only print which schemas would be migrated",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        # Load migration function from 0003
        base_dir = getattr(settings, "BASE_DIR", os.getcwd())
        path = os.path.join(base_dir, "dimension", "migrations", "0003_dimension_id_pk.py")
        if not os.path.exists(path):
            self.stdout.write(self.style.ERROR(f"Migration file not found: {path}"))
            return

        spec = importlib.util.spec_from_file_location("dimension_0003", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        migrate_fn = mod.migrate_dimension_pk_to_id

        with connection.cursor() as cursor:
            schemas = _get_schemas_with_dimension_table(cursor)

        if not schemas:
            self.stdout.write(self.style.WARNING("No schemas with dimension_dimension table found."))
            return

        self.stdout.write(f"Found {len(schemas)} schema(s) with dimension tables.")

        for schema_name in schemas:
            with connection.cursor() as cursor:
                cursor.execute("SET search_path TO %s", [schema_name])
                if _schema_already_has_id_pk(cursor):
                    self.stdout.write(f"  [SKIP] {schema_name}: already has id as PK")
                    continue

            if dry_run:
                self.stdout.write(f"  [WOULD RUN] {schema_name}")
                continue

            try:
                with connection.cursor() as cursor:
                    cursor.execute("SET search_path TO %s", [schema_name])
                migrate_fn(None, None)
                self.stdout.write(self.style.SUCCESS(f"  [OK] {schema_name}"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  [FAIL] {schema_name}: {e}"))

        if not dry_run:
            self.stdout.write(self.style.SUCCESS("\nDone. Reload Django admin and try again."))
