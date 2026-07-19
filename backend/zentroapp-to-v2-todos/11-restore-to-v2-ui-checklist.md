# 11 — After any DB restore: make V2 web UI work (Role Centre + login)

**Use this every time** you restore a dump into V2 (`zentroapp_v2_db` or another DB) and expect the Next.js frontend to work.

**Symptom if skipped:** empty sidebar (*“No navigation for your role”*), dashboard cards show `—`, profile shows generic **User**, or login authenticates the wrong company.

**Index:** [README.md](./README.md)  
**Pilot detail:** [08-primewise-v2-readiness.md](./08-primewise-v2-readiness.md)

Replace `TENANT` / `primewise` with your schema name.

---

## Why this exists (Jul 2026 production restore lessons)

Restoring V1 dump + migrating is **not enough** for V2 UI. These failed in production and must be repeated:

| # | Failure | What you see | Fix |
|---|---------|--------------|-----|
| 1 | No `seed_pages` | Empty pages / no Role Centre | `seed_pages --schema=TENANT` |
| 2 | `ApplicationProfile.role_centre_page` FK → `public.page_engine_page` | Seed/RC broken | Recreate FK → `TENANT.page_engine_page` |
| 3 | Missing `page_engine_field` columns on tenant | Seed crashes on `relation_lookup_footer` | `pages/schema_ddl.py` `DDL_ALTER` + SQL below |
| 4 | Blanket `BUSINESS-MGR` for every user | All users same Role Centre | `assign_application_profiles --force` from old roles/groups |
| 5 | Subscription expired | `/api/pages/` → **402**; empty UI | Extend / renew subscription |
| 6 | Nginx header buffers 16k | Admin JWT ~19KB → **400 Request Header Or Cookie Too Large** | Buffers **64k** + slim JWT for super users |
| 7 | Apex API login (no tenant Host) | Same email logs into **public** user, not tenant | `TenantJWTMiddleware` resolves tenant from **Origin** |
| 8 | Domains / nginx hosts | Wrong API host after cutover | **V2** = `*.zentroapp-backend.com`; **V1** parked on `zentroapp-api.uncodedsolutions.com` |

| 9 | V2 deploy overwrites V1 supervisor | V1 **502** | Keep V2 as `zentrov2-*.conf` only |
| 10 | `zentrov2` left **STOPPED** after restore | Login shows CORS / “Invalid password”; API **502** | `supervisorctl start zentrov2` (and celery) before smoke |
| 11 | Document URL uses **Sales Invoice** SystemId on Posted page | Posted Sales Invoice **404** | Backend resolves linked posted doc (`pages/views.py`) |

Code fixes that should already be in the repo (verify after pull):

- `utils/tenant_middleware.py` — Origin/Referer → tenant schema  
- `authentication/serializers.py` — no full `page_permissions` in JWT for super users  
- `authentication/views.py` — login response includes session (`navItems`, `roleCentrePageId`)  
- `authentication/profile_assignment.py` — Role Centre from legacy Role / UserGroup  
- `pages/schema_ddl.py` — `relation_lookup_footer` / `relation_part_control_name` in `DDL_ALTER`  
- `pages/bc_page_ids.py` + `align_zentro_page_ids` — PageId == ObjectId (Zentro 10xxx)  
- `pages/views.py` — PostedSalesInvoice lookup via linked SalesInvoice SystemId  
- `deploy/nginx/zentro-api.conf` — `large_client_header_buffers 4 64k`

---

## Full checklist (new DB / new tenant)

### 0. Infra (once per server)

- [ ] V2 gunicorn on its own port (e.g. `:8002`) — **do not** overwrite V1 `zentro-*.conf`
- [ ] Nginx site for **V2**: `.zentroapp-backend.com` → `:8002` (64k header buffers)
- [ ] Nginx site for **V1** (parked): `zentroapp-api.uncodedsolutions.com` → `:8000`
- [ ] Reload nginx: `nginx -t && systemctl reload nginx`
- [ ] Frontend env: `NEXT_PUBLIC_API_URL` / base URL → `https://zentroapp-backend.com`
- [ ] Optional: wildcard SSL already on `*.zentroapp-backend.com`; V1 api host is apex-only unless you add `*.zentroapp-api...`

### 1. Restore + migrate

```bash
# Stop V2 before restore (reconnects will fail otherwise)
supervisorctl stop zentrov2 zentrov2-celery zentrov2-celery-beat zentrov2-flower

# Recreate target DB (jom often cannot CREATE DATABASE — use postgres)
sudo -u postgres psql -v ON_ERROR_STOP=1 <<'SQL'
SELECT pg_terminate_backend(pid) FROM pg_stat_activity
WHERE datname = 'zentroapp_v2_db' AND pid <> pg_backend_pid();
DROP DATABASE IF EXISTS zentroapp_v2_db;
CREATE DATABASE zentroapp_v2_db OWNER jom;
SQL

pg_restore -h 127.0.0.1 -U jom -d zentroapp_v2_db --no-owner --no-acl -j 2 /path/to/dump.dump

cd /root/projects/zentro-appv2/backend
source ../env/bin/activate
export DJANGO_SETTINGS_MODULE=core.settingsprod
export PYTHONPATH=$(pwd)
export PYTHONIOENCODING=utf-8

# After pg_restore into zentroapp_v2_db (or your DB):
python scripts/fix_all_pg_sequences.py
python manage.py migrate_schemas --shared
# Pilot first (faster) — migrate other tenants later the same way:
python manage.py migrate_schemas --schema=TENANT --tenant
```

