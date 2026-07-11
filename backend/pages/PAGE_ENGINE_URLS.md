# Page Engine — URL, API & Frontend Reference

> **Backend:** `backend/pages/`  
> **Frontend:** `frontend/` (Next.js 16 App Router)  
> **URL module:** `backend/pages/urls.py`  
> **Views:** `backend/pages/views.py`  
> **Serializers:** `backend/pages/serializers.py`  
> **Frontend clients:** `frontend/services/page.service.ts`, `frontend/services/pagedata.service.ts`

---

## Mounting

The page engine is included at the **root** of both URLconfs (no extra prefix beyond `api/pages/`):

| URLconf | File | Used when |
|---------|------|-----------|
| Tenant | `backend/core/urls.py` | `path("", include("pages.urls", namespace="pages"))` |
| Public | `backend/core/urls-public.py` | Same include |

**Full base URL (local):** `http://localhost:8002/api/pages/…`  
**Namespace:** `pages` (`app_name = 'pages'` in `urls.py`)

---

## Authentication & tenancy

Every endpoint requires:

| Requirement | Detail |
|-------------|--------|
| **Auth** | `Authorization: Bearer <access_token>` |
| **Class** | `JWTAuthenticationWithRevocationChecks` (`authentication.authentication`) |
| **Permission** | `IsAuthenticated` |
| **Tenant** | JWT claim `schema_name` → `schema_context(schema)` for all DB access |

**Error if no tenant in token:** `400 {"error": "No tenant in token"}`

---

## Route table

| # | Method | Path | View | URL name |
|---|--------|------|------|----------|
| 1 | `GET` | `/api/pages/` | `PagesListView` | `pages-list` |
| 2 | `GET` | `/api/pages/page/` | `PageDetailView` | `page-detail` |
| 3 | `GET` | `/api/pages/data/` | `PageDataView` | `page-data` |
| 4 | `POST` | `/api/pages/data/` | `PageDataView` | `page-data` |
| 5 | `GET` | `/api/pages/data/<system_id>/` | `PageDataRecordView` | `page-data-record` |
| 6 | `PATCH` | `/api/pages/data/<system_id>/` | `PageDataRecordView` | `page-data-record` |
| 7 | `DELETE` | `/api/pages/data/<system_id>/` | `PageDataRecordView` | `page-data-record` |
| 8 | `POST` | `/api/pages/relations/` | `TableRelationsView` | `page-relations` |

**Source (`urls.py`):**

```python
urlpatterns = [
    path('api/pages/', PagesListView.as_view(), name='pages-list'),
    path('api/pages/page/', PageDetailView.as_view(), name='page-detail'),
    path('api/pages/data/', PageDataView.as_view(), name='page-data'),
    path('api/pages/data/<str:system_id>/', PageDataRecordView.as_view(), name='page-data-record'),
    path('api/pages/relations/', TableRelationsView.as_view(), name='page-relations'),
]
```

---

## 1. List all pages

```
GET /api/pages/
```

**Purpose:** Return every `Page` in the current tenant schema with nested controls, fields, and actions. Used by the sidebar to resolve `Page.Name` → `PageId`.

**Query params:** None

**Response:** `200` — array of `PageSerializer` objects (camelCase keys)

**Frontend:** `pageService.getPages()` → `usePages()` hook

**Example response shape:**

```json
[
  {
    "PageId": 1,
    "Name": "ItemList",
    "Caption": "Items",
    "SourceTable": "Item",
    "PageType": "List",
    "Editable": true,
    "InsertAllowed": true,
    "DeleteAllowed": true,
    "ModifyAllowed": true,
    "CardPageId": 4,
    "HeaderPageId": null,
    "ContextFilterField": "",
    "ContextKeyField": "",
    "PageControls": [
      {
        "PageControlId": 1,
        "ControlType": "Repeater",
        "SourceTable": "Item",
        "Editable": false,
        "Fields": [
          {
            "PageControlFieldId": 1,
            "FieldId": 0,
            "Name": "no",
            "Caption": "No.",
            "FieldType": "Code",
            "Visible": true,
            "Editable": false,
            "FreezeColumn": true,
            "HasDrillDownPage": false,
            "HasTableRelation": false
          }
        ]
      }
    ],
    "PageActions": []
  }
]
```

