from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("restaurant_management", "0004_menuitem_kitchen_facing_name"),
    ]

    operations = [
        migrations.AddField(
            model_name="menuitem",
            name="tile_accent_color",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Preset key or #RRGGBB for POS tile / title strip when layout tile has no override.",
                max_length=16,
                verbose_name="Tile accent color",
            ),
        ),
    ]
