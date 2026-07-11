import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from django.db import connection
from django_tenants.utils import schema_context

schema = "hotbarmutungo"
with schema_context(schema):
    with connection.cursor() as c:
        c.execute("SELECT COALESCE(MAX(id), 0) FROM django_migrations")
        max_id = c.fetchone()[0]
        c.execute("SELECT pg_get_serial_sequence('django_migrations', 'id')")
        seq = c.fetchone()[0]
        if seq:
            c.execute("SELECT setval(%s, %s)", [seq, max_id])
        c.execute(
            """
            SELECT column_name, data_type, numeric_precision, numeric_scale
            FROM information_schema.columns
            WHERE table_schema = current_schema()
              AND table_name = 'items_itemjournal'
              AND column_name IN ('unit_amount', 'unit_cost', 'amount')
            ORDER BY column_name
            """
        )
        cols = c.fetchall()

print("schema:", schema)
print("max_migration_id:", max_id)
print("sequence:", seq)
print("itemjournal money columns:", cols)
