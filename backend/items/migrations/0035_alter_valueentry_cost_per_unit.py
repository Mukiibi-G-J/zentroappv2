from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("items", "0034_add_performance_indexes"),
    ]

    operations = [
        migrations.AlterField(
            model_name="valueentry",
            name="cost_per_unit",
            field=models.FloatField(default=0, verbose_name="Cost Per Unit"),
        ),
    ]
