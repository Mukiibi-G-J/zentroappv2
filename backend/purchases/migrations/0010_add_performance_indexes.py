from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("purchases", "0009_not_null_branch_dimensions"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="vendor",
            index=models.Index(
                fields=["updated_at", "id"],
                name="purch_vend_upd_id_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="vendorledger",
            index=models.Index(
                fields=["vendor", "open"],
                name="purch_vl_vend_open_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="purchaseinvoice",
            index=models.Index(
                fields=["posting_date", "status"],
                name="purch_pi_date_status_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="purchaseinvoice",
            index=models.Index(
                fields=["vendor", "status"],
                name="purch_pi_vend_status_idx",
            ),
        ),
    ]
