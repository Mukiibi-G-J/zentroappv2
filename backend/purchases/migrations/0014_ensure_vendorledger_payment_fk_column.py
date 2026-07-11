from django.db import migrations


def _column_names(schema_editor, table):
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = current_schema()
              AND table_name = %s
            """,
            [table],
        )
        return {row[0] for row in cursor.fetchall()}


def forwards(apps, schema_editor):
    VendorLedger = apps.get_model("purchases", "VendorLedger")
    table = VendorLedger._meta.db_table
    cols = _column_names(schema_editor, table)

    if "applies_to_id_id" in cols and "payment_id" not in cols:
        schema_editor.execute(
            f'ALTER TABLE "{table}" RENAME COLUMN "applies_to_id_id" TO "payment_id"'
        )


def backwards(apps, schema_editor):
    VendorLedger = apps.get_model("purchases", "VendorLedger")
    table = VendorLedger._meta.db_table
    cols = _column_names(schema_editor, table)

    if "payment_id" in cols and "applies_to_id_id" not in cols:
        schema_editor.execute(
            f'ALTER TABLE "{table}" RENAME COLUMN "payment_id" TO "applies_to_id_id"'
        )


class Migration(migrations.Migration):

    dependencies = [
        ("purchases", "0013_backfill_applies_to_id"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
