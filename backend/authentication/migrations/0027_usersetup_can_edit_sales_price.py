from django.db import migrations, models


def add_can_edit_sales_price_if_not_exists(apps, schema_editor):
    """Add can_edit_sales_price only when authentication_usersetup exists in this schema."""
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT 1
            FROM information_schema.tables
            WHERE table_name = 'authentication_usersetup'
              AND table_schema = current_schema()
            """
        )
        if not cursor.fetchone():
            return

        cursor.execute(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_name = 'authentication_usersetup'
              AND column_name = 'can_edit_sales_price'
              AND table_schema = current_schema()
            """
        )
        if cursor.fetchone():
            return

        cursor.execute(
            """
            ALTER TABLE authentication_usersetup
            ADD COLUMN can_edit_sales_price BOOLEAN NOT NULL DEFAULT FALSE
            """
        )


def reverse_add_can_edit_sales_price(apps, schema_editor):
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_name = 'authentication_usersetup'
              AND column_name = 'can_edit_sales_price'
              AND table_schema = current_schema()
            """
        )
        if not cursor.fetchone():
            return

        cursor.execute(
            """
            ALTER TABLE authentication_usersetup
            DROP COLUMN can_edit_sales_price
            """
        )


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0026_impersonationauditlog_schema_name"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(
                    add_can_edit_sales_price_if_not_exists,
                    reverse_add_can_edit_sales_price,
                ),
            ],
            state_operations=[
                migrations.AddField(
                    model_name="usersetup",
                    name="can_edit_sales_price",
                    field=models.BooleanField(
                        default=False,
                        help_text="Allow user to edit unit prices on Sales/POS",
                    ),
                ),
            ],
        ),
    ]
