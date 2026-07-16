"""Reset serial sequences for public + primewise only (fast restore path)."""
import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from django.db import connection
from django_tenants.utils import schema_context

SQL = """
DO $$
DECLARE r RECORD;
BEGIN
  FOR r IN
    SELECT n.nspname AS schema_name,
           c.relname AS seq_name,
           t.relname AS table_name,
           a.attname AS column_name
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    JOIN pg_depend d ON d.objid = c.oid AND d.deptype = 'a'
    JOIN pg_class t ON t.oid = d.refobjid
    JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = d.refobjsubid
    WHERE c.relkind = 'S' AND n.nspname = current_schema()
  LOOP
    EXECUTE format(
      'SELECT setval(%L, COALESCE((SELECT MAX(%I) FROM %I.%I), 1), true)',
      r.schema_name || '.' || r.seq_name,
      r.column_name,
      r.schema_name,
      r.table_name
    );
  END LOOP;
END $$;
"""

for schema in ("public", "primewise"):
    with schema_context(schema):
        with connection.cursor() as c:
            c.execute(SQL)
        print(f"sequences_fixed schema={schema}")

print("done")
