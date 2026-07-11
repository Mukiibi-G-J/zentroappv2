import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("loans", "0004_add_global_dimension_1"),
        ("dimension", "0007_dimension_backfill_audit_and_data"),
    ]

    operations = [
        migrations.AlterField(
            model_name="loan",
            name="global_dimension_1",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="loans",
                to="dimension.dimensionvalue",
                verbose_name="Global Dimension 1 (Branch)",
            ),
        ),
        migrations.AlterField(
            model_name="loanrepayment",
            name="global_dimension_1",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="loan_repayments",
                to="dimension.dimensionvalue",
                verbose_name="Global Dimension 1 (Branch)",
            ),
        ),
    ]
