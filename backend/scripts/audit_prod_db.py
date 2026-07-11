"""Audit public schema and tenant migration gaps."""
import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from django.db import connection

# Public schema checks
with connection.cursor() as cur:
    cur.execute("SET search_path TO public")
    for table in ("company_domain", "company_company", "pages_page", "django_migrations"):
        cur.execute(
            """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = %s
            )
            """,
            [table],
        )
        print(f"public.{table}: {cur.fetchone()[0]}")
    cur.execute("SELECT COUNT(*) FROM django_migrations")
    print(f"public django_migrations count: {cur.fetchone()[0]}")

print()
print("Tenants with broken django_migrations sequence (seq < max_id):")
from company.models import Company

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
        if not cur.fetchone()[0]:
            print(f"  {c.schema_name}: no sequence (max_id={max_id})")
            continue
        cur.execute("SELECT last_value FROM django_migrations_id_seq")
        seq_val = cur.fetchone()[0]
        if seq_val < max_id:
            print(f"  {c.schema_name}: seq={seq_val} max_id={max_id}")
