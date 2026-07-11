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


def drop_legacy_source_no_column(apps, schema_editor):
    """
    Some tenants have BOTH source_no_id (NOT NULL, legacy) and item_id (ORM).
    Django only writes item_id; Postgres then rejects the row because source_no_id
    stays NULL. Drop the obsolete column when both exist; otherwise align like 0014.
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

        if "source_no_id" in cols and "item_id" in cols:
            cursor.execute(
                f'ALTER TABLE "{table}" DROP COLUMN source_no_id CASCADE'
            )
        elif "source_no_id" in cols and "item_id" not in cols:
            cursor.execute(
                f'ALTER TABLE "{table}" RENAME COLUMN source_no_id TO item_id'
            )

        cols = _columns(cursor, table)
        if "item_id" in cols:
            cursor.execute(
                f'ALTER TABLE "{table}" ALTER COLUMN item_id DROP NOT NULL'
            )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("production", "0014_align_productionorder_source_no_column_to_item_id"),
    ]

    operations = [
        migrations.RunPython(drop_legacy_source_no_column, noop_reverse),
    ]
