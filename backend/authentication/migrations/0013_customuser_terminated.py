from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0012_usersetup_can_view_only_their_sales"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql="""
                        ALTER TABLE authentication_customuser
                        ADD COLUMN IF NOT EXISTS terminated BOOLEAN NOT NULL DEFAULT FALSE;
                    """,
                    reverse_sql=migrations.RunSQL.noop,
                ),
            ],
            state_operations=[
                migrations.AddField(
                    model_name="customuser",
                    name="terminated",
                    field=models.BooleanField(
                        default=False,
                        help_text="When true, user is terminated and hidden from user lists.",
                    ),
                ),
            ],
        ),
    ]
