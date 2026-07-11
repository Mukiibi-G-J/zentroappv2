from django_tenants.utils import get_tenant_model, schema_context
from pages.seed import seed

TenantModel = get_tenant_model()
tenants = list(TenantModel.objects.all())

for tenant in tenants:
    try:
        with schema_context(tenant.schema_name):
            ids = seed()
        print('OK %s: Items=%d Customers=%d Vendors=%d' % (
            tenant.schema_name,
            ids['items_page_id'],
            ids['customers_page_id'],
            ids['vendors_page_id'],
        ))
    except Exception as e:
        print('ERR %s: %s' % (tenant.schema_name, str(e)[:80]))

print('Done.')
