"""Repair authentication_usersetup columns on tenant schemas when migration is recorded but DDL missing."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

import django

django.setup()

from company.models import Company
from django.db import connection
from django_tenants.utils import schema_context

USERS_SETUP_COLS = [
    "can_view_only_their_sales boolean NOT NULL DEFAULT true",
    "can_reverse_item_journal boolean NOT NULL DEFAULT false",
]


def repair_schema(schema: str) -> bool:
    with schema_context(schema):
        with connection.cursor() as c:
            c.execute(
                """
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = current_schema()
                  AND table_name = 'authentication_usersetup'
                """
            )
            if not c.fetchone():
                return False
            for col_def in USERS_SETUP_COLS:
                col_name = col_def.split()[0]
                c.execute(
                    """
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = current_schema()
                      AND table_name = 'authentication_usersetup'
                      AND column_name = %s
                    """,
                    [col_name],
                )
                if c.fetchone():
                    continue
                c.execute(
                    f"ALTER TABLE authentication_usersetup ADD COLUMN IF NOT EXISTS {col_def}"
                )
                print(f"  added {col_name}")
            return True


def main():
    schemas = list(
        Company.objects.exclude(schema_name="public").values_list("schema_name", flat=True)
    )
    for schema in schemas:
        print(f"repair {schema}...")
        if repair_schema(schema):
            print(f"  ok")
        else:
            print(f"  skip (no usersetup table)")


if __name__ == "__main__":
    main()
