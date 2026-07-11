"""
Create missing tables in tenant schemas (for faked migrations).
Run: python manage.py create_missing_tenant_tables --settings=core.settingsprod
"""
from django.core.management.base import BaseCommand
from django.db import connection


# SQL to run per schema: CREATE TABLE IF NOT EXISTS (so safe to run multiple times).
# Table purchases_documentattachment (from purchases.0002_document_attachment)
CREATE_PURCHASES_DOCUMENTATTACHMENT = """
CREATE TABLE IF NOT EXISTS purchases_documentattachment (
    id bigserial PRIMARY KEY,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    system_id varchar(36) NOT NULL UNIQUE,
    file varchar(255) NOT NULL DEFAULT '',
    name varchar(255) NOT NULL DEFAULT '',
    purchase_invoice_id bigint NOT NULL REFERENCES purchases_purchaseinvoice(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS purchases_documentattachment_created_at_idx
    ON purchases_documentattachment (created_at);
CREATE INDEX IF NOT EXISTS purchases_documentattachment_system_id_idx
    ON purchases_documentattachment (system_id);
CREATE INDEX IF NOT EXISTS purchases_documentattachment_purchase_invoice_id_idx
    ON purchases_documentattachment (purchase_invoice_id);
"""

# Table authentication_passwordresettoken (from authentication.0007_passwordresettoken)
# Required for forgot-password (link-based reset).
CREATE_AUTH_PASSWORDRESETTOKEN = """
CREATE TABLE IF NOT EXISTS authentication_passwordresettoken (
    id bigserial PRIMARY KEY,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    system_id varchar(36) NOT NULL UNIQUE,
    token_hash varchar(255) NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    user_id bigint NOT NULL REFERENCES authentication_customuser(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS authentication_passwordresettoken_created_at_idx
    ON authentication_passwordresettoken (created_at);
CREATE INDEX IF NOT EXISTS authentication_passwordresettoken_system_id_idx
    ON authentication_passwordresettoken (system_id);
CREATE INDEX IF NOT EXISTS authentication_passwordresettoken_token_hash_idx
    ON authentication_passwordresettoken (token_hash);
CREATE INDEX IF NOT EXISTS authentication_passwordresettoken_expires_at_idx
    ON authentication_passwordresettoken (expires_at);
CREATE INDEX IF NOT EXISTS authentication_passwordresettoken_user_id_idx
    ON authentication_passwordresettoken (user_id);
"""


def get_tenant_schemas(cursor):
    cursor.execute("""
        SELECT schema_name FROM information_schema.schemata
        WHERE schema_name NOT IN ('pg_catalog', 'information_schema', 'pg_toast', 'public')
        AND EXISTS (SELECT 1 FROM information_schema.tables t WHERE t.table_schema = schemata.schema_name AND t.table_name = 'django_migrations')
    """)
    return [r[0] for r in cursor.fetchall()]


class Command(BaseCommand):
    help = "Create missing tables in tenant schemas (e.g. purchases_documentattachment)"

    def handle(self, *args, **options):
        with connection.cursor() as c:
            schemas = get_tenant_schemas(c)
        self.stdout.write(f"Found {len(schemas)} tenant schema(s).")
        for schema in schemas:
            with connection.cursor() as c:
                c.execute("SET search_path TO %s", [schema])
                for label, sql in [
                    ("purchases_documentattachment", CREATE_PURCHASES_DOCUMENTATTACHMENT),
                    ("authentication_passwordresettoken", CREATE_AUTH_PASSWORDRESETTOKEN),
                ]:
                    try:
                        c.execute(sql)
                        self.stdout.write(self.style.SUCCESS(f"  {schema}: {label} OK"))
                    except Exception as e:
                        self.stdout.write(self.style.WARNING(f"  {schema} {label}: {e}"))
        self.stdout.write(self.style.SUCCESS("Done."))
