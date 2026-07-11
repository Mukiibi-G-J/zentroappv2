# Generated manually for context-sensitive table relations

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pages', '0003_rolecentre_cue_fields'),
    ]

    operations = [
        migrations.CreateModel(
            name='TableRelation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('source_table', models.CharField(max_length=200)),
                ('source_field', models.CharField(max_length=200)),
                ('related_table', models.CharField(max_length=200)),
                ('related_field', models.CharField(max_length=200)),
                ('display_field', models.CharField(max_length=200)),
                ('context_field', models.CharField(
                    blank=True,
                    help_text='When set with context_value, this row applies only for that context.',
                    max_length=200,
                )),
                ('context_value', models.CharField(blank=True, max_length=200)),
            ],
            options={
                'db_table': 'page_engine_table_relation',
                'unique_together': {('source_table', 'source_field', 'context_field', 'context_value')},
            },
        ),
    ]
