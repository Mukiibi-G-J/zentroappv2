import django.db.models.deletion
from django.db import migrations, models


def _pg_column_exists(cursor, relname, attname):
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
    DimensionValue = apps.get_model("dimension", "DimensionValue")
    DimensionSet = apps.get_model("dimension", "DimensionSet")
    specs = [
        (
            "salesinvoice",
            "global_dimension_1",
            True,
            {
                "related_name": "sales_invoice_headers",
                "verbose_name": "Global Dimension 1",
            },
        ),
        (
            "salesinvoice",
            "dimension_set",
            False,
            {
                "related_name": "sales_invoice_headers",
                "verbose_name": "Dimension Set",
            },
        ),
        (
            "salesinvoiceline",
            "global_dimension_1",
            True,
            {"related_name": "sales_lines"},
        ),
        (
            "salesinvoiceline",
            "dimension_set",
            False,
            {"related_name": "sales_lines"},
        ),
        (
            "salesorderline",
            "global_dimension_1",
            True,
            {"related_name": "sales_order_lines"},
        ),
        (
            "salesorderline",
            "dimension_set",
            False,
            {"related_name": "sales_order_lines"},
        ),
        (
            "postedsalesinvoice",
            "global_dimension_1",
            True,
            {
                "related_name": "posted_sales_invoice_headers",
                "verbose_name": "Global Dimension 1",
            },
        ),
        (
            "postedsalesinvoice",
            "dimension_set",
            False,
            {
                "related_name": "posted_sales_invoice_headers",
                "verbose_name": "Dimension Set",
            },
        ),
        (
            "postedsalesinvoiceline",
            "global_dimension_1",
            True,
            {"related_name": "posted_sales_lines"},
        ),
        (
            "postedsalesinvoiceline",
            "dimension_set",
            False,
            {"related_name": "posted_sales_lines"},
        ),
        (
            "detailedcustomerledgerentry",
            "global_dimension_1",
            True,
            {
                "help_text": "Global Dimension 1 value",
                "related_name": "sales_customer_detailed_entries",
            },
        ),
        (
            "detailedcustomerledgerentry",
            "dimension_set",
            False,
            {"related_name": "sales_customer_detailed_entries"},
        ),
        (
            "salescreditmemo",
            "global_dimension_1",
            True,
            {
                "related_name": "sales_credit_memo_headers",
                "verbose_name": "Global Dimension 1",
            },
        ),
        (
            "salescreditmemo",
            "dimension_set",
            False,
            {
                "related_name": "sales_credit_memo_headers",
                "verbose_name": "Dimension Set",
            },
        ),
        (
            "salescreditmemoline",
            "global_dimension_1",
            True,
            {
                "related_name": "credit_memo_lines",
                "verbose_name": "Global Dimension 1",
            },
        ),
        (
            "salescreditmemoline",
            "dimension_set",
            False,
            {"related_name": "credit_memo_lines"},
        ),
        (
            "customerledgerentry",
            "global_dimension_1",
            True,
            {
                "related_name": "customer_ledger_entries",
                "verbose_name": "Global Dimension 1",
            },
        ),
        (
            "customerledgerentry",
            "dimension_set",
            False,
            {"related_name": "customer_ledger_entries"},
        ),
    ]
    with schema_editor.connection.cursor() as c:
        for model_name, attr, use_dv, fn_kw in specs:
            M = apps.get_model("sales", model_name)
            old_f = M._meta.get_field(attr)
            col = old_f.column
            if not _pg_column_exists(c, M._meta.db_table, col):
                continue
            if _pg_fk_count_for_column(c, M._meta.db_table, col) == 0:
                old_f.db_constraint = False
            to_m = DimensionValue if use_dv else DimensionSet
            nf = models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                to=to_m,
                **fn_kw,
            )
            nf.set_attributes_from_name(attr)
            nf.model = M
            schema_editor.alter_field(M, old_f, nf, strict=False)


