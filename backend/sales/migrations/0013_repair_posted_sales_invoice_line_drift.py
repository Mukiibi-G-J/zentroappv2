from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("sales", "0012_add_vat_fields_to_invoices"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                ALTER TABLE IF EXISTS sales_postedsalesinvoiceline
                    ADD COLUMN IF NOT EXISTS type varchar(10) NOT NULL DEFAULT 'item';

                ALTER TABLE IF EXISTS sales_postedsalesinvoiceline
                    ADD COLUMN IF NOT EXISTS resource_id bigint NULL;

                ALTER TABLE IF EXISTS sales_postedsalesinvoiceline
                    ADD COLUMN IF NOT EXISTS dimension_set_id bigint NULL;

                ALTER TABLE IF EXISTS sales_postedsalesinvoiceline
                    ADD COLUMN IF NOT EXISTS global_dimension_1_id bigint NULL;

                CREATE INDEX IF NOT EXISTS posted_sales_line_type_idx
                    ON sales_postedsalesinvoiceline (type);
            """,
            reverse_sql=migrations.RunSQL.noop,
        )
    ]
