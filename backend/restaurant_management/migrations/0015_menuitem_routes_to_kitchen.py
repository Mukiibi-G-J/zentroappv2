# Manual migration: per-menu-item KDS routing override

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("restaurant_management", "0014_menucategory_routes_to_kitchen"),
    ]

    operations = [
        migrations.AddField(
            model_name="menuitem",
            name="routes_to_kitchen",
            field=models.BooleanField(
                blank=True,
                help_text="If set, overrides the category for Fire/KDS routing. If unset, use the menu category flag.",
                null=True,
                verbose_name="Routes to kitchen / KDS",
            ),
        ),
    ]
