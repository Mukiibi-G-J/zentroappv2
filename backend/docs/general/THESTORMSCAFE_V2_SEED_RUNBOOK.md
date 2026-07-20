# Production Runbook: Seed V2 UI + Storms Cafe (`thestormscafe`)

## Symptom

After migrations on a restored/old tenant:

| What you see | Cause |
|--------------|--------|
| `GET /api/pages/` → `[]` | No page-engine rows |
| Sidebar: “No navigation for your roles…” | Missing Role Centre / ApplicationProfile / page permissions |
| Dashboard Items/Customers/Vendors = `—` | Empty master data (and/or empty pages) |
| Login works, UI empty | Seed not run (migrate alone is not enough) |

## Root cause

V2 UI needs **page engine data** (`seed_pages`) plus **permission sets** and **ApplicationProfile** assignment. Restaurant POS also needs **restaurant module + menu** seeds.

This is the same flow as [11-restore-to-v2-ui-checklist.md](../../zentroapp-to-v2-todos/11-restore-to-v2-ui-checklist.md) and [08-primewise-v2-readiness.md](../../zentroapp-to-v2-todos/08-primewise-v2-readiness.md), specialized for **`thestormscafe`**.

---

## Settings

| Environment | Settings |
|-------------|----------|
| Local | `core.settings` |
| Production | `core.settingsprod` |

```bash
export DJANGO_SETTINGS_MODULE=core.settingsprod   # production
cd /path/to/zentroapp-webV2/backend
```

---

## Prerequisites (DDL)

Ensure the tenant has current migrations **before** seeding. `seed_pages` will fail if tables are missing, e.g.:

- `payments_cashreceiptjournalbatch` → migrate `payments`
- `financials_generaljournalbatch` → migrate `financials` (incl. `0015_general_journal`)
- `page_engine_page.object_id` → migrate `pages` through `0013_page_object_id`

```bash
# Auth drift (must_change_password) — see MUST_CHANGE_PASSWORD_SCHEMA_DRIFT_RUNBOOK.md
python manage.py migrate_schemas --schema=thestormscafe authentication 0019 --fake --settings=core.settingsprod  # only if system_id exists
python manage.py migrate_schemas --schema=thestormscafe authentication --settings=core.settingsprod
python manage.py migrate_schemas --schema=thestormscafe pages --settings=core.settingsprod
python manage.py migrate_schemas --schema=thestormscafe payments --settings=core.settingsprod
python manage.py migrate_schemas --schema=thestormscafe financials --settings=core.settingsprod

# Or catch all remaining for that tenant:
python manage.py migrate_schemas --schema=thestormscafe --settings=core.settingsprod
```

Also repair auth/pages column drift per:

- [MUST_CHANGE_PASSWORD_SCHEMA_DRIFT_RUNBOOK.md](./MUST_CHANGE_PASSWORD_SCHEMA_DRIFT_RUNBOOK.md)

---

## Seed sequence (production copy-paste)

Replace settings flag for local as needed. Run from `backend/`.

### 1) Pages engine (REQUIRED for sidebar / `/api/pages/`)

```bash
python manage.py seed_pages --schema=thestormscafe --settings=core.settingsprod
```

Creates Role Centre pages, list/card pages, restaurant pages, receipt templates, aligns PageId == ObjectId, and assigns ApplicationProfiles when possible.

**Expect:** `Done — schema: thestormscafe` and list/card page IDs printed.

### 2) Page permission sets (REQUIRED for non-superuser nav)

```bash
python manage.py tenant_command setup_page_permissions --schema=thestormscafe --settings=core.settingsprod
```

**Expect:** `Page permissions setup complete!` (sets updated / lines created).

### 3) Sync page permission Objects (recommended)

```bash
python manage.py tenant_command sync_page_permission_objects --schema=thestormscafe --settings=core.settingsprod
```

**Expect:** `thestormscafe: created=… updated=…` (local run: `updated=108`).

> Note: without `--schema`, this command walks **all** tenants. Prefer `--schema=` in production.

### 4) Role Centre profiles for users

```bash
python manage.py tenant_command assign_application_profiles --schema=thestormscafe --force --settings=core.settingsprod
```

Maps legacy Role / UserGroup → ApplicationProfile (do **not** blanket BUSINESS-MGR for everyone).

### 5) Restaurant module scaffolding

```bash
python manage.py tenant_command seed_restaurant_module --schema=thestormscafe --settings=core.settingsprod
```

May warn/error on duplicate permission-set lines if step 2 already created them — that is usually safe to ignore if restaurant NoSeries / menu series are already configured.

### 6) Storms Cafe menu + POS items (tenant-specific)

