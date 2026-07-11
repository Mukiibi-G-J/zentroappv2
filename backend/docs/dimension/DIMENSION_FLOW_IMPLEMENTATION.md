# Dimension Flow: Item Default Dimensions → Line → Posting

This document describes how to implement BC-style dimensions in Zentro so that items with default dimensions (e.g., BRANCH, SHOE_TYPE) automatically stamp on sales lines and carry through to posting.

---

## Overview Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  1. SETUP: Dimensions + Default Dimensions on Items                          │
│     • Dimension: BRANCH (values: Ntinda, Kyanja)                            │
│     • Dimension: SHOE_TYPE (values: Sneakers, Office Shoes, Boots)           │
│     • DefaultDimension: Item ITM-001 → BRANCH=Ntinda, SHOE_TYPE=Sneakers   │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  2. LINE CREATION: User selects item on sales invoice line                   │
│     • get_merged_line_dimensions() merges: Customer → Item → User → Explicit │
│     • DimensionSet created (or reused) for merged combination                │
│     • line.dimension_set + line.global_dimension_1 stored on SalesInvoiceLine│
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  3. POSTING: dimension_set carried to all ledger entries                     │
│     • PostedSalesInvoiceLine: dimension_set, global_dimension_1             │
│     • GeneralLedgerEntry: dimension_set, global_dimension_1/2               │
│     • ItemLedgerEntries, ValueEntry: global_dimension_1                     │
│     • CustomerLedgerEntry: global_dimension_1                               │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Step 1: Create Dimensions and Dimension Values

1. **Django Admin → Dimension → Dimensions**
   - Create dimension: `BRANCH` (e.g., "Branch / Location")
   - Create dimension: `SHOE_TYPE` (e.g., "Shoe Type / Category")

2. **Django Admin → Dimension → Dimension Values**
   - For BRANCH: `Ntinda`, `Kyanja`, etc.
   - For SHOE_TYPE: `Sneakers`, `Office Shoes`, `Boots`, etc.
   - Each DimensionValue must have:
     - `code` (e.g., "NTINDA")
     - `description` (e.g., "Ntinda")
     - `dimension_type`: Standard
     - `dimension_code`: Link to BRANCH or SHOE_TYPE

3. **General Ledger Setup** (Financials → General Ledger Setup)
   - Set `global_dimension_1` = BRANCH (or your primary dimension)
   - Set `global_dimension_2` = SHOE_TYPE (optional second global)
   - With **Multiple Branches** enabled, each user has **`can_switch_branch`**: if `False`, API branch context is always their assigned `global_dimension_1` and `X-Branch-Id` is ignored (see `dimension/branch_filter.py`).

---

## Step 2: Ensure Objects Table Has Item Table

For DefaultDimension to work, the `base.Objects` table must have an entry for the Item model:

- **object_type**: Table
- **related_model**: `items.Item`
- **object_id**: 2500 (or whatever your Items table ID is)

Run:
```bash
python manage.py tenant_command populate_objects_table --schema=your_tenant
```

This populates Objects with all tenant models including `items.Item`.

---

## Step 3: Set Default Dimensions on Items

1. **Django Admin → Dimension → Default Dimensions**
2. Add rows for each item (or use bulk if you have a seed command):

   | Table (Objects) | No (Item No) | Dimension Code | Dimension Value | Value Posting |
   |-----------------|--------------|----------------|-----------------|---------------|
   | items.Item      | ITM-001      | BRANCH         | Ntinda          | None          |
   | items.Item      | ITM-001      | SHOE_TYPE      | Sneakers        | None          |
   | items.Item      | ITM-002      | BRANCH         | Kyanja          | None          |
   | items.Item      | ITM-002      | SHOE_TYPE      | Office Shoes    | None          |

   - **Table**: Select the Object with `related_model` = `items.Item`
   - **no**: The item's `no` field (e.g., `ITM-001`)
   - **dimension_code**: BRANCH or SHOE_TYPE
   - **dimension_value**: The specific value for that item

---

## Step 4: Current Code Flow (Already Implemented)

### When Creating/Updating a Sales Invoice Line

**Sales Invoice create** (`sales/serializers.py`):

```python
dims = get_merged_line_dimensions(
    customer_no=customer_no,
    item=item,
    resource=resource,
    request_user=request_user,
    line_data=line_data,
)
line_data["dimension_set"] = dims.get("dimension_set")
line_data["global_dimension_1"] = dims.get("global_dimension_1")
SalesInvoiceLine.objects.create(sales_invoice=sales_invoice, **line_data)
```

