import django.db.models.deletion
from django.db import migrations, models


def _pg_column_exists(cursor, relname, attname):
    """Match 0003_add_header_dimensions: detect column on current search_path."""
    cursor.execute(
        """
        SELECT 1
        FROM pg_attribute a
        JOIN pg_class c ON a.attrelid = c.oid
        JOIN pg_namespace n ON c.relnamespace = n.oid
        WHERE n.nspname = current_schema()
          AND c.relname = %s
          AND a.attname = %s
          AND a.attnum > 0
          AND NOT a.attisdropped
        """,
        [relname, attname],
    )
    return cursor.fetchone() is not None


def _pg_fk_count_for_column(cursor, table_name, column_name):
    """
    0003 may have added a bigint without a named FK that Django can match.
    If there are 0 FK constraints, we clear old_field.db_constraint so
    _alter_field does not require strict=1 to drop, and the new PROTECT FK is created.
    """
    cursor.execute(
        """
        SELECT count(*)
        FROM information_schema.table_constraints AS tc
        JOIN information_schema.key_column_usage AS kcu
          ON tc.constraint_name = kcu.constraint_name
         AND tc.table_schema = kcu.table_schema
         AND tc.table_name = kcu.table_name
        WHERE tc.constraint_type = 'FOREIGN KEY'
          AND tc.table_schema = current_schema()
          AND tc.table_name = %s
          AND kcu.column_name = %s
        """,
        [table_name, column_name],
    )
    return int(cursor.fetchone()[0])


def _forwards(apps, schema_editor):
    """
    0003 may be recorded as applied but columns missing (faked / partial DB).
    Only ALTER columns that already exist; state still updated via state_operations.
    """
    DimensionValue = apps.get_model("dimension", "DimensionValue")
    DimensionSet = apps.get_model("dimension", "DimensionSet")
    T_PRE = "prepayment_preayment"
    T_LINE = "prepayment_preaymentline"
    Pre = apps.get_model("prepayment", "preayment")
    Line = apps.get_model("prepayment", "preaymentline")

    # to= must be a model class here (not "app.Model" string) or schema_editor fails.
    steps = [
        (
            Pre,
            T_PRE,
            "global_dimension_1",
            "global_dimension_1_id",
            DimensionValue,
            "preayment_headers",
            "Global Dimension 1",
        ),
        (Pre, T_PRE, "dimension_set", "dimension_set_id", DimensionSet, "preayment_headers", "Dimension Set"),
        (Line, T_LINE, "global_dimension_1", "global_dimension_1_id", DimensionValue, "preayment_lines", "Global Dimension 1"),
        (Line, T_LINE, "dimension_set", "dimension_set_id", DimensionSet, "preayment_lines", "Dimension Set"),
    ]

    with schema_editor.connection.cursor() as c:
        for model, table, attr_name, col_name, to_model, rel_name, vname in steps:
            if not _pg_column_exists(c, table, col_name):
                continue
            old_f = model._meta.get_field(attr_name)
            if _pg_fk_count_for_column(c, table, col_name) == 0:
                old_f.db_constraint = False
            nf = models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name=rel_name,
                to=to_model,
                verbose_name=vname,
            )
            nf.set_attributes_from_name(attr_name)
            nf.model = model
            schema_editor.alter_field(model, old_f, nf, strict=False)


def _backwards(apps, schema_editor):
    """Restore 0003-style nullable + SET_NULL when columns exist."""
    DimensionValue = apps.get_model("dimension", "DimensionValue")
    DimensionSet = apps.get_model("dimension", "DimensionSet")
    T_PRE = "prepayment_preayment"
    T_LINE = "prepayment_preaymentline"
    Pre = apps.get_model("prepayment", "preayment")
    Line = apps.get_model("prepayment", "preaymentline")

    steps = [
        (
            Pre,
            T_PRE,
            "global_dimension_1",
            "global_dimension_1_id",
            DimensionValue,
            "preayment_headers",
            "Global Dimension 1",
        ),
        (Pre, T_PRE, "dimension_set", "dimension_set_id", DimensionSet, "preayment_headers", "Dimension Set"),
        (Line, T_LINE, "global_dimension_1", "global_dimension_1_id", DimensionValue, "preayment_lines", "Global Dimension 1"),
        (Line, T_LINE, "dimension_set", "dimension_set_id", DimensionSet, "preayment_lines", "Dimension Set"),
    ]

    with schema_editor.connection.cursor() as c:
        for model, table, attr_name, col_name, to_model, rel_name, vname in steps:
            if not _pg_column_exists(c, table, col_name):
                continue
            old_f = model._meta.get_field(attr_name)
            if _pg_fk_count_for_column(c, table, col_name) == 0:
                old_f.db_constraint = False
            nf = models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name=rel_name,
                to=to_model,
                verbose_name=vname,
            )
            nf.set_attributes_from_name(attr_name)
            nf.model = model
            schema_editor.alter_field(model, old_f, nf, strict=False)


class Migration(migrations.Migration):

    dependencies = [
        ("prepayment", "0003_add_header_dimensions"),
        ("dimension", "0007_dimension_backfill_audit_and_data"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterField(
                    model_name="preayment",
                    name="global_dimension_1",
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="preayment_headers",
                        to="dimension.dimensionvalue",
                        verbose_name="Global Dimension 1",
                    ),
                ),
                migrations.AlterField(
                    model_name="preayment",
                    name="dimension_set",
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="preayment_headers",
                        to="dimension.dimensionset",
                        verbose_name="Dimension Set",
                    ),
                ),
                migrations.AlterField(
                    model_name="preaymentline",
                    name="global_dimension_1",
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="preayment_lines",
                        to="dimension.dimensionvalue",
                        verbose_name="Global Dimension 1",
                    ),
                ),
                migrations.AlterField(
                    model_name="preaymentline",
                    name="dimension_set",
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="preayment_lines",
                        to="dimension.dimensionset",
                        verbose_name="Dimension Set",
                    ),
                ),
            ],
            database_operations=[
                migrations.RunPython(_forwards, _backwards),
            ],
        ),
    ]
