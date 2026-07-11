import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("restaurant_management", "0005_menuitem_tile_accent_color"),
    ]

    operations = [
        migrations.AddField(
            model_name="menuitem",
            name="service_menu",
            field=models.ForeignKey(
                blank=True,
                help_text="When set, this catalog row is scoped to that service menu (Menu Builder list).",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="menu_items",
                to="restaurant_management.servicemenu",
            ),
        ),
    ]
