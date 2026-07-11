# Repair tenant schemas where resources_resource.base_unit_id was added as bigint
# (via add_missing_tenant_columns) instead of varchar FK to items_unitofmeasure(code).

import django.db.models.deletion
from django.db import migrations, models


def _table_exists(schema_editor, table_name: str) -> bool:
    connection = schema_editor.connection
    with connection.cursor() as cursor:
        if connection.vendor == "postgresql":
            cursor.execute(
                """
                SELECT 1
                FROM pg_catalog.pg_tables
                WHERE schemaname = current_schema()
                  AND tablename = %s
                """,
                [table_name],
            )
        else:
            cursor.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = %s",
                [table_name],
            )
        return cursor.fetchone() is not None


def _column_type(schema_editor, table_name: str, column_name: str) -> str | None:
    connection = schema_editor.connection
    with connection.cursor() as cursor:
        if connection.vendor == "postgresql":
            cursor.execute(
                """
                SELECT data_type
                FROM information_schema.columns
                WHERE table_schema = current_schema()
                  AND table_name = %s
                  AND column_name = %s
                """,
                [table_name, column_name],
            )
        else:
            cursor.execute(
                f'PRAGMA table_info("{table_name}")',
            )
            for row in cursor.fetchall():
                if row[1] == column_name:
                    return row[2].lower()
            return None
        row = cursor.fetchone()
        return row[0] if row else None


def _column_exists(schema_editor, table_name: str, column_name: str) -> bool:
    return _column_type(schema_editor, table_name, column_name) is not None


def _drop_fk_constraints(schema_editor, table_name: str, column_name: str) -> None:
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT conname
            FROM pg_constraint
            WHERE conrelid = %s::regclass
              AND contype = 'f'
              AND conkey = (
                  SELECT ARRAY[attnum]
                  FROM pg_attribute
                  WHERE attrelid = %s::regclass
                    AND attname = %s
                    AND NOT attisdropped
              )
            """,
            [table_name, table_name, column_name],
        )
        for (conname,) in cursor.fetchall():
            cursor.execute(
                f'ALTER TABLE "{table_name}" DROP CONSTRAINT IF EXISTS "{conname}"'
            )


def forwards(apps, schema_editor):
    table = "resources_resource"
    column = "base_unit_id"
    if not _table_exists(schema_editor, table):
        return
    if not _column_exists(schema_editor, table, column):
        return
    if _column_type(schema_editor, table, column) != "bigint":
        return

    connection = schema_editor.connection
    with connection.cursor() as cursor:
        _drop_fk_constraints(schema_editor, table, column)

        if connection.vendor == "postgresql":
            cursor.execute(
                f"""
                ALTER TABLE "{table}"
                ALTER COLUMN "{column}" TYPE varchar(10)
                USING CASE
                    WHEN "{column}" IS NULL THEN NULL
                    ELSE "{column}"::varchar(10)
                END
                """
            )
        else:
            cursor.execute(
                f'ALTER TABLE "{table}" RENAME COLUMN "{column}" TO "{column}_old"'
            )
            cursor.execute(
                f'ALTER TABLE "{table}" ADD COLUMN "{column}" varchar(10) NULL'
            )
            cursor.execute(
                f"""
                UPDATE "{table}"
                SET "{column}" = CAST("{column}_old" AS TEXT)
                WHERE "{column}_old" IS NOT NULL
                """
            )
            cursor.execute(f'ALTER TABLE "{table}" DROP COLUMN "{column}_old"')

        if _column_exists(schema_editor, table, "base_unit"):
            cursor.execute(
                f"""
                UPDATE "{table}"
                SET "{column}" = "base_unit"
                WHERE "{column}" IS NULL
                  AND "base_unit" IS NOT NULL
                  AND TRIM("base_unit") <> ''
                """
            )

        if connection.vendor == "postgresql":
            cursor.execute(
                f"""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_constraint
                        WHERE conname = 'resources_resource_base_unit_id_fk_items_uom_code'
                    ) THEN
                        ALTER TABLE "{table}"
                        ADD CONSTRAINT resources_resource_base_unit_id_fk_items_uom_code
                        FOREIGN KEY ("{column}")
                        REFERENCES items_unitofmeasure (code)
                        ON DELETE SET NULL
                        DEFERRABLE INITIALLY DEFERRED;
                    END IF;
                END $$;
                """
            )

        if _column_exists(schema_editor, table, "base_unit"):
            cursor.execute(f'ALTER TABLE "{table}" DROP COLUMN "base_unit"')


class Migration(migrations.Migration):
    """
    Fix resources_resource.base_unit_id stored as bigint on some tenant schemas.
    UnitOfMeasure uses code (varchar) as primary key; bigint breaks SET_NULL on delete.
    """

    dependencies = [
        ("items", "0001_initial"),
        ("resources", "0007_repair_resourceunitofmeasure_table"),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="resource",
            name="base_unit",
            field=models.ForeignKey(
                blank=True,
                help_text="Unit of measurement for this resource (same model as items)",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="resources_using_as_base",
                to="items.unitofmeasure",
                to_field="code",
                verbose_name="Base Unit",
            ),
        ),
    ]
