from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("purchases", "0010_add_performance_indexes"),
    ]

    operations = [
        migrations.AddField(
            model_name="vendorledger",
            name="applies_to_doc_type",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Document type of the ledger entry this entry applies to",
                max_length=20,
                verbose_name="Applies-to Doc. Type",
            ),
        ),
        migrations.AddField(
            model_name="vendorledger",
            name="applies_to_doc_no",
            field=models.CharField(
                blank=True,
                default="",
                max_length=50,
                verbose_name="Applies-to Doc. No.",
            ),
        ),
        migrations.AddField(
            model_name="vendorledger",
            name="applies_to_entry_no",
            field=models.IntegerField(
                blank=True,
                help_text="Entry No. of the vendor ledger entry this entry applies to",
                null=True,
                verbose_name="Applies-to ID",
            ),
        ),
        migrations.AddField(
            model_name="vendorledger",
            name="applies_to_ext_doc_no",
            field=models.CharField(
                blank=True,
                default="",
                max_length=35,
                verbose_name="Applies-to Ext. Doc. No.",
            ),
        ),
    ]
