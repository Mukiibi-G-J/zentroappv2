# Production Runbook: `must_change_password` Auth Schema Drift

## Symptom

Login fails with HTTP 500 on `/api/auth/token/`:

```text
psycopg2.errors.UndefinedColumn:
column authentication_customuser.must_change_password does not exist
```

UI may show a generic “Invalid username or password” if the frontend maps non-401 failures poorly. The real error is in Django logs.

## Root cause

Tenant schema(s) are behind on `authentication` migrations. The model/code expects `CustomUser.must_change_password` (migration `authentication.0024_customuser_must_change_password`), but the column was never created in that schema.

Common companion drift (seen on `thestormscafe` locally):

| Migration | Issue |
|-----------|--------|
| `0019_customuser_system_id` | Column `system_id` **already exists**, but migration is **not** recorded → plain `migrate` fails with `DuplicateColumn` |
| `0020`–`0026` | Not applied → missing personalization / application profile / `must_change_password` / impersonation audit |

`authentication` is in both `SHARED_APPS` and `TENANT_APPS`, so **each tenant schema that has `authentication_customuser` must be aligned**.

---

## Settings module

| Environment | Settings |
|-------------|----------|
| Local / staging (V2) | `core.settings` |
| Production | `core.settingsprod` |

Always use the same DB credentials as the running app.

```bash
# Production examples below use:
export DJANGO_SETTINGS_MODULE=core.settingsprod
# or pass --settings=core.settingsprod on every manage.py call
```

---

## Before you touch production

1. **Backup / snapshot** the database.
2. Confirm which schemas are broken (read-only check below).
3. Prefer migrating **one known-bad tenant** first, then scan for others.
4. Schedule a short maintenance window if you will run full `migrate_schemas` (can be slow and may run `RunPython` seed steps).

---

## 1) Find affected schemas (read-only)

```sql
SELECT n.nspname AS schema_name,
       EXISTS (
         SELECT 1
         FROM information_schema.columns c
         WHERE c.table_schema = n.nspname
           AND c.table_name = 'authentication_customuser'
           AND c.column_name = 'must_change_password'
       ) AS has_must_change_password,
       EXISTS (
         SELECT 1
         FROM information_schema.columns c
         WHERE c.table_schema = n.nspname
           AND c.table_name = 'authentication_customuser'
           AND c.column_name = 'system_id'
       ) AS has_system_id
FROM pg_namespace n
JOIN pg_class t ON t.relnamespace = n.oid AND t.relname = 'authentication_customuser'
WHERE n.nspname NOT IN ('pg_catalog', 'information_schema')
ORDER BY 1;
```

Any row with `has_must_change_password = false` needs repair.

Replace `thestormscafe` below with each affected `schema_name` (or run the “all tenants” section).

---

## 2) Confirm Django migration history for one tenant

```bash
cd /path/to/zentroapp-webV2/backend
python manage.py tenant_command showmigrations authentication \
  --schema=thestormscafe \
  --settings=core.settingsprod
```

Expected healthy end state includes:

```text
 [X] 0019_customuser_system_id
 [X] 0020_userpersonalization
 [X] 0021_applicationprofile
 [X] 0022_userpersonalization_role_fk
 [X] 0023_ensure_customuser_system_id_column
 [X] 0024_customuser_must_change_password
 [X] 0025_impersonationauditlog
 [X] 0026_impersonationauditlog_schema_name
```

If `0019` is `[ ]` but SQL shows `system_id` already exists, you must **fake** `0019` before migrating further.

---

## 3) Repair one tenant (what we did for `thestormscafe`)

### Step A — Fake `0019` only if `system_id` already exists

```bash
# Only when DuplicateColumn would otherwise fail:
python manage.py migrate_schemas --schema=thestormscafe authentication 0019 --fake \
  --settings=core.settingsprod
```

### Step B — Apply remaining authentication migrations

```bash
python manage.py migrate_schemas --schema=thestormscafe authentication \
  --settings=core.settingsprod
```

This should apply `0020` … `0026` and create `must_change_password`.

### Step C — Optional: catch up other apps on that tenant

Only if that tenant is also behind on other apps:

```bash
python manage.py migrate_schemas --schema=thestormscafe \
  --settings=core.settingsprod
```

**Note:** A full per-tenant migrate can take a long time and may execute seed/`RunPython` migrations. For a login outage, **Step B alone is enough**.

---

## 4) Verify the fix

### Column exists

```sql
SELECT column_name, data_type, column_default
FROM information_schema.columns
WHERE table_schema = 'thestormscafe'
  AND table_name = 'authentication_customuser'
  AND column_name = 'must_change_password';
```

Expect one row (`boolean`, default `false`).

### Migration recorded

```bash
python manage.py tenant_command showmigrations authentication \
  --schema=thestormscafe \
  --settings=core.settingsprod
```

`0024_customuser_must_change_password` must be `[X]`.

### Login

```bash
# Smoke: POST token for that tenant (Host / Origin must resolve the tenant)
curl -s -o /tmp/token.json -w "%{http_code}" \
  -X POST "https://YOUR_API_HOST/api/auth/token/" \
  -H "Content-Type: application/json" \
  -H "Origin: https://thestormscafe.YOUR_FRONTEND_DOMAIN" \
  -d '{"username":"USER","password":"PASS"}'
```

Expect `200` (or `401` for bad credentials) — **not** `500`.

Restart gunicorn/Celery only if workers were started before deploy; schema changes are usually visible immediately to new DB connections.

---

## 5) Production: repair all tenants that are missing the column

After fixing one tenant and confirming login works:

### Option A — Per schema (safest, explicit)

For each schema from the SQL report with `has_must_change_password = false`:

