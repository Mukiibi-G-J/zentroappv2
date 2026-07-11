from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pages', '0008_page_type_pos'),
    ]

    operations = [
        migrations.AddField(
            model_name='pagecontrolfield',
            name='relation_lookup_footer',
            field=models.BooleanField(
                default=False,
                help_text='Show BC-style relation menu footer (+ New, Show details, Select from full list).',
            ),
        ),
        migrations.AddField(
            model_name='pagecontrolfield',
            name='relation_part_control_name',
            field=models.CharField(
                blank=True,
                help_text='PageControl name of the Part to scroll to / add lines on for relation footer actions.',
                max_length=200,
                null=True,
            ),
        ),
    ]
