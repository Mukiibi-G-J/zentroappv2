# Generated manually for ribbon action dropdown groups (BC Apply Entries menu).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pages', '0016_user_settings_username_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='pageaction',
            name='ribbon_group',
            field=models.CharField(
                blank=True,
                help_text=(
                    'When set, actions sharing the same ribbon_group on a tab '
                    'render as one dropdown menu. The group value is the menu caption '
                    '(e.g. "Apply Entries").'
                ),
                max_length=100,
                null=True,
            ),
        ),
    ]
