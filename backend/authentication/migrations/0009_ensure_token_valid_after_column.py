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


def add_token_valid_after_if_missing(apps, schema_editor):
    """Repair schemas where 0008 is recorded but the column was never created."""
    with schema_editor.connection.cursor() as cursor:
        if _pg_column_exists(cursor, "authentication_customuser", "token_valid_after"):
            return
        cursor.execute(
            """
            ALTER TABLE authentication_customuser
            ADD COLUMN token_valid_after timestamp with time zone NULL
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS authentication_customuser_token_valid_after
            ON authentication_customuser (token_valid_after)
            """
        )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0008_customuser_token_valid_after"),
    ]

    operations = [
        migrations.RunPython(add_token_valid_after_if_missing, noop_reverse),
    ]
