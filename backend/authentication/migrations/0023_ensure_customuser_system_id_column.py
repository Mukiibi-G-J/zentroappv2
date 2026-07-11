import uuid

from django.db import migrations


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


def add_system_id_if_missing(apps, schema_editor):
    """Repair schemas where 0019 is recorded but system_id was never created."""
    with schema_editor.connection.cursor() as cursor:
        if _pg_column_exists(cursor, "authentication_customuser", "system_id"):
            return
        cursor.execute(
            """
            ALTER TABLE authentication_customuser
            ADD COLUMN system_id varchar(36) NULL
            """
        )
        CustomUser = apps.get_model("authentication", "CustomUser")
        for user in CustomUser.objects.all().iterator():
            user.system_id = str(uuid.uuid4())
            user.save(update_fields=["system_id"])
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
        ("authentication", "0022_userpersonalization_role_fk"),
    ]

    operations = [
        migrations.RunPython(add_system_id_if_missing, noop_reverse),
    ]
