from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sales", "0017_repair_sales_line_type_resource_drift"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="customer",
            index=models.Index(
                fields=["updated_at", "id"],
                name="sales_cust_upd_id_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="customerledgerentry",
            index=models.Index(
                fields=["customer", "open"],
                name="sales_cle_cust_open_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="customerledgerentry",
            index=models.Index(
                fields=["open", "posting_date"],
                name="sales_cle_open_date_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="postedsalesinvoice",
            index=models.Index(
                fields=["posting_date"],
                name="sales_psi_post_date_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="postedsalesinvoice",
            index=models.Index(
                fields=["customer", "posting_date"],
                name="sales_psi_cust_date_idx",
            ),
        ),
    ]
