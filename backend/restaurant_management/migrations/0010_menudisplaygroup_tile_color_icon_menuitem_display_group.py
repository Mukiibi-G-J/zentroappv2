import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("restaurant_management", "0009_fix_menu_rename_schema"),
    ]

    operations = [
        migrations.AddField(
            model_name="menudisplaygroup",
            name="tile_color",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Preset key or #RRGGBB for POS tile background.",
                max_length=16,
                verbose_name="Tile color",
            ),
        ),
        migrations.AddField(
            model_name="menudisplaygroup",
            name="icon",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Optional icon identifier for POS (e.g. react-icons export name).",
                max_length=64,
                verbose_name="Icon key",
            ),
        ),
        migrations.AddField(
            model_name="menuitem",
            name="display_group",
            field=models.ForeignKey(
                blank=True,
                help_text="POS display group for this menu (one group per item; null = ungrouped on home grid).",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="menu_items",
                to="restaurant_management.menudisplaygroup",
            ),
        ),
    ]
