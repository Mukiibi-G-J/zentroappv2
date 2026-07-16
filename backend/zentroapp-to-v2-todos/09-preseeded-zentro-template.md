# 09 — Pre-seeded `_zentro_template` (fast company creation)

**Feature:** zentroapp-webV2 company signup performance  
**Status:** ✅ Code landed (Jul 2026) · ☐ Rebuild template on each env after deploy  
**Index:** [README.md](./README.md)

---

## Goal

New companies clone a **pre-seeded** golden schema instead of re-running roles, pages engine, page permissions, JSON import, and seed commands on every signup.

---

## What was implemented

| Piece | Path / command |
|-------|----------------|
| Shared baseline bootstrap | `company/tenant_baseline.py` (`run_tenant_baseline_bootstrap`) |
| Rebuild seeds template | `rebuild_template_schema` → migrations **then** baseline bootstrap |
| Signup skips duplicate work | `create_company_task` uses `tenant_has_baseline_data()` after clone |
| Verify includes baseline | `verify_template_schema` fails if pages/roles/permissions/no-series missing |
| Docs | `docs/template-schema.md`, `docs/COMPANY_CREATION_PERFORMANCE.md` |

### Baked into template (tenant-generic)

- Roles, role centres, user groups  
- `seed_pages` (pages engine + Zentro PageId/ObjectId)  
- `setup_page_permissions` + legacy `populate_page_objects`  
- JSON chart/posting import + related seeds  
- Number series + PurchasePayable / SalesReceivable  

### Still done per new company (company-specific)

- Admin user, domain, subscription patch  
- Location contact fields  
- General vendor/customer addresses  
- Debug admin / SMS / completion email  

---

## Checklist (every env after template-affecting migrations)

- [ ] `python manage.py rebuild_template_schema` (slow once; seeds baseline)
- [ ] `python manage.py verify_template_schema` (exit 0)
- [ ] Signup one company → Celery log should show `Using pre-seeded template baseline` / `skipped: template baseline`
- [ ] Grep `company_creation_timing` — roles/import phases near-zero when seeded

```powershell
cd backend
python manage.py rebuild_template_schema
python manage.py verify_template_schema
```

If template is **empty DDL only** (old rebuild), signup still runs full bootstrap (safe fallback).

---

## Related

- [../docs/template-schema.md](../docs/template-schema.md)
- [../docs/COMPANY_CREATION_PERFORMANCE.md](../docs/COMPANY_CREATION_PERFORMANCE.md)
- [../docs/PRODUCTION_ZENTRO_TEMPLATE_RELEASE_PROMPT.md](../docs/PRODUCTION_ZENTRO_TEMPLATE_RELEASE_PROMPT.md)
- Existing-tenant pilot (not new signup): [08-primewise-v2-readiness.md](./08-primewise-v2-readiness.md)
