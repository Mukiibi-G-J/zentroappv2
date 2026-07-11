# Generated manually for kitchen vs non-kitchen category routing

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("restaurant_management", "0013_restaurantorder_covers_nullable"),
    ]

    operations = [
        migrations.AddField(
            model_name="menucategory",
            name="routes_to_kitchen",
            field=models.BooleanField(
                default=True,
                help_text="When enabled, items in this category are sent to the kitchen on Fire. Disable for bar-only categories (e.g. drinks) so they skip KDS.",
                verbose_name="Routes to kitchen / KDS",
            ),
        ),
    ]
