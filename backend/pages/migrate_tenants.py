"""
Run via: python manage.py shell < pages/migrate_tenants.py
"""
from django_tenants.utils import get_tenant_model, schema_context
from django.db import connection

from pages.schema_ddl import ensure_page_engine_schema

TenantModel = get_tenant_model()
tenants = list(TenantModel.objects.all())

for tenant in tenants:
    try:
        with schema_context(tenant.schema_name):
            with connection.cursor() as cur:
                ensure_page_engine_schema(cur)
        print(f'OK: {tenant.schema_name}')
    except Exception as e:
        print(f'ERR {tenant.schema_name}: {str(e)[:100]}')

print('Migration complete.')
