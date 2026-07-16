"""Assess primewise schema readiness for V2. Run from backend/."""
import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from django.db import connection
from django_tenants.utils import schema_context, get_tenant_model


def table_exists(schema: str, table: str) -> bool:
    with connection.cursor() as c:
        c.execute(
            """
            SELECT 1 FROM information_schema.tables
            WHERE table_schema=%s AND table_name=%s
            """,
            [schema, table],
        )
        return c.fetchone() is not None


def has_column(schema: str, table: str, column: str) -> bool:
    with connection.cursor() as c:
        c.execute(
            """
            SELECT 1 FROM information_schema.columns
            WHERE table_schema=%s AND table_name=%s AND column_name=%s
            """,
            [schema, table, column],
        )
        return c.fetchone() is not None


Tenant = get_tenant_model()
with schema_context("public"):
    names = list(Tenant.objects.order_by("schema_name").values_list("schema_name", flat=True))

print(f"tenants={len(names)}")
print(f"has_primewise={'primewise' in names}")

schema = "primewise"
if schema not in names:
    raise SystemExit(1)

checks = {
    "page_engine_page": table_exists(schema, "page_engine_page"),
    "system_id": has_column(schema, "authentication_customuser", "system_id"),
    "token_valid_after": has_column(
        schema, "authentication_customuser", "token_valid_after"
    ),
    "vendor_applies_to_id": has_column(
        schema, "purchases_vendorledger", "applies_to_id"
    ),
    "customer_applies_to_id": has_column(
        schema, "sales_customerledgerentry", "applies_to_id"
    ),
    "sync_device": table_exists(schema, "sync_device"),
}
print("schema_checks=", checks)

with schema_context(schema):
    with connection.cursor() as c:
        c.execute("SELECT COUNT(*) FROM django_migrations")
        print("migration_rows=", c.fetchone()[0])

        if checks["page_engine_page"]:
            c.execute("SELECT COUNT(*) FROM page_engine_page")
            print("page_count=", c.fetchone()[0])
            c.execute(
                """
                SELECT COUNT(*) FROM page_engine_page
                WHERE object_id IS NOT NULL AND object_id > 0
                """
            )
            print("pages_with_object_id=", c.fetchone()[0])

        if checks["vendor_applies_to_id"]:
            c.execute(
                """
                SELECT COUNT(*) FROM purchases_vendorledger
                WHERE document_type = 'Payment'
                  AND COALESCE(applies_to_id, '') <> ''
                """
            )
            print("bad_vendor_payment_applies=", c.fetchone()[0])

        if checks["customer_applies_to_id"]:
            c.execute(
                """
                SELECT COUNT(*) FROM sales_customerledgerentry
                WHERE document_type = 'Payment'
                  AND COALESCE(applies_to_id, '') <> ''
                """
            )
            print("bad_customer_payment_applies=", c.fetchone()[0])

        # permission sets / objects
        if table_exists(schema, "permissions_permissionset"):
            c.execute("SELECT COUNT(*) FROM permissions_permissionset")
            print("permission_sets=", c.fetchone()[0])
        if table_exists(schema, "base_objects"):
            c.execute(
                """
                SELECT COUNT(*) FROM base_objects o
                JOIN base_objecttype t ON o.object_type_id = t.id
                WHERE t.code = 'PAGE' OR LOWER(t.name) = 'page'
                """
            )
            print("page_objects=", c.fetchone()[0])
