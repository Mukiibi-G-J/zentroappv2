from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("items", "0033_add_minimum_stock_to_item"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="item",
            index=models.Index(
                fields=["updated_at", "no"],
                name="items_item_upd_no_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="item",
            index=models.Index(
                fields=["bar_code_no"],
                name="items_item_barcode_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="itemledgerentries",
            index=models.Index(
                fields=["item", "global_dimension_1"],
                name="items_ile_item_branch_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="itemledgerentries",
            index=models.Index(
                fields=["item", "posting_date"],
                name="items_ile_item_date_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="itemledgerentries",
            index=models.Index(
                fields=["document_no"],
                name="items_ile_doc_no_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="valueentry",
            index=models.Index(
                fields=["document_no"],
                name="items_ve_doc_no_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="valueentry",
            index=models.Index(
                fields=["item", "posting_date"],
                name="items_ve_item_date_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="itemjournal",
            index=models.Index(
                fields=["status", "journal_template"],
                name="items_ij_status_tpl_idx",
            ),
        ),
    ]
