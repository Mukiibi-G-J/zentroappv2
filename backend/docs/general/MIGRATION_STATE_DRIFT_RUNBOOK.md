# Django Tenants Migration State Drift Runbook

## Purpose

Use this runbook when migrations fail with duplicate table/column errors even though Django says migrations are not applied, and business errors appear like:

- `column "type" of relation "sales_postedsalesinvoiceline" does not exist`
- `relation "<table>" already exists`
- `column "<column>" ... already exists`

This happened in our invoice posting flow because model code expected fields that were missing in some tenant schemas.

---

## Root Cause

Migration history drift between:

1. `django_migrations` records (what Django thinks is applied), and
2. actual schema objects in PostgreSQL (what exists physically).

In this state:

- `makemigrations` reports `No changes detected` (correct for code),
- but runtime fails because DB tables/columns are not aligned everywhere.

`RequestsDependencyWarning` from `requests`/`urllib3` is unrelated to this DB problem.

---

## Confirm Drift

Run:

```bash
python manage.py showmigrations dimension sales setup
```

Typical drift signal:

- many migrations show `[ ]`, but
- database already has related tables.

---

## Recovery Strategy (Safe)

### 1) Public schema first

Repair only conflicting migrations with `--fake` when objects already exist, then continue.

Example sequence used successfully:

```bash
python manage.py migrate_schemas --schema=public dimension 0002 --fake
python manage.py migrate_schemas --schema=public dimension 0004 --fake
python manage.py migrate_schemas --schema=public setup 0001 --fake
python manage.py migrate_schemas --schema=public setup 0002 --fake
python manage.py migrate_schemas --schema=public setup 0008 --fake
python manage.py migrate_schemas --schema=public sales
```

Notes:

- Do not blindly fake everything.
- Fake only migrations that fail because objects already exist.
- Re-run the migrate command after each resolved conflict.

---

### 2) Tenant schemas

Some tenants may still miss columns even after public is fixed.

Check which tenant schemas have `sales_postedsalesinvoiceline` and which of those already have `type`:

```sql
SELECT table_schema
FROM information_schema.tables
WHERE table_name = 'sales_postedsalesinvoiceline'
ORDER BY table_schema;

SELECT DISTINCT table_schema
FROM information_schema.columns
WHERE table_name = 'sales_postedsalesinvoiceline'
  AND column_name = 'type'
ORDER BY table_schema;
```

If any tenant schema is missing required columns, add missing fields safely with `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`.

Minimum fields that were missing in our incident:

- `type`
- `resource_id`
- `dimension_set_id`
- `global_dimension_1_id`

Example SQL template (run per affected tenant schema):

```sql
ALTER TABLE "<schema>"."sales_postedsalesinvoiceline"
  ADD COLUMN IF NOT EXISTS "type" varchar(10) NOT NULL DEFAULT 'item';

ALTER TABLE "<schema>"."sales_postedsalesinvoiceline"
  ADD COLUMN IF NOT EXISTS "resource_id" bigint NULL;

ALTER TABLE "<schema>"."sales_postedsalesinvoiceline"
  ADD COLUMN IF NOT EXISTS "dimension_set_id" bigint NULL;

ALTER TABLE "<schema>"."sales_postedsalesinvoiceline"
  ADD COLUMN IF NOT EXISTS "global_dimension_1_id" bigint NULL;
```

---

## Verification Checklist

1. Sales migrations show applied:

```bash
python manage.py showmigrations sales
```

Must include at least:

- `0006_add_line_type_and_resource` as `[X]`

2. Every tenant schema that has `sales_postedsalesinvoiceline` also has `type`:

```sql
SELECT t.table_schema
FROM information_schema.tables t
LEFT JOIN (
  SELECT DISTINCT table_schema
  FROM information_schema.columns
  WHERE table_name = 'sales_postedsalesinvoiceline'
    AND column_name = 'type'
) c
  ON c.table_schema = t.table_schema
WHERE t.table_name = 'sales_postedsalesinvoiceline'
  AND c.table_schema IS NULL;
```

Expected result: zero rows.

3. Functional test:

- Post a sales invoice in target tenant(s).
- Confirm no missing-column SQL error.

---

## Production Safety Rules

- Take a DB backup before migration repair.
- Run first in staging using production-like data.
- Use `--fake` only for migrations where DB objects already exist.
- Avoid destructive commands (`DROP`, `TRUNCATE`, reset migration history).
- Keep a log of each schema and command executed for audit/repeatability.

---

## Quick Incident Summary (This Case)

- Symptom: invoice posting failed on missing `sales_postedsalesinvoiceline.type`.
- Cause: migration state drift across schemas.
- Fix: selective `--fake` for conflicting migrations + complete `sales` chain + patch missing columns in tenant schemas + deploy migration `sales.0013_repair_posted_sales_invoice_line_drift` as a drift guard.
- Result: invoice posting no longer fails on missing `sales_postedsalesinvoiceline.type`, and future deploys self-heal the known drifted columns.
