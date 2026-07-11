# 03 — PostgreSQL sequence reset after restore

**Migration:** zentroapp-web → zentroapp-webV2  
**Status:** ✅ Fixed locally · ☐ Run on production before/after `migrate_schemas`  
**Index:** [README.md](./README.md)

---

## Problem

After restoring a production PostgreSQL dump, `migrate_schemas` fails with:

```
IntegrityError: duplicate key value violates unique constraint "django_migrations_pkey"
DETAIL: Key (id)=(1) already exists.
```

or during `post_migrate`:

```
IntegrityError: duplicate key value violates unique constraint "django_content_type_pkey"
DETAIL: Key (id)=(1) already exists.
```

**Root cause:** `pg_restore` / dump copy leaves serial sequences (`*_id_seq`) at `1` while tables already contain rows with higher IDs.

**Affected locally:** 8 tenants on first `pages.0001_initial` (`cminteriors`, `icecube`, `moubarak`, `phonefixsenegal`, `restaurantdemo`, `restaurantdemo1`, `shopwise`, and others with `seq=1`).

---

## Fix

Run **before** or **immediately after** first failed migrate attempt:

```powershell
cd backend
python scripts/fix_all_pg_sequences.py
```

This resets every serial sequence in `public` and each tenant schema to `MAX(id)` per table.

Then retry:

```powershell
python manage.py migrate_schemas
# or per tenant
python manage.py migrate_schemas --schema=TENANT
```

---

## Manual SQL (single schema)

```sql
SET search_path TO TENANT_SCHEMA;

SELECT setval(
  pg_get_serial_sequence('django_migrations', 'id'),
  COALESCE((SELECT MAX(id) FROM django_migrations), 1),
  true
);

SELECT setval(
  pg_get_serial_sequence('django_content_type', 'id'),
  COALESCE((SELECT MAX(id) FROM django_content_type), 1),
  true
);
```

Prefer `fix_all_pg_sequences.py` — it covers all tables with serial columns.

---

## Production checklist

- [ ] Take DB backup
- [ ] `migrate_schemas --shared`
- [ ] `python scripts/fix_all_pg_sequences.py`
- [ ] `migrate_schemas` (all allowed tenants)
- [ ] If migrate fails mid-tenant: fix sequences again, retry that schema only
