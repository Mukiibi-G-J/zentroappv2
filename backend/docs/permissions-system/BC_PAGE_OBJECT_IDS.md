# BC-Aligned Page Object IDs

Zentro permission lines use the same numeric IDs as Microsoft Dynamics 365 Business Central pages, with a fixed offset so they never collide with BC table IDs (which use low numbers like 18 for Customer).

## Formula

```
Zentro page object ID = 1000 + BC page ID
```

| BC page ID | BC name (base app) | Zentro object ID | Page engine `name` |
|-----------:|--------------------|-----------------:|--------------------|
| 15 | G/L Account | **1015** | `GLAccountCard` |
| 16 | Chart of Accounts | **1016** | `GLAccountList` |
| 21 | Customer Card | **1021** | `CustomerCard` |
| 22 | Customer List | **1022** | `CustomerList` |
| 26 | Vendor Card | **1026** | `VendorCard` |
| 27 | Vendor List | **1027** | `VendorList` |
| 30 | Item Card | **1030** | `ItemCard` |
| 31 | Item List | **1031** | `ItemList` |
| 371 | Bank Account Card | **1371** | `BankAccountCard` |
| 372 | Bank Account List | **1372** | `BankAccountList` |

BC table data permissions still use **table** object IDs from `populate_objects_table.py` (e.g. table 18 Customer → object 18), separate from page IDs.

## Architecture (same as BC)

1. **`pages.Page`** — runtime page engine (`page_id` = auto per tenant for API URLs).
2. **`Page.object_id`** — stable BC-style permission ID (1015, 1016, …) — **same on every tenant**.
3. **`base.Objects`** — permission registry; synced from pages with `sync_page_permission_objects`.
4. **Permission set lines** — reference `object_type=Page` + `object_id` (e.g. 1016), exactly like BC.

## Zentro-only pages

Pages with no BC counterpart get IDs from **15000** upward (`ZENTRO_CUSTOM_PAGE_ID_START` in `pages/bc_page_ids.py`), similar to BC partner extension ranges.

## Registry

Add mappings in `backend/pages/bc_page_ids.py` → `BC_PAGE_REGISTRY`:

```python
'GLAccountList': (16, 'financials'),
```

Then run:

```bash
python manage.py tenant_command seed_pages --schema=<tenant>
python manage.py tenant_command sync_page_permission_objects --schema=<tenant>
```

`seed_pages` already calls sync at the end for all registered pages.

## Migrating from old module-based IDs

The previous scheme used module bands (e.g. `10501` Chart of Accounts, `10101` Customer Management). When moving to BC IDs, update permission set lines and any `check_object_permission(...)` calls:

| Old (module scheme) | New (BC scheme) | BC ref |
|--------------------:|----------------:|-------:|
| 10501 | 1016 | Page 16 |
| 10101 | 1022 | Page 22 |
| 10201 | 1031 | Page 31 |

Legacy REST viewsets that still use old IDs should be updated to the BC-aligned constants as each module is migrated to the page engine.

## API

Page config responses include `ObjectId` alongside `PageId` so the UI can show BC-style permission IDs.
