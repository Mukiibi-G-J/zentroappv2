from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pages', '0009_pagecontrolfield_relation_lookup_footer'),
    ]

    operations = [
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
                    ('CueGroup', 'Cue Group'),
                    ('Cue', 'Cue'),
                    ('HeadlineGroup', 'Headline Group'),
                    ('Headline', 'Headline'),
                ],
                default='Repeater',
                max_length=20,
            ),
        ),
    ]
