# Generated manually - Remove unique constraint from dimension_type

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("dimension", "0004_add_dimension_set_models"),
    ]

    operations = [
        migrations.AlterField(
            model_name="dimensionvalue",
            name="dimension_type",
            field=models.CharField(
                choices=[("Standard", "Standard"), ("Custom", "Custom")],
                max_length=255,
            ),
        ),
    ]
