from django.db import migrations


def _table_exists(schema_editor, table_name: str) -> bool:
    connection = schema_editor.connection
    with connection.cursor() as cursor:
        if connection.vendor == "postgresql":
            cursor.execute(
                """
                SELECT 1
                FROM pg_catalog.pg_tables
                WHERE schemaname = current_schema()
                  AND tablename = %s
                """,
                [table_name],
            )
        else:
            cursor.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = %s",
                [table_name],
            )
        return cursor.fetchone() is not None


def forwards(apps, schema_editor):
    table = "items_physinventoryledgerentry"
    if _table_exists(schema_editor, table):
        return
    PhysInventoryLedgerEntry = apps.get_model("items", "PhysInventoryLedgerEntry")
    schema_editor.create_model(PhysInventoryLedgerEntry)


class Migration(migrations.Migration):
    """
    Repair tenant schemas where items_physinventoryledgerentry is missing
    while migration 0014 is recorded as applied.
    """

    dependencies = [
        ("items", "0031_alter_itemjournal_dimension_set_and_more"),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
