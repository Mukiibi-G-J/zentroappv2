# Generated manually to fix missing column
from django.db import migrations, models


def add_can_post_previous_dates_if_not_exists(apps, schema_editor):
    """
    Add can_post_previous_dates field only if it doesn't exist.
    This handles cases where the column might have been added manually
    or already exists in some tenant schemas.
    """
    with schema_editor.connection.cursor() as cursor:
        # Check if column exists in current schema
        cursor.execute(
            """
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='authentication_usersetup' 
            AND column_name='can_post_previous_dates'
            AND table_schema = current_schema()
        """
        )
        exists = cursor.fetchone()

        if not exists:
            # Add the column if it doesn't exist
            cursor.execute(
                """
                ALTER TABLE authentication_usersetup 
                ADD COLUMN can_post_previous_dates BOOLEAN DEFAULT TRUE
            """
            )


def reverse_add_can_post_previous_dates(apps, schema_editor):
    """
    Remove the column if it exists (for reverse migration)
    """
    with schema_editor.connection.cursor() as cursor:
        # Check if column exists
        cursor.execute(
            """
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='authentication_usersetup' 
            AND column_name='can_post_previous_dates'
            AND table_schema = current_schema()
        """
        )
        exists = cursor.fetchone()

        if exists:
            # Remove the column if it exists
            cursor.execute(
                """
                ALTER TABLE authentication_usersetup 
                DROP COLUMN can_post_previous_dates
            """
            )


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0002_initial"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            # Database operation: conditionally add column if it doesn't exist
            database_operations=[
                migrations.RunPython(
                    add_can_post_previous_dates_if_not_exists,
                    reverse_add_can_post_previous_dates,
                ),
            ],
            # State operation: update Django's migration state
            state_operations=[
                migrations.AddField(
                    model_name="usersetup",
                    name="can_post_previous_dates",
                    field=models.BooleanField(
                        default=True,
                        help_text="Allow user to post sales or purchases for previous dates",
                    ),
                ),
            ],
        ),
    ]
