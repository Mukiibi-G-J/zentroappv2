# 12 — Zentro page IDs (PageId == ObjectId)

**Why this exists:** The UI and permissions must use the **same** stable number for each page. That number is a **Zentro-owned** ID in the `10xxx` / `12xxx` bands (same ranges as classic ZentroApp page objects).

**Index:** [README.md](./README.md)  
**Code source of truth:** [`pages/bc_page_ids.py`](../pages/bc_page_ids.py) → `ZENTRO_PAGE_REGISTRY`

---

## One-sentence rule

| Field | Value |
|-------|--------|
| **PageId** (`page_engine_page.page_id`) | Zentro page ID (e.g. `10004`) |
| **ObjectId** (`page_engine_page.object_id`) | **Same** Zentro page ID |
| **Name** | Stable string key, e.g. `PostedSalesInvoiceList` |

Use that ID in URLs (`?page=`), Role Centre drill-downs, and permission lines.

---

## ID bands

| Band | Module |
|------|--------|
| 10000–10099 | Sales |
| 10100–10199 | Customers |
| 10200–10299 | Items / inventory |
| 10300–10399 | Purchases / vendors |
| 10400–10499 | Payments |
| 10500–10599 | Financials / G/L |
| 10600–10699 | Bank / dimensions / setup extras |
| 10700–10799 | Restaurant |
| 10800–10899 | User management |
| 10900–10999 | Company / manufacturing / reports |
| 12000–12999 | Role Centres & V2-only shells |

Examples:

```python
'PostedSalesInvoiceList': (10004, 'sales'),
'ItemList': (10201, 'inventory'),
'BusinessManagerRC': (12001, 'general'),
```

---

## After restore / seed

```bash
python manage.py seed_pages --schema=TENANT
# seed ends with align_zentro_page_ids → PageId == ObjectId from registry

# Or run align alone on an already-seeded tenant:
python manage.py tenant_command align_zentro_page_ids --schema=TENANT

python manage.py tenant_command setup_page_permissions --schema=TENANT
```

---

## Checklist

- [ ] Dashboard / Role Centre use **Zentro PageId** only
- [ ] Nav resolves `TargetPageName` → `page_id` (by `Name`)
- [ ] Permission lines use the same number as `object_id` / `page_id`
- [ ] Do **not** invent separate “permission-only” numbers for pages

---

## Quick SQL (primewise)

```sql
SELECT page_id, object_id, name, caption
FROM primewise.page_engine_page
WHERE name IN (
  'ItemList', 'SalesInvoice', 'PostedSalesInvoiceList', 'BusinessManagerRC'
)
ORDER BY page_id;
-- Expect page_id = object_id for each registered name (e.g. ItemList → 10201)
```

---

## Related

- Registry: [`../pages/bc_page_ids.py`](../pages/bc_page_ids.py)
- Align command: [`../pages/management/commands/align_zentro_page_ids.py`](../pages/management/commands/align_zentro_page_ids.py)
- Permission object docs: [`../docs/permissions-system/ZENTRO_PAGE_IDS.md`](../docs/permissions-system/ZENTRO_PAGE_IDS.md)
- Restore UI checklist: [11-restore-to-v2-ui-checklist.md](./11-restore-to-v2-ui-checklist.md)
