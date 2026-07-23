# Production Runbook: Unapplied Migrations / Missing `system_id`

## Symptom

Local or production backend logs show:

```text
You have N unapplied migration(s). Your project may not work properly until you apply the migrations for app(s): authentication, ...
```

And login fails with:

```text
django.db.utils.ProgrammingError: column authentication_customuser.system_id does not exist
POST /api/auth/token/ → 500
```

Related missing-column failures (same class of problem):

- `authentication_customuser.system_id` (migrations `authentication.0019` … `0023`)
- Other auth/company columns after a code deploy without `migrate_schemas`

## Root cause

Django models/JWT auth expect columns that are not yet present in PostgreSQL.

This app uses **django-tenants**. Applying only `migrate` (public) is not enough — every **tenant schema** must also receive the migrations.

## When this happens

- Fresh/restored DB, or DB behind a new release
- Deploy updated code without running tenant migrations
- Public schema migrated but tenant schemas left stale

## Production-safe fix

Settings module: use **`core.settingsprod`** in production (not `core.settings`).

### 1) Backup

Take a DB snapshot/backup before migrating.

### 2) Confirm pending migrations (read-only)

From the backend app directory, with production env / DB credentials:

```bash
export DJANGO_SETTINGS_MODULE=core.settingsprod

python manage.py showmigrations authentication | tail -30
python manage.py migrate_schemas --plan
```

Look for unapplied rows such as:

- `[ ] 0019_customuser_system_id`
- `[ ] 0023_ensure_customuser_system_id_column`

### 3) Apply migrations to public + all tenants

```bash
export DJANGO_SETTINGS_MODULE=core.settingsprod

# Preferred: all schemas (shared/public + every tenant)
python manage.py migrate_schemas
```

This can take a long time when many tenants exist (each schema applies the same pending set). Let it finish.

Optional targeted runs:

```bash
# Shared / public only
python manage.py migrate_schemas --shared

# One tenant (django-tenants uses -s / --schema_name, not --tenant=name)
python manage.py migrate_schemas -s thestormscafe
```

Example when a subdomain login fails but public already has the column:

```bash
# Symptom: http://thestormscafe.localhost:.../login → system_id does not exist
python manage.py migrate_schemas -s thestormscafe
```

Windows PowerShell equivalent:

```powershell
$env:DJANGO_SETTINGS_MODULE = "core.settingsprod"
python manage.py migrate_schemas
```

### Alternative when `migrate_schemas` fails mid-way (schema drift)

If a tenant already has tables but migration history is behind (e.g.
`relation "page_engine_page" already exists`), do **not** keep forcing a full
migrate on that schema. Repair the auth column across all schemas, then
reconcile migrations separately:

```bash
# Adds system_id + backfill + unique index everywhere it is missing
python manage.py repair_customuser_system_id_all_schemas --settings=core.settingsprod

# Optional check
python manage.py repair_customuser_system_id_all_schemas --settings=core.settingsprod --dry-run
```

Then reconcile Django migration state as needed (`migrate_schemas`, `--fake`,
or `--fake-initial` for drifted apps). Login only requires the column to exist.

Command source: `authentication/management/commands/repair_customuser_system_id_all_schemas.py`.

### 4) Verify `system_id` exists (public)

```bash
python manage.py shell --settings=core.settingsprod
```

```python
from django.db import connection
from django_tenants.utils import schema_context

with schema_context("public"):
    with connection.cursor() as c:
        c.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = current_schema()
              AND table_name = 'authentication_customuser'
              AND column_name = 'system_id'
            """
        )
        print(c.fetchone())  # expect ('system_id',)
```

Repeat with `schema_context("<tenant>")` for a sample tenant if needed.

### 5) Restart app processes

Restart gunicorn/uwsgi/Celery (and any `runserver` / desktop API proxies) so workers pick up a clean connection pool.

### 6) Retest login

- `POST /api/auth/token/` should return **200** (not 500)
- Desktop / web sign-in should proceed past the token step

## Local incident notes (2026-07-23)

What we saw and did on a local `zentroapp-webV2` DB:

1. Server warned about **53 unapplied migrations** (authentication, financials, items, pages, payments, purchases, resources, restaurant_management, sales, setup).
2. `POST /api/auth/token/` → 500: `authentication_customuser.system_id does not exist`.
3. `showmigrations authentication` showed pending from `0019_customuser_system_id` onward.
4. Ran:

```powershell
cd backend
.\.venv\Scripts\python.exe manage.py migrate_schemas
```

5. Confirmed **public** had `system_id` while `migrate_schemas` continued across remaining tenant schemas.
6. Login token endpoint worked after public auth migrations applied; remaining tenants continued migrating in the background.

## Related runbooks

- `docs/general/TOKEN_VALID_AFTER_PRODUCTION_RUNBOOK.md` — same pattern for `token_valid_after`
- `PRODUCTION_RUNBOOK.md` — standard “always run `migrate_schemas` first”
- `docs/template-schema.md` — `_zentro_template` rebuild after tenant migration changes

## Checklist (copy/paste)

- [ ] DB backup taken
- [ ] `DJANGO_SETTINGS_MODULE` points at the DB the app actually uses
- [ ] `showmigrations` / `--plan` reviewed
- [ ] `python manage.py migrate_schemas` completed (all schemas)
- [ ] `system_id` verified on public (+ sample tenant)
- [ ] App processes restarted
- [ ] `/api/auth/token/` returns 200
- [ ] If new tenant migrations were added: consider `rebuild_template_schema` / `verify_template_schema` so new signups stay fast
