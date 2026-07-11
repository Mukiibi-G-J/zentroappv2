# Production runbook: schema drift repair + branch/dimension backfill

This runbook documents the exact fixes we applied on a **production DB imported into test**, so the same playbook can be repeated safely in **staging/production** when tenant schemas are behind the codebase (schema drift) and dimension backfill / NOT NULL migrations must be applied.

It complements:
- `docs/branch_dimension_backfill_production.md` (backfill + NOT NULL migration flow)
- `docs/branch_viewset_inventory.md` (API branch scoping overview)

---

## 0) Key concepts (multi-tenant)

### Public schema vs tenant schema
This project uses **django-tenants**. There are two relevant “admin sites”:

- **Public/global admin** (runs on *public schema*):
  - Wired in `core/urls-public.py`:
    - `path("admin/", global_admin_site.urls)`
  - Intended to manage shared/public models like `Company`, `Domain`, billing, etc.

- **Tenant admin** (runs inside one tenant schema):
  - Wired in `core/urls.py`:
    - `path("admin/", admin.site.urls)`

### Domain routing rules (critical)
For local/dev:
- Public/global admin: `http://localhost:8000/admin/` (no subdomain ⇒ public)
- Tenant admin: `http://<tenant>.localhost:8000/admin/`
  - Example: `http://primewise.localhost:8000/admin/`

**Do NOT map bare `localhost` to a tenant** in `company_domain`, or you’ll break the public/global admin by forcing it into a tenant schema.

For production:
- Ensure each tenant domain exists in **public** `company_domain`.
  - Example: `primewise.zentroapp.app` → schema `primewise`

---

## 1) Standard backfill + migrations flow (recommended)

### A) Pre-flight audit (read-only)

```bash
python manage.py audit_dimension_nulls
python manage.py audit_dimension_nulls --schema=TENANT_SCHEMA
python manage.py audit_dimension_nulls --output-csv=audit_nulls.csv
```

### B) Run migrations

```bash
python manage.py migrate_schemas
# or pilot one tenant first
python manage.py migrate_schemas --schema=TENANT_SCHEMA
```

Notes:
- `dimension.0007_dimension_backfill_audit_and_data` runs the backfill with audit enabled.
- If a tenant table is behind models, some backfill steps may be skipped (schema drift); you may need drift repair + re-run.

### C) Re-run backfill (idempotent) when needed
If any NOT NULL enforcement fails (or you imported new rows), re-run:

```bash
python manage.py backfill_branch_dimensions --schema=TENANT_SCHEMA --allow-multiple-branch-values
```

Then retry migrations for that tenant:

```bash
python manage.py migrate_schemas --schema=TENANT_SCHEMA
```

### D) Verify

```bash
python manage.py verify_branch_dimensions
python manage.py verify_branch_dimensions --schema=TENANT_SCHEMA
```

---

## 2) Schema drift symptoms & fixes (what we hit)

### Symptom class: admin crashes due to missing columns/tables
Example errors we saw:
- `column <table>.<column> does not exist`
- `relation <table> does not exist`

Root cause:
- The tenant schema has old tables/columns, or
- A migration is marked applied, but the DB object was not created (drift).

Strategy:
- Prefer applying the correct tenant migrations.
- If migration state is applied but DB object is missing, use **manual drift repair**:
  - `ALTER TABLE ... ADD COLUMN IF NOT EXISTS ...`
  - Create missing table (rare; when state says “applied” but table is missing)

---

## 3) Domain mapping fixes (public schema)

### Ensure tenant host resolves to tenant schema (dev/local)
We added a `Domain` row in **public**:
- `primewise.localhost` → tenant schema `primewise`

This is required so `primewise.localhost` routes into the tenant schema.

### Keep `localhost` for public/global admin
We removed any `Domain(domain='localhost')` mapping to a tenant, so:
- `http://localhost:8000/admin/` stays in **public** and uses `global_admin_site`.

---

## 4) Public schema drift repairs (admin login columns)

### Why this was needed
Public/global admin login may query the configured `AUTH_USER_MODEL` table in **public**.
If public schema is behind, login can crash due to missing columns.

### A) Add `can_switch_branch` to public `authentication_customuser`
From migration: `authentication.0010_customuser_can_switch_branch`

```sql
ALTER TABLE IF EXISTS authentication_customuser
ADD COLUMN IF NOT EXISTS can_switch_branch boolean NOT NULL DEFAULT true;
```

### B) Add `restaurant_pin_hash` to public `authentication_customuser`
From migration: `authentication.0011_customuser_restaurant_pin_hash`

```sql
ALTER TABLE IF EXISTS authentication_customuser
ADD COLUMN IF NOT EXISTS restaurant_pin_hash varchar(128) NULL;
```

---

## 5) Tenant drift repairs we applied (primewise examples)

All examples below assume you are operating in the tenant schema (production equivalent):
- `SET search_path TO primewise, public;`

### Purchases

#### `purchases_purchasecreditmemo.dimension_set_id`

```sql
ALTER TABLE purchases_purchasecreditmemo
ADD COLUMN IF NOT EXISTS dimension_set_id bigint NULL;

ALTER TABLE purchases_purchasecreditmemo
ADD CONSTRAINT purchases_purchasecreditmemo_dimension_set_id_fk
FOREIGN KEY (dimension_set_id) REFERENCES dimension_dimensionset(id) ON DELETE SET NULL;
```

#### `purchases_purchasecreditmemoline.global_dimension_1_id`

