"""
Align authentication 0010/0011 on tenant schemas when DB columns exist
but django_migrations rows are missing (avoids DuplicateColumn on migrate).

Run from zentro-backend:
  .venv\\Scripts\\python.exe scripts/align_auth_migrations_tenants.py
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

M10 = "0010_customuser_can_switch_branch"
M11 = "0011_customuser_restaurant_pin_hash"


def migration_applied(schema_name: str, name: str) -> bool:
    with connection.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM django_migrations WHERE app = %s AND name = %s LIMIT 1",
            ["authentication", name],
        )
        return cur.fetchone() is not None


def column_exists(schema_name: str, table: str, column: str) -> bool:
    with connection.cursor() as cur:
        cur.execute(
            """
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = %s AND table_name = %s AND column_name = %s
            LIMIT 1
            """,
            [schema_name, table, column],
        )
        return cur.fetchone() is not None


def main():
    Tenant = get_tenant_model()
    for tenant in Tenant.objects.all().order_by("schema_name"):
        schema = tenant.schema_name
        with schema_context(schema):
            m10 = migration_applied(schema, M10)
            m11 = migration_applied(schema, M11)
            col_branch = column_exists(schema, "authentication_customuser", "can_switch_branch")
            col_pin = column_exists(schema, "authentication_customuser", "restaurant_pin_hash")

            if m10 and m11:
                print(f"[{schema}] already at 0011+")
                continue

            if not m10:
                if col_branch:
                    print(f"[{schema}] faking {M10} (column exists)")
                    call_command(
                        "migrate",
                        "authentication",
                        M10,
                        fake=True,
                        verbosity=0,
                        interactive=False,
                    )
                else:
                    print(f"[{schema}] applying {M10}")
                    call_command(
                        "migrate",
                        "authentication",
                        M10,
                        verbosity=1,
                        interactive=False,
                    )

            if not migration_applied(schema, M11):
                if col_pin:
                    print(f"[{schema}] faking {M11} (column exists)")
                    call_command(
                        "migrate",
                        "authentication",
                        M11,
                        fake=True,
                        verbosity=0,
                        interactive=False,
                    )
                else:
                    print(f"[{schema}] applying {M11}")
                    call_command(
                        "migrate",
                        "authentication",
                        M11,
                        verbosity=1,
                        interactive=False,
                    )

            print(f"[{schema}] done")


if __name__ == "__main__":
    main()
