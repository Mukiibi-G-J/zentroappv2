---
description: Breakdown and implementation plan for Sales Order module (mirroring Sales Invoice)
globs: zentro-backend/sales/**/*
alwaysApply: false
---

### Sales Order Module – Breakdown & Plan

#### 1. Backend: Data model for Sales Orders

- **1.1 SalesOrder header model**
  - Create `SalesOrder` model patterned on `SalesInvoice`:
    - Fields: `order_no` (SO-0001 format via `SalesReceivable.sales_no`), `customer`, `contact_person`, `order_date`, `expected_delivery_date`, `notes`, `status` (Open, Partially Delivered, Completed, Converted to Invoice).
    - Remove/avoid accounting-specific fields that only make sense at invoice/posted level (ledger links, posting dates, VAT dates, payment fields).
  - Ensure **no accounting posting** fields or posting logic is triggered from this model.

- **1.2 SalesOrderLine model**
  - Create `SalesOrderLine` similar to `SalesInvoiceLine`:
    - Fields: `sales_order` FK, `item`, `description`, `location_code`, `quantity`, `unit_of_measure`, `item_unit_of_measure`, `unit_price`, computed `line_amount` / `total_amount`, `dimension_1`.
  - Reuse the same UOM + item normalization pattern as Sales Invoice / Prepayment lines.
  - Optionally add per-line status for future `Partially Delivered` logic.

- **1.3 Totals and helpers**
  - Add `recalculate_totals()` on `SalesOrder` to sum line amounts into `total_amount`.
  - Ensure line `save()` triggers parent `recalculate_totals()` (prepayment pattern).
  - Ensure **no inventory deduction** or ledger creation from orders.

#### 2. Backend: Serializers and endpoints

- **2.1 Serializers**
  - `SalesOrderLineSerializer`:
    - Same fields and read-only behavior as `SalesInvoiceLineSerializer` (UOM options, item name/number, read-only totals, location).
  - `SalesOrderSerializer`:
    - Nested `lines`, `customer_name`, `total_amount`, `status`, dates, notes.
    - Based on `SalesInvoiceSerializer` but stripped of accounting/payment-specific logic.
    - Create/update:
      - On create: build order + lines, with item/UOM normalization patterned after prepayment serializers.
      - On update: update header; lines handled by separate `update_lines` action.

- **2.2 ViewSet & routes**
  - Add `SalesOrderViewSet`:
    - List/filter by `status`, `customer`, `order_date`.
    - Retrieve single order with lines.
    - Create/update/delete order (soft delete if using the same pattern as sales).
    - `duplicate` action to clone header + lines into a new order with a new number.
    - `update_lines` action using Card+Lines upsert pattern (like prepayments/sales).
  - Wire routes under `sales.urls`:
    - `GET /api/sales-orders/`
    - `POST /api/sales-orders/`
    - `GET /api/sales-orders/{id}/`
    - `POST /api/sales-orders/upsert/`
    - `POST /api/sales-orders/{id}/update_lines/`
    - `POST /api/sales-orders/{id}/duplicate/`

- **2.3 Conversion endpoint (Sales Order → Sales Invoice)**
  - `POST /api/sales-orders/{id}/convert-to-invoice/`:
    - Validate order status (must be `Open` or `Completed`).
    - Create a `SalesInvoice` from the order:
      - Map header fields (customer, dates, notes).
      - Copy lines (item, qty, UOM, price) into `SalesInvoiceLine`.
    - Do **not** change accounting/inventory behavior beyond what existing invoice posting already does.
    - Mark order `status = "Converted to Invoice"` and optionally store linked invoice id/number.

- **2.4 Print/Proforma endpoints**
  - Add endpoint for order print/proforma:
    - `GET /api/sales-orders/{id}/print/` (or similar).
    - Reuse invoice print template/style but change labels to “Proforma / Sales Order”.
  - Must be available while order is `Open`.

