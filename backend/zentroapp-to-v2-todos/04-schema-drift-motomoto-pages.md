# 04 — Schema drift: `motomoto` pages tables without migration rows

**Migration:** zentroapp-web → zentroapp-webV2  
**Status:** ✅ Fixed locally · ☐ Watch for same pattern on production  
**Index:** [README.md](./README.md)

---

## Symptom

`migrate_schemas --schema=motomoto` failed with:

```
ProgrammingError: relation "page_engine_page" already exists
```

while `django_migrations` had **no** `pages.*` rows (tenant stuck at 266 migration records).

Missing columns/tables vs other tenants:

- `authentication_devicepushtoken`
- `authentication_customuser.system_id`
- `purchases_vendorledger.applies_to_id`
- `sales_customerledgerentry.applies_to_id`

---

## Cause

Partial/failed migration left **tables created** but **migration history not recorded** (often combined with sequence errors from [03](./03-pg-sequence-reset-after-restore.md)).

---

## Fix applied

```powershell
# 1. Fix sequences first (if not done)
python scripts/fix_all_pg_sequences.py

# 2. Fake pages migrations — tables already exist
python manage.py migrate_schemas --schema=motomoto pages 0010 --fake

# 3. Apply remaining migrations
python manage.py migrate_schemas --schema=motomoto
```

**Result:** `motomoto` at 301 migration rows; passes all critical schema checks.

---

## If this happens on another tenant in production

1. Confirm table exists: `page_engine_page` in tenant schema
2. Confirm no `pages.*` rows in `django_migrations` for that schema
3. `--fake` pages through `0010`, then `migrate_schemas --schema=TENANT`
4. Re-run `scripts/compare_schema_checks.py`

**Do not** drop `page_engine_*` tables unless you intend a full re-migrate.