**Do not leave V2 stopped** — start it again after migrate (or at latest before login smoke):

```bash
supervisorctl start zentrov2 zentrov2-celery zentrov2-celery-beat zentrov2-flower
```

### 2. Remap domains (match nginx cutover)

**V2 DB** (`zentroapp_v2_db`) — production API host:

```sql
UPDATE company_domain
SET domain = replace(domain, '.zentroapp-api.uncodedsolutions.com', '.zentroapp-backend.com')
WHERE domain LIKE '%.zentroapp-api.uncodedsolutions.com';

UPDATE company_company
SET domain_url = replace(domain_url, '.zentroapp-api.uncodedsolutions.com', '.zentroapp-backend.com')
WHERE domain_url LIKE '%.zentroapp-api.uncodedsolutions.com';
```

Expect: `TENANT.zentroapp-backend.com`

**V1 DB** (`zentroapp_db`) — parked:

```sql
UPDATE company_domain
SET domain = replace(domain, '.zentroapp-backend.com', '.zentroapp-api.uncodedsolutions.com')
WHERE domain LIKE '%.zentroapp-backend.com';

UPDATE company_company
SET domain_url = replace(domain_url, '.zentroapp-backend.com', '.zentroapp-api.uncodedsolutions.com')
WHERE domain_url LIKE '%.zentroapp-backend.com';
```

### 3. Auth column repairs

```bash
python manage.py repair_customuser_system_id_all_schemas
python manage.py repair_token_valid_after_all_schemas
```

### 4. Page engine DDL gaps (common after restore)

Tenant `page_engine_*` tables may exist but miss newer columns. Before `seed_pages`,
`ensure_page_engine_schema` / `pages/schema_ddl.py` `DDL_ALTER` should add them. If seed
still fails, run:

```sql
ALTER TABLE TENANT.page_engine_field
  ADD COLUMN IF NOT EXISTS relation_lookup_footer boolean NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS relation_part_control_name varchar(200) NULL;
-- Also fix _zentro_template.page_engine_field if template is used for signup
```

### 5. Fix ApplicationProfile → Role Centre FK (critical)

After restore, FK often points at **`public.page_engine_page`**. Seed then fails or RC is wrong.

```sql
ALTER TABLE TENANT.authentication_applicationprofile
  DROP CONSTRAINT IF EXISTS authentication_appli_role_centre_page_id_afff28e4_fk_page_engi;

-- Clear stale page ids that don't exist in tenant pages
UPDATE TENANT.authentication_applicationprofile
SET role_centre_page_id = NULL
WHERE role_centre_page_id IS NOT NULL
  AND role_centre_page_id NOT IN (SELECT page_id FROM TENANT.page_engine_page);

ALTER TABLE TENANT.authentication_applicationprofile
  ADD CONSTRAINT authentication_appli_role_centre_page_id_afff28e4_fk_page_engi
  FOREIGN KEY (role_centre_page_id)
  REFERENCES TENANT.page_engine_page(page_id)
  DEFERRABLE INITIALLY DEFERRED;
```

Constraint name may differ — check with:

```sql
SELECT conname, confrelid::regclass
FROM pg_constraint
WHERE conrelid = 'TENANT.authentication_applicationprofile'::regclass
  AND contype = 'f';
```

### 6. Seed pages + permissions

```bash
python manage.py seed_pages --schema=TENANT
# seed aligns PageId == ObjectId from ZENTRO_PAGE_REGISTRY (10xxx)
python manage.py tenant_command setup_page_permissions --schema=TENANT
python manage.py clear_invalid_ledger_applies_to_ids --schema=TENANT
python manage.py tenant_command backfill_entry_dimensions --schema=TENANT --first-branch
```

If pages were seeded before the Zentro ID align:

```bash
python manage.py tenant_command align_zentro_page_ids --schema=TENANT
python manage.py tenant_command setup_page_permissions --schema=TENANT
```

### 7. Backfill UserPersonalization (Role Centre from old access)

**Do not** assign every user `BUSINESS-MGR`. Map from legacy `Role.role_center` / `UserGroup`:

```bash
python manage.py tenant_command assign_application_profiles --schema=TENANT --force
```

Mapping (see `authentication/profile_assignment.py`):

| Old RoleCenter / UserGroup | ApplicationProfile |
|----------------------------|--------------------|
| ADMIN_CENTER / ADMIN | BUSINESS-MGR |
| CASHIER_CENTER / DISPENSER | CASHIER |
| MANAGER_CENTER / MANAGER | OPERATIONS-MGR |
| INVENTORY_CENTER / PHARCIST | PHARMACIST |
| INVENTORY_MANAGER | WAREHOUSE |

