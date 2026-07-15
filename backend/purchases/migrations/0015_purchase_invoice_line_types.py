from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("financials", "0001_initial"),
        ("resources", "0001_initial"),
        ("purchases", "0014_ensure_vendorledger_payment_fk_column"),
    ]

    operations = [
        migrations.AddField(
            model_name="purchaseinvoiceline",
            name="type",
            field=models.CharField(
                choices=[
                    ("item", "Item"),
                    ("resource", "Resource"),
                    ("gl_account", "G/L Account"),
                ],
                default="item",
                help_text="Whether this line purchases an Item, Resource, or G/L Account (BC-style)",
                max_length=20,
                verbose_name="Line Type",
            ),
        ),
        migrations.AddField(
            model_name="purchaseinvoiceline",
            name="resource",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="purchase_invoice_lines",
                to="resources.resource",
                verbose_name="Resource",
            ),
        ),
        migrations.AddField(
            model_name="purchaseinvoiceline",
            name="gl_account",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="purchase_invoice_lines",
                to="financials.g_laccount",
                verbose_name="G/L Account",
            ),
        ),
        migrations.AlterField(
            model_name="purchaseinvoiceline",
            name="item",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="purchase_lines",
                to="items.item",
            ),
        ),
        migrations.AlterField(
            model_name="purchaseinvoiceline",
            name="location_code",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="location_purchase_lines",
                to="items.location",
            ),
        ),
        migrations.AddField(
            model_name="postedpurchaseinvoiceline",
            name="type",
            field=models.CharField(
                choices=[
                    ("item", "Item"),
                    ("resource", "Resource"),
                    ("gl_account", "G/L Account"),
                ],
                default="item",
                max_length=20,
                verbose_name="Line Type",
            ),
        ),
        migrations.AddField(
            model_name="postedpurchaseinvoiceline",
            name="resource",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="posted_purchase_invoice_lines",
                to="resources.resource",
                verbose_name="Resource",
            ),
        ),
        migrations.AddField(
            model_name="postedpurchaseinvoiceline",
            name="gl_account",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="posted_purchase_invoice_lines",
                to="financials.g_laccount",
                verbose_name="G/L Account",
            ),
        ),
        migrations.AlterField(
            model_name="postedpurchaseinvoiceline",
            name="item",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="posted_purchase_invoice_lines",
                to="items.item",
            ),
        ),
        migrations.AlterField(
            model_name="postedpurchaseinvoiceline",
            name="location_code",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="location_posted_purchase_invoice_lines",
                to="items.location",
            ),
        ),
    ]
