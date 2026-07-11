import django.db.models.deletion
from django.db import migrations, models


def backfill_items_branch_dimensions(apps, schema_editor):
    """
    Ensure ItemLedgerEntries/ValueEntry have global_dimension_1 + dimension_set filled
    before enforcing NOT NULL / PROTECT.

    Note: `dimension.0007` may have run before `items.0027` added `global_dimension_2`,
    causing the generic backfill to skip items models (schema drift). This re-run is
    idempotent and safe.
    """
    from dimension.schema_repair import ensure_dimensionset_tables
    from dimension.backfill import run_branch_dimension_backfill

    ensure_dimensionset_tables(apps, schema_editor)

    results, err = run_branch_dimension_backfill(
        allow_multiple_branch_values=True,
        write_audit=True,
    )
    # Fresh tenants often reach this migration before financials/setup seeds
    # GeneralLedgerSetup.global_dimension_1 or Dimension BRANCH; skip backfill-only.
    # Follow-up AlterFields still run (matching expenses.0004 drift semantics)—safe when
    # ItemLedgerEntries/ValueEntry are empty at signup migration time.
    if err and (
        err.startswith("SCHEMA_DRIFT:")
        or err.startswith("No branch dimension:")
        or err.startswith("No DimensionValue for dimension")
    ):
        return
    if err:
        raise ValueError(f"Branch dimension backfill (items.0028): {err}")


class Migration(migrations.Migration):
    # PostgreSQL: bulk UPDATE in RunPython can queue deferred triggers on affected tables.
    # AlterField on those tables in the same transaction raises "pending trigger events".
    atomic = False

    dependencies = [
        ("items", "0027_add_global_dimension_2_to_item_value_ledger"),
        ("dimension", "0007_dimension_backfill_audit_and_data"),
    ]

    operations = [
        migrations.RunPython(backfill_items_branch_dimensions, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="itemledgerentries",
            name="global_dimension_1",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="item_ledger_entries",
                to="dimension.dimensionvalue",
            ),
        ),
        migrations.AlterField(
            model_name="itemledgerentries",
            name="dimension_set",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="item_ledger_entries",
                to="dimension.dimensionset",
            ),
        ),
        migrations.AlterField(
            model_name="valueentry",
            name="global_dimension_1",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="value_entries",
                to="dimension.dimensionvalue",
            ),
        ),
        migrations.AlterField(
            model_name="valueentry",
            name="dimension_set",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="value_entries",
                to="dimension.dimensionset",
            ),
        ),
    ]
