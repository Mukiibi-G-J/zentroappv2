from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("financials", "0013_add_payment_method_indexes"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="generalledgerentry",
            index=models.Index(
                fields=["posting_date", "gl_account"],
                name="fin_gle_date_acct_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="generalledgerentry",
            index=models.Index(
                fields=["global_dimension_1", "posting_date"],
                name="fin_gle_branch_date_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="generalledgerentry",
            index=models.Index(
                fields=["document_no"],
                name="fin_gle_doc_no_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="payment",
            index=models.Index(
                fields=["status", "payment_date"],
                name="fin_pay_status_date_idx",
            ),
        ),
    ]
