from django.db import migrations, models


def apply_desktop_flags(apps, schema_editor):
    Page = apps.get_model('pages', 'Page')
    from pages.desktop_pages import DESKTOP_ENABLED_PAGE_NAMES

    Page.objects.all().update(desktop_enabled=False)
    Page.objects.filter(name__in=DESKTOP_ENABLED_PAGE_NAMES).update(desktop_enabled=True)


class Migration(migrations.Migration):

    dependencies = [
        ('pages', '0013_page_object_id'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql="""
                        ALTER TABLE page_engine_page
                        ADD COLUMN IF NOT EXISTS desktop_enabled BOOLEAN NOT NULL DEFAULT FALSE;
                    """,
                    reverse_sql=migrations.RunSQL.noop,
                ),
            ],
            state_operations=[
                migrations.AddField(
                    model_name='page',
                    name='desktop_enabled',
                    field=models.BooleanField(
                        default=False,
                        help_text='When true, this page is available in the Zentro Desktop Electron app.',
                    ),
                ),
            ],
        ),
        migrations.RunPython(apply_desktop_flags, migrations.RunPython.noop),
    ]
