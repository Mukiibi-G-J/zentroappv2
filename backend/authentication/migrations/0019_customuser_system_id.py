import uuid

from django.db import migrations, models
import utils.utils


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


def apply_system_id(apps, schema_editor):
    """
    Add + backfill system_id when missing.

    Restored V1→V2 tenant dumps often already have the column while
    django_migrations is still at 0018 — plain AddField then fails with
    DuplicateColumn and aborts migrate_schemas for every remaining tenant.

    Use SQL only: SeparateDatabaseAndState RunPython sees the *pre*-AddField
    historical model, so ORM filters on system_id would raise FieldError.
    """
    with schema_editor.connection.cursor() as cursor:
        if not _pg_column_exists(cursor, "authentication_customuser", "system_id"):
            cursor.execute(
                """
                ALTER TABLE authentication_customuser
                ADD COLUMN system_id varchar(36) NULL
                """
            )

        cursor.execute(
            """
            UPDATE authentication_customuser
            SET system_id = gen_random_uuid()::text
            WHERE system_id IS NULL OR system_id = ''
            """
        )
        cursor.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS authentication_customuser_system_id_key
            ON authentication_customuser (system_id)
            """
        )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0018_devicepushtoken"),
    ]

    operations = [
        # Keep Django model state in sync without assuming the DB column is absent.
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name="customuser",
                    name="system_id",
                    field=models.CharField(
                        max_length=36,
                        null=True,
                        editable=False,
                    ),
                ),
                migrations.AlterField(
                    model_name="customuser",
                    name="system_id",
                    field=utils.utils.UUIField(
                        db_index=True,
                        default=uuid.uuid4,
                        editable=False,
                        max_length=36,
                        unique=True,
                        verbose_name="System ID",
                    ),
                ),
            ],
            database_operations=[
                migrations.RunPython(apply_system_id, noop_reverse),
            ],
        ),
    ]