def _backwards(apps, schema_editor):
    DimensionValue = apps.get_model("dimension", "DimensionValue")
    DimensionSet = apps.get_model("dimension", "DimensionSet")
    specs = [
        (
            "salesinvoice",
            "global_dimension_1",
            True,
            {
                "blank": True,
                "null": True,
                "on_delete": django.db.models.deletion.SET_NULL,
                "related_name": "sales_invoice_headers",
                "verbose_name": "Global Dimension 1",
            },
        ),
        (
            "salesinvoice",
            "dimension_set",
            False,
            {
                "blank": True,
                "null": True,
                "on_delete": django.db.models.deletion.SET_NULL,
                "related_name": "sales_invoice_headers",
                "verbose_name": "Dimension Set",
            },
        ),
        (
            "salesinvoiceline",
            "global_dimension_1",
            True,
            {
                "blank": True,
                "null": True,
                "on_delete": django.db.models.deletion.SET_NULL,
                "related_name": "sales_lines",
            },
        ),
        (
            "salesinvoiceline",
            "dimension_set",
            False,
            {
                "blank": True,
                "null": True,
                "on_delete": django.db.models.deletion.SET_NULL,
                "related_name": "sales_lines",
            },
        ),
        (
            "salesorderline",
            "global_dimension_1",
            True,
            {
                "blank": True,
                "null": True,
                "on_delete": django.db.models.deletion.SET_NULL,
                "related_name": "sales_order_lines",
            },
        ),
        (
            "salesorderline",
            "dimension_set",
            False,
            {
                "blank": True,
                "null": True,
                "on_delete": django.db.models.deletion.SET_NULL,
                "related_name": "sales_order_lines",
            },
        ),
        (
            "postedsalesinvoice",
            "global_dimension_1",
            True,
            {
                "blank": True,
                "null": True,
                "on_delete": django.db.models.deletion.SET_NULL,
                "related_name": "posted_sales_invoice_headers",
                "verbose_name": "Global Dimension 1",
            },
        ),
        (
            "postedsalesinvoice",
            "dimension_set",
            False,
            {
                "blank": True,
                "null": True,
                "on_delete": django.db.models.deletion.SET_NULL,
                "related_name": "posted_sales_invoice_headers",
                "verbose_name": "Dimension Set",
            },
        ),
        (
            "postedsalesinvoiceline",
            "global_dimension_1",
            True,
            {
                "blank": True,
                "null": True,
                "on_delete": django.db.models.deletion.SET_NULL,
                "related_name": "posted_sales_lines",
            },
        ),
        (
            "postedsalesinvoiceline",
            "dimension_set",
            False,
            {
                "blank": True,
                "null": True,
                "on_delete": django.db.models.deletion.SET_NULL,
                "related_name": "posted_sales_lines",
            },
        ),
        (
            "detailedcustomerledgerentry",
            "global_dimension_1",
            True,
            {
                "blank": True,
                "null": True,
                "on_delete": django.db.models.deletion.SET_NULL,
                "help_text": "Global Dimension 1 value",
                "related_name": "sales_customer_detailed_entries",
            },
        ),
        (
            "detailedcustomerledgerentry",
            "dimension_set",
            False,
            {
                "blank": True,
                "null": True,
                "on_delete": django.db.models.deletion.SET_NULL,
                "related_name": "sales_customer_detailed_entries",
            },
        ),
        (
            "salescreditmemo",
            "global_dimension_1",
            True,
            {
                "blank": True,
                "null": True,
                "on_delete": django.db.models.deletion.SET_NULL,
                "related_name": "sales_credit_memo_headers",
                "verbose_name": "Global Dimension 1",
            },
        ),
        (
            "salescreditmemo",
            "dimension_set",
            False,
            {
                "blank": True,
                "null": True,
                "on_delete": django.db.models.deletion.SET_NULL,
                "related_name": "sales_credit_memo_headers",
                "verbose_name": "Dimension Set",
            },
        ),
        (
            "salescreditmemoline",
            "global_dimension_1",
            True,
            {
                "blank": True,
                "null": True,
                "on_delete": django.db.models.deletion.SET_NULL,
                "related_name": "credit_memo_lines",
                "verbose_name": "Global Dimension 1",
            },
        ),
        (
            "salescreditmemoline",
            "dimension_set",
            False,
            {
                "blank": True,
                "null": True,
                "on_delete": django.db.models.deletion.SET_NULL,
                "related_name": "credit_memo_lines",
            },
        ),
        (
            "customerledgerentry",
            "global_dimension_1",
            True,
            {
                "blank": True,
                "null": True,
                "on_delete": django.db.models.deletion.SET_NULL,
                "related_name": "customer_ledger_entries",
                "verbose_name": "Global Dimension 1",
            },
        ),
        (
            "customerledgerentry",
            "dimension_set",
            False,
            {
                "blank": True,
                "null": True,
                "on_delete": django.db.models.deletion.SET_NULL,
                "related_name": "customer_ledger_entries",
            },
        ),
    ]
    with schema_editor.connection.cursor() as c:
        for model_name, attr, use_dv, b_kw in specs:
            M = apps.get_model("sales", model_name)
            old_f = M._meta.get_field(attr)
            col = old_f.column
            if not _pg_column_exists(c, M._meta.db_table, col):
                continue
            if _pg_fk_count_for_column(c, M._meta.db_table, col) == 0:
                old_f.db_constraint = False
            to_m = DimensionValue if use_dv else DimensionSet
            odelete = b_kw["on_delete"]
            rest = {k: v for k, v in b_kw.items() if k != "on_delete"}
            nf = models.ForeignKey(
                to=to_m,
                on_delete=odelete,
                **rest,
            )
            nf.set_attributes_from_name(attr)
            nf.model = M
            schema_editor.alter_field(M, old_f, nf, strict=False)


