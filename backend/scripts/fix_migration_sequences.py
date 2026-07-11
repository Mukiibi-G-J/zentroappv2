"""Fix django_migrations_id_seq and report tenant migration completion."""
import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from django.db import connection
from company.models import Company

EXPECTED_TABLE = "page_engine_page"

fixed = []
for c in Company.objects.all().order_by("schema_name"):
    with connection.cursor() as cur:
        cur.execute(f"SET search_path TO {c.schema_name}")
        cur.execute("SELECT MAX(id) FROM django_migrations")
        max_id = cur.fetchone()[0] or 0
        cur.execute(
            """
            SELECT EXISTS (
                SELECT 1 FROM pg_class WHERE relname = 'django_migrations_id_seq'
            )
            """
        )
        if cur.fetchone()[0]:
            cur.execute("SELECT last_value FROM django_migrations_id_seq")
            seq_val = cur.fetchone()[0]
            if seq_val < max_id:
                cur.execute(
                    "SELECT setval('django_migrations_id_seq', %s, true)",
                    [max_id],
                )
                fixed.append(f"{c.schema_name}: {seq_val} -> {max_id}")
        cur.execute(
            """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = current_schema() AND table_name = %s
            )
            """,
            [EXPECTED_TABLE],
        )
        has_pages = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM django_migrations")
        mig_count = cur.fetchone()[0]
    status = "OK" if has_pages else "PENDING"
    print(f"{c.schema_name:30} migrations={mig_count:4} page_engine={has_pages} {status}")

if fixed:
    print("\nFixed sequences:")
    for line in fixed:
        print(f"  {line}")
else:
    print("\nNo sequence fixes needed.")
