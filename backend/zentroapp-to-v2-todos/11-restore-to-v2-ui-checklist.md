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
| 3 | Missing `page_engine_field` columns on tenant | Seed crashes | Add `relation_lookup_footer`, `relation_part_control_name` |
| 4 | No `UserPersonalization` | No Role Centre for user | Backfill default `BUSINESS-MGR` |
| 5 | Subscription expired | `/api/pages/` → **402**; empty UI | Extend / renew subscription |
| 6 | Nginx header buffers 16k | Admin JWT ~19KB → **400 Request Header Or Cookie Too Large** | Buffers **64k** + slim JWT for super users |
| 7 | Apex API login (no tenant Host) | Same email logs into **public** user, not tenant | `TenantJWTMiddleware` resolves tenant from **Origin** |
| 8 | Domains still `*.zentroapp-backend.com` | Wrong Host / SSL | Remap to `*.zentroapp-api.uncodedsolutions.com` |
| 9 | V2 deploy overwrites V1 supervisor | V1 **502** | Keep V2 as `zentrov2-*.conf` only |

Code fixes that should already be in the repo (verify after pull):

- `utils/tenant_middleware.py` — Origin/Referer → tenant schema  
- `authentication/serializers.py` — no full `page_permissions` in JWT for super users  
- `authentication/views.py` — login response includes session (`navItems`, `roleCentrePageId`)  
- `deploy/nginx/zentro-api.conf` — `large_client_header_buffers 4 64k`

---

## Full checklist (new DB / new tenant)

### 0. Infra (once per server)

- [ ] V2 gunicorn on its own port (e.g. `:8002`) — **do not** overwrite V1 `zentro-*.conf`
- [ ] Nginx site for `zentroapp-api.uncodedsolutions.com` with:

```nginx
client_header_buffer_size 64k;
large_client_header_buffers 4 64k;
```

- [ ] Reload nginx: `nginx -t && systemctl reload nginx`
- [ ] Frontend env: `NEXT_PUBLIC_API_URL` / base URL → `https://zentroapp-api.uncodedsolutions.com`
- [ ] Optional later: wildcard SSL for `*.zentroapp-api.uncodedsolutions.com`

### 1. Restore + migrate

```bash
cd /root/projects/zentro-appv2/backend
source ../env/bin/activate
export DJANGO_SETTINGS_MODULE=core.settingsprod
export PYTHONPATH=$(pwd)
export PYTHONIOENCODING=utf-8

# After pg_restore into zentroapp_v2_db (or your DB):
python scripts/_fix_primewise_sequences.py   # or fix_all_pg_sequences.py
python manage.py migrate_schemas --shared
python manage.py migrate_schemas --schema=TENANT --tenant
```

### 2. Remap domains (V1 host → V2 API host)

```sql
-- Run against restored DB
UPDATE company_domain
SET domain = replace(domain, '.zentroapp-backend.com', '.zentroapp-api.uncodedsolutions.com')
WHERE domain LIKE '%.zentroapp-backend.com';

UPDATE company_company
SET domain_url = replace(domain_url, '.zentroapp-backend.com', '.zentroapp-api.uncodedsolutions.com')
WHERE domain_url LIKE '%.zentroapp-backend.com';
```

Expect tenant API domain like: `TENANT.zentroapp-api.uncodedsolutions.com`

### 3. Auth column repairs

```bash
python manage.py repair_customuser_system_id_all_schemas
python manage.py repair_token_valid_after_all_schemas
```

### 4. Page engine DDL gaps (common after restore)

Tenant `page_engine_*` tables may exist but miss newer columns. Before `seed_pages`:

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

### 7. Backfill UserPersonalization (Role Centre profile)

```bash
python manage.py shell --settings=core.settingsprod <<'PY'
from django_tenants.utils import schema_context
from authentication.models import CustomUser, UserPersonalization, ApplicationProfile

SCHEMA = 'primewise'  # change me
with schema_context(SCHEMA):
    default = ApplicationProfile.objects.filter(code='BUSINESS-MGR').first()
    assert default and default.role_centre_page_id, 'seed_pages / profiles missing'
    for u in CustomUser.objects.all():
        p, _ = UserPersonalization.objects.get_or_create(
            user=u,
            defaults={
                'role': default,
                'created_by': u.email,
                'modified_by': u.email,
            },
        )
        if not p.role_id:
            p.role = default
            p.save(update_fields=['role'])
    print('users', CustomUser.objects.count(),
          'personalizations', UserPersonalization.objects.count(),
          'RC', default.role_centre_page.name)
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
Sidebar empty / cards show "—"
├─ Network: /api/auth/me/ or /api/pages/ → 400 "Header Too Large"
│    → nginx 64k buffers + slim JWT; re-login
├─ Network: /api/pages/ → 402 subscription_expired
│    → renew / extend subscription; re-login
├─ /api/auth/me/ → navItems=[] or roleCentrePageId=null
│    → seed_pages + ApplicationProfile FK + UserPersonalization
├─ me/ shows wrong name / "User" / public user
│    → Origin tenant middleware; clear tokens; re-login on tenant subdomain
└─ me/ has nav but UI still empty
     → confirm frontend calls /api/pages/rolecentre/?PageId=<rc>
```

---

## Related

- Playbook: [00-restore-production-db-playbook.md](./00-restore-production-db-playbook.md)  
- Pilot: [08-primewise-v2-readiness.md](./08-primewise-v2-readiness.md)  
- **Zentro page IDs (PageId == ObjectId):** [12-page-id-vs-object-id.md](./12-page-id-vs-object-id.md)  
- Sequences: [03-pg-sequence-reset-after-restore.md](./03-pg-sequence-reset-after-restore.md)  
- Deploy: [../../deploy/DEPLOY.md](../../deploy/DEPLOY.md)  
- Nginx template: [../../deploy/nginx/zentro-api.conf](../../deploy/nginx/zentro-api.conf)
