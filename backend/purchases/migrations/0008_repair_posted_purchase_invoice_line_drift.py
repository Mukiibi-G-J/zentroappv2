"""
Repair migration for schema drift: add dimension columns to
purchases_postedpurchaseinvoiceline if missing.

Some tenant schemas were created before 0005_add_header_dimensions ran,
or drifted from migration state. This adds the columns with IF NOT EXISTS
so it is safe to run on all schemas.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("purchases", "0007_add_vat_fields_to_invoices"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                ALTER TABLE IF EXISTS purchases_postedpurchaseinvoiceline
                    ADD COLUMN IF NOT EXISTS global_dimension_1_id bigint NULL;

                ALTER TABLE IF EXISTS purchases_postedpurchaseinvoiceline
                    ADD COLUMN IF NOT EXISTS global_dimension_2_id bigint NULL;

                ALTER TABLE IF EXISTS purchases_postedpurchaseinvoiceline
                    ADD COLUMN IF NOT EXISTS dimension_set_id bigint NULL;
            """,
            reverse_sql=migrations.RunSQL.noop,
        )
    ]
