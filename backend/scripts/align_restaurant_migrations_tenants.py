"""
Repair tenant schemas where restaurant_management tables are missing or only
partially created (django migration drift / failed RunPython).

Also relies on 0001_initial RunPython using historical models (apps.get_model),
not live imports — see migration 0001 fix.

Run from zentro-backend:
  .venv\\Scripts\\python.exe scripts/align_restaurant_migrations_tenants.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

import django

django.setup()

from django.core.management import call_command
from django.db import connection
from django_tenants.utils import get_tenant_model, schema_context

# Tables created by 0001_initial (Django default names)
REQUIRED_0001 = frozenset(
    {
        "restaurant_management_floor",
        "restaurant_management_menucategory",
        "restaurant_management_table",
        "restaurant_management_menuitem",
        "restaurant_management_reservation",
        "restaurant_management_restaurantorder",
        "restaurant_management_restaurantorderitem",
    }
)


def restaurant_table_names(schema_name: str) -> set[str]:
    with connection.cursor() as cur:
        cur.execute(
            """
            SELECT tablename FROM pg_tables
            WHERE schemaname = %s AND tablename LIKE 'restaurant_management_%%'
            """,
            [schema_name],
        )
        return {row[0] for row in cur.fetchall()}


def drop_restaurant_tables(schema_name: str) -> None:
    names = sorted(restaurant_table_names(schema_name))
    if not names:
        return
    with schema_context(schema_name):
        with connection.cursor() as cur:
            for t in names:
                cur.execute(
                    'DROP TABLE IF EXISTS "%s"."%s" CASCADE' % (schema_name, t)
                )


def clear_restaurant_migration_rows_in_schema(schema: str) -> None:
    with schema_context(schema):
        with connection.cursor() as cur:
            cur.execute("DELETE FROM django_migrations WHERE app = %s", ["restaurant_management"])


def main():
    Tenant = get_tenant_model()
    for tenant in Tenant.objects.all().order_by("schema_name"):
        schema = tenant.schema_name
        have = restaurant_table_names(schema)
        if have and REQUIRED_0001.issubset(have):
            print(f"[{schema}] restaurant 0001 tables OK — skipping repair")
            continue
        if have:
            print(f"[{schema}] partial or empty restaurant tables {sorted(have)} — resetting…")
        else:
            print(f"[{schema}] no restaurant tables — creating from migrations…")
        drop_restaurant_tables(schema)
        clear_restaurant_migration_rows_in_schema(schema)
        call_command(
            "migrate_schemas",
            "-s",
            schema,
            "--tenant",
            "restaurant_management",
            verbosity=1,
            interactive=False,
        )
        print(f"[{schema}] done")


if __name__ == "__main__":
    main()
