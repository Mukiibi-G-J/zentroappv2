import django.db.models.deletion
from django.db import migrations, models
from django.db.models import Q


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


def _ensure_expense_dimension_fks_if_missing(schema_editor):
    """
    Some schemas have dimension columns on expenses_expense but no FK metadata.
    Django's alter_field(..., strict=True) requires exactly one FK constraint.
    """
    c = schema_editor.connection.cursor()
    qn = schema_editor.connection.ops.quote_name

    c.execute(
        """
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = current_schema() AND table_name = 'expenses_expense'
        """
    )
    if not c.fetchone():
        return

    c.execute(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name = 'dimension_dimensionvalue'
          AND column_name = 'id'
        """
    )
    if not c.fetchone():
        return

    c.execute(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name = 'dimension_dimensionset'
          AND column_name = 'id'
        """
    )
    if not c.fetchone():
        return

    def _has_fk_on_column(column_name: str) -> bool:
        c.execute(
            """
            SELECT 1
            FROM pg_constraint con
            JOIN pg_class rel ON rel.oid = con.conrelid
            JOIN pg_namespace ns ON ns.oid = rel.relnamespace
            WHERE con.contype = 'f'
              AND ns.nspname = current_schema()
              AND rel.relname = 'expenses_expense'
              AND pg_get_constraintdef(con.oid) LIKE %s
            """,
            [f"%FOREIGN KEY ({column_name})%"],
        )
        return c.fetchone() is not None

    specs = [
        (
            "expenses_expense_dimension_set_id_67c151a3_fk_dimension",
            "dimension_set_id",
            "dimension_dimensionset",
            "id",
        ),
        (
            "expenses_expense_global_dimension_1_i_13c8f272_fk_dimension",
            "global_dimension_1_id",
            "dimension_dimensionvalue",
            "id",
        ),
        (
            "expenses_expense_global_dimension_2_i_4a6d9357_fk_dimension",
            "global_dimension_2_id",
            "dimension_dimensionvalue",
            "id",
        ),
    ]

    for conname, col, reftable, refcol in specs:
        if _has_fk_on_column(col):
            continue
        c.execute(
            """
            SELECT 1 FROM pg_constraint con
            JOIN pg_class rel ON rel.oid = con.conrelid
            JOIN pg_namespace ns ON ns.oid = rel.relnamespace
            WHERE con.contype = 'f'
              AND ns.nspname = current_schema()
              AND rel.relname = 'expenses_expense'
              AND con.conname = %s
            """,
            [conname],
        )
        if c.fetchone():
            continue
        c.execute(
            f"""
            ALTER TABLE {qn("expenses_expense")}
            ADD CONSTRAINT {qn(conname)}
            FOREIGN KEY ({qn(col)})
            REFERENCES {qn(reftable)} ({qn(refcol)})
            """
        )


def enforce_expense_not_nulls(apps, schema_editor):
    """
    Backfill then enforce NOT NULL / PROTECT for Expense dimensions.
    Skip on legacy schema drift so tenant migrations can proceed.
    """
    _ensure_expense_dimension_fks_if_missing(schema_editor)

    table = "expenses_expense"
    if not _column_exists(schema_editor, table, "global_dimension_1_id"):
        return
    if not _column_exists(schema_editor, table, "dimension_set_id"):
        return

    from dimension.backfill import run_branch_dimension_backfill

    _, err = run_branch_dimension_backfill(
        allow_multiple_branch_values=True,
        write_audit=True,
    )
    if err and (
        err.startswith("SCHEMA_DRIFT:")
        or err.startswith("No branch dimension:")
        or err.startswith("No DimensionValue for dimension")
    ):
        return
    if err:
        raise ValueError(f"Branch dimension backfill (expenses.0004): {err}")

    Expense = apps.get_model("expenses", "Expense")

    # _backfill_model can soft-skip (schema drift) without failing the aggregate
    # backfill—rows would still be NULL here and AlterField below would abort the
    # whole migration txn (PostgreSQL "current transaction is aborted").
    if Expense.objects.filter(
        Q(global_dimension_1_id__isnull=True) | Q(dimension_set_id__isnull=True)
    ).exists():
        return

    DimensionValue = apps.get_model("dimension", "DimensionValue")
    DimensionSet = apps.get_model("dimension", "DimensionSet")

    old_g1 = Expense._meta.get_field("global_dimension_1")
    new_g1 = models.ForeignKey(
        on_delete=django.db.models.deletion.PROTECT,
        related_name="expense_headers",
        to=DimensionValue,
        verbose_name="Global Dimension 1",
    )
    new_g1.set_attributes_from_name("global_dimension_1")
    new_g1.model = Expense
    schema_editor.alter_field(Expense, old_g1, new_g1, strict=True)

    old_ds = Expense._meta.get_field("dimension_set")
    new_ds = models.ForeignKey(
        on_delete=django.db.models.deletion.PROTECT,
        related_name="expense_headers",
        to=DimensionSet,
        verbose_name="Dimension Set",
    )
    new_ds.set_attributes_from_name("dimension_set")
    new_ds.model = Expense
    schema_editor.alter_field(Expense, old_ds, new_ds, strict=True)


class Migration(migrations.Migration):
    # Non-atomic migration + RunPython(..., atomic=False): bulk UPDATE + schema_editor DDL
    # should not fight PostgreSQL deferred-constraint bookkeeping the way one big txn can.
    atomic = False

    dependencies = [
        ("expenses", "0003_add_dimension_fields_to_expense"),
        ("dimension", "0007_dimension_backfill_audit_and_data"),
        ("dimension", "0008_repair_missing_id_pk"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterField(
                    model_name="expense",
                    name="global_dimension_1",
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="expense_headers",
                        to="dimension.dimensionvalue",
                        verbose_name="Global Dimension 1",
                    ),
                ),
                migrations.AlterField(
                    model_name="expense",
                    name="dimension_set",
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="expense_headers",
                        to="dimension.dimensionset",
                        verbose_name="Dimension Set",
                    ),
                ),
            ],
            database_operations=[
                migrations.RunPython(
                    enforce_expense_not_nulls,
                    migrations.RunPython.noop,
                    atomic=False,
                )
            ],
        )
    ]
