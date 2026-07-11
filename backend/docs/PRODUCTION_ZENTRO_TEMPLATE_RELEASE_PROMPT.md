# Production / release handoff — Zentro golden template and recent fixes

Copy everything below the line into your deployment ticket, runbook, or chat with the production engineer.

---

## Context (what changed in the app)

Multi-tenant signup clones a **golden PostgreSQL schema** named **`_zentro_template`** instead of replaying every tenant migration per new company (fast vs slow).

**Recent fixes (high level):**

- **Golden template**: New tenants need `_zentro_template` built after code + migrations land; otherwise `Company.save` logs a warning and falls back to **slow per-tenant migrations** for each signup.
- **Signup UX**: Prevent double-submit on company creation; trial success route is **public** so users are not bounced to `/landing?redirectUrl=...` before seeing the success screen; post-trial navigation sends unauthenticated users to **sign-in**.
- **Verification email / OTP**: Account verification emails use the same **Mailtrap / Django `EMAIL_*`** path as other transactional mail (no dependency on a public `EmailSetup` row). **`/api/auth/resend-otp/`** and **`/api/auth/verify-otp/`** are **AllowAny** so unverified users are not blocked by JWT rules.
- **Debug admin**: Centralized in **`ensure_debug_admin_for_schema`**; runs after template clone commits and again post-bootstrap so every tenant gets the debug admin user when configured.

---

## What production must run (migrations + Zentro template)

Run from the **backend** directory. **Zentro production** uses **`--settings=core.settingsprod`** (see `core/settingsprod.py`).

### Zentro production: tenant migrations (who gets migrated)

On the live Zentro database, **do not** run tenant migrations on **`primewise`** or **`semuna`** (legacy / intentional drift). **Do** migrate **`public` (shared apps)** and **every other tenant schema** registered in `company_company` so new code matches the DB.

`migrate_schemas` with no flags migrates **all** tenants, so use **shared first**, then **per-schema tenant** migrations for allowed tenants only (django-tenants 3.7 has no built-in exclude list).

### 1. Deploy application code

Merge/deploy the release branch that includes the template clone, `rebuild_template_schema`, and `verify_template_schema` commands.

### 2. Apply database migrations (shared + allowed tenants only)

**Step A — shared / `public` schema:**

```bash
python manage.py migrate_schemas --shared --settings=core.settingsprod
```

**Step B — tenant apps on each schema except `primewise` and `semuna`:**

From the backend root, run (adjust `SKIP` if you add more frozen schemas):

```bash
python manage.py shell --settings=core.settingsprod <<'PY'
from django.core.management import call_command
from django_tenants.utils import get_public_schema_name
from company.models import Company

SKIP = {"primewise", "semuna", get_public_schema_name(), "_zentro_template"}
qs = Company.objects.exclude(schema_name__in=SKIP).values_list("schema_name", flat=True).order_by("schema_name")
for schema_name in qs:
    print(f"--- migrate_schemas --tenant --schema={schema_name} ---")
    call_command("migrate_schemas", schema_name=schema_name, tenant=True, interactive=False)
print("Done.")
PY
```

**Alternative (not recommended on Zentro prod):** `python manage.py migrate_schemas --settings=core.settingsprod` migrates **every** tenant including `primewise` and `semuna` — only use if you have explicitly unfrozen those schemas.

Tenant apps on allowed schemas must be current **before** rebuilding the golden template (step 3).

### 3. Build the golden template schema (required once per environment, and after tenant migration changes)

This **drops and recreates** `_zentro_template` from full tenant migrations and removes the throwaway `Company` row so the template is **not** linked in `public.company_company`:

```bash
python manage.py rebuild_template_schema --settings=core.settingsprod
```

**Scheduling:** Run during a maintenance window if you prefer; it replaces the `_zentro_template` schema. Existing real tenant schemas are **not** dropped.

### 4. Verify the template (CI or manual gate)

```bash
python manage.py verify_template_schema --settings=core.settingsprod
```

- **Exit 0**: `_zentro_template` exists and has **no pending migrations**.
- **Exit 1**: Missing or stale — **do not** consider signup “fast path” healthy until this passes.

Add **`verify_template_schema`** to your release pipeline after **`rebuild_template_schema`** (or after migrations if you rely on the app’s optional atexit rebuild — see below).

### 5. Optional: CI / scripted migrations without surprise rebuild

If a job runs migrations and you **do not** want the Django process to trigger an automatic template rebuild on exit:

```bash
export DISABLE_TEMPLATE_REBUILD=1
python manage.py migrate_schemas --shared --settings=core.settingsprod
# Then run the same shell loop as in §2 Step B (skip primewise / semuna), or your CI equivalent.
python manage.py rebuild_template_schema --settings=core.settingsprod
python manage.py verify_template_schema --settings=core.settingsprod
```

---

## Operational notes

- **`primewise` / `semuna`**: If you skip tenant migrations there, those schemas stay on older migration state until you run a targeted repair; **new signups** still use **`_zentro_template`** (fast path) once steps 3–4 pass. Plan separately if those two tenants must eventually catch up.
- **`_zentro_template`** must not remain as a normal tenant row in `public.company_company` after `rebuild_template_schema` (the command cleans that up).
- **Email**: Ensure production **`DEFAULT_FROM_EMAIL`**, **`EMAIL_*`**, and/or **`MAILTRAP_SEND_API_KEY`** (or `EMAIL_HOST_API_KEY`) match your working transactional mail setup so verification OTPs send.
- **Full reference**: [template-schema.md](./template-schema.md)

---

## Checklist for the release owner

- [ ] Code deployed
- [ ] Shared + **allowed** tenant `migrate_schemas` completed (`primewise` / `semuna` skipped unless intentionally unfrozen)
- [ ] `rebuild_template_schema` executed successfully
- [ ] `verify_template_schema` exits **0**
- [ ] Spot-check: create a test company (or staging) and confirm signup completes in **seconds**, not many minutes

---

_End of handoff block._
