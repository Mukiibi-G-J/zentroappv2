"""
Add missing columns to tenant schema tables (fix for faked migrations).
Run per-schema; only adds columns that don't exist.
"""

from django.core.management.base import BaseCommand
from django.db import connection

# (table, column, sql_type_with_default). Only columns on existing tables.
COLUMNS = [
    ("sales_salesinvoice", "prices_including_vat", "boolean DEFAULT false"),
    ("sales_salesinvoice", "total_vat_amount", "numeric(18,2) DEFAULT 0"),
    ("sales_salesinvoiceline", "vat_amount", "numeric(18,2) DEFAULT 0"),
    ("sales_salesinvoiceline", "vat_percent", "numeric(5,2) DEFAULT 0"),
    ("sales_salesinvoiceline", "type", "varchar(10) DEFAULT 'item'"),
    ("sales_salesinvoiceline", "resource_id", "bigint NULL"),
    ("sales_salesinvoiceline", "global_dimension_1_id", "bigint NULL"),
    ("sales_salesinvoiceline", "dimension_set_id", "bigint NULL"),
    ("sales_salesinvoice", "global_dimension_1_id", "bigint NULL"),
    ("sales_salesinvoice", "global_dimension_2_id", "bigint NULL"),
    ("sales_salesinvoice", "dimension_set_id", "bigint NULL"),
    ("sales_postedsalesinvoice", "global_dimension_1_id", "bigint NULL"),
    ("sales_postedsalesinvoice", "global_dimension_2_id", "bigint NULL"),
    ("sales_postedsalesinvoice", "dimension_set_id", "bigint NULL"),
    ("sales_customer", "vat_business_posting_group_id", "bigint NULL"),
    ("sales_customerledgerentry", "global_dimension_1_id", "bigint NULL"),
    ("sales_customerledgerentry", "dimension_set_id", "bigint NULL"),
    ("sales_salescreditmemo", "global_dimension_1_id", "bigint NULL"),
    ("sales_salescreditmemo", "global_dimension_2_id", "bigint NULL"),
    ("sales_salescreditmemo", "dimension_set_id", "bigint NULL"),
    ("sales_detailedcustomerledgerentry", "global_dimension_1_id", "bigint NULL"),
    ("sales_detailedcustomerledgerentry", "dimension_set_id", "bigint NULL"),
    ("purchases_purchaseinvoice", "prices_including_vat", "boolean DEFAULT false"),
    ("purchases_purchaseinvoice", "total_vat_amount", "numeric(18,2) DEFAULT 0"),
    ("purchases_purchaseinvoice", "global_dimension_1_id", "bigint NULL"),
    ("purchases_purchaseinvoice", "global_dimension_2_id", "bigint NULL"),
    ("purchases_purchaseinvoice", "dimension_set_id", "bigint NULL"),
    ("purchases_purchaseinvoiceline", "vat_percent", "numeric(5,2) DEFAULT 0"),
    ("purchases_purchaseinvoiceline", "vat_amount", "numeric(18,2) DEFAULT 0"),
    ("purchases_purchaseinvoiceline", "global_dimension_1_id", "bigint NULL"),
    ("purchases_purchaseinvoiceline", "dimension_set_id", "bigint NULL"),
    ("purchases_postedpurchaseinvoice", "global_dimension_2_id", "bigint NULL"),
    ("purchases_purchasecreditmemo", "global_dimension_2_id", "bigint NULL"),
    ("purchases_detailedvendorledgerentry", "dimension_set_id", "bigint NULL"),
    ("purchases_vendor", "vat_business_posting_group_id", "bigint NULL"),
    ("purchases_vendorledger", "dimension_set_id", "bigint NULL"),
    ("purchases_vendorledger", "global_dimension_1_id", "bigint NULL"),
    ("purchases_detailedvendorledgerentry", "global_dimension_1_id", "bigint NULL"),
    ("purchases_postedpurchaseinvoice", "global_dimension_1_id", "bigint NULL"),
    ("purchases_postedpurchaseinvoice", "dimension_set_id", "bigint NULL"),
    ("purchases_purchasecreditmemo", "global_dimension_1_id", "bigint NULL"),
    ("financials_generalledgerentry", "dimension_set_id", "bigint NULL"),
    ("financials_generalledgerentry", "global_dimension_1_id", "bigint NULL"),
    ("financials_generalledgerentry", "global_dimension_2_id", "bigint NULL"),
    ("financials_generalledgersetup", "shortcut_dimension_3_id", "bigint NULL"),
    ("financials_generalledgersetup", "shortcut_dimension_4_id", "bigint NULL"),
    ("financials_generalledgersetup", "shortcut_dimension_5_id", "bigint NULL"),
    ("financials_generalledgersetup", "shortcut_dimension_6_id", "bigint NULL"),
    (
        "financials_generalledgersetup",
        "enable_sales_line_type_selection",
        "boolean DEFAULT false",
    ),
    (
        "financials_generalledgersetup",
        "enable_multiple_branches",
        "boolean DEFAULT false",
    ),
    ("financials_generalledgersetup", "vat_enabled", "boolean DEFAULT false"),
    ("financials_generalledgersetup", "default_vat_date", "varchar(20) NULL"),
    ("prepayment_prepayment", "global_dimension_1_id", "bigint NULL"),
    ("prepayment_preaymentline", "global_dimension_1_id", "bigint NULL"),
    ("loans_loan", "global_dimension_1_id", "bigint NULL"),
    ("loans_loanrepayment", "global_dimension_1_id", "bigint NULL"),
    ("expenses_expense", "global_dimension_1_id", "bigint NULL"),
    ("expenses_expense", "global_dimension_2_id", "bigint NULL"),
    ("expenses_expense", "dimension_set_id", "bigint NULL"),
    (
        "setup_inventorysetup",
        "show_adjustment_history_before_after",
        "boolean DEFAULT false",
    ),
    ("setup_manufacturingsetup", "manufacturing_enabled", "boolean DEFAULT false"),
    ("production_productionorder", "item_id", "bigint NULL"),
    ("production_productionorderline", "global_dimension_1_id", "bigint NULL"),
    ("items", "vat_product_posting_group_id", "bigint NULL"),
    ("items_valueentry", "global_dimension_1_id", "bigint NULL"),
    ("items_valueentry", "global_dimension_2_id", "bigint NULL"),
    ("items_valueentry", "dimension_set_id", "bigint NULL"),
    ("items_valueentry", "cost_amount_non_invtbl", "numeric(18,2) DEFAULT 0 NULL"),
    ("Item Ledger Entries", "global_dimension_1_id", "bigint NULL"),
    ("Item Ledger Entries", "global_dimension_2_id", "bigint NULL"),
    ("Item Ledger Entries", "dimension_set_id", "bigint NULL"),
    ("items_trackingspecification", "source_template_id", "bigint NULL"),
    ("items_trackingspecification", "source_batch_id", "bigint NULL"),
    ("production_productionorder", "status", "varchar(20) DEFAULT 'simulated'"),
    ("production_productionorderline", "dimension_set_id", "bigint NULL"),
    ("resources_resource", "base_unit_id", "varchar(10) NULL"),
    # authentication (tenant); migrations 0010, 0011
    ("authentication_customuser", "can_switch_branch", "boolean DEFAULT true"),
    ("authentication_customuser", "restaurant_pin_hash", "varchar(128) NULL"),
]


