# 00 — Restore production DB playbook (replay every time)

**Use this** whenever you import a fresh dump from **production** (or staging) into local/dev, or before **go-live** on the real production server.

**Goal:** Apply zentroapp-webV2 migrations and repairs without surprises.

**Index:** [README.md](./README.md)

---

## Quick copy-paste (PowerShell, from `backend/`)

```powershell
cd C:\PROJECTS\zentroapp-webV2\backend
.\.venv\Scripts\activate

# --- 1. Migrations (shared first) ---
python manage.py migrate_schemas --shared

# --- 2. Fix PG sequences (REQUIRED after pg_restore) ---
python scripts/fix_all_pg_sequences.py

# --- 3. Tenant migrations ---
python manage.py migrate_schemas
# If a tenant fails mid-run: fix sequences again, then:
#   python manage.py migrate_schemas --schema=TENANT_NAME

# --- 4. Auth column repairs (public admin login) ---
python manage.py repair_customuser_system_id_all_schemas --dry-run
python manage.py repair_customuser_system_id_all_schemas
python manage.py repair_token_valid_after_all_schemas --dry-run
python manage.py repair_token_valid_after_all_schemas

# --- 5. Apply any new repair migrations ---
python manage.py migrate_schemas --shared
python manage.py migrate_schemas

# --- 6. Verify ---
python scripts/compare_schema_checks.py
python scripts/final_migration_audit.py

# --- 7. Smoke tests ---
# Public admin: http://localhost:8002/admin/login/
# Tenant admin: http://TENANT.localhost:8002/admin/

# --- 8. V2 pages engine (REQUIRED per tenant used in V2 UI) ---
# python manage.py seed_pages --schema=primewise
# python manage.py tenant_command setup_page_permissions --schema=primewise
# See: 08-primewise-v2-readiness.md
```

---

## Step-by-step (with “if this fails”)

### 1. Restore DB and point `.env` at it

- Restore dump into PostgreSQL (e.g. `zentroapp_refactor` locally).
- Confirm `backend/core/.env` has correct `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`.

### 2. Shared migrations

```powershell
python manage.py migrate_schemas --shared
```

Applies public-schema migrations (company, pages auth 0018–0022, etc.).

**Symptom if skipped:** `relation "company_domain" does not exist` on API requests.

→ Detail: [02-production-db-migration-run.md](./02-production-db-migration-run.md)

### 3. Reset PostgreSQL sequences (mandatory after restore)

```powershell
python scripts/fix_all_pg_sequences.py
```

**Symptom if skipped:**

- `duplicate key value violates unique constraint "django_migrations_pkey"`
- `duplicate key value violates unique constraint "django_content_type_pkey"`

→ Detail: [03-pg-sequence-reset-after-restore.md](./03-pg-sequence-reset-after-restore.md)

### 4. Tenant migrations

```powershell
python manage.py migrate_schemas
```

If it stops on one tenant:

1. Run `fix_all_pg_sequences.py` again.
2. Retry that tenant only: `python manage.py migrate_schemas --schema=TENANT`.

**Special case — pages table exists but migration not recorded:**

```powershell
python manage.py migrate_schemas --schema=TENANT pages 0010 --fake
python manage.py migrate_schemas --schema=TENANT
```

→ Detail: [04-schema-drift-motomoto-pages.md](./04-schema-drift-motomoto-pages.md)

### 5. Public auth column repairs

Migrations can be **recorded** without the column existing on **public** (bare `localhost` admin).

```powershell
python manage.py repair_customuser_system_id_all_schemas
python manage.py repair_token_valid_after_all_schemas
```

**Symptom if skipped:**

- `column authentication_customuser.system_id does not exist` at `/admin/login/`
- Similar for `token_valid_after` on authenticated requests

→ Detail: [07-public-schema-system-id.md](./07-public-schema-system-id.md)  
→ Also: [../docs/general/TOKEN_VALID_AFTER_PRODUCTION_RUNBOOK.md](../docs/general/TOKEN_VALID_AFTER_PRODUCTION_RUNBOOK.md)

