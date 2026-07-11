"""Reset PostgreSQL serial sequences after production DB restore."""
import os
import sys

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)
os.chdir(BACKEND_DIR)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

import django

django.setup()

from django.db import connection
from company.models import Company

FIX_SQL = """
DO $$
DECLARE
    r RECORD;
BEGIN
    FOR r IN (
        SELECT
            n.nspname AS schema_name,
            c.relname AS table_name,
            a.attname AS column_name,
            pg_get_serial_sequence(
                quote_ident(n.nspname) || '.' || quote_ident(c.relname),
                a.attname
            ) AS seq_name
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        JOIN pg_attribute a ON a.attrelid = c.oid
        WHERE n.nspname = current_schema()
          AND c.relkind = 'r'
          AND a.attnum > 0
          AND NOT a.attisdropped
          AND pg_get_serial_sequence(
                quote_ident(n.nspname) || '.' || quote_ident(c.relname),
                a.attname
              ) IS NOT NULL
    ) LOOP
        EXECUTE format(
            'SELECT setval(%L, COALESCE((SELECT MAX(%I) FROM %I.%I), 1), true)',
            r.seq_name, r.column_name, r.schema_name, r.table_name
        );
    END LOOP;
END $$;
"""

schemas = ["public"] + list(
    Company.objects.order_by("schema_name").values_list("schema_name", flat=True)
)

for schema in schemas:
    with connection.cursor() as cur:
        cur.execute(f"SET search_path TO {schema}")
        try:
            cur.execute(FIX_SQL)
            print(f"{schema}: sequences reset OK")
        except Exception as exc:
            print(f"{schema}: ERROR {exc}")
