# 07 — Public schema: `authentication_customuser.system_id` missing

**Migration:** zentroapp-web → zentroapp-webV2  
**Status:** ✅ Fixed locally (`public`) · ☐ Run on production  
**Index:** [README.md](./README.md)

---

## Symptom

`http://localhost:8002/admin/login/` (public / global admin) fails on POST:

```
ProgrammingError: column authentication_customuser.system_id does not exist
```

Tenant subdomains work if their schema has the column; **bare `localhost` uses `public`**.

---

## Cause

`authentication.0019_customuser_system_id` is **recorded** in `public.django_migrations` but the column was never created on `public.authentication_customuser` (same drift class as `token_valid_after` — see [docs/general/TOKEN_VALID_AFTER_PRODUCTION_RUNBOOK.md](../docs/general/TOKEN_VALID_AFTER_PRODUCTION_RUNBOOK.md)).

`localhost` admin login queries `AUTH_USER_MODEL` in **public**, not a tenant schema.

---

## Fix

```powershell
cd backend

# Immediate repair (all schemas missing the column)
python manage.py repair_customuser_system_id_all_schemas

# Dry-run first on production
python manage.py repair_customuser_system_id_all_schemas --dry-run

# Then apply repair migration on future deploys
python manage.py migrate_schemas --shared
python manage.py migrate_schemas
```

**Migration added:** `authentication.0023_ensure_customuser_system_id_column` (idempotent `RunPython` repair, like `0009` for `token_valid_after`).

---

## Verify

```powershell
python manage.py repair_customuser_system_id_all_schemas --dry-run
# Expected: "All schemas ... already have system_id."

# Or SQL
# SELECT column_name FROM information_schema.columns
# WHERE table_schema='public' AND table_name='authentication_customuser' AND column_name='system_id';
```

Retry `http://localhost:8002/admin/login/`.

---

## Related public drift (not blocking login)

Public may also lack tables from auth migrations 0018–0022 (`authentication_devicepushtoken`, `authentication_userpersonalization`, etc.) because those are tenant-app migrations recorded on public without creating objects. Only repair if a public-schema feature needs them.

---

## Production checklist

- [ ] `repair_customuser_system_id_all_schemas --dry-run`
- [ ] `repair_customuser_system_id_all_schemas`
- [ ] `migrate_schemas` (applies `0023`)
- [ ] Test public admin login on main domain
