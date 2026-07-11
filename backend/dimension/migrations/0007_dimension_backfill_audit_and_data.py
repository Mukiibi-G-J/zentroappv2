# Branch / dimension set backfill (idempotent) + audit table for rollback

from django.db import migrations, models


def forward_backfill(apps, schema_editor):
    from dimension.backfill import run_branch_dimension_backfill

    # django-tenants runs migrations for the public schema too. Public may not have tenant-only
    # tables (e.g. financials_generalledgersetup), so the backfill must be a no-op there.
    required_tables = {
        "dimension_dimensionvalue",
        "dimension_dimension",
        "financials_generalledgersetup",
    }
    existing = set(schema_editor.connection.introspection.table_names())
    if not required_tables.issubset(existing):
        return

    def _has_column(table: str, column: str) -> bool:
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

    # Some legacy schemas may have old dimension tables without Django's BigAutoField `id`.
    # If so, skip backfill so migrations can continue (backfill can be run later after repair).
    if not _has_column("dimension_dimension", "id"):
        return

    # Prefer first branch by code if multiple values exist (legacy tenants).
    results, err = run_branch_dimension_backfill(
        allow_multiple_branch_values=True,
        write_audit=True,
    )
    if err:
        raise ValueError(f"Branch dimension backfill: {err}")
    import logging
    import django.db

    log = logging.getLogger(__name__)
    schema = getattr(django.db.connection, "schema_name", None) or "?"
    log.info("dimension backfill in schema %s: %s", schema, results)


def reverse_backfill(apps, schema_editor):
    from dimension.backfill import reverse_branch_dimension_backfill

    reverse_branch_dimension_backfill()


class Migration(migrations.Migration):

    dependencies = [
        ("dimension", "0006_add_shortcut_dimensions_to_general_ledger_setup"),
    ]

    operations = [
        migrations.CreateModel(
            name="DimensionBackfillAudit",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("app_label", models.CharField(db_index=True, max_length=100)),
                ("model_name", models.CharField(db_index=True, max_length=100)),
                ("object_id", models.BigIntegerField()),
                (
                    "prev_global_dimension_1_id",
                    models.IntegerField(blank=True, null=True),
                ),
                (
                    "prev_global_dimension_2_id",
                    models.IntegerField(blank=True, null=True),
                ),
                (
                    "prev_dimension_set_id",
                    models.IntegerField(blank=True, null=True),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "db_table": "dimension_backfill_audit",
            },
        ),
        migrations.AddIndex(
            model_name="dimensionbackfillaudit",
            index=models.Index(
                fields=["app_label", "model_name", "object_id"],
                name="dimension_b_app_lab_585f37_idx",
            ),
        ),
        migrations.RunPython(forward_backfill, reverse_backfill),
    ]
