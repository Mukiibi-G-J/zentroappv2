from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("financials", "0012_add_local_currency_code_to_general_ledger_setup"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="paymentmethod",
            index=models.Index(
                fields=["updated_at", "id"],
                name="fin_pm_upd_id_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="paymentmethod",
            index=models.Index(
                fields=["description"],
                name="fin_pm_desc_idx",
            ),
        ),
    ]
