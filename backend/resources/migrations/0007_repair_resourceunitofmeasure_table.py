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


def _backfill_resource_units_of_measure(apps):
    Resource = apps.get_model("resources", "Resource")
    ResourceUnitOfMeasure = apps.get_model("resources", "ResourceUnitOfMeasure")
    for resource in Resource.objects.all():
        base_unit_id = getattr(resource, "base_unit_id", None)
        if not base_unit_id:
            continue
        ResourceUnitOfMeasure.objects.get_or_create(
            resource=resource,
            unit_of_measure_id=base_unit_id,
            defaults={"quantity_per_unit": 1, "default": True},
        )


def forwards(apps, schema_editor):
    table = "resources_resourceunitofmeasure"
    if not _table_exists(schema_editor, table):
        ResourceUnitOfMeasure = apps.get_model("resources", "ResourceUnitOfMeasure")
        schema_editor.create_model(ResourceUnitOfMeasure)
    _backfill_resource_units_of_measure(apps)


class Migration(migrations.Migration):
    """
    Repair tenant schemas where resources_resourceunitofmeasure is missing
    while migration 0003 is recorded as applied.
    """

    dependencies = [
        ("resources", "0006_resource_ledger_entry"),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