**Sales Order update_lines** (`sales/serializers.py` → `_merge_line_dimensions`):

```python
dims = get_merged_line_dimensions(
    customer_no=customer_no,
    item=item,
    resource=resource,
    request_user=request_user,
    line_data=line_data,
)
prepared_data["dimension_set"] = dims.get("dimension_set")
prepared_data["global_dimension_1"] = dims.get("global_dimension_1")
```

**Merge order** (in `get_merged_line_dimensions`):

1. Customer defaults (header)
2. Item defaults (overrides customer for same dimension)
3. User's `global_dimension_1` (overrides both)
4. Explicit `line_data` (user selection on line – highest priority)

### When Posting

- **PostedSalesInvoiceLine**: Gets `line.dimension_set` and `line.global_dimension_1`
- **GeneralLedgerEntry**: Uses `get_posting_dimension_payload(dimension_set=..., global_dimension_1=...)` from line
- **ItemLedgerEntries / ValueEntry**: Use `line.global_dimension_1`
- **CustomerLedgerEntry**: Uses customer entry dimensions from line

---

## Step 5: Frontend Requirements

For dimensions to appear and be editable on the line:

1. **Line serializer** should expose:
   - `dimension_set` (id)
   - `global_dimension_1` (id, code, description)

2. **Item selection** should trigger a line update that includes the item:
   - Backend recalculates dimensions via `get_merged_line_dimensions` when `item` is in `line_data`
   - Frontend can send `line_data` with `dimensions` or `global_dimension_1` for user overrides

3. **Dimension picker** (optional): If you want users to override dimensions on the line:
   - Send `dimensions: { "BRANCH": <dim_value_id>, "SHOE_TYPE": <dim_value_id> }` in line payload
   - Or `global_dimension_1`: <dim_value_id> for the primary dimension

---

## Step 6: Verify the Flow

### Backend

1. Ensure `get_default_dimensions_for_entity("items.Item", item.no)` returns data:
   ```python
   from dimension.models import get_default_dimensions_for_entity
   d = get_default_dimensions_for_entity("items.Item", "ITM-001")
   # Should return {<Dimension BRANCH>: <DimensionValue Ntinda>, ...}
   ```

2. Ensure Objects has Item:
   ```python
   from base.models import Objects
   Objects.objects.filter(object_type="Table", related_model="items.Item").first()
   ```

3. Ensure DefaultDimensions exist for your items:
   ```python
   from dimension.models import DefaultDimension
   DefaultDimension.objects.filter(no="ITM-001").select_related("dimension_code", "dimension_value")
   ```

### End-to-end

1. Create a Sales Invoice with customer.
2. Add a line with an item that has default dimensions.
3. Save – line should have `dimension_set` and `global_dimension_1` populated.
4. Post – PostedSalesInvoiceLine, GL entries, Item entries should carry the dimensions.

---

## Line Dimensions in Posting (Implemented)

The posting processor (`SalesInvoiceProcessor`) uses **each line's** `dimension_set` and `global_dimension_1` when building GL, Item, and Value entries. If a line has no dimensions, it falls back to the logged-in user's `global_dimension_1`.

- `items_lines` includes `dimension_set` and `global_dimension_1` from each `SalesInvoiceLine`
- GL entries (sales, COGS, inventory, discounts) use the line's dimensions
- Item and Value entries use the line's dimensions
- Posted sales invoice lines carry `dimension_set` and `global_dimension_1` through to posting

---

## Troubleshooting

| Issue | Check |
|-------|-------|
| Dimensions not stamping on line | `Objects` has `items.Item`? `DefaultDimension` rows exist for that item `no`? |
| Wrong dimension wins | Merge order: Customer → Item → User → Explicit. Item overrides Customer for same dimension. |
| Dimensions not in GL | Ensure line has `dimension_set` / `global_dimension_1` before posting (from item defaults or user selection). |
| `get_default_dimensions_for_entity` returns {} | Table object must match `related_model="items.Item"`. Run `populate_objects_table`. |

---

## Related Files

- `dimension/models.py`: `get_merged_line_dimensions`, `get_default_dimensions_for_entity`, `get_or_create_dimension_set`
- `sales/serializers.py`: `_merge_line_dimensions`, `create`, `_update_lines`
- `sales/admin.py`: Posting logic, `line.global_dimension_1` → ledger entries
- `financials/models.py`: `GeneralLedgerSetup` (global_dimension_1, global_dimension_2)
