"""Golden tenant template schema name and helpers."""

from __future__ import annotations

from django.db import connection

TEMPLATE_SCHEMA_NAME: str = "_zentro_template"


def template_schema_exists() -> bool:
    """Return True if PostgreSQL schema ``_zentro_template`` exists."""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT EXISTS(
                SELECT 1
                FROM information_schema.schemata
                WHERE schema_name = %s
            )
            """,
            [TEMPLATE_SCHEMA_NAME],
        )
        row = cursor.fetchone()
    return bool(row and row[0])
