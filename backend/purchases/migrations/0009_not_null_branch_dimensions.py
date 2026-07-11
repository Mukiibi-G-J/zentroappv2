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
    from dimension.schema_repair import ensure_dimensionset_tables
    from dimension.backfill import run_branch_dimension_backfill

    ensure_dimensionset_tables(apps, schema_editor)

    qn = schema_editor.connection.ops.quote_name
    header_tables = (
        "purchases_postedpurchaseinvoice",
        "purchases_postedpurchaseinvoiceline",
        "purchases_purchasecreditmemo",
        "purchases_purchaseinvoice",
    )
    with schema_editor.connection.cursor() as cursor:
        for table in header_tables:
            if not _pg_column_exists(cursor, table, "dimension_set_id"):
                cursor.execute(
                    f"""
                    ALTER TABLE {qn(table)}
                    ADD COLUMN IF NOT EXISTS dimension_set_id bigint NULL
                    REFERENCES {qn("dimension_dimensionset")}(id)
                    ON DELETE SET NULL
                    """
                )

    _, err = run_branch_dimension_backfill(
        allow_multiple_branch_values=True,
        write_audit=True,
    )
    if err and not (
        err.startswith("SCHEMA_DRIFT:")
        or err.startswith("No branch dimension:")
        or err.startswith("No DimensionValue for dimension")
    ):
        raise ValueError(f"purchases.0009 branch backfill: {err}")

    from dimension.utils import resolve_default_branch_for_tenant

    branch, dim_set, _resolve_err = resolve_default_branch_for_tenant(
        allow_multiple_branch_values=True,
    )

    DimensionValue = apps.get_model("dimension", "DimensionValue")
    DimensionSet = apps.get_model("dimension", "DimensionSet")
    qn = schema_editor.connection.ops.quote_name
    ledger_tables = {
        "purchases_vendorledger",
        "purchases_detailedvendorledgerentry",
    }
    # (model, field, use_dimension_value, forward_kw for ForeignKey besides on_delete/to)
    specs = [
        (
            "purchaseinvoice",
            "global_dimension_1",
            True,
            {
                "related_name": "purchase_invoice_headers",
                "verbose_name": "Global Dimension 1",
            },
        ),
        (
            "purchaseinvoice",
            "dimension_set",
            False,
            {
                "related_name": "purchase_invoice_headers",
                "verbose_name": "Dimension Set",
            },
        ),
        (
            "purchaseinvoiceline",
            "global_dimension_1",
            True,
            {"related_name": "purchase_lines"},
        ),
        (
            "purchaseinvoiceline",
            "dimension_set",
            False,
            {"related_name": "purchase_lines"},
        ),
        (
            "postedpurchaseinvoice",
            "global_dimension_1",
            True,
            {
                "related_name": "posted_purchase_invoice_headers",
                "verbose_name": "Global Dimension 1",
            },
        ),
        (
            "postedpurchaseinvoice",
            "dimension_set",
            False,
            {
                "related_name": "posted_purchase_invoice_headers",
                "verbose_name": "Dimension Set",
            },
        ),
        (
            "postedpurchaseinvoiceline",
            "global_dimension_1",
            True,
            {
                "related_name": "posted_purchase_invoice_lines",
                "verbose_name": "Global Dimension 1",
            },
        ),
        (
            "postedpurchaseinvoiceline",
            "dimension_set",
            False,
            {
                "related_name": "posted_purchase_invoice_lines",
                "verbose_name": "Dimension Set",
            },
        ),
        (
            "vendorledger",
            "global_dimension_1",
            True,
            {
                "db_column": "dimension_1",
                "related_name": "vendor_ledger_entries",
            },
        ),
        (
            "vendorledger",
            "dimension_set",
            False,
            {"related_name": "vendor_ledger_entries"},
        ),
        (
            "purchasecreditmemo",
            "global_dimension_1",
            True,
            {
                "related_name": "purchase_credit_memo_headers",
                "verbose_name": "Global Dimension 1",
            },
        ),
        (
            "purchasecreditmemo",
            "dimension_set",
            False,
            {
                "related_name": "purchase_credit_memo_headers",
                "verbose_name": "Dimension Set",
            },
        ),
        (
            "purchasecreditmemoline",
            "global_dimension_1",
            True,
            {
                "related_name": "purchase_credit_memo_lines",
                "verbose_name": "Global Dimension 1",
            },
        ),
        (
            "purchasecreditmemoline",
            "dimension_set",
            False,
            {"related_name": "purchase_credit_memo_lines"},
        ),
        (
            "detailedvendorledgerentry",
            "global_dimension_1",
            True,
            {
                "help_text": "Global Dimension 1 value",
                "related_name": "vendor_detailed_entries",
            },
        ),
        (
            "detailedvendorledgerentry",
            "dimension_set",
            False,
            {"related_name": "vendor_detailed_entries"},
        ),
    ]
    with schema_editor.connection.cursor() as c:
        seen_tables = set()
        for model_name, _, _, _ in specs:
            M = apps.get_model("purchases", model_name)
            tbl = M._meta.db_table
            if tbl in seen_tables:
                continue
            seen_tables.add(tbl)
            g1c = M._meta.get_field("global_dimension_1").column
            dsc = M._meta.get_field("dimension_set").column
            has_g1 = _pg_column_exists(c, tbl, g1c)
            has_ds = _pg_column_exists(c, tbl, dsc)
            if branch and branch.pk and has_g1:
                c.execute(
                    f"UPDATE {qn(tbl)} SET {qn(g1c)} = %s WHERE {qn(g1c)} IS NULL",
                    [branch.pk],
                )
            if dim_set and dim_set.pk and has_ds:
                c.execute(
                    f"UPDATE {qn(tbl)} SET {qn(dsc)} = %s WHERE {qn(dsc)} IS NULL",
                    [dim_set.pk],
                )
            if tbl in ledger_tables:
                continue
            if has_g1 and has_ds:
                c.execute(
                    f"DELETE FROM {qn(tbl)} "
                    f"WHERE {qn(g1c)} IS NULL OR {qn(dsc)} IS NULL"
                )
            elif has_g1:
                c.execute(
                    f"DELETE FROM {qn(tbl)} WHERE {qn(g1c)} IS NULL"
                )
        c.execute("SET CONSTRAINTS ALL IMMEDIATE")

        for model_name, attr, use_dv, fn_kw in specs:
            M = apps.get_model("purchases", model_name)
            old_f = M._meta.get_field(attr)
            col = old_f.column
            tbl = M._meta.db_table
            if not _pg_column_exists(c, tbl, col):
                continue
            c.execute(
                f"SELECT COUNT(*) FROM {qn(tbl)} WHERE {qn(col)} IS NULL"
            )
            if c.fetchone()[0] > 0:
                continue
            if _pg_fk_count_for_column(c, tbl, col) == 0:
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
    """Restore nullable SET_NULL where columns exist (match pre-0009 drift repairs)."""
    DimensionValue = apps.get_model("dimension", "DimensionValue")
    DimensionSet = apps.get_model("dimension", "DimensionSet")
    specs = [
        (
            "purchaseinvoice",
            "global_dimension_1",
            True,
            {
                "blank": True,
                "null": True,
                "on_delete": django.db.models.deletion.SET_NULL,
                "related_name": "purchase_invoice_headers",
                "verbose_name": "Global Dimension 1",
            },
        ),
        (
            "purchaseinvoice",
            "dimension_set",
            False,
            {
                "blank": True,
                "null": True,
                "on_delete": django.db.models.deletion.SET_NULL,
                "related_name": "purchase_invoice_headers",
                "verbose_name": "Dimension Set",
            },
        ),
        (
            "purchaseinvoiceline",
            "global_dimension_1",
            True,
            {
                "blank": True,
                "null": True,
                "on_delete": django.db.models.deletion.SET_NULL,
                "related_name": "purchase_lines",
            },
        ),
        (
            "purchaseinvoiceline",
            "dimension_set",
            False,
            {
                "blank": True,
                "null": True,
                "on_delete": django.db.models.deletion.SET_NULL,
                "related_name": "purchase_lines",
            },
        ),
        (
            "postedpurchaseinvoice",
            "global_dimension_1",
            True,
            {
                "blank": True,
                "null": True,
                "on_delete": django.db.models.deletion.SET_NULL,
                "related_name": "posted_purchase_invoice_headers",
                "verbose_name": "Global Dimension 1",
            },
        ),
        (
            "postedpurchaseinvoice",
            "dimension_set",
            False,
            {
                "blank": True,
                "null": True,
                "on_delete": django.db.models.deletion.SET_NULL,
                "related_name": "posted_purchase_invoice_headers",
                "verbose_name": "Dimension Set",
            },
        ),
        (
            "postedpurchaseinvoiceline",
            "global_dimension_1",
            True,
            {
                "blank": True,
                "null": True,
                "on_delete": django.db.models.deletion.SET_NULL,
                "related_name": "posted_purchase_invoice_lines",
                "verbose_name": "Global Dimension 1",
            },
        ),
        (
            "postedpurchaseinvoiceline",
            "dimension_set",
            False,
            {
                "blank": True,
                "null": True,
                "on_delete": django.db.models.deletion.SET_NULL,
                "related_name": "posted_purchase_invoice_lines",
                "verbose_name": "Dimension Set",
            },
        ),
        (
            "vendorledger",
            "global_dimension_1",
            True,
            {
                "blank": True,
                "null": True,
                "on_delete": django.db.models.deletion.SET_NULL,
                "db_column": "dimension_1",
                "related_name": "vendor_ledger_entries",
            },
        ),
        (
            "vendorledger",
            "dimension_set",
            False,
            {
                "blank": True,
                "null": True,
                "on_delete": django.db.models.deletion.SET_NULL,
                "related_name": "vendor_ledger_entries",
            },
        ),
        (
            "purchasecreditmemo",
            "global_dimension_1",
            True,
            {
                "blank": True,
                "null": True,
                "on_delete": django.db.models.deletion.SET_NULL,
                "related_name": "purchase_credit_memo_headers",
                "verbose_name": "Global Dimension 1",
            },
        ),
        (
            "purchasecreditmemo",
            "dimension_set",
            False,
            {
                "blank": True,
                "null": True,
                "on_delete": django.db.models.deletion.SET_NULL,
                "related_name": "purchase_credit_memo_headers",
                "verbose_name": "Dimension Set",
            },
        ),
        (
            "purchasecreditmemoline",
            "global_dimension_1",
            True,
            {
                "blank": True,
                "null": True,
                "on_delete": django.db.models.deletion.SET_NULL,
                "related_name": "purchase_credit_memo_lines",
                "verbose_name": "Global Dimension 1",
            },
        ),
        (
            "purchasecreditmemoline",
            "dimension_set",
            False,
            {
                "blank": True,
                "null": True,
                "on_delete": django.db.models.deletion.SET_NULL,
                "related_name": "purchase_credit_memo_lines",
            },
        ),
        (
            "detailedvendorledgerentry",
            "global_dimension_1",
            True,
            {
                "blank": True,
                "null": True,
                "on_delete": django.db.models.deletion.SET_NULL,
                "help_text": "Global Dimension 1 value",
                "related_name": "vendor_detailed_entries",
            },
        ),
        (
            "detailedvendorledgerentry",
            "dimension_set",
            False,
            {
                "blank": True,
                "null": True,
                "on_delete": django.db.models.deletion.SET_NULL,
                "related_name": "vendor_detailed_entries",
            },
        ),
    ]
    with schema_editor.connection.cursor() as c:
        for model_name, attr, use_dv, b_kw in specs:
            M = apps.get_model("purchases", model_name)
            old_f = M._meta.get_field(attr)
            col = old_f.column
            if not _pg_column_exists(c, M._meta.db_table, col):
                continue
            if _pg_fk_count_for_column(c, M._meta.db_table, col) == 0:
                old_f.db_constraint = False
            to_m = DimensionValue if use_dv else DimensionSet
            # b_kw has on_delete inside - extract
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
        ("purchases", "0008_repair_posted_purchase_invoice_line_drift"),
        ("dimension", "0007_dimension_backfill_audit_and_data"),
        ("dimension", "0008_repair_missing_id_pk"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterField(
                    model_name="purchaseinvoice",
                    name="global_dimension_1",
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="purchase_invoice_headers",
                        to="dimension.dimensionvalue",
                        verbose_name="Global Dimension 1",
                    ),
                ),
                migrations.AlterField(
                    model_name="purchaseinvoice",
                    name="dimension_set",
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="purchase_invoice_headers",
                        to="dimension.dimensionset",
                        verbose_name="Dimension Set",
                    ),
                ),
                migrations.AlterField(
                    model_name="purchaseinvoiceline",
                    name="global_dimension_1",
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="purchase_lines",
                        to="dimension.dimensionvalue",
                    ),
                ),
                migrations.AlterField(
                    model_name="purchaseinvoiceline",
                    name="dimension_set",
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="purchase_lines",
                        to="dimension.dimensionset",
                    ),
                ),
                migrations.AlterField(
                    model_name="postedpurchaseinvoice",
                    name="global_dimension_1",
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="posted_purchase_invoice_headers",
                        to="dimension.dimensionvalue",
                        verbose_name="Global Dimension 1",
                    ),
                ),
                migrations.AlterField(
                    model_name="postedpurchaseinvoice",
                    name="dimension_set",
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="posted_purchase_invoice_headers",
                        to="dimension.dimensionset",
                        verbose_name="Dimension Set",
                    ),
                ),
                migrations.AlterField(
                    model_name="postedpurchaseinvoiceline",
                    name="global_dimension_1",
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="posted_purchase_invoice_lines",
                        to="dimension.dimensionvalue",
                        verbose_name="Global Dimension 1",
                    ),
                ),
                migrations.AlterField(
                    model_name="postedpurchaseinvoiceline",
                    name="dimension_set",
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="posted_purchase_invoice_lines",
                        to="dimension.dimensionset",
                        verbose_name="Dimension Set",
                    ),
                ),
                migrations.AlterField(
                    model_name="vendorledger",
                    name="global_dimension_1",
                    field=models.ForeignKey(
                        db_column="dimension_1",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="vendor_ledger_entries",
                        to="dimension.dimensionvalue",
                    ),
                ),
                migrations.AlterField(
                    model_name="vendorledger",
                    name="dimension_set",
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="vendor_ledger_entries",
                        to="dimension.dimensionset",
                    ),
                ),
                migrations.AlterField(
                    model_name="purchasecreditmemo",
                    name="global_dimension_1",
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="purchase_credit_memo_headers",
                        to="dimension.dimensionvalue",
                        verbose_name="Global Dimension 1",
                    ),
                ),
                migrations.AlterField(
                    model_name="purchasecreditmemo",
                    name="dimension_set",
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="purchase_credit_memo_headers",
                        to="dimension.dimensionset",
                        verbose_name="Dimension Set",
                    ),
                ),
                migrations.AlterField(
                    model_name="purchasecreditmemoline",
                    name="global_dimension_1",
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="purchase_credit_memo_lines",
                        to="dimension.dimensionvalue",
                        verbose_name="Global Dimension 1",
                    ),
                ),
                migrations.AlterField(
                    model_name="purchasecreditmemoline",
                    name="dimension_set",
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="purchase_credit_memo_lines",
                        to="dimension.dimensionset",
                    ),
                ),
                migrations.AlterField(
                    model_name="detailedvendorledgerentry",
                    name="global_dimension_1",
                    field=models.ForeignKey(
                        help_text="Global Dimension 1 value",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="vendor_detailed_entries",
                        to="dimension.dimensionvalue",
                    ),
                ),
                migrations.AlterField(
                    model_name="detailedvendorledgerentry",
                    name="dimension_set",
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="vendor_detailed_entries",
                        to="dimension.dimensionset",
                    ),
                ),
            ],
            database_operations=[
                migrations.RunPython(_forwards, _backwards),
            ],
        ),
    ]