```sql
ALTER TABLE purchases_purchasecreditmemoline
ADD COLUMN IF NOT EXISTS global_dimension_1_id bigint NULL;

ALTER TABLE purchases_purchasecreditmemoline
ADD CONSTRAINT purchases_purchasecreditmemoline_gdim1_fk
FOREIGN KEY (global_dimension_1_id) REFERENCES dimension_dimensionvalue(id) ON DELETE SET NULL;
```

#### `purchases_purchasecreditmemoline.dimension_set_id`

```sql
ALTER TABLE purchases_purchasecreditmemoline
ADD COLUMN IF NOT EXISTS dimension_set_id bigint NULL;

ALTER TABLE purchases_purchasecreditmemoline
ADD CONSTRAINT purchases_purchasecreditmemoline_dimension_set_id_fk
FOREIGN KEY (dimension_set_id) REFERENCES dimension_dimensionset(id) ON DELETE SET NULL;
```

### Sales

#### `sales_salesorderline.global_dimension_1_id`

```sql
ALTER TABLE sales_salesorderline
ADD COLUMN IF NOT EXISTS global_dimension_1_id bigint NULL;

ALTER TABLE sales_salesorderline
ADD CONSTRAINT sales_salesorderline_gdim1_fk
FOREIGN KEY (global_dimension_1_id) REFERENCES dimension_dimensionvalue(id) ON DELETE SET NULL;
```

#### `sales_salesorderline.type`
From `sales/migrations/0006_add_line_type_and_resource.py`

```sql
ALTER TABLE sales_salesorderline
ADD COLUMN IF NOT EXISTS type varchar(10) NOT NULL DEFAULT 'item';
```

#### `sales_salesorderline.resource_id`
From `sales/migrations/0006_add_line_type_and_resource.py`

```sql
ALTER TABLE sales_salesorderline
ADD COLUMN IF NOT EXISTS resource_id bigint NULL;

ALTER TABLE sales_salesorderline
ADD CONSTRAINT sales_salesorderline_resource_fk
FOREIGN KEY (resource_id) REFERENCES resources_resource(id) ON DELETE SET NULL;
```

#### `sales_salesorderline.dimension_set_id`

```sql
ALTER TABLE sales_salesorderline
ADD COLUMN IF NOT EXISTS dimension_set_id bigint NULL;

ALTER TABLE sales_salesorderline
ADD CONSTRAINT sales_salesorderline_dimension_set_id_fk
FOREIGN KEY (dimension_set_id) REFERENCES dimension_dimensionset(id) ON DELETE SET NULL;
```

#### `sales_salescreditmemoline.global_dimension_1_id`

```sql
ALTER TABLE sales_salescreditmemoline
ADD COLUMN IF NOT EXISTS global_dimension_1_id bigint NULL;

ALTER TABLE sales_salescreditmemoline
ADD CONSTRAINT sales_salescreditmemoline_gdim1_fk
FOREIGN KEY (global_dimension_1_id) REFERENCES dimension_dimensionvalue(id) ON DELETE SET NULL;
```

#### `sales_salescreditmemoline.dimension_set_id`

```sql
ALTER TABLE sales_salescreditmemoline
ADD COLUMN IF NOT EXISTS dimension_set_id bigint NULL;

ALTER TABLE sales_salescreditmemoline
ADD CONSTRAINT sales_salescreditmemoline_dimension_set_id_fk
FOREIGN KEY (dimension_set_id) REFERENCES dimension_dimensionset(id) ON DELETE SET NULL;
```

### Financials

#### `financials_vatentry` missing but `financials.0010_add_vat_entry` is marked applied
This can happen when a migration used `SeparateDatabaseAndState` and the DB operation was skipped or failed silently earlier.

**Fix (safe approach):**
1) Confirm migration record exists in tenant `django_migrations`.
2) If table is missing, create it (Django schema_editor `create_model(VatEntry)`).

Operational checklist:
- In that tenant schema, check:
  - `information_schema.tables` for `financials_vatentry`
- If missing:
  - Create the table using the same model definition as `financials.models.VatEntry`.

---

## 6) Code hardening that should be deployed (so prod is smoother next time)

These are code-level fixes we made during the test import to reduce production failures:
- `financials/migrations/0011_not_null_branch_dimensions.py`:
  - Fixed a crash in `alter_field()` by resolving FK target via `apps.get_model()` rather than a string.
- `items/migrations/0030_not_null_itemjournal_template_batch.py`:
  - Set `atomic = False` to avoid PostgreSQL “pending trigger events” when mixing data writes + DDL.
- `dimension/migrations/0007_dimension_backfill_audit_and_data.py`:
  - Skip backfill safely in schemas missing required tables/columns (e.g. public or legacy tenants).
- `items/migrations/0028_not_null_branch_dimensions.py`:
  - Re-run branch backfill right before enforcing NOT NULL/PROTECT for items ledgers.
- `bank_account/migrations/0005_not_null_branch_dimensions.py` and `expenses/migrations/0004_not_null_branch_dimensions.py`:
  - Conditional DDL via `SeparateDatabaseAndState` so legacy schemas missing columns don’t crash all migrations.
- `dimension/utils.py`:
  - Return a `SCHEMA_DRIFT:` error string (instead of hard-crashing) when resolving default branch fails due to missing legacy tables/columns.

---

## 7) Operational safety notes (production)

- Always **backup** before any manual DDL (schema drift repair).
- Prefer:
  - `audit_dimension_nulls` → `migrate_schemas` → `verify_branch_dimensions`
- Use manual drift repairs only when:
  - A migration is marked applied but DB object is missing, or
  - You must unblock admin/critical operations while planning a full drift reconciliation.

