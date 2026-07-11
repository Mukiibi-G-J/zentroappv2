import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

import django

django.setup()

from django.db import connection
from django_tenants.utils import get_tenant_model

TABLE = "restaurant_management_table"


def has_table(schema: str) -> bool:
    with connection.cursor() as cur:
        cur.execute(
            """
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = %s AND table_name = %s
            LIMIT 1
            """,
            [schema, TABLE],
        )
        return cur.fetchone() is not None


def main():
    for t in get_tenant_model().objects.all().order_by("schema_name"):
        ok = has_table(t.schema_name)
        print(f"{t.schema_name}: {'OK' if ok else 'MISSING'}")


if __name__ == "__main__":
    main()
