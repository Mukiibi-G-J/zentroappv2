"""Raw DDL for tenant page-engine tables (django-tenants per-schema setup)."""

DDL_CREATE = """
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

# Idempotent column adds for schemas created before Part / RoleCentre migrations.
DDL_ALTER = """
ALTER TABLE page_engine_control ADD COLUMN IF NOT EXISTS part_page_id INTEGER REFERENCES page_engine_page(page_id);
ALTER TABLE page_engine_control ADD COLUMN IF NOT EXISTS link_field VARCHAR(100) NOT NULL DEFAULT '';
ALTER TABLE page_engine_control ADD COLUMN IF NOT EXISTS tab_index INTEGER NOT NULL DEFAULT 0;
ALTER TABLE page_engine_control ADD COLUMN IF NOT EXISTS parent_control_id INTEGER REFERENCES page_engine_control(page_control_id);
ALTER TABLE page_engine_control ADD COLUMN IF NOT EXISTS max_records INTEGER NOT NULL DEFAULT 5;
ALTER TABLE page_engine_control ADD COLUMN IF NOT EXISTS cue_source_table VARCHAR(100) NOT NULL DEFAULT '';
ALTER TABLE page_engine_control ADD COLUMN IF NOT EXISTS cue_aggregate VARCHAR(20) NOT NULL DEFAULT 'count';
ALTER TABLE page_engine_control ADD COLUMN IF NOT EXISTS cue_filter_field VARCHAR(100) NOT NULL DEFAULT '';
ALTER TABLE page_engine_control ADD COLUMN IF NOT EXISTS cue_filter_value VARCHAR(100) NOT NULL DEFAULT '';
ALTER TABLE page_engine_control ADD COLUMN IF NOT EXISTS cue_aggregate_field VARCHAR(100) NOT NULL DEFAULT '';
ALTER TABLE page_engine_control ADD COLUMN IF NOT EXISTS drill_down_page_id INTEGER REFERENCES page_engine_page(page_id);
ALTER TABLE page_engine_control ADD COLUMN IF NOT EXISTS cue_style VARCHAR(20) NOT NULL DEFAULT '';
ALTER TABLE page_engine_control ADD COLUMN IF NOT EXISTS headline_template VARCHAR(500) NOT NULL DEFAULT '';
ALTER TABLE page_engine_field ADD COLUMN IF NOT EXISTS threshold_warning INTEGER;
ALTER TABLE page_engine_field ADD COLUMN IF NOT EXISTS threshold_danger INTEGER;
ALTER TABLE page_engine_action ADD COLUMN IF NOT EXISTS action_type VARCHAR(20) NOT NULL DEFAULT 'Ribbon';
ALTER TABLE page_engine_page ADD COLUMN IF NOT EXISTS list_filter_field VARCHAR(200) NOT NULL DEFAULT '';
ALTER TABLE page_engine_page ADD COLUMN IF NOT EXISTS list_filter_value VARCHAR(200) NOT NULL DEFAULT '';
ALTER TABLE page_engine_page ADD COLUMN IF NOT EXISTS object_id INTEGER UNIQUE;
ALTER TABLE page_engine_page ADD COLUMN IF NOT EXISTS desktop_enabled BOOLEAN NOT NULL DEFAULT FALSE;
"""


def ensure_page_engine_schema(cursor):
    cursor.execute(DDL_CREATE)
    cursor.execute(DDL_ALTER)
