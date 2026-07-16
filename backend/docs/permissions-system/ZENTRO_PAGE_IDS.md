# Zentro page IDs (PageId == ObjectId)

Permission lines and the page engine use the **same** stable Zentro page ID.

> See also: [`../../zentroapp-to-v2-todos/12-page-id-vs-object-id.md`](../../zentroapp-to-v2-todos/12-page-id-vs-object-id.md)

## Rule

```
PageId = ObjectId = ZENTRO_PAGE_REGISTRY[name]
```

IDs live in classic Zentro bands (`10000+` pages, `12000+` Role Centres). Source of truth: `pages/bc_page_ids.py` → `ZENTRO_PAGE_REGISTRY`.

| Example `name` | ID |
|----------------|---:|
| `PostedSalesInvoiceList` | **10004** |
| `CustomerList` | **10101** |
| `ItemList` | **10201** |
| `BusinessManagerRC` | **12001** |

Table / ledger data permissions still use the separate low table-object ranges from `populate_objects_table` — not these page IDs.

## Architecture

1. **`pages.Page`** — `page_id` and `object_id` are equal for registered pages.
2. **`base.Objects`** — synced from pages via `sync_page_permission_objects`.
3. **Permission set lines** — `object_type=Page` + that same numeric ID.

## After seed / restore

```bash
python manage.py seed_pages --schema=<tenant>
# includes align_zentro_page_ids

# Or alone:
python manage.py tenant_command align_zentro_page_ids --schema=<tenant>
python manage.py tenant_command setup_page_permissions --schema=<tenant>
```

Add new mappings only in `ZENTRO_PAGE_REGISTRY`, then re-seed / align the tenant.
