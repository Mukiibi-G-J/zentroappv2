from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("items", "0032_repair_phys_inventory_ledger_entry_table"),
    ]

    operations = [
        migrations.AddField(
            model_name="item",
            name="minimum_stock",
            field=models.PositiveIntegerField(
                blank=True,
                help_text="Reorder threshold; item is low stock when on-hand is at or below this value.",
                null=True,
                verbose_name="Minimum Stock",
            ),
        ),
    ]
