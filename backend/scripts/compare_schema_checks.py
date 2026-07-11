"""Compare critical V2 schema objects between primewise (reference) and other tenants."""
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

CHECKS = [
    ("table", "page_engine_page"),
    ("table", "sync_device"),
    ("table", "authentication_devicepushtoken"),
    ("table", "financials_generaljournal"),
    ("column", "authentication_customuser", "system_id"),
    ("column", "authentication_customuser", "token_valid_after"),
    ("column", "purchases_vendorledger", "applies_to_id"),
    ("column", "sales_customerledgerentry", "applies_to_id"),
]

REF = "primewise"


def exists_table(schema: str, table: str) -> bool:
    with connection.cursor() as cur:
        cur.execute(
            """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = %s AND table_name = %s
            )
            """,
            [schema, table],
        )
        return cur.fetchone()[0]


def exists_column(schema: str, table: str, column: str) -> bool:
    with connection.cursor() as cur:
        cur.execute(
            """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = %s AND table_name = %s AND column_name = %s
            )
            """,
            [schema, table, column],
        )
        return cur.fetchone()[0]


ref_state = {}
for kind, *rest in CHECKS:
    if kind == "table":
        ref_state[("table", rest[0])] = exists_table(REF, rest[0])
    else:
        ref_state[("column", rest[0], rest[1])] = exists_column(REF, rest[0], rest[1])

print(f"Reference schema: {REF}")
for key, val in ref_state.items():
    print(f"  {key}: {val}")

print()
issues = []
for c in Company.objects.exclude(schema_name=REF).order_by("schema_name"):
    missing = []
    for check in CHECKS:
        kind = check[0]
        if kind == "table":
            key = ("table", check[1])
            ok = exists_table(c.schema_name, check[1])
        else:
            key = ("column", check[1], check[2])
            ok = exists_column(c.schema_name, check[1], check[2])
        if ref_state[key] and not ok:
            missing.append(f"{check[1]}" + (f".{check[2]}" if kind == "column" else ""))
    if missing:
        issues.append((c.schema_name, missing))
        print(f"{c.schema_name}: MISSING {', '.join(missing)}")

if not issues:
    print("All tenants match primewise on critical V2 schema checks.")
else:
    print(f"\n{len(issues)} tenant(s) with schema gaps.")
