from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0016_alter_customuser_phone_number"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql="""
                        ALTER TABLE authentication_usersetup
                        ADD COLUMN IF NOT EXISTS can_reverse_item_journal BOOLEAN NOT NULL DEFAULT FALSE;
                    """,
                    reverse_sql=migrations.RunSQL.noop,
                ),
            ],
            state_operations=[
                migrations.AddField(
                    model_name="usersetup",
                    name="can_reverse_item_journal",
                    field=models.BooleanField(
                        default=False,
                        help_text=(
                            "Allow user to reverse posted item journals from Django admin "
                            "(preview reversing G/L, item ledger, and value entries before applying)."
                        ),
                    ),
                ),
            ],
        ),
    ]
