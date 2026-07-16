# 08 — Primewise pilot: restore prod dump → V2 ready

**Migration:** zentroapp-web → zentroapp-webV2  
**Status:** ✅ Local `primewise` on restored prod dump (Jul 2026)  
**Index:** [README.md](./README.md)

---

## Goal

Take one real production schema (`primewise`) through every V2 gap. When this is green, repeat the same steps for other tenants.

---

## Checklist

### A. Schema (DDL)

- [x] Point `.env` at restored DB (`zentroapp_refactor`)
- [x] Fix sequences for `public` + `primewise` (after `pg_restore`)
- [x] `migrate_schemas --shared` (needs resilient `authentication.0020` index rename)
- [x] `migrate_schemas --schema=primewise`
- [x] Critical columns/tables present (see verify below)

### B. Auth / repairs

- [x] `system_id` present on `primewise.authentication_customuser`
- [x] `token_valid_after` present
- [ ] Public/global admin: `repair_customuser_system_id_all_schemas` (other schemas still missing — optional for primewise-only pilot)

### C. Data + V2 engine (was missing from older todos)

- [x] `seed_pages --schema=primewise` (pages engine + BC `object_id` sync)
- [x] `tenant_command setup_page_permissions --schema=primewise` (BC-style permission sets)
- [x] `clear_invalid_ledger_applies_to_ids --schema=primewise` (0 rows on this dump)
- [x] `tenant_command backfill_entry_dimensions --schema=primewise --first-branch`
  - **No-op on this dump:** all tables `updated=0 matched=0`. Does **not** create/rename/merge branch values (Central / Mwanjarai unchanged). Only fills NULL `global_dimension_1` / `dimension_set_id` on ledgers/docs.
- [ ] Optional: `populate_page_objects` (legacy module IDs) — not required if navigating via page engine; Windows console may need `PYTHONIOENCODING=utf-8`
- [ ] Smoke: login `primewise.localhost`, Role Centre, Item/Customer/Vendor lists, Apply Entries

---

## Copy-paste (PowerShell, from `backend/`)

```powershell
cd C:\PROJECTS\zentroapp-webV2\backend
.\.venv\Scripts\activate
$env:PYTHONPATH = (Get-Location).Path
$env:PYTHONIOENCODING = "utf-8"

# 1) Sequences (public + pilot tenant)
python scripts/_fix_primewise_sequences.py
# Or all tenants: python scripts/fix_all_pg_sequences.py

# 2) Migrations
python manage.py migrate_schemas --shared
python manage.py migrate_schemas --schema=primewise

# 3) Pages engine + BC permissions (REQUIRED for V2 UI)
python manage.py seed_pages --schema=primewise
python manage.py tenant_command setup_page_permissions --schema=primewise

# 4) Ledger / dimensions
python manage.py clear_invalid_ledger_applies_to_ids --schema=primewise
python manage.py tenant_command backfill_entry_dimensions --schema=primewise --first-branch

# 5) Verify
python scripts/_assess_primewise_v2.py
```

---

## Verify (must all be green)

| Check | Expected |
|-------|----------|
| `page_engine_page` table | exists |
| `page_engine_page` row count | **> 0** after `seed_pages` |
| `authentication_customuser.system_id` | column exists |
| `purchases_vendorledger.applies_to_id` | column exists |
| `sales_customerledgerentry.applies_to_id` | column exists |
| Payment rows with `applies_to_id` set | **0** |
| BC permission sets | updated via `setup_page_permissions` |

Helper: `scripts/_assess_primewise_v2.py`

---

## Gaps this todo adds (vs 00–07)

| Gap | Why it matters |
|-----|----------------|
| **`seed_pages`** | V2 dynamic UI / Role Centre; empty `page_engine_*` after migrate alone |
| **BC `setup_page_permissions`** | Permission lines use page-engine object IDs (1000 + BC page id) |
| **Primewise-only migrate** | Faster iteration than migrating all 30+ tenants first |
| **`authentication.0020` safe RenameIndex** | Shared migrate failed on restored public when old `auth_devpush_*` indexes missing |

---

## Related

- Playbook: [00-restore-production-db-playbook.md](./00-restore-production-db-playbook.md)
- Sequences: [03-pg-sequence-reset-after-restore.md](./03-pg-sequence-reset-after-restore.md)
- Payment applies-to: [01-payment-ledger-applies-to-id.md](./01-payment-ledger-applies-to-id.md)
- Template seed (new companies): [../docs/template-schema.md](../docs/template-schema.md)

---

## Local results (this restore)

| Item | Result |
|------|--------|
| Schema checks | All critical V2 columns/tables **present** |
| Migrations on `primewise` | **364** rows |
| `seed_pages` | Lists/cards + restaurant + permission set pages seeded |
| `setup_page_permissions` | 28 updated, 5 created, 139 lines |
| Bad payment `applies_to_id` | **0** |
| Pages after seed | **130** rows (`102` with BC `object_id`) |
| Permission sets | **42** after BC setup |
| Dimension `--first-branch` | **No row updates** (existing branches intact) |
| Other tenants | Still need migrate / `system_id` repair (not in pilot scope) |
