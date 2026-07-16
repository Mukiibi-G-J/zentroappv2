# 10 — Safe `authentication.0020` DevicePushToken index rename

**Migration:** zentroapp-web → zentroapp-webV2 (restore blockers)  
**Status:** ✅ Fixed in code · applied on local shared + `primewise`  
**Index:** [README.md](./README.md)

---

## Problem

After restoring a production dump, `migrate_schemas --shared` failed with:

```text
ProgrammingError: relation "auth_devpush_user_active_idx" does not exist
```

`authentication.0020_userpersonalization` used hard `RenameIndex` from the long names created in `0018` to Django’s truncated names. On some restored `public` (and tenants) those old index names were never present.

---

## Fix

`authentication/migrations/0020_userpersonalization.py` now uses `SeparateDatabaseAndState` + `RunPython` that renames **only if** the old index exists and the new one does not.

---

## Checklist

- [x] Code change landed
- [x] Local shared migrate succeeded after fix
- [x] Local `primewise` migrated
- [ ] Confirm on production shared migrate after next restore/deploy

---

## Related

- Hit during: [08-primewise-v2-readiness.md](./08-primewise-v2-readiness.md)
- Playbook: [00-restore-production-db-playbook.md](./00-restore-production-db-playbook.md)
