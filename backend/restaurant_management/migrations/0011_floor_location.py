import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("items", "0001_initial"),
        ("restaurant_management", "0010_menudisplaygroup_tile_color_icon_menuitem_display_group"),
    ]

    operations = [
        migrations.AddField(
            model_name="floor",
            name="location",
            field=models.ForeignKey(
                blank=True,
                help_text="Inventory location this floor plan belongs to (e.g. branch / site).",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="restaurant_floors",
                to="items.location",
            ),
        ),
    ]
