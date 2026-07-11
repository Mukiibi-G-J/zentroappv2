# Generated manually to rename dimension_1_id to global_dimension_1_id (preserves data)

from django.db import migrations


def _pg_column_exists(cursor, relname, attname):
    cursor.execute(
        """
        SELECT 1
        FROM pg_attribute a
        JOIN pg_class c ON a.attrelid = c.oid
        JOIN pg_namespace n ON c.relnamespace = n.oid
        WHERE n.nspname = current_schema()
          AND c.relname = %s
          AND a.attname = %s
          AND a.attnum > 0
          AND NOT a.attisdropped
        """,
        [relname, attname],
    )
    return cursor.fetchone() is not None


def rename_columns(apps, schema_editor):
    """Rename dimension_1_id to global_dimension_1_id for all sales models."""
    if schema_editor.connection.vendor != "postgresql":
        raise NotImplementedError("This migration only supports PostgreSQL")
    tables = [
        "sales_customerledgerentry",
        "sales_detailedcustomerledgerentry",
        "sales_salesinvoiceline",
        "sales_salesorderline",
        "sales_postedsalesinvoiceline",
        "sales_salescreditmemoline",
    ]
    with schema_editor.connection.cursor() as cursor:
        for table in tables:
            has_old = _pg_column_exists(cursor, table, "dimension_1_id")
            has_new = _pg_column_exists(cursor, table, "global_dimension_1_id")
            if has_old and not has_new:
                cursor.execute(
                    f"ALTER TABLE {table} RENAME COLUMN dimension_1_id TO global_dimension_1_id"
                )
            elif has_old and has_new:
                cursor.execute(f"ALTER TABLE {table} DROP COLUMN dimension_1_id CASCADE")


def reverse_rename(apps, schema_editor):
    """Reverse: rename global_dimension_1_id back to dimension_1_id."""
    if schema_editor.connection.vendor != "postgresql":
        raise NotImplementedError("This migration only supports PostgreSQL")
    tables = [
        "sales_customerledgerentry",
        "sales_detailedcustomerledgerentry",
        "sales_salesinvoiceline",
        "sales_salesorderline",
        "sales_postedsalesinvoiceline",
        "sales_salescreditmemoline",
    ]
    with schema_editor.connection.cursor() as cursor:
        for table in tables:
            has_new = _pg_column_exists(cursor, table, "global_dimension_1_id")
            has_old = _pg_column_exists(cursor, table, "dimension_1_id")
            if has_new and not has_old:
                cursor.execute(
                    f"ALTER TABLE {table} RENAME COLUMN global_dimension_1_id TO dimension_1_id"
                )


class Migration(migrations.Migration):

    dependencies = [
        ("sales", "0007_add_dimension_set_to_ledger_models"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RenameField(
                    "customerledgerentry", "dimension_1", "global_dimension_1"
                ),
                migrations.RenameField(
                    "detailedcustomerledgerentry", "dimension_1", "global_dimension_1"
                ),
                migrations.RenameField(
                    "salesinvoiceline", "dimension_1", "global_dimension_1"
                ),
                migrations.RenameField(
                    "salesorderline", "dimension_1", "global_dimension_1"
                ),
                migrations.RenameField(
                    "postedsalesinvoiceline", "dimension_1", "global_dimension_1"
                ),
                migrations.RenameField(
                    "salescreditmemoline", "dimension_1", "global_dimension_1"
                ),
            ],
            database_operations=[
                migrations.RunPython(rename_columns, reverse_rename),
            ],
        ),
    ]
