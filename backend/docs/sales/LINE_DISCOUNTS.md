# Sales Line Discounts

This document explains how per-line discounting works for **Sales Invoices** and **Sales Orders**, covering the backend, posting, and frontend behavior.

---

## 1. Feature Overview

Line discounts let a user reduce the amount of a single sales line by entering a fixed discount amount. The discount:

- Is stored on each **SalesInvoiceLine** and **SalesOrderLine** (`line_discount_amount` integer field).
- Recalculates the line’s net amount (`total_amount = qty × unit_price × quantity_per_unit − discount`).
- Resets automatically when the unit of measure changes (discounts are tied to the original UoM/quantity).

Two independent endpoints exist:

| Document Type | Endpoint                                          | Viewset / Action                 |
| ------------- | ------------------------------------------------- | -------------------------------- |
| Sales Invoice | `POST /api/sales/<invoice_id>/update_lines/`      | `SalesViewSet.update_lines`      |
| Sales Order   | `POST /api/sales-orders/<order_id>/update_lines/` | `SalesOrderViewSet.update_lines` |

Both endpoints accept the same payload shape but operate on separate models/tables.

---

## 2. Backend Details

### 2.1 Data Model

| Model                          | New Field / Setting                                          | Purpose                                                 |
| ------------------------------ | ------------------------------------------------------------ | ------------------------------------------------------- |
| `postings.GeneralPostingSetup` | `sales_line_discount_account` (FK → `financials.G_LAccount`) | Stores the G/L account debited for “Discount Granted”.  |
| `sales.SalesReceivable`        | `enable_line_discounts` (bool, default `False`)              | Tenant-level feature toggle.                            |
| `sales.SalesInvoiceLine`       | `line_discount_amount` (int)                                 | Discount per invoice line (stored after normalization). |
| `sales.SalesOrderLine`         | `line_discount_amount` (int)                                 | Same semantics for sales orders.                        |

### 2.2 Normalization & Validation

1. **Feature flag** – When `enable_line_discounts` is `False`, the UI hides the discount column and any incoming non-zero values are coerced to `0`.
2. **Clamp values** – `line_discount_amount` is forced into the range `0…gross_amount`. This prevents negative totals or discounts larger than the line price.
3. **Unit of measure changes** – Changing the UoM forces the discount back to zero to avoid stale adjustments (handled on both backend and frontend).

### 2.3 Posting (Invoices)

During invoice posting (`SalesInvoiceProcessor`):

1. A line’s **gross amount** (quantity × unit_price × quantity_per_unit) is credited to the sales account.
2. The **discount amount** is debited to `sales_line_discount_account` and credited back to the sales account (creating an “Entry of Discount Granted”).
3. Remaining ledger entries (COGS, inventory, receivables) use the line’s `total_amount` (already net of discount).

### 2.4 API Surface

- `SalesInvoiceLineSerializer` / `SalesOrderLineSerializer` expose `line_discount_amount` (and `gross_amount` for invoices).
- `SalesViewSet.update_lines` accepts either `line_discount_amount` or `lineDiscountAmount` and persists normalized values.
- `SalesOrderViewSet.update_lines` does the same but targets order lines.

**Note:** Only invoices create G/L discount entries; orders simply store the amount until the order is converted to an invoice.

---

## 3. Frontend Implementation

### 3.1 Feature toggle

`SalesServices.getSalesSetup()` returns:

```json
{
  "prevent_price_below_original": false,
  "disable_price_editing": false,
  "line_discounts_enabled": true
}
```

The `line_discounts_enabled` flag controls whether the discount column renders in both the POS screen (`Sales.tsx`) and the sales-order form (`SalesOrderLinesSection.tsx`). Disabling the flag clears any in-memory discounts before the lines are sent to the server.

### 3.2 POS / Sales Invoice UI

- Each `SaleItem` carries `line_discount_amount`.
- Inputs use the shared `computeLineTotals` helper ensuring totals stay synchronized.
- Updates are persisted through `SalesServices.updateSalesLines(systemId, id, lines)` → `POST /api/sales/<invoice_id>/update_lines/`.
- Discounts reset whenever the UoM dropdown changes.

### 3.3 Sales Orders UI

- Uses its own component (`SalesOrderLinesSection.tsx`) and service method (`SalesServices.updateSalesOrderLines`).
- Calls `/api/sales-orders/<order_id>/update_lines/`.
- Behavior mirrors invoices but without G/L postings until conversion.

### 3.4 Receipts & Totals

- Totals (`sale.total`, receipt summaries, ledger previews) always use the net line amount.
- Reloading a draft invoice/order repopulates the discount inputs via serializer data.

---

## 4. Admin & Operational Notes

1. **Configuration**
   - Populate `General Posting Setup → Sales Line Discount Account`.
   - Enable “Line Discounts” in **Sales & Receivables Setup** per tenant.
2. **Import/Export**
   - `company/management/commands/import_tenant_data.py` ensures G/L accounts are loaded before posting setups so the FK is valid.
3. **Migrations**
   - New fields live in the `postings` and `sales` migration chains; run `python manage.py migrate_schemas --schema=<tenant>` after pulling.

---

## 5. Troubleshooting

- **404 on `/api/sales/<id>/update_lines/`** – Ensure the backend is running with the explicit URL mapping in `sales/urls.py` (added alongside the router definitions) and that you restarted after pulling.
- **`AttributeError: update_lines`** – This indicates an outdated deployment; the method lives inside `SalesViewSet` and `SalesOrderViewSet`. Redeploy/restart so DRF binds the action.
- **Discount ignored** – Check `enable_line_discounts`; if `False`, the backend clamps the value to `0`.
- **Ledger entry errors** – Confirm `sales_line_discount_account` is configured for the relevant General Business/Product Posting Group combination. Posting will raise if it’s missing when a discount exists.

---

## 6. Quick Reference

- Toggle: `Sales & Receivables > enable_line_discounts`.
- Invoice API: `POST /api/sales/<invoice_id>/update_lines/`.
- Order API: `POST /api/sales-orders/<order_id>/update_lines/`.
- GL Account: `GeneralPostingSetup.sales_line_discount_account` (debit “Discount Granted”).
- Frontend flag: `SalesServices.getSalesSetup().data.line_discounts_enabled`.

With these pieces in place, line discounts remain consistent from the UI through posting and ledger integration.