---

## 2. Get single page metadata

```
GET /api/pages/page/?PageId={pageId}
```

**Purpose:** Full page definition for one list or card screen.

**Query params:**

| Param | Required | Type | Description |
|-------|----------|------|-------------|
| `PageId` | Yes | int | `Page.page_id` |

**Responses:**

| Status | Body |
|--------|------|
| `200` | Single `PageSerializer` object |
| `400` | `{"error": "PageId is required"}` or `{"error": "No tenant in token"}` |
| `404` | `{"error": "Page not found"}` |

**Frontend:** `pageService.getPage(pageId)` → `usePage(pageId)` hook

---

## 3. List / create records

```
GET  /api/pages/data/
POST /api/pages/data/
```

### GET — list records

**Purpose:** Paginated rows for a list (`Repeater`) or group control. Serializes only **visible** fields on the control, ordered by `tab_index`.

**Query params:**

| Param | Required | Default | Description |
|-------|----------|---------|-------------|
| `PageId` | Yes | — | Target page |
| `ControlId` | No | first `Repeater` or `Group` on page | Specific control |
| `search` | No | `""` | `icontains` on up to 5 Text/Code fields |
| `limit` | No | `100` | Page size |
| `offset` | No | `0` | Skip rows |
| *any other* | No | — | Drill-down filters (see below) |

**Reserved params (not used as filters):** `PageId`, `ControlId`, `search`, `limit`, `offset`

**Drill-down filters:** Any extra query param whose key matches a model field (or `field_id`) is passed to `qs.filter(**filters)`. Example:

```
GET /api/pages/data/?PageId=9&customer__no=C001&limit=50&offset=0
```

**Control resolution (no `ControlId`):**

```python
control = page.page_controls.filter(
    control_type__in=['Repeater', 'Group']
).first()
```

**Source table:** `control.source_table` or fallback `page.source_table`

**Responses:**

| Status | Body |
|--------|------|
| `200` | Array of record objects |
| `200` | `[]` if page has no matching control |
| `400` | Model/tenant errors |
| `404` | Page or control not found |

**Record shape:**

```json
{
  "SystemId": "uuid-or-pk-string",
  "no": "ITEM-001",
  "item_name": "Widget",
  "unit_price": "1500.00"
}
```

- `SystemId` = `obj.system_id` if present, else `str(obj.pk)`
- Field keys = `PageControlField.name` (snake_case), not camelCase
- FK Code fields serialize as related `.code` when available
- `@property` fields (e.g. `balance`, `inventory`) are resolved

**Search behavior:**

- Fields with `field_type` in `Text`, `Code` on the visible field list
- FK fields use `{name}__{related_key}__icontains` (e.g. `bank_account_posting_group__code__icontains`)
- `UserSetup`: also searches `user__full_name`, `user__email`, `user__username`
- `CustomUser`: also searches `full_name`, `email`, `username`, `phone_number`

**Default ordering (when applicable):**

| Source table | Order |
|--------------|-------|
| `UserSetup` | `user__full_name`, `user__username` |
| `BankAccount` | `no` |
| `BankAccountLedgerEntry` | `-posting_date`, `-entry_no` |
| `CustomerLedgerEntry`, `VendorLedger`, `ItemLedgerEntries` | `-posting_date`, `-id` |

**Frontend:** `pageDataService.list()` → `usePageDataInfinite()` (page size **50**, offset pagination)

---

### POST — create record

**Purpose:** Create a row via list inline-add (rarely used; cards usually create via PATCH on `new`).

**Body (JSON):**

```json
{
  "PageId": 1,
  "ControlId": 1,
  "no": "ITEM-002",
  "item_name": "New item"
}
```

| Field | Required | Description |
|-------|----------|-------------|
| `PageId` | Yes | Page |
| `ControlId` | Yes | Control (must exist on page) |
| *model fields* | — | All other keys passed to `model.objects.create(**payload)` |

**Responses:**

| Status | Body |
|--------|------|
| `201` | Serialized new record (all control fields) |
| `400` | `{"error": "..."}` validation/ORM error |
| `404` | Page or control not found |

**Frontend:** `pageDataService.create()` → `useCreateRecord()`

