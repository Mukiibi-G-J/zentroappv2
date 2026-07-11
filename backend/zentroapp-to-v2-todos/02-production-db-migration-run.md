# 02 — Production DB migration run (local restore)

**Migration:** zentroapp-web → zentroapp-webV2  
**Status:** ✅ Shared + tenant migrations applied on restored production DB (28 tenants)  
**Environment:** Local dev with production DB dump (Jul 2026)  
**Index:** [README.md](./README.md)

---

## Checklist

- [x] Backup verified (production dump restored locally)
- [x] `python manage.py migrate_schemas --shared`
- [x] `python manage.py migrate_schemas` (all tenants)
- [x] Fix PostgreSQL sequences after restore — [03-pg-sequence-reset-after-restore.md](./03-pg-sequence-reset-after-restore.md)
- [x] Repair `motomoto` pages drift (fake + migrate) — [04-schema-drift-motomoto-pages.md](./04-schema-drift-motomoto-pages.md)
- [x] Schema spot-check vs `primewise` — all tenants pass
- [ ] Ship pending model migrations before go-live — [05-unmigrated-model-changes.md](./05-unmigrated-model-changes.md)
- [ ] Post-migration data todos — [01-payment-ledger-applies-to-id.md](./01-payment-ledger-applies-to-id.md)
- [ ] Per-tenant seeds / permissions (production runbook)

---

## Commands run (order)

```powershell
cd backend

# 1. Shared (public) schema — 35 pending migrations applied
python manage.py migrate_schemas --shared

# 2. All tenant schemas — partial success; see issues 03 + 04
python manage.py migrate_schemas

# 3. Reset broken PG sequences (required after pg_restore)
python manage.py shell < scripts/fix_all_pg_sequences.py
# Or: python scripts/fix_all_pg_sequences.py  (with PYTHONPATH=backend)

# 4. Retry failed tenants (after sequence fix)
python scripts/migrate_pending_tenants.py

# 5. motomoto: pages table existed without migration rows
python manage.py migrate_schemas --schema=motomoto pages 0010 --fake
python manage.py migrate_schemas --schema=motomoto

# 6. Verify
python scripts/compare_schema_checks.py
python scripts/final_migration_audit.py
```

---

## Results summary

| Area | Result |
|------|--------|
| **Public schema** | 35 migrations applied; `company_domain` restored (was missing before migrate) |
| **Tenants** | 28 companies; all pass critical V2 schema checks vs `primewise` |
| **Blockers hit** | PG sequence desync; `motomoto` pages drift |
| **Migration row count** | 25 tenants show 301 rows vs 349 on `primewise`/`semuna`/`mtindohome` — see [06-migration-history-row-count.md](./06-migration-history-row-count.md) (cosmetic; schema OK) |
| **Pending code** | `makemigrations --check` fails — new migrations needed before prod deploy |

---

## Critical schema checks (all tenants ✅)

Verified present on every tenant (reference: `primewise`):

- `page_engine_page`
- `sync_device`
- `authentication_devicepushtoken`
- `authentication_customuser.system_id`
- `authentication_customuser.token_valid_after`
- `purchases_vendorledger.applies_to_id`
- `sales_customerledgerentry.applies_to_id`

Script: `backend/scripts/compare_schema_checks.py`

---

## Production go-live order

1. **Backup** production DB
2. `migrate_schemas --shared`
3. `scripts/fix_all_pg_sequences.py` on **public + all tenant schemas**
4. `migrate_schemas` (or per-tenant if excluding `primewise`/`semuna` per [PRODUCTION_ZENTRO_TEMPLATE_RELEASE_PROMPT.md](../docs/PRODUCTION_ZENTRO_TEMPLATE_RELEASE_PROMPT.md))
5. Re-run `compare_schema_checks.py`; fix any drift (fake + migrate pattern)
6. Complete data todos (payment ledger cleanup, dimension backfill, seeds)
7. Smoke test per tenant

---

## Helper scripts (this repo)

| Script | Purpose |
|--------|---------|
| `scripts/fix_all_pg_sequences.py` | Reset all serial sequences after restore |
| `scripts/compare_schema_checks.py` | Compare critical tables/columns vs reference tenant |
| `scripts/final_migration_audit.py` | Migration row counts + `page_engine_page` presence |
| `scripts/migrate_pending_tenants.py` | Migrate tenants missing `page_engine_page` |
