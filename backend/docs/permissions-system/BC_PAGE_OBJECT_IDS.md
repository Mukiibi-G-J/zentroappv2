# Zentro page IDs (moved)

This file previously described a dual PageId/ObjectId scheme.

**Current docs:**

- [`ZENTRO_PAGE_IDS.md`](./ZENTRO_PAGE_IDS.md) — PageId == ObjectId (Zentro `10xxx` bands)
- [`../../zentroapp-to-v2-todos/12-page-id-vs-object-id.md`](../../zentroapp-to-v2-todos/12-page-id-vs-object-id.md)

**Registry:** `pages/bc_page_ids.py` → `ZENTRO_PAGE_REGISTRY`  
**Align command:** `python manage.py tenant_command align_zentro_page_ids --schema=<tenant>`