```bash
SCHEMA=other_tenant

# Fake 0019 only if system_id exists and 0019 is unapplied
python manage.py migrate_schemas --schema=$SCHEMA authentication 0019 --fake \
  --settings=core.settingsprod

python manage.py migrate_schemas --schema=$SCHEMA authentication \
  --settings=core.settingsprod
```

### Option B — All tenants authentication only

```bash
# Migrates authentication across tenants (django-tenants)
python manage.py migrate_schemas --tenant authentication \
  --settings=core.settingsprod
```

If any tenant fails with `DuplicateColumn: system_id`, fake `0019` for **that** schema (Step A), then re-run Option B / per-schema Step B.

### Option C — Emergency SQL (column only; still reconcile migrations)

If you cannot run Django immediately, add the column everywhere it is missing, then fake/reconcile migrations so Django history matches:

```sql
DO $$
DECLARE r record;
BEGIN
  FOR r IN
    SELECT n.nspname AS schema_name
    FROM pg_namespace n
    JOIN pg_class c ON c.relnamespace = n.oid
    WHERE c.relname = 'authentication_customuser'
      AND n.nspname NOT IN ('pg_catalog', 'information_schema')
  LOOP
    EXECUTE format(
      'ALTER TABLE %I.authentication_customuser
       ADD COLUMN IF NOT EXISTS must_change_password boolean NOT NULL DEFAULT false',
      r.schema_name
    );
  END LOOP;
END $$;
```

Then for each repaired schema, ensure Django records `0024` (and any earlier missing auth migrations) via `migrate` / `--fake` as appropriate — **do not leave history permanently out of sync**.

---

## Incident log (local `thestormscafe`, 2026-07-20)

| Step | Action | Result |
|------|--------|--------|
| 1 | `tenant_command showmigrations authentication --schema=thestormscafe` | `0019`–`0026` unapplied |
| 2 | `migrate_schemas --schema=thestormscafe` | Failed: `DuplicateColumn system_id` on `0019` |
| 3 | Confirmed `system_id` present, `must_change_password` absent | Drift confirmed |
| 4 | `migrate_schemas --schema=thestormscafe authentication 0019 --fake` | OK |
| 5 | `migrate_schemas --schema=thestormscafe authentication` | Applied `0020`–`0026` including `0024` |
| 6 | Optional full `migrate_schemas --schema=thestormscafe` | Completed (exit 0); not required for login fix |
| 7 | Verified column list includes `must_change_password` | Token login unblocked |
| 8 | After login: `/api/auth/me/` and `/api/pages/` 500 | `page_engine_page.object_id` missing |
| 9 | `showmigrations pages` → `0005`–`0016` unapplied | Includes `0013_page_object_id` |
| 10 | `migrate_schemas --schema=thestormscafe pages` | Applied `0005`–`0016`; `object_id` present |

---

## Companion fix: missing `page_engine_page.object_id`

### Symptom (after auth token succeeds)

```text
Error building auth session: column page_engine_page.object_id does not exist
Internal Server Error: /api/auth/me/
Internal Server Error: /api/pages/
```

### Cause

Tenant is behind on `pages` migrations. Column is added by `pages.0013_page_object_id`. On `thestormscafe`, `0005`–`0016` were all unapplied.

### Production repair

```bash
python manage.py tenant_command showmigrations pages \
  --schema=THE_SCHEMA \
  --settings=core.settingsprod

python manage.py migrate_schemas --schema=THE_SCHEMA pages \
  --settings=core.settingsprod
```

### Verify

```sql
SELECT column_name
FROM information_schema.columns
WHERE table_schema = 'THE_SCHEMA'
  AND table_name = 'page_engine_page'
  AND column_name = 'object_id';
```

Then confirm `GET /api/auth/me/` returns 200 for that tenant.

### Find all schemas missing `object_id`

```sql
SELECT n.nspname AS schema_name
FROM pg_namespace n
JOIN pg_class t ON t.relnamespace = n.oid AND t.relname = 'page_engine_page'
WHERE n.nspname NOT IN ('pg_catalog', 'information_schema')
  AND NOT EXISTS (
    SELECT 1 FROM information_schema.columns c
    WHERE c.table_schema = n.nspname
      AND c.table_name = 'page_engine_page'
      AND c.column_name = 'object_id'
  )
ORDER BY 1;
```

**Production tip:** After fixing auth drift on a restored/old tenant, immediately catch up `pages` (and ideally run `showmigrations` for other apps) — login can succeed while session/pages still 500.

---

## Do / Don’t

**Do**

- Backup first.
- Fake **only** migrations whose objects already exist.
- Prefer app-scoped migrate (`authentication`, then `pages`) for outages.
- Re-check **all** tenant schemas after fixing one.
- After token works, smoke-test `/api/auth/me/` before calling the tenant healthy.

**Don’t**

- Blindly `--fake` all authentication migrations.
- Assume `public` alone is enough (tenant login uses the tenant schema).
- Ignore a `DuplicateColumn` by skipping the rest of the queue — fake the conflicting migration, then continue.
- Stop after `authentication` only if `/api/auth/me/` still fails — check `pages` next.

---

## Related docs

- [MIGRATION_STATE_DRIFT_RUNBOOK.md](./MIGRATION_STATE_DRIFT_RUNBOOK.md) — general fake-then-migrate pattern
- [TOKEN_VALID_AFTER_PRODUCTION_RUNBOOK.md](./TOKEN_VALID_AFTER_PRODUCTION_RUNBOOK.md) — similar auth column drift (`token_valid_after`)
- Migration sources:
  - `authentication/migrations/0024_customuser_must_change_password.py`
  - `pages/migrations/0013_page_object_id.py`
