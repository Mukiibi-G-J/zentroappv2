# Generated manually for covers picker / "No covers" support

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("restaurant_management", "0012_floorsection_table_section_plan_size"),
    ]

    operations = [
        migrations.AlterField(
            model_name="restaurantorder",
            name="covers",
            field=models.PositiveIntegerField(
                blank=True,
                default=1,
                help_text="Number of guests (covers) for this order/check; null when not tracked (No covers).",
                null=True,
                verbose_name="Covers",
            ),
        ),
    ]