---

## 4. Single record CRUD

```
GET    /api/pages/data/<system_id>/
PATCH  /api/pages/data/<system_id>/
DELETE /api/pages/data/<system_id>/
```

`<system_id>` is the URL path segment — typically a UUID `system_id` or primary key string (e.g. bank account `no`).

### GET — fetch one record

**Query params:**

| Param | Required | Description |
|-------|----------|-------------|
| `PageId` | Yes | Page |
| `ControlId` | No | Defaults to first `Group`, else first control |

**Record lookup (`_get_obj`):**

1. `CustomUser` → `get_user_by_page_id(system_id)`
2. Models with `system_id` → filter by `system_id`
3. Fallback → filter by `pk=system_id`

**Response:** `200` — serialized record with visible fields  
**Errors:** `404` page/control/record not found

**Frontend:** `pageDataService.getRecord()` → `usePageDataRecord()`

---

### PATCH — update one field (or create on card)

**Purpose:** Card pages update field-by-field on blur. Supports **create-on-first-edit** when `system_id` is `new` and `page.insert_allowed` is true.

**Body (JSON):**

```json
{
  "PageId": 4,
  "field": "item_name",
  "value": "Updated name"
}
```

| Field | Required | Description |
|-------|----------|-------------|
| `PageId` | Yes | Page |
| `field` | Yes | `PageControlField.name` |
| `value` | Yes | New value |

**Special cases:**

| Source table | Behavior |
|--------------|----------|
| `CustomUser` | `create_user_for_page` / `update_user_for_page` via `user_page_service` |
| Other, record missing + `insert_allowed` | `update_or_create(system_id=..., defaults={field: value})` |
| Other, record exists | `setattr` + `save(update_fields=[field])` |

**Response:** `200` — `{"ok": true, "Created": false}` (`Created: true` when row was created)

**Frontend:** `pageDataService.update()` → `useUpdateField()`

---

### DELETE — remove record

**Query params:**

| Param | Required | Description |
|-------|----------|-------------|
| `PageId` | Yes | Page |

**Guards:**

- `page.delete_allowed` must be true → else `403 {"error": "Delete not allowed on this page"}`
- `CustomUser` → `soft_delete_user(obj)` (not hard delete)
- Other models → `obj.delete()`

**Response:** `204` No Content  
**Frontend:** `pageDataService.delete()` — passes `ControlId` in query params (backend ignores it; only `PageId` is read)

---

## 5. Table relations (dropdown options)

```
POST /api/pages/relations/
```

**Purpose:** Options for fields with `HasTableRelation=true` (e.g. Bank Acc. Posting Group).

**Body (JSON):**

```json
{
  "PageId": 7,
  "PageControlId": 8,
  "PageControlFieldId": 49
}
```

| Field | Required | Description |
|-------|----------|-------------|
| `PageId` | Yes | Page |
| `PageControlId` | Yes | Control |
| `PageControlFieldId` | Yes | Field PK (`page_control_field_id`) |

**Note:** Frontend also sends `CurrentRecordSystemId` and `CurrentRecordValues` — **backend currently ignores these** (not implemented in `TableRelationsView`).

**Logic:**

1. Load field; verify `has_table_relation`, `related_table`, `related_field`
2. Resolve model via `MODEL_REGISTRY` using `related_table`
3. Return all rows ordered by `related_field` (or `pk`)

**Response:** `200` — array of:

```json
[
  { "Value": "CASH", "Caption": "Cash Account" }
]
```

**Errors:** `400` missing params / unknown model; `404` field not found; `[]` if relation not configured

**Frontend:** `pageService.fetchTableRelations()` → `useRelationOptions()`

---

## MODEL_REGISTRY

Maps `Page.source_table` / `PageControl.source_table` strings to Django models (`pages/views.py`):

