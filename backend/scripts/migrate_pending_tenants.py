"""Migrate pending tenant schemas."""
import os
import subprocess
import sys

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)
os.chdir(BACKEND_DIR)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

import django

django.setup()

from django.db import connection
from company.models import Company

PENDING = []
for c in Company.objects.all().order_by("schema_name"):
    with connection.cursor() as cur:
        cur.execute(f"SET search_path TO {c.schema_name}")
        cur.execute(
            """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = current_schema() AND table_name = 'page_engine_page'
            )
            """
        )
        if not cur.fetchone()[0]:
            PENDING.append(c.schema_name)

print(f"Pending tenants ({len(PENDING)}): {', '.join(PENDING)}")

failed = []
for schema in PENDING:
    print(f"\n=== migrate_schemas --schema={schema} ===", flush=True)
    result = subprocess.run(
        [sys.executable, "manage.py", "migrate_schemas", f"--schema={schema}"],
        cwd=BACKEND_DIR,
    )
    if result.returncode != 0:
        failed.append(schema)
        print(f"FAILED: {schema}", flush=True)

if failed:
    print(f"\nFailed schemas: {failed}")
    sys.exit(1)
print("\nAll pending tenants migrated successfully.")
