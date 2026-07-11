# 05 — Unmigrated model changes (pre go-live)

**Migration:** zentroapp-web → zentroapp-webV2  
**Status:** ☐ Not done — `makemigrations --check` fails  
**Index:** [README.md](./README.md)

---

## Problem

After applying all existing migrations, Django reports model changes not reflected in migrations:

```powershell
python manage.py makemigrations --check --dry-run
# Exit code 1 — would create new migrations
```

This appears on **every** `migrate_schemas` run as a warning. Must be resolved before production deploy so prod does not drift immediately after go-live.

---

## Apps with pending changes (Jul 2026 audit)

| App | Migration (would be created) | Notes |
|-----|------------------------------|-------|
| `app_updates` | `0002_alter_appversion_*` | APK / download URL field alters |
| `authentication` | `0023_alter_usersetup_options` | Meta options only |
| `company` | `0018_alter_billingexpiryreminder_*` | Reminder source, grace days |
| `financials` | `0017_alter_generalledgersetup_*` | Index renames, GL entry / payment `document_type` |
| `payments` | `0003_rename_*` | Cash receipt journal index renames, account_type alters |
| `production` | `0018_rename_*` | Index rename on `productionorder` |
| `purchases` | `0015_alter_vendorledger_payment` | FK alter |
| `receipt_templates` | `0003_alter_*` | receipt_type, system_id, process |
| `restaurant_management` | `0020_alter_orderactionlog_action_type` | action_type alter |
| `setup` | `0011_alter_companyinformation_*` | Meta + index removals |
| `resources` | `0010_alter_resource_base_unit` | FK alter |

---

## Action before production

```powershell
cd backend
python manage.py makemigrations
python manage.py migrate_schemas --shared
python scripts/fix_all_pg_sequences.py   # if restore-based deploy
python manage.py migrate_schemas
python manage.py makemigrations --check  # must exit 0
```

Review each new migration — several are index renames (low risk); field alters need staging verification.

---

## Risk if skipped

- Next deploy may auto-generate migrations under pressure
- Index rename migrations can lock large tables briefly on PostgreSQL
- `document_type` / FK alters need verification on posting flows
