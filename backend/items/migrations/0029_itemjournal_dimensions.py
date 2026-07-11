# Generated manually: add ItemJournal dimensions + backfill (drift-safe)

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


def add_columns_if_missing(apps, schema_editor):
    """
    Some tenants may have schema drift; add missing dimension columns for ItemJournal.
    Keep columns nullable; NOT NULL constraints are handled separately (if desired).
    """
    if schema_editor.connection.vendor != "postgresql":
        raise NotImplementedError("This migration only supports PostgreSQL")
    with schema_editor.connection.cursor() as cursor:
        table = "items_itemjournal"
        specs = [
            ("global_dimension_1_id", "dimension_dimensionvalue"),
            ("global_dimension_2_id", "dimension_dimensionvalue"),
            ("dimension_set_id", "dimension_dimensionset"),
        ]
        for col, ref_table in specs:
            if _pg_column_exists(cursor, table, col):
                continue
            cursor.execute(
                f"""
                ALTER TABLE {table}
                ADD COLUMN {col} bigint NULL
                REFERENCES {ref_table}(id)
                ON DELETE SET NULL
                """
            )


def backfill_itemjournal_dimensions(apps, schema_editor):
    """
    Backfill dimensions for ItemJournal:
    - Posted journals: copy from the first ItemLedgerEntries row for the same document_no.
    - Open journals: use user.global_dimension_1 (and optional G2), then build dimension_set.

    All operations are best-effort and drift-safe (skips if required columns/tables are missing).
    """
    # NOTE: This migration uses SeparateDatabaseAndState. The historical ItemJournal
    # model passed into RunPython may not yet expose the new fields. Therefore, we
    # backfill using SQL writes to the columns directly (drift-safe).
    ItemJournal = apps.get_model("items", "ItemJournal")
    ItemLedgerEntries = apps.get_model("items", "ItemLedgerEntries")

    # Use runtime models for dimension resolution to avoid class mismatches between
    # historical `apps.get_model()` classes and the runtime `dimension.models.Dimension`.
    from authentication.models import CustomUser as RuntimeUser
    from financials.models import GeneralLedgerSetup as RuntimeGeneralLedgerSetup
    from dimension.models import get_posting_dimension_payload
    from dimension.utils import resolve_default_branch_for_tenant

    def qn(name: str) -> str:
        return schema_editor.quote_name(name)

    with schema_editor.connection.cursor() as cursor:
        t = ItemJournal._meta.db_table
        needed_cols = ["global_dimension_1_id", "dimension_set_id", "global_dimension_2_id"]
        for c in needed_cols:
            if not _pg_column_exists(cursor, t, c):
                return

    gl = RuntimeGeneralLedgerSetup.objects.first()

    # 1) Posted journals: copy from ItemLedgerEntries when possible
    with schema_editor.connection.cursor() as cursor:
        ij_t = ItemJournal._meta.db_table
        ile_t = ItemLedgerEntries._meta.db_table
        cursor.execute(
            f"""
            UPDATE {qn(ij_t)} ij
            SET
              global_dimension_1_id = COALESCE(ij.global_dimension_1_id, ile.global_dimension_1_id),
              global_dimension_2_id = COALESCE(ij.global_dimension_2_id, ile.global_dimension_2_id),
              dimension_set_id = COALESCE(ij.dimension_set_id, ile.dimension_set_id)
            FROM {qn(ile_t)} ile
            WHERE ij.status <> 'Open'
              AND ij.document_no = ile.document_no
              AND (
                ij.global_dimension_1_id IS NULL
                OR ij.global_dimension_2_id IS NULL
                OR ij.dimension_set_id IS NULL
              )
            """
        )

    # 2) Open journals: use user branch (G1), compute DS (+G2) from posting payload
    # If user has no branch, fall back to tenant default branch resolver.
    for j in ItemJournal.objects.filter(status__iexact="Open").only(
        "pk", "user_id", "document_no"
    ).iterator(
        chunk_size=200
    ):
        user = RuntimeUser.objects.filter(pk=j.user_id).first() if j.user_id else None
        g1 = getattr(user, "global_dimension_1", None) if user else None
        g2 = getattr(user, "global_dimension_2", None) if user else None

        if g1 is None:
            g1, _ds, _err = resolve_default_branch_for_tenant(allow_multiple_branch_values=True)

        payload = get_posting_dimension_payload(
            global_dimension_1=g1,
            global_dimension_2=g2,
            gl_setup=gl,
        )
        ds = payload.get("dimension_set")
        g1o = payload.get("global_dimension_1") or g1
        g2o = payload.get("global_dimension_2") or g2

        g1_id = getattr(g1o, "pk", None)
        g2_id = getattr(g2o, "pk", None)
        ds_id = getattr(ds, "pk", None)
        if not g1_id and not g2_id and not ds_id:
            continue

        with schema_editor.connection.cursor() as cursor:
            cursor.execute(
                f"""
                UPDATE {qn(ItemJournal._meta.db_table)}
                SET
                  global_dimension_1_id = COALESCE(global_dimension_1_id, %s),
                  global_dimension_2_id = COALESCE(global_dimension_2_id, %s),
                  dimension_set_id = COALESCE(dimension_set_id, %s)
                WHERE id = %s
                """,
                [g1_id, g2_id, ds_id, j.pk],
            )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("items", "0028_not_null_branch_dimensions"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name="itemjournal",
                    name="global_dimension_1",
                    field=models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="item_journals_global_dim_1",
                        to="dimension.dimensionvalue",
                        verbose_name="Global Dimension 1",
                    ),
                ),
                migrations.AddField(
                    model_name="itemjournal",
                    name="global_dimension_2",
                    field=models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="item_journals_global_dim_2",
                        to="dimension.dimensionvalue",
                        verbose_name="Global Dimension 2",
                    ),
                ),
                migrations.AddField(
                    model_name="itemjournal",
                    name="dimension_set",
                    field=models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="item_journals",
                        to="dimension.dimensionset",
                        verbose_name="Dimension Set",
                    ),
                ),
            ],
            database_operations=[
                migrations.RunPython(add_columns_if_missing, noop_reverse),
                migrations.RunPython(backfill_itemjournal_dimensions, noop_reverse),
            ],
        ),
    ]

