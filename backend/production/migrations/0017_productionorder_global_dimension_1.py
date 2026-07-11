import django.db.models.deletion
from django.db import migrations, models


def backfill_production_order_branch(apps, schema_editor):
    ProductionOrder = apps.get_model("production", "ProductionOrder")
    ProductionOrderLine = apps.get_model("production", "ProductionOrderLine")
    for po in ProductionOrder.objects.filter(global_dimension_1_id__isnull=True).iterator():
        line = (
            ProductionOrderLine.objects.filter(production_order_id=po.id)
            .order_by("id")
            .first()
        )
        if line and line.global_dimension_1_id:
            po.global_dimension_1_id = line.global_dimension_1_id
            po.save(update_fields=["global_dimension_1_id"])


class Migration(migrations.Migration):

    dependencies = [
        ("production", "0016_not_null_branch_dimensions"),
        ("dimension", "0007_dimension_backfill_audit_and_data"),
    ]

    operations = [
        migrations.AddField(
            model_name="productionorder",
            name="global_dimension_1",
            field=models.ForeignKey(
                blank=True,
                help_text="Branch for list filtering and posting; set on create and refresh",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="branch_production_orders",
                to="dimension.dimensionvalue",
                verbose_name="Global Dimension 1",
            ),
        ),
        migrations.AddIndex(
            model_name="productionorder",
            index=models.Index(
                fields=["global_dimension_1"],
                name="production__global_d_idx",
            ),
        ),
        migrations.RunPython(backfill_production_order_branch, migrations.RunPython.noop),
    ]
