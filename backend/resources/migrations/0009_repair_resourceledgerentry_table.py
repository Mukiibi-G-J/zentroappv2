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
    table = "resources_resourceledgerentry"
    if _table_exists(schema_editor, table):
        return
    ResourceLedgerEntry = apps.get_model("resources", "ResourceLedgerEntry")
    schema_editor.create_model(ResourceLedgerEntry)


class Migration(migrations.Migration):
    """
    Repair tenant schemas where resources_resourceledgerentry is missing
    while migration 0006 is recorded as applied.
    """

    dependencies = [
        ("resources", "0008_repair_resource_base_unit_id_column"),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