Optional verify:

```bash
python manage.py shell --settings=core.settingsprod <<'PY'
from django_tenants.utils import schema_context
from authentication.models import CustomUser, UserPersonalization

SCHEMA = 'primewise'
with schema_context(SCHEMA):
    for u in CustomUser.objects.all().order_by('username'):
        p = UserPersonalization.objects.filter(user=u).select_related('role').first()
        print(u.username, '->', p.role.code if p and p.role_id else None)
PY
```

### 8. Subscription must be active

`SubscriptionCheckMiddleware` returns **402** on `/api/pages/` when expired. Frontend then looks empty even if `/api/auth/me/` has nav.

```bash
python manage.py shell --settings=core.settingsprod <<'PY'
from datetime import date, timedelta
from django_tenants.utils import schema_context
from company.models import Company, Subscription

SCHEMA = 'primewise'
with schema_context('public'):
    c = Company.objects.get(schema_name=SCHEMA)
    sub = Subscription.objects.filter(company=c).first()
    print('before', sub.status, sub.subscription_end_date, 'active=', sub.is_active())
    # Pilot only — for real go-live use billing, don't silently extend
    sub.subscription_end_date = date.today() + timedelta(days=60)
    sub.status = 'active'
    sub.save(update_fields=['subscription_end_date', 'status'])
    print('after', sub.subscription_end_date, 'active=', sub.is_active())
PY
```

### 9. Restart V2 + smoke

```bash
supervisorctl restart zentrov2
```

Verify (with a token issued **after** Origin middleware is live, from the tenant frontend host):

| Check | Expected |
|-------|----------|
| Login Origin `https://TENANT.zentroapp.uncodedsolutions.com` | Authenticates **tenant** user, not `public` user with same email |
| API base URL | `https://zentroapp-backend.com` (V2) |
| JWT `schema_name` | `TENANT` (not `public`) |
| JWT size (Admin) | ≲ ~5KB after slim `page_permissions` |
| `GET /api/auth/me/` | `roleCentrePageId` set, `navItems.length > 0`, `user.fullName` correct |
| `GET /api/pages/` | **200** (not 402 / 400) |
| `GET /api/pages/rolecentre/?PageId=<rc>` | Sections + NavItems |
| Browser | Sign **out** + sign **in** (stale public JWT is useless) |

Helper for primewise: `python scripts/_assess_primewise_v2.py`

---

## Same email in `public` and tenant (gotcha)

Production dumps often have `mukiibijoseph19@gmail.com` (etc.) in **both** `public` and `primewise`.

| Schema | Example | Role Centre |
|--------|---------|-------------|
| `public` | id=1, username `Mukiibi-G-J` | None / wrong |
| `primewise` | id=6, `Joseph Mukiibi` / `debug_admin` | Business Manager |

Frontend → apex API without Origin/tenant Host used to log into **public**.  
Middleware must map Origin `TENANT.zentroapp.uncodedsolutions.com` → schema `TENANT` **before** `/api/auth/token/`.

After any middleware fix: users **must sign out and sign in** so JWT `schema_name` is the tenant.

---

## Empty UI decision tree

```
Sidebar empty / cards show "—" / login "Invalid password" + CORS
├─ Network: /api/auth/token/ → CORS / 502
│    → zentrov2 STOPPED? supervisorctl start zentrov2; re-login
├─ Network: /api/auth/me/ or /api/pages/ → 400 "Header Too Large"
│    → nginx 64k buffers + slim JWT; re-login
├─ Network: /api/pages/ → 402 subscription_expired
│    → renew / extend subscription; re-login
├─ /api/auth/me/ → navItems=[] or roleCentrePageId=null
│    → seed_pages + ApplicationProfile FK + assign_application_profiles
├─ me/ shows wrong name / "User" / public user
│    → Origin tenant middleware; clear tokens; re-login on tenant subdomain
├─ Posted document 404 (PageId ok, SystemId is open Sales Invoice)
│    → backend linked-invoice resolve (already in pages/views.py); re-try
└─ me/ has nav but UI still empty
     → confirm frontend calls /api/pages/rolecentre/?PageId=<rc>
```

---

## Related

- Playbook: [00-restore-production-db-playbook.md](./00-restore-production-db-playbook.md)  
- Pilot: [08-primewise-v2-readiness.md](./08-primewise-v2-readiness.md)  
- **Zentro page IDs (PageId == ObjectId):** [12-page-id-vs-object-id.md](./12-page-id-vs-object-id.md)  
- Profile mapping: [`../authentication/profile_assignment.py`](../authentication/profile_assignment.py)  
- Sequences: [03-pg-sequence-reset-after-restore.md](./03-pg-sequence-reset-after-restore.md)  
- Deploy: [../../deploy/DEPLOY.md](../../deploy/DEPLOY.md)  
- Nginx template: [../../deploy/nginx/zentro-api.conf](../../deploy/nginx/zentro-api.conf)
