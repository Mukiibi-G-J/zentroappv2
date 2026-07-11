"""
Run this to create page engine tables in all tenant schemas.
Usage: python manage.py shell -c "exec(open('pages/create_tables.py').read())"
"""
import django
import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django_tenants.utils import get_tenant_model, schema_context

DDL = """
CREATE TABLE IF NOT EXISTS page_engine_page (
    page_id SERIAL PRIMARY KEY,
    name VARCHAR(200) UNIQUE NOT NULL,
    caption VARCHAR(200) NOT NULL,
    source_table VARCHAR(200) NOT NULL,
    page_type VARCHAR(20) NOT NULL DEFAULT 'List',
    editable BOOLEAN NOT NULL DEFAULT TRUE,
    insert_allowed BOOLEAN NOT NULL DEFAULT TRUE,
    delete_allowed BOOLEAN NOT NULL DEFAULT TRUE,
    modify_allowed BOOLEAN NOT NULL DEFAULT TRUE,
    card_page_id INTEGER REFERENCES page_engine_page(page_id),
    header_page_id INTEGER REFERENCES page_engine_page(page_id),
    context_filter_field VARCHAR(200) NOT NULL DEFAULT '',
    context_key_field VARCHAR(200) NOT NULL DEFAULT '',
    document_type VARCHAR(100) NOT NULL DEFAULT '',
    list_exclude_field VARCHAR(200) NOT NULL DEFAULT '',
    list_exclude_values TEXT NOT NULL DEFAULT '',
    title_field VARCHAR(200) NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS page_engine_action (
    action_id SERIAL PRIMARY KEY,
    page_id INTEGER NOT NULL REFERENCES page_engine_page(page_id),
    name VARCHAR(200) NOT NULL,
    caption VARCHAR(200) NOT NULL,
    requires_confirmation BOOLEAN NOT NULL DEFAULT FALSE,
    confirmation_message TEXT,
    tooltip VARCHAR(500),
    visible BOOLEAN NOT NULL DEFAULT TRUE,
    image_url VARCHAR(500),
    action_relative_url VARCHAR(500),
    ribbon_tab VARCHAR(100),
    visible_when_field VARCHAR(200),
    visible_when_values TEXT
);
CREATE TABLE IF NOT EXISTS page_engine_control (
    page_control_id SERIAL PRIMARY KEY,
    page_id INTEGER NOT NULL REFERENCES page_engine_page(page_id),
    control_type VARCHAR(20) NOT NULL DEFAULT 'Repeater',
    name VARCHAR(200) NOT NULL,
    caption VARCHAR(200) NOT NULL,
    source_table VARCHAR(200) NOT NULL,
    show_caption BOOLEAN NOT NULL DEFAULT TRUE,
    editable BOOLEAN NOT NULL DEFAULT TRUE,
    visible BOOLEAN NOT NULL DEFAULT TRUE
);
CREATE TABLE IF NOT EXISTS page_engine_field (
    page_control_field_id SERIAL PRIMARY KEY,
    page_control_id INTEGER NOT NULL REFERENCES page_engine_control(page_control_id),
    page_id INTEGER NOT NULL REFERENCES page_engine_page(page_id),
    field_id INTEGER NOT NULL DEFAULT 0,
    name VARCHAR(200) NOT NULL,
    caption VARCHAR(200) NOT NULL,
    field_type VARCHAR(20) NOT NULL DEFAULT 'Text',
    visible BOOLEAN NOT NULL DEFAULT TRUE,
    editable BOOLEAN NOT NULL DEFAULT TRUE,
    primary_key BOOLEAN NOT NULL DEFAULT FALSE,
    required BOOLEAN NOT NULL DEFAULT FALSE,
    tab_index INTEGER NOT NULL DEFAULT 0,
    tooltip VARCHAR(500),
    enum_values TEXT,
    no_series_code VARCHAR(50),
    has_lookup_page BOOLEAN NOT NULL DEFAULT FALSE,
    lookup_page_id INTEGER REFERENCES page_engine_page(page_id),
    has_drill_down_page BOOLEAN NOT NULL DEFAULT FALSE,
    drill_down_page_id INTEGER REFERENCES page_engine_page(page_id),
    has_table_relation BOOLEAN NOT NULL DEFAULT FALSE,
    related_table VARCHAR(200),
    related_field VARCHAR(200),
    related_display_field VARCHAR(200),
    relation_context_field VARCHAR(200),
    relation_context_default VARCHAR(200),
    freeze_column BOOLEAN NOT NULL DEFAULT FALSE,
    visible_when_field VARCHAR(200),
    visible_when_values TEXT
);
CREATE TABLE IF NOT EXISTS page_engine_table_relation (
    id SERIAL PRIMARY KEY,
    source_table VARCHAR(200) NOT NULL,
    source_field VARCHAR(200) NOT NULL,
    related_table VARCHAR(200) NOT NULL,
    related_field VARCHAR(200) NOT NULL,
    display_field VARCHAR(200) NOT NULL,
    context_field VARCHAR(200) NOT NULL DEFAULT '',
    context_value VARCHAR(200) NOT NULL DEFAULT '',
    UNIQUE (source_table, source_field, context_field, context_value)
);
"""

TenantModel = get_tenant_model()
tenants = list(TenantModel.objects.all())

for tenant in tenants:
    try:
        with schema_context(tenant.schema_name):
            from django.db import connection
            with connection.cursor() as cur:
                cur.execute(DDL)
        print(f'OK: {tenant.schema_name}')
    except Exception as e:
        print(f'ERR {tenant.schema_name}: {e}')

print('Done.')