class Migration(migrations.Migration):

    dependencies = [
        ("sales", "0015_sales_favorite_slot"),
        ("dimension", "0007_dimension_backfill_audit_and_data"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterField(
                    model_name="salesinvoice",
                    name="global_dimension_1",
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="sales_invoice_headers",
                        to="dimension.dimensionvalue",
                        verbose_name="Global Dimension 1",
                    ),
                ),
                migrations.AlterField(
                    model_name="salesinvoice",
                    name="dimension_set",
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="sales_invoice_headers",
                        to="dimension.dimensionset",
                        verbose_name="Dimension Set",
                    ),
                ),
                migrations.AlterField(
                    model_name="salesinvoiceline",
                    name="global_dimension_1",
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="sales_lines",
                        to="dimension.dimensionvalue",
                    ),
                ),
                migrations.AlterField(
                    model_name="salesinvoiceline",
                    name="dimension_set",
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="sales_lines",
                        to="dimension.dimensionset",
                    ),
                ),
                migrations.AlterField(
                    model_name="salesorderline",
                    name="global_dimension_1",
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="sales_order_lines",
                        to="dimension.dimensionvalue",
                    ),
                ),
                migrations.AlterField(
                    model_name="salesorderline",
                    name="dimension_set",
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="sales_order_lines",
                        to="dimension.dimensionset",
                    ),
                ),
                migrations.AlterField(
                    model_name="postedsalesinvoice",
                    name="global_dimension_1",
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="posted_sales_invoice_headers",
                        to="dimension.dimensionvalue",
                        verbose_name="Global Dimension 1",
                    ),
                ),
                migrations.AlterField(
                    model_name="postedsalesinvoice",
                    name="dimension_set",
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="posted_sales_invoice_headers",
                        to="dimension.dimensionset",
                        verbose_name="Dimension Set",
                    ),
                ),
                migrations.AlterField(
                    model_name="postedsalesinvoiceline",
                    name="global_dimension_1",
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="posted_sales_lines",
                        to="dimension.dimensionvalue",
                    ),
                ),
                migrations.AlterField(
                    model_name="postedsalesinvoiceline",
                    name="dimension_set",
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="posted_sales_lines",
                        to="dimension.dimensionset",
                    ),
                ),
                migrations.AlterField(
                    model_name="detailedcustomerledgerentry",
                    name="global_dimension_1",
                    field=models.ForeignKey(
                        help_text="Global Dimension 1 value",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="sales_customer_detailed_entries",
                        to="dimension.dimensionvalue",
                    ),
                ),
                migrations.AlterField(
                    model_name="detailedcustomerledgerentry",
                    name="dimension_set",
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="sales_customer_detailed_entries",
                        to="dimension.dimensionset",
                    ),
                ),
                migrations.AlterField(
                    model_name="salescreditmemo",
                    name="global_dimension_1",
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="sales_credit_memo_headers",
                        to="dimension.dimensionvalue",
                        verbose_name="Global Dimension 1",
                    ),
                ),
                migrations.AlterField(
                    model_name="salescreditmemo",
                    name="dimension_set",
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="sales_credit_memo_headers",
                        to="dimension.dimensionset",
                        verbose_name="Dimension Set",
                    ),
                ),
                migrations.AlterField(
                    model_name="salescreditmemoline",
                    name="global_dimension_1",
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="credit_memo_lines",
                        to="dimension.dimensionvalue",
                        verbose_name="Global Dimension 1",
                    ),
                ),
                migrations.AlterField(
                    model_name="salescreditmemoline",
                    name="dimension_set",
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="credit_memo_lines",
                        to="dimension.dimensionset",
                    ),
                ),
                migrations.AlterField(
                    model_name="customerledgerentry",
                    name="global_dimension_1",
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="customer_ledger_entries",
                        to="dimension.dimensionvalue",
                        verbose_name="Global Dimension 1",
                    ),
                ),
                migrations.AlterField(
                    model_name="customerledgerentry",
                    name="dimension_set",
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="customer_ledger_entries",
                        to="dimension.dimensionset",
                    ),
                ),
            ],
            database_operations=[
                migrations.RunPython(_forwards, _backwards),
            ],
        ),
    ]