| source_table | App | Model |
|--------------|-----|-------|
| `Item` | `items` | `Item` |
| `Customer` | `sales` | `Customer` |
| `Vendor` | `purchases` | `Vendor` |
| `CustomerLedgerEntry` | `sales` | `CustomerLedgerEntry` |
| `VendorLedger` | `purchases` | `VendorLedger` |
| `ItemLedgerEntries` | `items` | `ItemLedgerEntries` |
| `BankAccount` | `bank_account` | `BankAccount` |
| `BankAccountLedgerEntry` | `bank_account` | `BankAccountLedgerEntry` |
| `BankAccountPostingGroup` | `bank_account` | `BankAccountPostingGroup` |
| `UserSetup` | `authentication` | `UserSetup` |
| `CustomUser` | `authentication` | `CustomUser` |

**Adding a new page type:** register here + seed in `pages/seed.py` + run `python manage.py seed_pages --schema <tenant>`.

---

## Seeded page names (reference)

Run `python manage.py seed_pages` to create/update. **PageIds are per-tenant AutoField values — do not hardcode across tenants.**

| Name | PageType | SourceTable |
|------|----------|-------------|
| `ItemCard` / `ItemList` | Card / List | `Item` |
| `CustomerCard` / `CustomerList` | Card / List | `Customer` |
| `VendorCard` / `VendorList` | Card / List | `Vendor` |
| `BankAccountCard` / `BankAccountList` | Card / List | `BankAccount` |
| `UsersCard` / `UsersList` | Card / List | `CustomUser` |
| `UserSetupList` | List | `UserSetup` |
| `CustomerLedgerEntryList` | List | `CustomerLedgerEntry` |
| `VendorLedgerEntryList` | List | `VendorLedger` |
| `ItemLedgerEntryList` | List | `ItemLedgerEntries` |
| `BankAccountLedgerEntryList` | List | `BankAccountLedgerEntry` |

---

## Frontend implementation

The V2 frontend is a **metadata-driven UI**: it does not have per-entity React pages. Two generic engines — `DynamicListPage` and `DynamicDetailPage` — render any page returned by `GET /api/pages/`.

### Stack

| Layer | Choice | Version |
|-------|--------|---------|
| Framework | Next.js App Router | 16.2.9 |
| UI | React + TypeScript | 19.2.4 |
| Server state | TanStack React Query | ^5.101.1 |
| HTTP | Axios | ^1.18.1 |
| Styling | Tailwind CSS 4 | custom tokens (`s1`, `softBg`, `strokeColor`) |
| Icons | lucide-react | — |
| Toasts | sonner | — |
| Selects | react-select | relation dropdowns |

**No Redux / Zustand.** Auth is `localStorage` tokens only (no auth Context).

### Frontend file tree (page engine)

```
frontend/
├── app/
│   ├── layout.tsx                         # Root: Outfit font, Sonner toaster
│   ├── page.tsx                           # / → redirect /dashboard
│   ├── login/page.tsx                     # LoginPage
│   └── (dashboard)/
│       ├── layout.tsx                     # QueryProvider + DashboardLayout
│       ├── dashboard/page.tsx             # ?page= → DynamicListPage
│       └── record/[pageId]/[systemId]/page.tsx  # DynamicDetailPage
├── components/
│   ├── auth/LoginPage.tsx
│   ├── dynamic/
│   │   ├── DynamicListPage.tsx            # List / worksheet
│   │   ├── DynamicDetailPage.tsx          # Card / detail
│   │   ├── DynamicField.tsx               # Field-type inputs
│   │   ├── DrillDownField.tsx             # Clickable drill-down links
│   │   ├── SearchableRelationSelect.tsx   # FK dropdown (react-select)
│   │   ├── FactBoxPanel.tsx               # Routes to ItemImagesFactBox
│   │   ├── ItemImagesFactBox.tsx          # Item images (non-page-engine API)
│   │   ├── CardRibbon.tsx                 # PageAction tabs
│   │   └── PasswordField.tsx              # Users card password modal
│   └── layout/
│       ├── DashboardLayout.tsx            # Shell + scroll container
│       ├── Sidebar.tsx                    # Nav → PageId resolution
│       └── DashboardHeader.tsx
├── context/QueryProvider.tsx
├── hooks/
│   ├── usePage.ts                         # Page metadata
│   ├── usePageData.ts                     # CRUD + infinite list
│   ├── useDrillDownFilters.ts             # URL ctx → API filters
│   └── useRelationOptions.ts              # Table relation options
├── services/
│   ├── page.service.ts                    # /api/pages/*
│   └── pagedata.service.ts                # /api/pages/data/*
├── lib/
│   ├── api.ts                             # Axios + JWT + base URL
│   ├── drillDown.ts                       # Drill-down URL builder
│   ├── fieldVisibility.ts                 # Per-page edit rules
│   ├── worksheetColumns.ts                # Frozen column layout
│   ├── cardAction.ts                      # Card ribbon navigation
│   └── pageIds.ts                         # Stale hardcoded IDs (avoid)
└── types/
    ├── page.ts                            # Page, PageControl, PageControlField
    └── pagedata.ts                        # DataRecord
```

