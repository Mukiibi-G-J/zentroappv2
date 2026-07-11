from django.db import migrations


class Migration(migrations.Migration):
    """
    Idempotent repair for schemas where sales_salesorderline (and invoice lines)
    are missing type/resource_id even though 0006 is recorded as applied.
    """

    dependencies = [
        ("sales", "0016_not_null_branch_dimensions"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                ALTER TABLE IF EXISTS sales_salesorderline
                    ADD COLUMN IF NOT EXISTS type varchar(10) NOT NULL DEFAULT 'item';

                ALTER TABLE IF EXISTS sales_salesorderline
                    ADD COLUMN IF NOT EXISTS resource_id bigint NULL;

                CREATE INDEX IF NOT EXISTS sales_order_line_type_idx
                    ON sales_salesorderline (type);

                ALTER TABLE IF EXISTS sales_salesinvoiceline
                    ADD COLUMN IF NOT EXISTS type varchar(10) NOT NULL DEFAULT 'item';

                ALTER TABLE IF EXISTS sales_salesinvoiceline
                    ADD COLUMN IF NOT EXISTS resource_id bigint NULL;

                CREATE INDEX IF NOT EXISTS sales_line_type_idx
                    ON sales_salesinvoiceline (type);
            """,
            reverse_sql=migrations.RunSQL.noop,
        )
    ]
