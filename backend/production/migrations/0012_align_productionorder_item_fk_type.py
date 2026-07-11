from django.db import migrations


def _table_exists(cursor, table_name):
    cursor.execute(
        """
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = current_schema()
          AND table_name = %s
        LIMIT 1
        """,
        [table_name],
    )
    return cursor.fetchone() is not None


def _column_type(cursor, table_name, column_name):
    cursor.execute(
        """
        SELECT data_type
        FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name = %s
          AND column_name = %s
        LIMIT 1
        """,
        [table_name, column_name],
    )
    row = cursor.fetchone()
    return row[0] if row else None


def align_productionorder_item_fk_type(apps, schema_editor):
    """
    Repair drifted tenant schemas where production_productionorder.item_id is bigint
    while items.no (Item PK) is varchar.
    """
    with schema_editor.connection.cursor() as cursor:
        if not _table_exists(cursor, "production_productionorder"):
            return

        data_type = _column_type(cursor, "production_productionorder", "item_id")
        if data_type is None or data_type in {"character varying", "text"}:
            return

        if data_type in {"bigint", "integer", "smallint"}:
            cursor.execute(
                """
                ALTER TABLE production_productionorder
                ALTER COLUMN item_id TYPE varchar(225)
                USING item_id::varchar(225)
                """
            )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("production", "0011_remove_productionorderline_dimension_1_and_more"),
    ]

    operations = [
        migrations.RunPython(align_productionorder_item_fk_type, noop_reverse),
    ]

