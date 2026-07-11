# 01 — Payment ledger `applies_to_id` cleanup

**Migration:** zentroapp-web → zentroapp-webV2  
**Status:** ☐ Not done on production · ✅ Done on dev (`primewise`: 12,691 payment rows cleared)  
**Index:** [README.md](./README.md)

---

## Checklist

- [ ] Deploy zentroapp-webV2 (code fix) **before** data cleanup
- [ ] `python manage.py migrate_schemas`
- [ ] `python manage.py clear_invalid_ledger_applies_to_ids --schema=<tenant_schema>` (pilot)
- [ ] `python manage.py clear_invalid_ledger_applies_to_ids` (all tenants)
- [ ] SQL / admin verify: zero Payment rows with `applies_to_id` set
- [ ] Functional: Apply Entries cancel clears stamps; Preview Posting counts match BC

---

## Problem

Vendor/customer **Payment** ledger rows incorrectly had `applies_to_id` set. In Business Central, Applies-to ID is a **temporary staging stamp on invoices/credits only** during Apply Entries — not on payment rows. Wrong values caused Apply Vendor Entries and Preview Posting to show huge filtered lists.

---

## Commands

```powershell
python manage.py migrate_schemas

python manage.py clear_invalid_ledger_applies_to_ids --schema=<tenant_schema>
python manage.py clear_invalid_ledger_applies_to_ids
```

Optional — General Journal + Apply Entries pages:

```powershell
python manage.py seed_pages --schema=<tenant_schema>
```

**Do not** use `backfill_applies_to_id` to fix payment rows — it stamps invoices only. Use `clear_invalid_ledger_applies_to_ids`.

---

## Background (BC semantics)

| Field | Where | Purpose |
|-------|-------|---------|
| **Applies-to ID** (staging) | Open **invoice/credit** rows only | Temporary stamp = payment document no. during Apply Entries |
| **Applies-to Doc. / Entry** | Payment **journal line** after OK | Committed application on the applying document |

Payment ledger rows must **not** carry `applies_to_id`.

### Legacy causes

1. `backfill_applies_to_id` migrations stamped payment rows.
2. Posting set `applies_to_id` on payment ledger rows.
3. `set-ledger-applies-to-id` could stamp payment rows.
4. Closing Apply Entries without OK left stale stamps.

### V2 code fix

| Area | File(s) |
|------|---------|
| Stamp rules | `payments/journal_application.py` |
| API | `payments/views.py` |
| Posting | `payments/admin.py` |
| Backfill | `financials/ledger_application.py` |
| Frontend | `WorksheetPageView.tsx`, `DynamicWorksheetModal.tsx`, `payments.service.ts` |
| Cleanup | `financials/management/commands/clear_invalid_ledger_applies_to_ids.py` |

---

## Verify

### SQL (per tenant schema)

```sql
SET search_path TO <tenant_schema>;

SELECT COUNT(*) FROM purchases_vendorledger
WHERE document_type = 'Payment' AND COALESCE(applies_to_id, '') <> '';

SELECT COUNT(*) FROM sales_customerledgerentry
WHERE document_type = 'Payment' AND COALESCE(applies_to_id, '') <> '';
```

Both counts must be **0**.

### Admin

Vendor Ledger → Document Type = **Payment** → Applies-to ID blank.

### Functional

1. Apply Vendor Entries → stage invoice → **Cancel** → stamp clears.
2. Preview before apply → **1** Detailed Vendor Ledg. row (Initial).
3. After apply → **3** detailed rows (Initial + 2 Application).

---

## Migrations (reference)

- `purchases.0012` / `0013` — vendor `applies_to_id`
- `sales.0023` / `0024` — customer `applies_to_id`
- `financials.0016` — General Journal application fields

---

## Completed reference

| Environment | Schema | Command | Result |
|-------------|--------|---------|--------|
| Local dev | `primewise` | `clear_invalid_ledger_applies_to_ids` | 12,691 rows cleared |

---

## Rollback

No automatic rollback for cleanup. Restore DB from backup taken before cleanup if required.
