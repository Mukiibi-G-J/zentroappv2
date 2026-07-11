import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("restaurant_management", "0016_restaurantorder_global_dimension_1"),
        ("dimension", "0007_dimension_backfill_audit_and_data"),
    ]

    operations = [
        migrations.AlterField(
            model_name="restaurantorder",
            name="global_dimension_1",
            field=models.ForeignKey(
                help_text="Branch this order belongs to (set automatically from session context).",
                on_delete=django.db.models.deletion.PROTECT,
                related_name="restaurant_orders",
                to="dimension.dimensionvalue",
                verbose_name="Branch (Global Dimension 1)",
            ),
        ),
    ]