#### 3. Frontend: Types, services, and store

- **3.1 Types**
  - Add `SalesOrderTypes`, `SalesOrderLineType`, `SalesOrderFilterQueries` mirroring invoice types with:
    - `order_no`, `order_date`, `expected_delivery_date`, `status`, `notes`, `total_amount`, `lines`.

- **3.2 Services**
  - `SalesOrderServices` (parallel to `SalesServices`):
    - `getSalesOrders(filters)`
    - `createSalesOrder(data)`
    - `updateSalesOrder(data)`
    - `updateSalesOrderLines(systemId, id, lines)`
    - `duplicateSalesOrder(id)`
    - `convertToInvoice(id)`
    - `printSalesOrder(id)`

- **3.3 Redux slice**
  - `salesOrderSlice` (parallel to `salesSlice`):
    - State: `loading`, `salesOrderList`, `lines`, `currentRec`, `tableData`, `filterData`, `ui.isCardModalOpen`.
    - Thunks: `getSalesOrders`, `createSalesOrder`, `updateSalesOrder`, `deleteSalesOrder`, `updateSalesOrderLine`, `getSalesOrderDetails`, `convertToInvoice`, `duplicateSalesOrder`.

#### 4. Frontend: Screens and components

- **4.1 Sales Order Card page**
  - `SalesOrder.tsx`:
    - Based on `SalesInvoice.tsx`.
    - Header card with: customer selector, order date, expected delivery date, notes, status, total amount (read-only).
    - Lines section using `EditableTable`/Card+Lines pattern.

- **4.2 Header form**
  - `SalesOrderForm`:
    - Clone of `SalesForm` with Sales Order fields and labels.
    - Buttons:
      - Save / Update
      - Print Order / Proforma
      - Convert to Invoice
      - Duplicate

- **4.3 Lines section**
  - `SalesOrderLinesSection`:
    - Clone/adapter of `PrepaymentLinesSection` tied to sales order APIs.
    - Add/remove lines, item & UOM pickers, quantity, price, computed totals.
    - Autosave on blur → `updateSalesOrderLines`.

- **4.4 Orders list / history**
  - Either:
    - Add `SalesOrderHistory` component, or
    - Extend existing `SalesHistory` with tab/filter for sales orders.
  - Enable actions: Edit, Delete, Duplicate, Convert to Invoice.

#### 5. Status & business rules

- **5.1 Status transitions**
  - Allowed transitions:
    - `Open` → `Partially Delivered` → `Completed`
    - `Open` / `Completed` → `Converted to Invoice`
  - Enforce via backend validation on status updates.

- **5.2 No posting from Sales Orders**
  - Sales Orders must **not**:
    - Create customer ledger entries.
    - Create item ledger entries.
  - Inventory and accounting remain tied to **Sales Invoice posting**.

#### 6. Permissions, navigation, and routes

- **6.1 Page Objects & permission sets**
  - Add page object for “Sales Orders” in `populate_page_objects.py` (IDs 10xxx).
  - Add permission sets in `setup_page_permissions.py`:
    - For example: `SALES_ORDER_FULL` with `RIMD` CRUD on Sales Order page.
  - Attach permission sets to user groups (not roles/users directly).

- **6.2 Role center & JWT**
  - Ensure new page object is included in permission sets so JWT has:
    - `page_permissions["Sales Order Page"] = { read, insert, modify, delete }`.

- **6.3 Frontend routing & navigation**
  - `appsRoute.ts`:
    - Add route:
      - `key: "appsSales.salesOrder"`
      - `path: ${APP_PREFIX_PATH}/sales/sales-order`
      - `component: lazy(() => import("@/views/sales/SalesOrder"))`
      - `pageName: "Sales Order Page"`
  - `apps.navigation.config.ts`:
    - Under the Sales module, add nav item for “Sales Order” with:
      - `moduleCode: "sales"`
      - `pageName: "Sales Order Page"`