def get_tenant_schemas(cursor):
    cursor.execute(
        """
        SELECT schema_name FROM information_schema.schemata
        WHERE schema_name NOT IN ('pg_catalog', 'information_schema', 'pg_toast', 'public')
        AND EXISTS (SELECT 1 FROM information_schema.tables t WHERE t.table_schema = schemata.schema_name AND t.table_name = 'django_migrations')
    """
    )
    return [r[0] for r in cursor.fetchall()]


def table_exists(cursor, table):
    cursor.execute(
        """
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = current_schema() AND table_name = %s
    """,
        [table],
    )
    return cursor.fetchone() is not None


def column_exists(cursor, table, column):
    cursor.execute(
        """
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = current_schema() AND table_name = %s AND column_name = %s
    """,
        [table, column],
    )
    return cursor.fetchone() is not None


def _public_has_auth_user_table(cursor) -> bool:
    cursor.execute(
        """
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = 'authentication_customuser'
        """
    )
    return cursor.fetchone() is not None


class Command(BaseCommand):
    help = "Add missing columns to tenant schemas (for faked migrations)"

    def handle(self, *args, **options):
        with connection.cursor() as c:
            schemas = list(get_tenant_schemas(c))
            if _public_has_auth_user_table(c):
                schemas.insert(0, "public")
        self.stdout.write(
            f"Found {len(schemas)} schema(s) to check (including public if auth table exists there)."
        )
        total_added = 0
        for schema in schemas:
            with connection.cursor() as c:
                c.execute("SET search_path TO %s", [schema])
                added = 0
                for table, column, sql_type in COLUMNS:
                    if not table_exists(c, table):
                        continue
                    if column_exists(c, table, column):
                        continue
                    try:
                        c.execute(
                            f'ALTER TABLE "{table}" ADD COLUMN IF NOT EXISTS "{column}" {sql_type}'
                        )
                        added += 1
                    except Exception as e:
                        self.stdout.write(
                            self.style.WARNING(f"  {schema}.{table}.{column}: {e}")
                        )
                if added:
                    total_added += added
                    self.stdout.write(
                        self.style.SUCCESS(f"  {schema}: added {added} column(s)")
                    )
        self.stdout.write(
            self.style.SUCCESS(f"\nDone. Added {total_added} column(s) across schemas.")
        )