### 6. Verify schema (do not rely on migration row counts alone)

```powershell
python scripts/compare_schema_checks.py
python scripts/final_migration_audit.py
```

- **Pass:** `All tenants match primewise on critical V2 schema checks.`
- Migration counts may differ (301 vs 349) — that is OK if checks pass.

→ Detail: [06-migration-history-row-count.md](./06-migration-history-row-count.md)

### 7. Before go-live only (not every local restore)

```powershell
python manage.py makemigrations --check
```

If this fails, create and apply new migrations before production deploy.

→ Detail: [05-unmigrated-model-changes.md](./05-unmigrated-model-changes.md)

### 8. Post-migration data work (production)

After schema is healthy:

```powershell
python manage.py clear_invalid_ledger_applies_to_ids
# Per tenant seeds, permissions, dimension backfill — see PRODUCTION_RUNBOOK.md
```

→ Detail: [01-payment-ledger-applies-to-id.md](./01-payment-ledger-applies-to-id.md)

---

## Helper scripts (keep in repo)

| Script | When to run |
|--------|-------------|
| `scripts/fix_all_pg_sequences.py` | **Every** restore, before/after migrate |
| `scripts/compare_schema_checks.py` | After migrate — confirms all tenants |
| `scripts/final_migration_audit.py` | Optional audit of migration counts |
| `scripts/migrate_pending_tenants.py` | Tenants missing `page_engine_page` |

## Management commands (repairs)

| Command | When to run |
|---------|-------------|
| `repair_customuser_system_id_all_schemas` | After restore; public admin login |
| `repair_token_valid_after_all_schemas` | After restore; session/JWT drift |
| `clear_invalid_ledger_applies_to_ids` | After migrate; payment ledger data fix |

---

## Checklist (tick each restore)

- [ ] DB restored; `.env` points to it
- [ ] `migrate_schemas --shared`
- [ ] `fix_all_pg_sequences.py`
- [ ] `migrate_schemas` (all tenants)
- [ ] `repair_customuser_system_id_all_schemas`
- [ ] `repair_token_valid_after_all_schemas`
- [ ] `migrate_schemas` again (if new repair migrations added)
- [ ] `compare_schema_checks.py` — all OK
- [ ] Public admin login works (`localhost:8002/admin/`)
- [ ] One tenant subdomain login works
- [ ] (Go-live) `makemigrations --check` passes
- [ ] (Go-live) payment ledger cleanup + seeds per runbook

---

## Production go-live note

On live Zentro, some tenants (`primewise`, `semuna`) may be intentionally excluded from tenant migrate — see [../docs/PRODUCTION_ZENTRO_TEMPLATE_RELEASE_PROMPT.md](../docs/PRODUCTION_ZENTRO_TEMPLATE_RELEASE_PROMPT.md). For a **full local prod copy**, migrate all tenants.

---

## Session reference (Jul 2026 local restore)

What we hit on first prod dump → V2 migrate:

| Issue | Fix |
|-------|-----|
| `company_domain` missing | `migrate_schemas --shared` |
| `django_migrations_pkey` duplicate | `fix_all_pg_sequences.py` |
| `motomoto` pages drift | fake `pages 0010` + migrate |
| Public admin `system_id` missing | `repair_customuser_system_id_all_schemas` |
| 301 vs 349 migration rows | Cosmetic — use `compare_schema_checks.py` |
| `auth_devpush_user_active_idx` missing on shared migrate | Safe rename in `authentication.0020` — [10](./10-auth-0020-safe-index-rename.md) |
| Empty `page_engine_page` after migrate | `seed_pages` + BC permissions — [08](./08-primewise-v2-readiness.md) |
| Slow new-company signup | Pre-seed `_zentro_template` — [09](./09-preseeded-zentro-template.md) |

All documented in todos `02`–`10` in this folder.
