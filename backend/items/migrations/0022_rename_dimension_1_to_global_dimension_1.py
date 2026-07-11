# Generated manually to rename dimension_1_id to global_dimension_1_id (preserves data)

from django.db import migrations


def _column_exists(cursor, table_name, column_name):
    """Check if column exists in current schema (for tenant-aware DB)."""
    cursor.execute(
        """
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = current_schema()
        AND LOWER(table_name) = LOWER(%s) AND column_name = %s
        """,
        [table_name, column_name],
    )
    return cursor.fetchone() is not None


def rename_columns(apps, schema_editor):
    """Rename dimension_1_id to global_dimension_1_id for items ValueEntry and ItemLedgerEntries."""
    if schema_editor.connection.vendor != "postgresql":
        raise NotImplementedError("This migration only supports PostgreSQL")
    with schema_editor.connection.cursor() as cursor:
        # items_valueentry - Django default table name
        # "Item Ledger Entries" - db_table with spaces
        tables = [
            ("items_valueentry", "items_valueentry"),
            ('"Item Ledger Entries"', "Item Ledger Entries"),
        ]
        for table_ref, table_lookup in tables:
            has_old = _column_exists(cursor, table_lookup, "dimension_1_id")
            has_new = _column_exists(cursor, table_lookup, "global_dimension_1_id")
            if has_old and not has_new:
                cursor.execute(
                    f'ALTER TABLE {table_ref} RENAME COLUMN "dimension_1_id" TO "global_dimension_1_id";'
                )


def reverse_rename(apps, schema_editor):
    """Reverse: rename global_dimension_1_id back to dimension_1_id."""
    if schema_editor.connection.vendor != "postgresql":
        raise NotImplementedError("This migration only supports PostgreSQL")
    with schema_editor.connection.cursor() as cursor:
        tables = [
            ("items_valueentry", "items_valueentry"),
            ('"Item Ledger Entries"', "Item Ledger Entries"),
        ]
        for table_ref, table_lookup in tables:
            has_new = _column_exists(cursor, table_lookup, "global_dimension_1_id")
            has_old = _column_exists(cursor, table_lookup, "dimension_1_id")
            if has_new and not has_old:
                cursor.execute(
                    f'ALTER TABLE {table_ref} RENAME COLUMN "global_dimension_1_id" TO "dimension_1_id";'
                )


class Migration(migrations.Migration):

    dependencies = [
        ("items", "0021_add_dimension_set_to_ledger_models"),
    ]

    operations = [
        migrations.RunPython(rename_columns, reverse_rename),
    ]
