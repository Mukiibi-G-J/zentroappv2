# Enforce NOT NULL on branch + dimension set (run after dimension.0007 backfill)

import django.db.models.deletion
from django.db import migrations, models


def _column_exists(schema_editor, table: str, column: str) -> bool:
    with schema_editor.connection.cursor() as c:
        c.execute(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = current_schema()
              AND table_name = %s
              AND column_name = %s
            """,
            [table, column],
        )
        return c.fetchone() is not None


def enforce_bank_account_ledger_not_nulls(apps, schema_editor):
    """
    Some tenant schemas may be behind and missing the new dimension columns.
    In that case, skip the DDL so migrations can proceed; the schema should be
    brought up-to-date and the backfill re-run later.
    """
    table = "bank_account_bankaccountledgerentry"
    if not _column_exists(schema_editor, table, "global_dimension_1_id"):
        return
    if not _column_exists(schema_editor, table, "dimension_set_id"):
        return

    Ledger = apps.get_model("bank_account", "BankAccountLedgerEntry")
    DimensionValue = apps.get_model("dimension", "DimensionValue")
    DimensionSet = apps.get_model("dimension", "DimensionSet")

    old_g1 = Ledger._meta.get_field("global_dimension_1")
    new_g1 = models.ForeignKey(
        on_delete=django.db.models.deletion.PROTECT,
        related_name="bank_account_ledger_entries",
        to=DimensionValue,
        verbose_name="Global Dimension 1",
    )
    new_g1.set_attributes_from_name("global_dimension_1")
    new_g1.model = Ledger
    schema_editor.alter_field(Ledger, old_g1, new_g1, strict=True)

    old_ds = Ledger._meta.get_field("dimension_set")
    new_ds = models.ForeignKey(
        on_delete=django.db.models.deletion.PROTECT,
        related_name="bank_account_ledger_entries",
        to=DimensionSet,
    )
    new_ds.set_attributes_from_name("dimension_set")
    new_ds.model = Ledger
    schema_editor.alter_field(Ledger, old_ds, new_ds, strict=True)


class Migration(migrations.Migration):

    dependencies = [
        ("bank_account", "0004_remove_bankaccountledgerentry_dimension_1_and_more"),
        ("dimension", "0007_dimension_backfill_audit_and_data"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterField(
                    model_name="bankaccountledgerentry",
                    name="global_dimension_1",
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="bank_account_ledger_entries",
                        to="dimension.dimensionvalue",
                        verbose_name="Global Dimension 1",
                    ),
                ),
                migrations.AlterField(
                    model_name="bankaccountledgerentry",
                    name="dimension_set",
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="bank_account_ledger_entries",
                        to="dimension.dimensionset",
                    ),
                ),
            ],
            database_operations=[
                migrations.RunPython(
                    enforce_bank_account_ledger_not_nulls,
                    migrations.RunPython.noop,
                )
            ],
        )
    ]
