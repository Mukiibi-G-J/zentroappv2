"""
0008 used current_schema() for information_schema checks; under django-tenants the
active schema may not match, so renames never ran while migration history advanced.

This migration re-applies the same physical renames using connection.schema_name
(and connection.tenant as fallback), with schema-qualified ALTER TABLE on PostgreSQL.
"""

from django.db import migrations


def _resolve_schema(connection):
    s = getattr(connection, "schema_name", None)
    if s:
        return s
    tenant = getattr(connection, "tenant", None)
    if tenant is not None:
        return getattr(tenant, "schema_name", None) or "public"
    return "public"


def _table_exists(cursor, schema: str, table: str) -> bool:
    cursor.execute(
        """
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables t
            WHERE lower(t.table_schema) = lower(%s) AND t.table_name = %s
        );
        """,
        [schema, table],
    )
    return bool(cursor.fetchone()[0])


def _column_exists(cursor, schema: str, table: str, column: str) -> bool:
    cursor.execute(
        """
        SELECT EXISTS (
            SELECT 1 FROM information_schema.columns c
            WHERE lower(c.table_schema) = lower(%s)
              AND c.table_name = %s AND c.column_name = %s
        );
        """,
        [schema, table, column],
    )
    return bool(cursor.fetchone()[0])


def forwards(apps, schema_editor):
    conn = schema_editor.connection
    if conn.vendor != "postgresql":
        return

    schema = _resolve_schema(conn)
    qn = conn.ops.quote_name

    def fq(table: str) -> str:
        return f"{qn(schema)}.{qn(table)}"

    with conn.cursor() as cursor:
        old_menu = "restaurant_management_servicemenu"
        new_menu = "restaurant_management_menu"
        if _table_exists(cursor, schema, old_menu) and not _table_exists(cursor, schema, new_menu):
            cursor.execute(
                f"ALTER TABLE {fq(old_menu)} RENAME TO {qn(new_menu)}"
            )

        old_loc = "restaurant_management_servicemenulocation"
        new_loc = "restaurant_management_menulocation"
        if _table_exists(cursor, schema, old_loc) and not _table_exists(cursor, schema, new_loc):
            cursor.execute(
                f"ALTER TABLE {fq(old_loc)} RENAME TO {qn(new_loc)}"
            )

        mi = "restaurant_management_menuitem"
        if _column_exists(cursor, schema, mi, "service_menu_id") and not _column_exists(
            cursor, schema, mi, "menu_id"
        ):
            cursor.execute(
                f"ALTER TABLE {fq(mi)} RENAME COLUMN {qn('service_menu_id')} TO {qn('menu_id')}"
            )


def backwards_noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("restaurant_management", "0008_bridge_menu_physical_names"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards_noop),
    ]