### App routing

| URL | File | Renders |
|-----|------|---------|
| `/` | `app/page.tsx` | Redirect → `/dashboard` |
| `/login` | `app/login/page.tsx` | `LoginPage` |
| `/dashboard` | `app/(dashboard)/dashboard/page.tsx` | `HomeDashboard` or `DynamicListPage` |
| `/dashboard?page={PageId}` | same | `DynamicListPage(pageId)` |
| `/record/{pageId}/new` | `app/(dashboard)/record/.../page.tsx` | `DynamicDetailPage` (create) |
| `/record/{pageId}/{systemId}` | same | `DynamicDetailPage` (edit) |

**No `middleware.ts`** — auth is enforced reactively when API returns 401.

**Drill-down URL params** (on `/dashboard`):

| Param | Set by | Used by |
|-------|--------|---------|
| `page` | Sidebar / drill-down | Active list `PageId` |
| `ctx` | `buildDrillDownUrl()` | Filter value for `page.ContextFilterField` |
| `ctxLabel` | drill-down | Display label in list header |
| `return` | drill-down | Back button URL |
| `ctx2`, `ctx2Field` | optional second filter | `useDrillDownFilters` |

### End-to-end data flow

```
LoginPage
  POST /api/auth/token/ → localStorage access_token

Sidebar (usePages)
  GET /api/pages/ → resolve ItemList → PageId

DynamicListPage
  usePage(pageId)           → GET /api/pages/page/?PageId=
  usePageDataInfinite(...)  → GET /api/pages/data/?PageId=&ControlId=&search=&limit=50&offset=…
  useDrillDownFilters       → extra query params from ?ctx=

DynamicDetailPage
  usePage(pageId)           → GET /api/pages/page/?PageId=
  usePageDataRecord(...)    → GET /api/pages/data/{systemId}/?PageId=
  useRelationOptions(...)   → POST /api/pages/relations/
  useUpdateField            → PATCH /api/pages/data/{systemId}/
  useDeleteRecord           → DELETE /api/pages/data/{systemId}/?PageId=
```

### Authentication (`lib/api.ts` + `LoginPage.tsx`)

**Login:**

```typescript
POST /api/auth/token/  { email, password }
→ localStorage.setItem('access_token', res.data.access)
→ router.push('/dashboard')
```

**Every API request** (`lib/api.ts`):

- `baseURL` from `NEXT_PUBLIC_API_URL`, or subdomain-aware `http://{hostname}:8002`
- Header: `Authorization: Bearer ${localStorage.access_token}`
- `withCredentials: true`
- On **401**: clear token, `window.location.href = '/login'`

JWT must include `schema_name` — backend page views reject requests without it.

### JSON key conventions

| Layer | Key style | Example |
|-------|-----------|---------|
| Page metadata (serializers) | **PascalCase** | `PageId`, `PageControlFieldId`, `HasDrillDownPage` |
| Record data (views) | **snake_case** | `no`, `item_name`, `bank_account_posting_group` |
| Both include | `SystemId` | Record primary identifier in lists/cards |

Frontend types in `types/page.ts` match metadata PascalCase. `DataRecord` is `Record<string, unknown> & { SystemId: string }` for row data.

### Services layer

#### `services/page.service.ts`

| Method | API | Used by |
|--------|-----|---------|
| `getPages()` | `GET /api/pages/` | `usePages`, Sidebar |
| `getPage(pageId)` | `GET /api/pages/page/?PageId=` | `usePage` |
| `fetchTableRelations(...)` | `POST /api/pages/relations/` | `useRelationOptions` |

Returns `[]` if response is not an array (silent empty on error).

