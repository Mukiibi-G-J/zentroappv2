from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("items", "0035_alter_valueentry_cost_per_unit"),
    ]

    operations = [
        migrations.AlterField(
            model_name="itemjournal",
            name="unit_amount",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                max_digits=15,
                null=True,
                verbose_name="Unit Amount",
            ),
        ),
        migrations.AlterField(
            model_name="itemjournal",
            name="amount",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                default=Decimal("0.00"),
                max_digits=15,
                null=True,
                verbose_name="Amount",
            ),
        ),
        migrations.AlterField(
            model_name="itemjournal",
            name="unit_cost",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                max_digits=15,
                null=True,
                verbose_name="Unit Cost",
            ),
        ),
    ]
