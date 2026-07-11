import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("dimension", "0006_add_shortcut_dimensions_to_general_ledger_setup"),
        ("restaurant_management", "0015_menuitem_routes_to_kitchen"),
    ]

    operations = [
        migrations.AddField(
            model_name="restaurantorder",
            name="global_dimension_1",
            field=models.ForeignKey(
                blank=True,
                help_text="Branch this order belongs to (set automatically from session context).",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="restaurant_orders",
                to="dimension.dimensionvalue",
                verbose_name="Branch (Global Dimension 1)",
            ),
        ),
    ]
