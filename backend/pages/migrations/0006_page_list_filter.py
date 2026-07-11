from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pages', '0005_pageaction_action_type'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql="""
                        ALTER TABLE page_engine_page
                        ADD COLUMN IF NOT EXISTS list_filter_field VARCHAR(200) NOT NULL DEFAULT '';
                        ALTER TABLE page_engine_page
                        ADD COLUMN IF NOT EXISTS list_filter_value VARCHAR(200) NOT NULL DEFAULT '';
                    """,
                    reverse_sql=migrations.RunSQL.noop,
                ),
            ],
            state_operations=[
                migrations.AddField(
                    model_name='page',
                    name='list_filter_field',
                    field=models.CharField(
                        blank=True,
                        help_text='When set with list_filter_value, list pages show only matching records (e.g. status=Posted).',
                        max_length=200,
                    ),
                ),
                migrations.AddField(
                    model_name='page',
                    name='list_filter_value',
                    field=models.CharField(
                        blank=True,
                        help_text='Value for list_filter_field (e.g. Posted, Open).',
                        max_length=200,
                    ),
                ),
            ],
        ),
    ]