#### `services/pagedata.service.ts`

| Method | API | Body / params |
|--------|-----|---------------|
| `list(...)` | `GET /api/pages/data/` | `PageId`, `ControlId`, `search`, `limit`, `offset`, + drill-down filters |
| `create(...)` | `POST /api/pages/data/` | `{ PageId, ControlId, ...fields }` |
| `getRecord(...)` | `GET /api/pages/data/{systemId}/` | `PageId`, `ControlId` |
| `update(...)` | `PATCH /api/pages/data/{systemId}/` | `{ PageId, field, value }` |
| `delete(...)` | `DELETE /api/pages/data/{systemId}/` | `PageId` (query) |

`update()` sends `field.Name` (snake_case) as the `field` key.

### React Query hooks

#### `hooks/usePage.ts`

```typescript
usePage(pageId)   // queryKey: ['page', pageId]     — staleTime: 0, refetchOnMount: 'always'
usePages()        // queryKey: ['pages']             — staleTime: 5 min (sidebar cache)
```

#### `hooks/usePageData.ts`

```typescript
usePageDataInfinite(pageId, controlId, search, filters)
  // queryKey: ['pagedata', 'infinite', pageId, controlId, search, filters]
  // PAGE_SIZE = 50, offset pagination via pageParam

usePageDataRecord(pageId, controlId, systemId)
  // queryKey: ['pagedata', 'record', pageId, controlId, systemId]
  // disabled when systemId undefined (e.g. /new before first save)

useUpdateField(pageId)    // PATCH → invalidates ['pagedata', pageId]
useDeleteRecord(pageId)   // DELETE → invalidates ['pagedata', pageId]
useCreateRecord(pageId)   // POST → invalidates ['pagedata', pageId]
```

#### `hooks/useDrillDownFilters.ts`

Reads `ctx`, `ctxLabel`, `return`, `ctx2`, `ctx2Field` from URL. Builds:

```typescript
filters[page.ContextFilterField] = contextValue  // e.g. customer__no=C001
```

Passed to `usePageDataInfinite` → appended as query params on `GET /api/pages/data/`.

#### `hooks/useRelationOptions.ts`

For each visible field with `HasTableRelation`, calls `fetchTableRelations` in a `useEffect` (not React Query). Returns `Record<PageControlFieldId, RelationOption[]>`.

### Layout shell

```
DashboardLayout
├── Sidebar (usePages → resolve page names)
├── DashboardHeader (logout clears localStorage)
└── main (flex flex-col min-h-0 overflow-hidden)
    └── children (dashboard or record pages)
```

List pages use **BC-style scrolling**: toolbar/search fixed (`shrink-0`), table body in `flex-1 overflow-auto`, `thead sticky top-0`. Implemented in `DynamicListPage` + `DashboardLayout`.

### `DynamicListPage` — render logic

**File:** `components/dynamic/DynamicListPage.tsx`

1. **Load metadata:** `usePage(pageId)`
2. **Pick list control:** first `PageControl` where `ControlType` is `Repeater` or `Group`
3. **Visible columns:** `listControl.Fields.filter(f => f.Visible)`
4. **Drill-down:** hide `ContextFilterField` column when `isDrillDown`
5. **Load rows:** `usePageDataInfinite(pageId, listControl.PageControlId, search, drillDownFilters)`
6. **Dedupe rows** by `SystemId` (infinite query safety)
7. **Infinite scroll:** `IntersectionObserver` with `scrollContainerRef` as `root` (not viewport)

**User actions:**

| Action | Behavior |
|--------|----------|
| Row click | `router.push(/record/{CardPageId}/{SystemId})` if `page.CardPageId` set |
| New | Navigate to `/record/{CardPageId}/new` if card exists; else `POST` create |
| Search | Local state → debounced via query key on `search` param |
| Inline edit | When `listControl.Editable` + field `Editable` + `page.ModifyAllowed` → `PATCH` on blur |
| Delete | Confirm modal → `DELETE /api/pages/data/{SystemId}/` |
| Drill-down cell | `DrillDownField` → `router.push(/dashboard?page={DrillDownPageId}&ctx=…)` |
| Refresh | `refetch()` on infinite query |

