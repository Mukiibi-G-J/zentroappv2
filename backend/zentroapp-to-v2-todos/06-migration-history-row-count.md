# 06 — Migration history row count mismatch (cosmetic)

**Migration:** zentroapp-web → zentroapp-webV2  
**Status:** ℹ️ Documented · No schema action required if checks pass  
**Index:** [README.md](./README.md)

---

## Observation

After full migration run:

| Migration row count | Tenants |
|---------------------|---------|
| **349** | `primewise`, `semuna`, `mtindohome` |
| **348** | `muxmedicalclinic`, `nitfy`, `skshasib`, `sukrésalé` |
| **301** | All other production tenants (21) |

`python manage.py migrate_schemas` reports **No migrations to apply** for 301-count tenants.

---

## Explanation

V2 squashed/renamed several migration files vs old **zentroapp-web**. Tenants that were migrated earlier on V2 (`primewise`, `semuna`, etc.) retain **extra rows** in `django_migrations` with **old migration names** (e.g. `authentication.0002_alter_role_description`) that no longer exist in the codebase.

Example: `primewise` has 48 migration rows that `bonus` does not — but `bonus` has **zero** rows that `primewise` lacks. The 301-count tenants are a **subset** of the history graph; schema is aligned.

348-count tenants are missing one legacy row name (e.g. `hotel_management.0002_remove_channelbooking_*`) that 349-count tenants have — not a pending codebase migration.

---

## How to verify (do this, not raw count)

```powershell
python scripts/compare_schema_checks.py
```

All 28 tenants passed critical V2 schema checks against `primewise` after migration run.

---

## Production guidance

- **Do not** manually insert migration rows to match 349 count
- **Do** use schema comparison scripts + functional smoke tests
- **Optional audit:** compare `django_migrations` app/name sets only when debugging a specific tenant failure

---

## Related

- [02-production-db-migration-run.md](./02-production-db-migration-run.md)
- [../docs/PRODUCTION_SCHEMA_DRIFT_REPAIR_AND_DIMENSION_BACKFILL.md](../docs/PRODUCTION_SCHEMA_DRIFT_REPAIR_AND_DIMENSION_BACKFILL.md)
