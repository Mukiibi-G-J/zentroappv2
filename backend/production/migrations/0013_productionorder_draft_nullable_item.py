import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("production", "0012_align_productionorder_item_fk_type"),
    ]

    operations = [
        migrations.AlterField(
            model_name="productionorder",
            name="item",
            field=models.ForeignKey(
                blank=True,
                help_text="Item to produce (must have a Production BOM); optional while order is draft",
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="production_orders",
                to="items.item",
                verbose_name="Item",
            ),
        ),
        migrations.AlterField(
            model_name="productionorder",
            name="status",
            field=models.CharField(
                choices=[
                    ("draft", "Draft"),
                    ("released", "Released"),
                    ("finished", "Finished"),
                ],
                default="released",
                help_text="Status of the production order",
                max_length=20,
                verbose_name="Status",
            ),
        ),
    ]