```bash
python manage.py tenant_command seed_storms_cafe_menu --schema=thestormscafe --settings=core.settingsprod
# Dry-run first if desired:
# python manage.py tenant_command seed_storms_cafe_menu --schema=thestormscafe --dry-run --settings=core.settingsprod
```

**Expect (local Jul 2026):**  
`82 items created, 82 menu items created, 13 categories, 7 display groups.`

### 7) Guest digital menu (QR / public `/menu` with images)

Requires migration `restaurant_management.0020_digital_menu_publication` (and static assets under `frontend/public/images/restaurant/storms-cafe/`).

```bash
python manage.py migrate_schemas --schema=thestormscafe restaurant_management --settings=core.settingsprod
python manage.py tenant_command seed_digital_menu --schema=thestormscafe --settings=core.settingsprod
# Optional refresh:
# python manage.py tenant_command seed_digital_menu --schema=thestormscafe --clear --settings=core.settingsprod
```

**Expect:** `publication=main, sections=7, lines=82`

Guest URL (local): `http://thestormscafe.localhost:3000/menu`  
API: `GET /api/restaurant/public-menu/` (no auth; subscription middleware allows it)

---

## Verify

```sql
-- Pages must be > 0
SELECT COUNT(*) FROM thestormscafe.page_engine_page;

-- Menu / items after storms seed (Item model uses db_table = "items")
SELECT COUNT(*) FROM thestormscafe.items;
SELECT COUNT(*) FROM thestormscafe.restaurant_management_menuitem;
SELECT COUNT(*) FROM thestormscafe.authentication_applicationprofile;
```

Smoke (after **sign out + sign in** so session rebuilds):

| Check | Expected |
|-------|----------|
| `GET /api/pages/` | Non-empty array (not `[]`) |
| `GET /api/auth/me/` | `navItems.length > 0`, `roleCentrePageId` set |
| Sidebar | Role Centre nav (not “No navigation…”) |
| Dashboard | Item counts > 0 after menu seed |
| `GET /api/restaurant/public-menu/` | Published menu JSON with sections + image URLs |
| `http://thestormscafe.localhost:3000/menu` | Guest menu UI with logo / section images |

Subscription must be active (expired → `/api/pages/` **402** looks like empty UI). Guest `/menu` does **not** require login.

---

## Incident log (local `thestormscafe`, 2026-07-20)

| Step | Result |
|------|--------|
| Migrate auth `0019` fake + `0020`–`0026` | `must_change_password` OK |
| Migrate `pages` `0005`–`0016` | `object_id` OK |
| Migrate `payments` / `financials` (general journal) | Unblocked `seed_pages` |
| `seed_pages --schema=thestormscafe` | Pages + RC + receipt templates OK |
| `setup_page_permissions` | 33 sets updated, 146 lines |
| `sync_page_permission_objects` | `thestormscafe` updated=108 |
| `assign_application_profiles --force` | 2 users already assigned |
| `seed_restaurant_module` | IntegrityError on duplicate permission line (benign if sets already present) |
| `seed_storms_cafe_menu` | 82 items / 82 menu items / 13 categories |
| `seed_digital_menu` | publication=main, 7 sections, 82 lines |

### Follow-up code fix (User Settings relations)

`POST /api/pages/relations/` crashed with:

```text
Field 'id' expected a number but got 'debug_admin'
```

**Cause:** `UserPersonalization.user_id` is serialized as **username**, but `TableRelationsView` looked up `CustomUser` by numeric `pk`.

**Fix:** resolve by `username`, then digit `pk`, then `system_id` (`pages/views.py`). Deploy this before production User Settings / Role Centre profile dropdowns are used.

---

## Do / Don’t

**Do**

- Backup first in production.
- Migrate DDL gaps before `seed_pages`.
- Seed **one tenant** with `--schema=` until verified.
- Sign out/in after seeding so `/api/auth/me/` rebuilds nav.

**Don’t**

- Expect migrate alone to fill `/api/pages/`.
- Run all-tenant sync/seed accidentally on production without a plan.
- Treat empty sidebar as “wrong password” — check pages count and subscription 402.

---

## Related

- [MUST_CHANGE_PASSWORD_SCHEMA_DRIFT_RUNBOOK.md](./MUST_CHANGE_PASSWORD_SCHEMA_DRIFT_RUNBOOK.md)
- [11-restore-to-v2-ui-checklist.md](../../zentroapp-to-v2-todos/11-restore-to-v2-ui-checklist.md)
- [08-primewise-v2-readiness.md](../../zentroapp-to-v2-todos/08-primewise-v2-readiness.md)
- Commands: `pages/management/commands/seed_pages.py`, `permissions/.../setup_page_permissions.py`, `restaurant_management/.../seed_storms_cafe_menu.py`
