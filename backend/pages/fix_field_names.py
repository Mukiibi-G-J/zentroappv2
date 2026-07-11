"""
Fix wrong field names in page_engine_field table across all tenant schemas.
Run: python manage.py shell < pages/fix_field_names.py

Renames:
  Customer: phone_no -> phone_number, email -> address (and adds city)
  Vendor:   phone_no -> phone,        caption 'Boolean' -> 'Blocked', adds email

Also deletes orphan fields that were replaced.
"""
from django_tenants.utils import get_tenant_model, schema_context
from django.db import connection

# Customer fixes: rename phone_no→phone_number, replace email col with address+city
CUSTOMER_SQL = """
-- Rename phone_no → phone_number (if phone_number doesn't already exist)
UPDATE page_engine_field
SET name = 'phone_number', caption = 'Phone No.'
WHERE name = 'phone_no'
  AND page_control_id IN (
      SELECT page_control_id FROM page_engine_control WHERE source_table = 'Customer'
  )
  AND NOT EXISTS (
      SELECT 1 FROM page_engine_field f2
      WHERE f2.name = 'phone_number'
        AND f2.page_control_id = page_engine_field.page_control_id
  );

-- Rename email → address
UPDATE page_engine_field
SET name = 'address', caption = 'Address', tab_index = 3
WHERE name = 'email'
  AND page_control_id IN (
      SELECT page_control_id FROM page_engine_control WHERE source_table = 'Customer'
  );

-- Add city field if missing
INSERT INTO page_engine_field
    (page_control_id, page_id, field_id, name, caption, field_type,
     visible, editable, primary_key, required, tab_index,
     has_lookup_page, has_drill_down_page, has_table_relation, freeze_column)
SELECT c.page_control_id, c.page_id, 4, 'city', 'City', 'Text',
       true, true, false, false, 4,
       false, false, false, false
FROM page_engine_control c
WHERE c.source_table = 'Customer'
  AND NOT EXISTS (
      SELECT 1 FROM page_engine_field f
      WHERE f.page_control_id = c.page_control_id AND f.name = 'city'
  );

-- Remove blocked field from Customer (doesn't exist on model)
DELETE FROM page_engine_field
WHERE name = 'blocked'
  AND page_control_id IN (
      SELECT page_control_id FROM page_engine_control WHERE source_table = 'Customer'
  );
"""

# Vendor fixes: rename phone_no→phone, fix 'Boolean' caption, add email
VENDOR_SQL = """
-- Rename phone_no → phone
UPDATE page_engine_field
SET name = 'phone', caption = 'Phone'
WHERE name = 'phone_no'
  AND page_control_id IN (
      SELECT page_control_id FROM page_engine_control WHERE source_table = 'Vendor'
  );

-- Fix caption 'Boolean' → 'Blocked' on blocked field
UPDATE page_engine_field
SET caption = 'Blocked'
WHERE name = 'blocked' AND caption = 'Boolean'
  AND page_control_id IN (
      SELECT page_control_id FROM page_engine_control WHERE source_table = 'Vendor'
  );

-- Add email field if missing
INSERT INTO page_engine_field
    (page_control_id, page_id, field_id, name, caption, field_type,
     visible, editable, primary_key, required, tab_index,
     has_lookup_page, has_drill_down_page, has_table_relation, freeze_column)
SELECT c.page_control_id, c.page_id, 3, 'email', 'E-Mail', 'Text',
       true, true, false, false, 3,
       false, false, false, false
FROM page_engine_control c
WHERE c.source_table = 'Vendor'
  AND NOT EXISTS (
      SELECT 1 FROM page_engine_field f
      WHERE f.page_control_id = c.page_control_id AND f.name = 'email'
  );

-- Shift blocked to tab_index 4
UPDATE page_engine_field
SET tab_index = 4
WHERE name = 'blocked'
  AND page_control_id IN (
      SELECT page_control_id FROM page_engine_control WHERE source_table = 'Vendor'
  );
"""

TenantModel = get_tenant_model()
tenants = list(TenantModel.objects.all())
ok = 0
errors = []

for tenant in tenants:
    try:
        with schema_context(tenant.schema_name):
            with connection.cursor() as cur:
                cur.execute(CUSTOMER_SQL)
                cur.execute(VENDOR_SQL)
        ok += 1
    except Exception as e:
        errors.append(f'{tenant.schema_name}: {str(e)[:80]}')

print(f'Fixed {ok}/{len(tenants)} tenants')
if errors:
    for err in errors:
        print('ERR', err)
else:
    print('All done — no errors')
