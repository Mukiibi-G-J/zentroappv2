# Production Runbook: Auth/Company Schema Drift Recovery

## Token valid-after: Root cause + production-safe repair

Migration drift: `authentication_customuser.token_valid_after` exists in code/migrations but is missing in one or more DB schemas (including public). The ORM then issues `SELECT` statements that reference that column. **Any authenticated session** triggers this on every request (including [`/admin/login/`](https://zentroapp-backend.com/admin/login/) if the browser still has a session cookie), so you see **Server Error (500)** until the column exists everywhere.

### Settings module

Use **`core.settingsprod`** for production (not `core.settings`). Set `DJANGO_SETTINGS_MODULE=core.settingsprod` or pass `--settings=core.settingsprod` to `manage.py`.

### Production-safe fix (preferred: management command)

1. Take a DB backup/snapshot.
2. From the `zentro-backend` directory, with **the same database URL/credentials the running app uses** (production `.env`):

```bash
# See which schemas are missing the column (no writes)
python manage.py repair_token_valid_after_all_schemas --settings=core.settingsprod --dry-run

# Apply repair (adds column + index in every schema that has authentication_customuser)
python manage.py repair_token_valid_after_all_schemas --settings=core.settingsprod
```

3. Reconcile Django migration state:

```bash
python manage.py migrate authentication --settings=core.settingsprod
python manage.py migrate_schemas --tenant authentication --settings=core.settingsprod
python manage.py migrate_schemas --settings=core.settingsprod
```

4. **Restart** all backend processes (gunicorn/uwsgi, Celery workers, etc.).
5. Test admin in a **private/incognito window** (or clear site cookies). An old session can keep hitting the broken code path until cookies are cleared.

### Verification (optional)

```bash
python manage.py repair_token_valid_after_all_schemas --settings=core.settingsprod --dry-run
```

Expected: `All schemas with authentication_customuser already have token_valid_after.`

### Alternative: raw SQL one-liner (no manage.py)

If you cannot deploy the new command yet, from `zentro-backend` with `DJANGO_SETTINGS_MODULE=core.settingsprod`:

```bash
export DJANGO_SETTINGS_MODULE=core.settingsprod
python -c "import os; os.environ.setdefault('DJANGO_SETTINGS_MODULE','core.settingsprod'); import django; django.setup(); from django.db import connection; sql=\"\"\"DO \$\$ DECLARE r record; BEGIN FOR r IN SELECT n.nspname AS schema_name FROM pg_namespace n JOIN pg_class c ON c.relnamespace = n.oid WHERE c.relname = 'authentication_customuser' AND n.nspname NOT IN ('pg_catalog', 'information_schema') LOOP EXECUTE format('ALTER TABLE %I.authentication_customuser ADD COLUMN IF NOT EXISTS token_valid_after timestamptz NULL', r.schema_name); EXECUTE format('CREATE INDEX IF NOT EXISTS %I ON %I.authentication_customuser (token_valid_after)', 'authentication_customuser_token_valid_after', r.schema_name); END LOOP; END \$\$;\"\"\"; cur=connection.cursor(); cur.execute(sql); cur.close(); print('repair-complete')"
```

### If it still 500 after repair

- Read the **server traceback** (e.g. gunicorn logs). If the error names a **different** missing column or table, use `MIGRATION_STATE_DRIFT_RUNBOOK.md` and fix that object.
- For `global_dimension_1` / `dimension_1` validation issues on users, see `authentication.management.commands.fix_user_dimension_1` (run via `tenant_command` per schema).
- Confirm production **`DJANGO_SETTINGS_MODULE`** matches the settings you used for the repair (so you repaired the same database the app uses).

### Notes

- Migration `authentication.0009_ensure_token_valid_after_column` adds the column per **current** schema only; multi-schema setups may still need the cross-schema repair above.
- Command source: `authentication/management/commands/repair_token_valid_after_all_schemas.py`.

## Scope

Use this when a production DB snapshot is loaded into local/staging and Django throws:

- `column ... does not exist`
- `relation ... does not exist`
- `InconsistentMigrationHistory`
- `/api/auth/token/` failures caused by missing auth/company schema objects

This is a multi-tenant setup. Always account for `public` and tenant schemas.

## Incident Summary (What We Did)

During this incident, we fixed:

1. Migration history mismatch:
   - `financials.0003_initial` applied before dependency `bank_account.0002_initial`.
2. Missing auth columns:
   - `authentication_customuser.can_switch_branch`
   - `authentication_customuser.restaurant_pin_hash`
   - `authentication_customuser.token_valid_after`
3. Missing company columns/tables:
   - `company_company.module_overrides`
   - `company_company.user_limit_override`
   - `company_pricing.included_modules`
   - `company_addon` table
4. Missing auth tables:
   - `authentication_usergroup`
   - `authentication_usersetup`
   - `authentication_usergroup_members`
   - `authentication_usergroup_permission_sets`
5. Token serializer runtime bug:
   - Filtering `Subscription` by `company=tenant` when tenant is `FakeTenant`.
   - Fixed by using safe `company_id` logic.

## Recovery Principles

1. Take backup/snapshot first.
2. Prefer idempotent SQL:
   - `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`
   - `CREATE TABLE IF NOT EXISTS`
3. Repair across every schema containing the target table.
4. Validate endpoint behavior after each patch.
5. Keep command log for audit/production replay.

## Command Patterns

Run from `zentro-backend`.

### A) Patch auth columns across all schemas with `authentication_customuser`

```bash
python manage.py shell -c 'from django.db import connection; c=connection.cursor(); c.execute("SELECT table_schema FROM information_schema.tables WHERE table_name=''authentication_customuser'' AND table_schema NOT IN (''pg_catalog'',''information_schema'') ORDER BY table_schema;"); schemas=[r[0] for r in c.fetchall()]; 
for s in schemas:
    c.execute(f"ALTER TABLE \"{s}\".authentication_customuser ADD COLUMN IF NOT EXISTS can_switch_branch boolean NOT NULL DEFAULT TRUE;")
    c.execute(f"ALTER TABLE \"{s}\".authentication_customuser ADD COLUMN IF NOT EXISTS restaurant_pin_hash varchar(128) NULL;")
    c.execute(f"ALTER TABLE \"{s}\".authentication_customuser ADD COLUMN IF NOT EXISTS token_valid_after timestamptz NULL;")
print("patched:", schemas)'
```

### B) Patch company columns in `public`

```bash
python manage.py shell -c 'from django.db import connection; c=connection.cursor(); c.execute("ALTER TABLE public.company_company ADD COLUMN IF NOT EXISTS module_overrides jsonb NOT NULL DEFAULT ''[]''::jsonb;"); c.execute("ALTER TABLE public.company_company ADD COLUMN IF NOT EXISTS user_limit_override integer NULL;"); c.execute("ALTER TABLE public.company_pricing ADD COLUMN IF NOT EXISTS included_modules jsonb NOT NULL DEFAULT ''[]''::jsonb;"); print("company columns patched")'
```

### C) Create missing tables (idempotent)

Use `CREATE TABLE IF NOT EXISTS` for known missing runtime tables (for example `company_addon`, `authentication_usergroup`, `authentication_usersetup`, and related M2M tables), then retry the endpoint.

## Verification Checklist

1. `POST /api/auth/token/` returns `200`.
2. No `relation ... does not exist` / `column ... does not exist` in logs.
3. `/api/company/add-ons/` returns `200`.
4. `python manage.py showmigrations authentication company setup` is coherent for target env.
5. Verify required auth columns:

```bash
python manage.py shell -c 'from django.db import connection; c=connection.cursor(); c.execute("SELECT table_schema, column_name FROM information_schema.columns WHERE table_name=''authentication_customuser'' AND column_name IN (''can_switch_branch'',''restaurant_pin_hash'',''token_valid_after'') ORDER BY table_schema, column_name;"); print(c.fetchall())'
```

## Production Notes

- Apply during maintenance window when possible.
- Test on staging snapshot first.
- Do not run destructive resets.
- Keep schema drift patches minimal and reversible.
