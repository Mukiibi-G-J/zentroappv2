import django.db.models.deletion
from django.db import migrations, models
from django.utils.translation import gettext_lazy as _


class Migration(migrations.Migration):
    dependencies = [
        ("items", "0030_not_null_itemjournal_template_batch"),
    ]

    operations = [
        migrations.AlterField(
            model_name="itemjournal",
            name="global_dimension_1",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="item_journals_global_dim_1",
                to="dimension.dimensionvalue",
                verbose_name=_("Global Dimension 1"),
            ),
        ),
        migrations.AlterField(
            model_name="itemjournal",
            name="global_dimension_2",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="item_journals_global_dim_2",
                to="dimension.dimensionvalue",
                verbose_name=_("Global Dimension 2"),
            ),
        ),
        migrations.AlterField(
            model_name="itemjournal",
            name="dimension_set",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="item_journals",
                to="dimension.dimensionset",
                verbose_name=_("Dimension Set"),
            ),
        ),
    ]