**Frozen columns:** `listFrozenFieldProps()` from `lib/worksheetColumns.ts` — sticky `left` on header + body for fields with `FreezeColumn: true`.

**React keys:** use `field.PageControlFieldId` (unique PK), **not** `field.FieldId`.

### `DynamicDetailPage` — render logic

**File:** `components/dynamic/DynamicDetailPage.tsx`

1. **Load metadata:** `usePage(pageId)`, `usePages()` (for back navigation + card actions)
2. **Controls:** `Group` → field sections; `FactBox` → side panels
3. **Load record:** `usePageDataRecord` — skipped when `systemId === 'new'`
4. **Create flow (`/new`):**
   - Generate `pendingId = crypto.randomUUID()`
   - First field blur → `PATCH /api/pages/data/{pendingId}/` with `{ field, value }`
   - Backend `update_or_create` when `insert_allowed`
   - On success → `router.replace(/record/{pageId}/{pendingId})`
5. **Update flow:** each editable field blur → `PATCH` single field
6. **Delete:** `DELETE` then navigate back to list via `CardPageId` reverse lookup
7. **Title:** `page.TitleField` value, or `"New {Caption}"` for create

**Field rendering priority** (in `FieldGroup`):

1. `HasTableRelation` → `SearchableRelationSelect`
2. `HasDrillDownPage` + not editable → `DrillDownField`
3. `FieldType === 'Password'` → `PasswordField` modal
4. `FieldType === 'Boolean'` → checkbox in styled label
5. Else → `DynamicField`

**Editability** (`isCardFieldEditable` + `lib/fieldVisibility.ts`):

- Respects `page.ModifyAllowed`, `control.Editable`, `field.Editable`
- `UsersCard` / `email`: locked after real email assigned (not `@zentro.pending`)
- `NoSeriesCode` fields: typically read-only on list

**FactBoxes:** `FactBoxPanel` delegates `ItemAttachments` / `ItemImages` to `ItemImagesFactBox`, which calls **`/api/item-images/`** (outside page engine).

**Card ribbon:** `CardRibbon` renders `page.PageActions` by `RibbonTab`; `buildCardActionUrl()` navigates to linked list pages.

### `DynamicField` — field types

**File:** `components/dynamic/DynamicField.tsx`

| FieldType | Control |
|-----------|---------|
| `Boolean` | checkbox (or read-only Yes/No) |
| `Enum` / `Option` | `<select>` from `EnumValues` comma list |
| `Date` / `DateTime` | `<input type="date|datetime-local">` |
| `Integer` / `Decimal` | `<input type="number">` |
| `Text` / `Code` | `<input type="text">` or read-only div |
| Non-editable | styled read-only div |

Local state syncs from `value` prop; **persists on `onBlur`** (not on every keystroke for text).

### Drill-down flow

**Files:** `lib/drillDown.ts`, `components/dynamic/DrillDownField.tsx`, `hooks/useDrillDownFilters.ts`

1. Field has `HasDrillDownPage: true` and `DrillDownPageId` (set in `pages/seed.py` via `_link_drill_down`)
2. User clicks balance/inventory on list or card
3. `drillDownKeyValue()` picks PK from record: `PrimaryKey` field → `email` → `no` → `code`
4. `buildDrillDownUrl()` produces:
   ```
   /dashboard?page={DrillDownPageId}&ctx={keyValue}&ctxLabel={name}&return={returnPath}
   ```
5. Target list page has `ContextFilterField` (e.g. `customer__no`, `bank_account_no`)
6. `useDrillDownFilters` maps `ctx` → API filter param
7. `GET /api/pages/data/` returns filtered ledger rows

### Table relations flow

1. Field has `HasTableRelation: true`, `RelatedTable`, `RelatedField`, `RelatedDisplayField`
2. Card loads → `useRelationOptions` POSTs to `/api/pages/relations/`
3. `SearchableRelationSelect` shows Value + Caption columns
4. On change → `PATCH` with selected value (FK code string)

### Sidebar navigation

**File:** `components/layout/Sidebar.tsx`

