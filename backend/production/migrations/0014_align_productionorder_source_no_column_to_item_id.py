from django.db import migrations


def _columns(cursor, table: str) -> set[str]:
    cursor.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name = %s
          AND column_name IN ('source_no_id', 'item_id')
        """,
        [table],
    )
    return {row[0] for row in cursor.fetchall()}


def align_production_order_item_column(apps, schema_editor):
    """
    Tenants where 0008 (RenameField source_no -> item) never updated the database
    still have NOT NULL source_no_id; Django ORM uses item_id. Rename when needed
    and allow NULL for draft orders.
    """
    table = "production_productionorder"
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = current_schema() AND table_name = %s
            LIMIT 1
            """,
            [table],
        )
        if cursor.fetchone() is None:
            return

        cols = _columns(cursor, table)
        if "source_no_id" in cols and "item_id" not in cols:
            cursor.execute(
                f'ALTER TABLE "{table}" RENAME COLUMN source_no_id TO item_id'
            )
            cols.discard("source_no_id")
            cols.add("item_id")

        if "item_id" in cols:
            cursor.execute(
                f'ALTER TABLE "{table}" ALTER COLUMN item_id DROP NOT NULL'
            )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("production", "0013_productionorder_draft_nullable_item"),
    ]

    operations = [
        migrations.RunPython(align_production_order_item_column, noop_reverse),
    ]
