from django.db import migrations, models


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
    CustomerLedgerEntry = apps.get_model("sales", "CustomerLedgerEntry")
    table = CustomerLedgerEntry._meta.db_table
    cols = _column_names(schema_editor, table)

    for col in (
        "applies_to_doc_type",
        "applies_to_doc_no",
        "applies_to_entry_no",
        "applies_to_ext_doc_no",
    ):
        if col in cols:
            schema_editor.execute(f'ALTER TABLE "{table}" DROP COLUMN "{col}"')

    cols = _column_names(schema_editor, table)
    if "applies_to_id" not in cols:
        field = models.CharField(
            max_length=50,
            blank=True,
            default="",
            verbose_name="Applies-to ID",
        )
        field.set_attributes_from_name("applies_to_id")
        schema_editor.add_field(CustomerLedgerEntry, field)


def backwards(apps, schema_editor):
    CustomerLedgerEntry = apps.get_model("sales", "CustomerLedgerEntry")
    table = CustomerLedgerEntry._meta.db_table
    cols = _column_names(schema_editor, table)
    if "applies_to_id" in cols:
        schema_editor.execute(f'ALTER TABLE "{table}" DROP COLUMN "applies_to_id"')


class Migration(migrations.Migration):

    dependencies = [
        ("sales", "0022_customerledgerentry_applies_to_fields"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(forwards, backwards),
            ],
            state_operations=[
                migrations.RemoveField(
                    model_name="customerledgerentry",
                    name="applies_to_doc_type",
                ),
                migrations.RemoveField(
                    model_name="customerledgerentry",
                    name="applies_to_doc_no",
                ),
                migrations.RemoveField(
                    model_name="customerledgerentry",
                    name="applies_to_entry_no",
                ),
                migrations.RemoveField(
                    model_name="customerledgerentry",
                    name="applies_to_ext_doc_no",
                ),
                migrations.AddField(
                    model_name="customerledgerentry",
                    name="applies_to_id",
                    field=models.CharField(
                        blank=True,
                        default="",
                        help_text="ID of entries that will be applied when you choose the Apply Entries action",
                        max_length=50,
                        verbose_name="Applies-to ID",
                    ),
                ),
            ],
        ),
    ]