```typescript
const NAV_ITEMS = [
  { label: 'Dashboard', pageName: null },
  { label: 'Items',       pageName: 'ItemList' },
  { label: 'Customers',   pageName: 'CustomerList' },
  { label: 'Vendors',     pageName: 'VendorList' },
  { label: 'Bank Accounts', pageName: 'BankAccountList' },
  { label: 'Users',       pageName: 'UsersList' },
  { label: 'User Setup',  pageName: 'UserSetupList' },
]
```

`pageName` must match `Page.Name` in DB exactly. If `seed_pages` not run → `PageId === 0` → nav item disabled.

### Frontend ↔ API quick map

| UI route | API calls |
|----------|-----------|
| `/dashboard` | — |
| `/dashboard?page={PageId}` | `GET /api/pages/page/`, `GET /api/pages/data/` |
| `/record/{pageId}/new` | `GET /api/pages/page/`, `PATCH /api/pages/data/{uuid}/` on first blur |
| `/record/{pageId}/{systemId}` | `GET /api/pages/page/`, `GET /api/pages/data/{systemId}/`, `PATCH` per field |
| Drill-down list | `GET /api/pages/data/?PageId=…&{ContextFilterField}={ctx}` |
| Card FK field | `POST /api/pages/relations/` |
| Item images FactBox | `GET/POST/DELETE /api/item-images/` (separate API) |

### Known frontend gaps

| Gap | Detail |
|-----|--------|
| No route guard | Unauthenticated users reach `/dashboard` until API 401 |
| API errors swallowed | `page.service` / `pagedata.service` return `[]` on non-array responses |
| No list error UI | Failed fetch shows "No records found" |
| `lib/pageIds.ts` stale | Hardcoded 1/2/3 — use `usePages()` instead |
| Relations context ignored | Frontend sends `CurrentRecordSystemId` / `CurrentRecordValues`; backend ignores |
| Header search | `DashboardHeader` search input not wired |
| Limited FactBoxes | Only `ItemImages` implemented; others show placeholder |
| No tests | No frontend test files |

---

## Error summary

| HTTP | Typical cause |
|------|----------------|
| `400` | Missing `PageId`, no `schema_name` in JWT, unknown `source_table` in registry |
| `401` | Missing/expired token (DRF / frontend redirect to `/login`) |
| `403` | Delete not allowed on page |
| `404` | Page, control, field, or record not found |
| `201` | Record created (POST) |
| `204` | Record deleted |

---

## Related files

### Backend

| File | Role |
|------|------|
| `backend/pages/urls.py` | URL patterns |
| `backend/pages/views.py` | View implementations |
| `backend/pages/serializers.py` | Page metadata JSON shape (camelCase) |
| `backend/pages/models.py` | `Page`, `PageControl`, `PageControlField`, `PageAction` |
| `backend/pages/seed.py` | Page definitions |
| `backend/pages/management/commands/seed_pages.py` | CLI to seed all tenants |
| `backend/pages/user_page_service.py` | CustomUser create/update/delete helpers |

### Frontend

| File | Role |
|------|------|
| `frontend/lib/api.ts` | Axios instance, JWT, subdomain base URL |
| `frontend/services/page.service.ts` | Metadata + relations client |
| `frontend/services/pagedata.service.ts` | Data CRUD client |
| `frontend/hooks/usePage.ts` | `usePage`, `usePages` |
| `frontend/hooks/usePageData.ts` | List infinite query, record CRUD mutations |
| `frontend/hooks/useDrillDownFilters.ts` | URL `ctx` → API filter params |
| `frontend/hooks/useRelationOptions.ts` | FK dropdown options |
| `frontend/components/dynamic/DynamicListPage.tsx` | List / worksheet renderer |
| `frontend/components/dynamic/DynamicDetailPage.tsx` | Card / detail renderer |
| `frontend/components/dynamic/DynamicField.tsx` | Field-type inputs |
| `frontend/components/dynamic/DrillDownField.tsx` | Drill-down navigation |
| `frontend/components/layout/Sidebar.tsx` | Nav + PageId resolution |
| `frontend/components/layout/DashboardLayout.tsx` | App shell + scroll layout |
| `frontend/lib/drillDown.ts` | Drill-down URL builder |
| `frontend/lib/worksheetColumns.ts` | Frozen column sticky layout |
| `frontend/types/page.ts` | TypeScript interfaces for page metadata |
