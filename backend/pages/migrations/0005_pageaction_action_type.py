from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pages', '0004_tablerelation'),
    ]

    operations = [
        migrations.AddField(
            model_name='pageaction',
            name='action_type',
            field=models.CharField(
                choices=[('Ribbon', 'Ribbon'), ('NavItem', 'Nav Item')],
                default='Ribbon',
                help_text='Ribbon = card/worksheet actions; NavItem = Role Centre sidebar links',
                max_length=20,
            ),
        ),
    ]
