from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0011_customuser_restaurant_pin_hash"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql="""
                        ALTER TABLE authentication_usersetup
                        ADD COLUMN IF NOT EXISTS can_view_only_their_sales BOOLEAN NOT NULL DEFAULT TRUE;
                    """,
                    reverse_sql=migrations.RunSQL.noop,
                ),
            ],
            state_operations=[
                migrations.AddField(
                    model_name="usersetup",
                    name="can_view_only_their_sales",
                    field=models.BooleanField(
                        default=True,
                        help_text="When enabled, Sales History shows only sales made by this user",
                    ),
                ),
            ],
        ),
    ]
