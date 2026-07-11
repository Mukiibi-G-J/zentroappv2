import django.db.models.deletion
from django.db import migrations, models


def prepare_generalledgerentry_not_null(apps, schema_editor):
    """
    Legacy tenants may have G/L rows with NULL dimension_set / global_dimension_1 while
    this migration enforces NOT NULL. When no DimensionSet rows exist, branch backfill
    cannot run; drop orphan ledger rows. Otherwise run branch backfill, then remove any
    rows that still cannot be tied to a dimension set / global dim 1.
    """
    c = schema_editor.connection.cursor()
    c.execute(
        """
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = current_schema()
          AND table_name = 'financials_generalledgerentry'
        """
    )
    if not c.fetchone():
        return

    c.execute("SELECT COUNT(*) FROM dimension_dimensionset")
    n_ds = int(c.fetchone()[0])
    if n_ds == 0:
        c.execute(
            "DELETE FROM financials_generalledgerentry "
            "WHERE dimension_set_id IS NULL OR global_dimension_1_id IS NULL"
        )
        return

    from dimension.backfill import run_branch_dimension_backfill

    _, err = run_branch_dimension_backfill(
        allow_multiple_branch_values=True,
        write_audit=True,
    )
    if err and not (
        err.startswith("SCHEMA_DRIFT:")
        or err.startswith("No branch dimension:")
        or err.startswith("No DimensionValue for dimension")
    ):
        raise ValueError(f"financials.0011 pre-backfill: {err}")

    c.execute(
        "DELETE FROM financials_generalledgerentry "
        "WHERE dimension_set_id IS NULL OR global_dimension_1_id IS NULL"
    )


def _vatentry_table_exists(schema_editor) -> bool:
    with schema_editor.connection.cursor() as c:
        c.execute(
            """
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = current_schema()
              AND table_name = 'financials_vatentry'
            """
        )
        return c.fetchone() is not None


def vatentry_global_dim_forwards(apps, schema_editor):
    """
    0010 may have applied state but skipped creating the table (SeparateDatabaseAndState
    with conditional RunPython). Do not ALTER a missing relation.
    """
    if not _vatentry_table_exists(schema_editor):
        return
    Vat = apps.get_model("financials", "VatEntry")
    DimensionValue = apps.get_model("dimension", "DimensionValue")
    old_f = Vat._meta.get_field("global_dimension_1")
    new_f = models.ForeignKey(
        on_delete=django.db.models.deletion.PROTECT,
        related_name="vat_entries",
        to=DimensionValue,
    )
    new_f.set_attributes_from_name("global_dimension_1")
    new_f.model = Vat
    schema_editor.alter_field(Vat, old_f, new_f, strict=True)


def vatentry_global_dim_backwards(apps, schema_editor):
    if not _vatentry_table_exists(schema_editor):
        return
    Vat = apps.get_model("financials", "VatEntry")
    DimensionValue = apps.get_model("dimension", "DimensionValue")
    old_f = Vat._meta.get_field("global_dimension_1")
    new_f = models.ForeignKey(
        blank=True,
        null=True,
        on_delete=django.db.models.deletion.SET_NULL,
        related_name="vat_entries",
        to=DimensionValue,
    )
    new_f.set_attributes_from_name("global_dimension_1")
    new_f.model = Vat
    schema_editor.alter_field(Vat, old_f, new_f, strict=True)


class Migration(migrations.Migration):

    dependencies = [
        ("financials", "0010_add_vat_entry"),
        ("dimension", "0007_dimension_backfill_audit_and_data"),
        ("dimension", "0008_repair_missing_id_pk"),
    ]

    operations = [
        migrations.RunPython(
            prepare_generalledgerentry_not_null,
            migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name="generalledgerentry",
            name="dimension_set",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="general_ledger_entries",
                to="dimension.dimensionset",
            ),
        ),
        migrations.AlterField(
            model_name="generalledgerentry",
            name="global_dimension_1",
            field=models.ForeignKey(
                db_index=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="general_ledger_entries_global_dim_1",
                to="dimension.dimensionvalue",
            ),
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterField(
                    model_name="vatentry",
                    name="global_dimension_1",
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="vat_entries",
                        to="dimension.dimensionvalue",
                    ),
                ),
            ],
            database_operations=[
                migrations.RunPython(
                    vatentry_global_dim_forwards,
                    vatentry_global_dim_backwards,
                ),
            ],
        ),
    ]
