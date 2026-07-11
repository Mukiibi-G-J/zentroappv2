import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("production", "0015_drop_legacy_source_no_id_if_duplicate_item_id"),
        ("dimension", "0007_dimension_backfill_audit_and_data"),
    ]

    operations = [
        migrations.AlterField(
            model_name="productionorderline",
            name="global_dimension_1",
            field=models.ForeignKey(
                help_text="Global Dimension 1 value",
                on_delete=django.db.models.deletion.PROTECT,
                related_name="production_order_lines_global_dimension_1",
                to="dimension.dimensionvalue",
                verbose_name="Global Dimension 1",
            ),
        ),
        migrations.AlterField(
            model_name="productionorderline",
            name="dimension_set",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="production_order_lines",
                to="dimension.dimensionset",
            ),
        ),
    ]
