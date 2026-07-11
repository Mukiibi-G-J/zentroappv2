"""Final migration audit across all schemas."""
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

rows = []
for c in Company.objects.all().order_by("schema_name"):
    with connection.cursor() as cur:
        cur.execute(f"SET search_path TO {c.schema_name}")
        cur.execute("SELECT COUNT(*) FROM django_migrations")
        mig_count = cur.fetchone()[0]
        cur.execute(
            """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = current_schema() AND table_name = 'page_engine_page'
            )
            """
        )
        has_pages = cur.fetchone()[0]
        cur.execute(
            """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = current_schema() AND table_name = 'sync_syncqueue'
            )
            """
        )
        has_sync = cur.fetchone()[0]
    rows.append((c.schema_name, mig_count, has_pages, has_sync))

max_mig = max(r[1] for r in rows)
print(f"Max migration count: {max_mig}")
print(f"{'schema':30} {'migrations':>10} {'pages':>6} {'sync':>5} {'status':>8}")
print("-" * 65)
for schema, mig, pages, sync in rows:
    behind = mig < max_mig
    status = "BEHIND" if behind else "OK"
    print(f"{schema:30} {mig:10} {str(pages):>6} {str(sync):>5} {status:>8}")

behind = [r[0] for r in rows if r[1] < max_mig]
if behind:
    print(f"\nSchemas behind ({len(behind)}): {', '.join(behind)}")
else:
    print("\nAll tenant schemas at same migration count.")
