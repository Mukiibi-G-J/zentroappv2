import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pages', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='page',
            name='page_type',
            field=models.CharField(
                choices=[
                    ('List', 'List'),
                    ('Card', 'Card'),
                    ('Document', 'Document'),
                    ('ListPart', 'ListPart'),
                    ('Journal', 'Journal'),
                    ('Worksheet', 'Worksheet'),
                ],
                default='List',
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name='pagecontrol',
            name='control_type',
            field=models.CharField(
                choices=[
                    ('Group', 'Group'),
                    ('SubPage', 'SubPage'),
                    ('Repeater', 'Repeater'),
                    ('FactBox', 'FactBox'),
                    ('Part', 'Part'),
                ],
                default='Repeater',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='pagecontrol',
            name='link_field',
            field=models.CharField(
                blank=True,
                default='',
                help_text='For ControlType=Part: field on sub-table that links to parent PK',
                max_length=100,
            ),
        ),
        migrations.AddField(
            model_name='pagecontrol',
            name='part_page',
            field=models.ForeignKey(
                blank=True,
                help_text='For ControlType=Part: the sub-page to embed',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='used_as_part',
                to='pages.page',
            ),
        ),
    ]
