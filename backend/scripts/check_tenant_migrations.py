"""Quick audit: per-tenant migration state and pages table presence."""
import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from django.db import connection
from company.models import Company

for c in Company.objects.all().order_by("schema_name"):
    with connection.cursor() as cur:
        cur.execute(f"SET search_path TO {c.schema_name}")
        cur.execute("SELECT COUNT(*) FROM django_migrations")
        mig_count = cur.fetchone()[0]
        cur.execute(
            """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = current_schema() AND table_name = 'pages_page'
            )
            """
        )
        has_pages = cur.fetchone()[0]
        cur.execute("SELECT MAX(id) FROM django_migrations")
        max_id = cur.fetchone()[0]
        cur.execute(
            """
            SELECT EXISTS (
                SELECT 1 FROM pg_class
                WHERE relname = 'django_migrations_id_seq'
            )
            """
        )
        has_seq = cur.fetchone()[0]
        seq_val = None
        if has_seq:
            cur.execute("SELECT last_value FROM django_migrations_id_seq")
            seq_val = cur.fetchone()[0]
    status = "OK" if has_pages else "PENDING"
    print(
        f"{c.schema_name:30} migrations={mig_count:4} max_id={max_id} "
        f"seq={seq_val} pages={has_pages} {status}"
    )
