"""One-off: align public.authentication_* columns when migrations are marked applied but DDL missing."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _apply_settings_module_from_argv() -> None:
    """Honor ``--settings=...`` / ``--settings ...`` like ``manage.py`` (must run before django.setup)."""
    for i, arg in enumerate(sys.argv):
        if arg.startswith("--settings="):
            os.environ["DJANGO_SETTINGS_MODULE"] = arg.partition("=")[2]
            return
        if arg == "--settings" and i + 1 < len(sys.argv):
            os.environ["DJANGO_SETTINGS_MODULE"] = sys.argv[i + 1]
            return


_apply_settings_module_from_argv()

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from django.db import connection
from django_tenants.utils import get_public_schema_name, schema_context


def _qual_table(schema: str, table: str) -> str:
    qn = connection.ops.quote_name
    return f"{qn(schema)}.{qn(table)}"


def _stmts_customuser(schema: str) -> list[str]:
    t = _qual_table(schema, "authentication_customuser")
    return [
        f"""
        ALTER TABLE {t}
        ADD COLUMN IF NOT EXISTS can_switch_branch boolean NOT NULL DEFAULT true;
        """,
        f"""
        ALTER TABLE {t}
        ADD COLUMN IF NOT EXISTS restaurant_pin_hash varchar(128) NULL;
        """,
        f"""
        ALTER TABLE {t}
        ADD COLUMN IF NOT EXISTS restaurant_pin_set_at timestamp with time zone NULL;
        """,
        f"""
        ALTER TABLE {t}
        ADD COLUMN IF NOT EXISTS terminated boolean NOT NULL DEFAULT false;
        """,
    ]


def _stmt_usersetup(schema: str) -> list[str]:
    t = _qual_table(schema, "authentication_usersetup")
    return [
        f"""
        ALTER TABLE {t}
        ADD COLUMN IF NOT EXISTS can_view_only_their_sales boolean NOT NULL DEFAULT true;
        """,
        f"""
        ALTER TABLE {t}
        ADD COLUMN IF NOT EXISTS can_reverse_item_journal boolean NOT NULL DEFAULT false;
        """,
    ]


def _table_exists(cursor, schema: str, table_name: str) -> bool:
    cursor.execute(
        """
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = %s AND table_name = %s
        """,
        [schema, table_name],
    )
    return cursor.fetchone() is not None


def _verify(cursor, schema: str) -> list[str]:
    cursor.execute(
        """
        SELECT column_name FROM information_schema.columns
        WHERE table_schema = %s AND table_name = %s
          AND column_name = ANY(%s)
        ORDER BY column_name
        """,
        [
            schema,
            "authentication_customuser",
            [
                "can_switch_branch",
                "restaurant_pin_hash",
                "restaurant_pin_set_at",
                "terminated",
            ],
        ],
    )
    return [row[0] for row in cursor.fetchall()]


def main():
    pub = get_public_schema_name()
    with schema_context(pub):
        with connection.cursor() as c:
            for sql in _stmts_customuser(pub):
                c.execute(sql)
            if _table_exists(c, pub, "authentication_usersetup"):
                for sql in _stmt_usersetup(pub):
                    c.execute(sql)
            else:
                print(
                    "Skipping usersetup (table missing on public; normal for global admin only)."
                )
            cols = _verify(c, pub)
    print("Applied public authentication column repairs.")
    print(f"Verified authentication_customuser columns on {pub!r}: {cols}")


if __name__ == "__main__":
    main()
