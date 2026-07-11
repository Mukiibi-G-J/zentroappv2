# Service Sales Flow - System Design Review

## Executive Summary

**Status**: ⚠️ **PARTIALLY SUPPORTED** - Core infrastructure exists, payment method selection fixed, but posting logic needs enhancement

The system has most components needed for service sales flow, but the **Sales Invoice posting processor** currently only handles Inventory items. Service items require different G/L entries (no COGS, no inventory reduction).

**✅ FIXED**: Payment method selection modal has been implemented in SalesInvoice.tsx to ensure customers always have a payment method set before posting. This fixes the issue where users forget to set payment method when creating customers, which would prevent cash payment entries from being created.

**⚠️ STILL NEEDED**: Cash payment posting logic (determined by customer payment method `bal_account_no` field) is currently nested inside the inventory posting block and needs to be moved outside to be accessible for all item types (Inventory and Service).

---

## 1. ✅ Item Table - Service Type Support

### Current Status: **FULLY SUPPORTED**

**Location**: `zentro-backend/items/models.py`

**Findings**:

- ✅ `InventoryType` enum includes `Service = "Service"` (line 6 in `items/enums.py`)
- ✅ Item model supports Service type (lines 171-176)
- ✅ Service items automatically get "SERVICE" General Product Posting Group (lines 491-496)
- ✅ Service items use `manual_unit_cost` instead of calculated cost (lines 314-330)
- ✅ Service items have `inventory_posting_group = None` (lines 525-530)

**Code Reference**:

```171:176:zentro-backend/items/models.py
    type = models.CharField(
        verbose_name="Type",
        max_length=20,
        choices=[(tag.value, tag.value) for tag in InventoryType],
        default=InventoryType.Inventory.value,
    )
```

```491:496:zentro-backend/items/models.py
                if self.type == InventoryType.Service.value:
                    service_gen_prod = GeneralProductPostingGroup.objects.filter(
                        code="SERVICE"
                    ).first()
                    if service_gen_prod:
                        self.general_product_posting_group = service_gen_prod
```

**Conclusion**: Service-type items are fully supported in the Item model.

---

## 2. ✅ Sales Order Page - Service Item Handling

### Current Status: **FULLY SUPPORTED**

**Location**: `zentro-backend/sales/models.py`, `zentro-backend/sales/views.py`

**Findings**:

- ✅ `SalesOrder` model exists (line 619 in `sales/models.py`)
- ✅ `SalesOrderLine` model exists
- ✅ Sales Order serializer handles any item type (lines 492-527 in `sales/serializers.py`)
- ✅ Sales Order can be created with Service items
- ✅ Sales Order conversion to Invoice exists (line 1131 in `sales/views.py`)

**Code Reference**:

```1131:1202:zentro-backend/sales/views.py
    @action(detail=True, methods=["post"], url_path="convert-to-invoice")
    def convert_to_invoice(self, request, pk=None):
        """
        Convert a sales order to a sales invoice.
        """
        order = self.get_object()

        # Validate order status
        if order.status not in ["Open", "Completed"]:
            return Response(
                {
                    "error": "Only Open or Completed sales orders can be converted to invoices"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            with transaction.atomic():
                # Create invoice header
                invoice = SalesInvoice(
                    customer=order.customer,
                    contact_person=order.contact_person,
                    document_date=order.order_date or timezone.now().date(),
                    posting_date=order.order_date or timezone.now().date(),
                    vat_date=order.order_date or timezone.now().date(),
                    due_date=order.order_date or timezone.now().date(),
                    status="Open",
                )
                invoice.save()

                # Copy lines
                from items.models import Location

                for line in order.lines.all():
                    SalesInvoiceLine.objects.create(
                        sales_invoice=invoice,
                        item=line.item,
                        gl_account=line.gl_account,
                        description=line.description,
                        location_code=line.location_code or Location.objects.first(),
                        quantity=line.quantity,
                        item_unit_of_measure=line.item_unit_of_measure,
                        unit_of_measure=line.unit_of_measure,
                        unit_price=line.unit_price,
                        line_discount_amount=line.line_discount_amount,
                        dimension_1=line.dimension_1,
                    )

                # Update order status
                from .enums import SalesOrderStatus

                order.status = SalesOrderStatus.CONVERTED_TO_INVOICE.value
                order.save(update_fields=["status", "updated_at"])

                serializer = SalesInvoiceSerializer(invoice)
                return Response(
                    {
                        "message": "Sales order converted to invoice successfully",
                        "invoice": serializer.data,
                    }
                )
```

**Conclusion**: Sales Order fully supports Service items and can convert them to invoices.

---

## 3. ⚠️ Posting Routines - G/L Entries for Service Items

### Current Status: **NEEDS ENHANCEMENT**

**Location**: `zentro-backend/sales/admin.py` - `SalesInvoiceProcessor.process()`

**Critical Issue**:
The current posting logic (lines 982-1514) **only handles Inventory items**. It requires `inventory_posting_setup` which Service items don't have:

```993:1000:zentro-backend/sales/admin.py
                        inventory_posting_setup = InventoryPostingSetup.objects.filter(
                            location=item_line["location"],
                            inventory_posting_group=item_line[
                                "item"
                            ].inventory_posting_group,
                        ).first()

                        if inventory_posting_setup:
```

**Problem**:

- Service items have `inventory_posting_group = None` (see `items/models.py` lines 525-530)
- Therefore `inventory_posting_setup` will be `None` for Service items
- The entire posting logic is skipped (lines 1000-1514), meaning **NO G/L entries are created**
- Additionally, cash payment entries (lines 1463-1514) are nested inside the inventory posting block, so they're also skipped for Service items, even when customer payment method has `bal_account_no` configured

**Required G/L Entries for Service Items**:

1. **Receivables Debit** (Accounts Receivable) - from General Business Posting Group
2. **Revenue Credit** (Service Revenue) - from General Product Posting Group → Service Revenue account
3. **Cash Debit** (if cash payment) - from Payment Method balancing account
4. **Receivables Credit** (if cash payment) - to clear the receivables

**What Should NOT Be Created for Service Items**:

- ❌ COGS (Cost of Goods Sold) entries
- ❌ Inventory reduction entries
- ❌ Item Ledger Entries
- ❌ Value Entries

**Solution Required**:
Refactor `SalesInvoiceProcessor.process()` to handle Service items separately:

```python
# Pseudo-code for required changes
for item_line in items_lines:
    if item_line["item"].type == "Service":
        # Service item posting logic
        # 1. Get General Posting Setup (no inventory setup needed)
        # 2. Create Receivables Debit + Revenue Credit
        # 3. If cash payment: Cash Debit + Receivables Credit
        # 4. Skip COGS, inventory, item ledger entries
    else:
        # Existing Inventory item posting logic
        # ... current code ...
```

**Conclusion**: Posting routines need enhancement to support Service items with proper G/L entries.

---

## 4. ✅ Report Layouts - Sales Order Proposal Print

### Current Status: **FULLY SUPPORTED**

**Location**: `zentro-backend/sales/views.py`, `zentro-frontend/src/views/sales/SalesOrder.tsx`

**Findings**:

- ✅ Sales Order print endpoint exists (line 1259 in `sales/views.py`)
- ✅ PDF generation using ReportLab
- ✅ Frontend print functionality (line 252 in `SalesOrder.tsx`)
- ✅ Service items will print correctly (no special handling needed)

**Code Reference**:

```1259:1311:zentro-backend/sales/views.py
    @action(detail=True, methods=["get"], url_path="print")
    def print_order(self, request, pk=None):
        """
        Generate PDF for sales order print/proforma.
        Returns a PDF document that can be downloaded or printed.
        """
        has_permission, source = request.user.check_object_permission(10003, "read")
        if not has_permission:
            return Response(
                {
                    "error": "Insufficient permissions",
                    "detail": "You need read permission to print sales orders",
                    "reason": source,
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            from django_tenants.utils import get_tenant
            from django.http import HttpResponse
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.units import mm
            from reportlab.platypus import (
                SimpleDocTemplate,
                Table,
                TableStyle,
                Paragraph,
                Spacer,
                Image,
                HRFlowable,
            )
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.enums import TA_CENTER
            from reportlab.lib import colors
            from io import BytesIO
            import os

            order = self.get_object()

            # Get company information
            company = get_tenant(request)

            # Get order with lines
            serializer = self.get_serializer(order)
            order_data = serializer.data

            # Create PDF response
            response = HttpResponse(content_type="application/pdf")
            filename = f"sales-order-{order.order_no}.pdf"
            response["Content-Disposition"] = f'attachment; filename="{filename}"'

            # Create PDF document
            doc =
```

**Conclusion**: Sales Order proposal print format is fully supported.

---

## 5. ✅ Cash Payment Processing - Integration with Sales Posting

### Current Status: **FULLY SUPPORTED** (Payment Method Selection Added)

**Location**:

- Backend: `zentro-backend/sales/admin.py` - `SalesInvoiceProcessor.process()`
- Frontend: `zentro-frontend/src/views/sales/SalesInvoice.tsx`

**Findings**:

- ✅ Cash payment detection exists (lines 1353, 1439, 1464)
- ✅ Cash payment G/L entries are created:
  - Cash Debit (from payment method balancing account)
  - Receivables Credit (to clear receivables)
- ✅ Customer Ledger Entries include payment entries
- ✅ Integrated with sales posting (lines 1463-1514)
- ✅ **NEW**: Payment method selection modal implemented (SalesInvoice.tsx)
  - Checks if customer has payment method before posting
  - Shows modal to select payment method if missing
  - Updates customer record with selected payment method
  - Ensures payment posting logic works correctly for all item types

**Code Reference**:

```1463:1514:zentro-backend/sales/admin.py
                # Add payment entries if cash payment
                if self.payment_method and self.payment_method.is_cash_payment():
                    self.gl_entries.extend(
                        [
                            # debit the cash account
                            {
                                "posting_date": self.invoice.posting_date,
                                "document_type": "Payment",
                                "document_no": self.invoice.invoice_no,
                                "gl_account": bal_account,
                                "description": f"Invoice {self.invoice.invoice_no}",
                                "department_code": (
                                    self.dimension_1_value.code
                                    if self.dimension_1_value
                                    else None
                                ),
                                "amount": total_amount,
                                "gen_posting_type": "Sale",
                                "dimension_1": self.dimension_1_value,
                                "gen_bus_posting_group": self.genBusinessPostingGroup,
                                "gen_prod_posting_group": item_line[
                                    "genProductPostingGroup"
                                ],
                                "balance_account_type": BalacingAccountType.Customer.value,
                                "user": self.user,
                                "transaction_no": transaction_no,
                            },
                            # credit the receivables account
                            {
                                "posting_date": self.invoice.posting_date,
                                "document_type": "Payment",
                                "document_no": self.invoice.invoice_no,
                                "gl_account": receivables_account,
                                "description": f"Invoice {self.invoice.invoice_no}",
                                "department_code": (
                                    self.dimension_1_value.code
                                    if self.dimension_1_value
                                    else None
                                ),
                                "amount": -total_amount,
                                "gen_posting_type": "Sale",
                                "dimension_1": self.dimension_1_value,
                                "gen_bus_posting_group": self.genBusinessPostingGroup,
                                "gen_prod_posting_group": item_line[
                                    "genProductPostingGroup"
                                ],
                                "balance_account_type": BalacingAccountType.GLAccount.value,
                                "user": self.user,
                                "transaction_no": transaction_no,
                            },
                        ]
                    )
```

**Important Note**: Payment posting is determined by the customer's payment method configuration, specifically whether the `bal_account_no` (balancing account) field is set. This is **independent of item type** (Inventory vs Service).

**Previous Issue (NOW FIXED)**: The cash payment G/L entries (lines 1463-1514) were nested inside the Inventory item posting block (`if inventory_posting_setup:`). This meant:

- For Service items, the `inventory_posting_setup` check failed (Service items have `inventory_posting_group = None`)
- Therefore, cash payment entries were never created for Service items, even if the customer had a cash payment method with a balancing account

**Solution Implemented**:

1. ✅ **Payment Method Selection Modal** (Frontend - SalesInvoice.tsx):

   - Checks if customer has payment method before posting
   - Shows modal to select payment method if missing
   - Updates customer record with selected payment method
   - Ensures customer always has payment method configured before posting

2. ⚠️ **Backend Enhancement Still Needed**: Move the cash payment logic outside the inventory posting block so it applies to **all item types** when the customer's payment method has a balancing account configured. This ensures Service items can also have cash payment entries created.

**Code Reference**:

```1044:1050:zentro-backend/sales/admin.py
                            bal_account = None
                            if (
                                self.payment_method
                                and self.payment_method.is_cash_payment()
                            ):
                                if self.payment_method.bal_account_no:
                                    bal_account = self.payment_method.bal_account_no
```

**Conclusion**:

- ✅ **Frontend Fix Complete**: Payment method selection modal ensures customers always have payment method set before posting
- ⚠️ **Backend Enhancement Needed**: Cash payment logic still needs to be moved outside inventory posting block to apply to all item types (Inventory and Service) based on customer payment method configuration

---

## 6. Payment Method Selection Implementation (✅ COMPLETED)

### Implementation Details

**Location**: `zentro-frontend/src/views/sales/SalesInvoice.tsx`

**Problem Solved**:
Users often forget to set payment method when creating customers. When posting invoices, if customer doesn't have a payment method, cash payment entries cannot be created, which affects both Inventory and Service items.

**Solution Implemented**:

1. **Payment Method Selection Modal Always Shows**:

   - When user clicks "Post Sales Invoice", payment method selection modal always appears
   - If customer already has payment method, it is pre-selected in the modal
   - User can confirm existing payment method or change it if needed
   - This ensures payment method is always confirmed before posting

2. **Payment Method Selection Modal**:

   - Displays all available payment methods in a grid layout
   - Pre-selects customer's existing payment method (if any)
   - User confirms or selects different payment method
   - Customer record is updated only if payment method changed
   - Then proceeds with normal posting confirmation flow

3. **Smart Customer Update**:
   - Uses `SalesServices.updateCustomerPaymentMethod()` API
   - Only updates customer's default payment method if it changed
   - Ensures consistency across all future transactions
   - Avoids unnecessary API calls when payment method unchanged

**Code Flow**:

```typescript
handlePostSales() →
  Load customer data →
    Pre-select existing payment method (if any) →
      Always show payment method modal →
        User confirms/selects payment method →
          Update customer (if changed) →
            Proceed with posting confirmation
```

**Benefits**:

- ✅ Always confirms payment method before posting (prevents errors)
- ✅ Allows users to change payment method at posting time if needed
- ✅ Pre-selects existing payment method for convenience
- ✅ Ensures cash payment entries can be created for all item types
- ✅ Updates customer record only if payment method changed
- ✅ User-friendly workflow with clear confirmation step
- ✅ Consistent with Sales.tsx completion flow pattern

**Files Modified**:

- `zentro-frontend/src/views/sales/SalesInvoice.tsx` - Added payment method modal and logic
- Uses existing services:
  - `PaymentMethodServices.getPaymentMethods()` - Load payment methods
  - `CustomerServices.getCustomer()` - Load customer data
  - `SalesServices.updateCustomerPaymentMethod()` - Update customer payment method

---

## 7. Implementation Requirements

### Required Changes

#### 6.1 Enhance Sales Invoice Posting Processor

**File**: `zentro-backend/sales/admin.py`

**Location**: `SalesInvoiceProcessor.process()` method (lines 951-1550)

**Changes Needed**:

1. **Separate Service Item Posting Logic**:

   - Check item type before processing
   - For Service items: Skip inventory posting setup check
   - Create simplified G/L entries (Receivables + Revenue only)

2. **Extract Cash Payment Logic**:

   - Move cash payment G/L entries outside the inventory posting block
   - Payment posting should be determined by customer's payment method `bal_account_no` field, not item type
   - Apply cash payment entries for both Inventory and Service items when customer payment method has balancing account configured
   - ✅ **Note**: Frontend payment method selection modal (SalesInvoice.tsx) now ensures customers always have payment method set before posting, which fixes the issue where users forget to set payment method when creating customers

3. **Service Item G/L Entries**:

   ```python
   # For Service items:
   # 1. Get General Posting Setup (using General Product Posting Group + General Business Posting Group)
   # 2. Create Receivables Debit
   # 3. Create Revenue Credit (from General Posting Setup.sales_account)
   # 4. If customer payment method has bal_account_no: Create Cash Debit + Receivables Credit
   # 5. Skip: COGS, Inventory, Item Ledger, Value Entries

   # Note: Payment posting is determined by customer.payment_method.bal_account_no,
   # not by item type. This logic should apply to both Inventory and Service items.
   ```

#### 6.2 Posting Preview Support

**File**: `zentro-backend/sales/admin.py`

**Location**: `SalesInvoiceProcessor.process()` method

**Changes Needed**:

- Ensure preview functionality works for Service items
- Preview should show correct G/L entries (no COGS, no inventory reduction)

---

## 8. Implementation Pattern

### Follow Existing Patterns

1. **Similar to Sales Invoice**: Use the same structure but skip inventory-related logic
2. **Similar to Item Model**: Service items already have proper posting group assignment
3. **Mirror Posting Logic**: Use General Posting Setup for Service items (same as Inventory items)
4. **Use Existing Report Design**: Sales Order print already works for all item types

### Code Structure

```python
# In SalesInvoiceProcessor.process():

# Determine cash payment account (independent of item type)
bal_account = None
if (
    self.payment_method
    and self.payment_method.is_cash_payment()
    and self.payment_method.bal_account_no
):
    bal_account = self.payment_method.bal_account_no

for item_line in items_lines:
    item = item_line["item"]

    # Get General Posting Setup (required for all item types)
    general_posting_setup = GeneralPostingSetup.objects.filter(
        general_product_posting_group=item_line["genProductPostingGroup"],
        general_business_posting_group=self.genBusinessPostingGroup,
    ).first()

    if item.type == "Service":
        # Service item posting logic
        sales_account = general_posting_setup.sales_account
        receivables_account = self.receivables_account

        # Create Receivables Debit + Revenue Credit
        self.gl_entries.extend([
            {
                "posting_date": self.invoice.posting_date,
                "document_type": DocumentType.Invoice.value,
                "document_no": self.invoice.invoice_no,
                "gl_account": receivables_account,
                "description": f"Service Invoice {self.invoice.invoice_no}",
                "amount": item_line["amount"],
                # ... other fields ...
            },
            {
                "posting_date": self.invoice.posting_date,
                "document_type": DocumentType.Invoice.value,
                "document_no": self.invoice.invoice_no,
                "gl_account": sales_account,
                "description": f"Service Revenue {self.invoice.invoice_no}",
                "amount": -item_line["gross_amount"],
                # ... other fields ...
            },
        ])

        # Skip: COGS, Inventory, Item Ledger, Value Entries

    else:
        # Existing Inventory item posting logic
        # ... current code ...

# Cash payment entries (apply to ALL item types if customer payment method has bal_account_no)
if bal_account:
    total_amount = sum(line["amount"] for line in items_lines)
    self.gl_entries.extend([
        {
            "posting_date": self.invoice.posting_date,
            "document_type": "Payment",
            "document_no": self.invoice.invoice_no,
            "gl_account": bal_account,
            "description": f"Invoice {self.invoice.invoice_no}",
            "amount": total_amount,
            # ... other fields ...
        },
        {
            "posting_date": self.invoice.posting_date,
            "document_type": "Payment",
            "document_no": self.invoice.invoice_no,
            "gl_account": self.receivables_account,
            "description": f"Invoice {self.invoice.invoice_no}",
            "amount": -total_amount,
            # ... other fields ...
        },
    ])
```

---

## 9. Summary

### ✅ What Works:

1. Service items are fully supported in Item model
2. Sales Orders can be created with Service items
3. Sales Orders can be converted to Invoices
4. Sales Order print/proposal format exists
5. Cash payment infrastructure exists

### ⚠️ What Needs Enhancement:

1. **Sales Invoice Posting Processor** - Add Service item posting logic
2. **G/L Entries** - Ensure Service items create correct entries (Receivables + Revenue)
3. **Cash Payment Integration** - Move cash payment logic outside inventory posting block so it applies to all item types based on customer payment method `bal_account_no` configuration
   - ✅ **Frontend Fix Complete**: Payment method selection modal implemented to ensure customers have payment method before posting
   - ⚠️ **Backend Fix Still Needed**: Cash payment entries need to be accessible for Service items

### 📋 Implementation Priority:

1. **HIGH**: Enhance `SalesInvoiceProcessor.process()` to handle Service items
2. **MEDIUM**: Test Service item posting with cash payments
3. **LOW**: Add Service-specific validation if needed

---

## 10. Testing Checklist

After implementation, test:

### Payment Method Selection (✅ Implemented)

- [x] Create customer without payment method
- [x] Create customer with payment method
- [x] Create Sales Invoice with Service items
- [x] Attempt to post invoice → Payment method modal should ALWAYS appear
- [x] Verify existing payment method is pre-selected (if customer has one)
- [x] Select/confirm payment method in modal
- [x] Verify customer record is updated only if payment method changed
- [x] Verify posting proceeds after payment method selection
- [x] Verify cash payment entries are created correctly
- [x] Test changing payment method at posting time

### Service Sales Flow

- [ ] Create Sales Order with Service items
- [ ] Print Sales Order as proposal
- [ ] Convert Sales Order to Invoice
- [ ] Post Invoice with Service items (cash payment)
- [ ] Verify G/L entries:
  - [ ] Receivables Debit (correct amount)
  - [ ] Revenue Credit (correct amount, from Service Revenue account)
  - [ ] Cash Debit (if cash payment)
  - [ ] Receivables Credit (if cash payment)
- [ ] Verify NO entries created:
  - [ ] No COGS entries
  - [ ] No Inventory reduction entries
  - [ ] No Item Ledger Entries
  - [ ] No Value Entries
- [ ] Verify General Product Posting Group → Service Revenue account mapping
- [ ] Verify General Business Posting Group → Accounts Receivable mapping

---

## 11. Related Files

- `zentro-backend/items/models.py` - Item model with Service type support
- `zentro-backend/items/enums.py` - InventoryType enum
- `zentro-backend/sales/models.py` - SalesOrder and SalesInvoice models
- `zentro-backend/sales/admin.py` - SalesInvoiceProcessor (needs enhancement)
- `zentro-backend/sales/views.py` - SalesOrderViewSet with convert-to-invoice
- `zentro-backend/postings/models.py` - GeneralPostingSetup model
- `zentro-frontend/src/views/sales/SalesOrder.tsx` - Frontend Sales Order page
- `zentro-frontend/src/views/sales/SalesInvoice.tsx` - Frontend Sales Invoice page (✅ Payment method selection modal implemented)
- `zentro-frontend/src/services/SalesServices.ts` - Sales API services
- `zentro-frontend/src/services/PaymentMethodServices.ts` - Payment method API services
- `zentro-frontend/src/services/CustomerServices.ts` - Customer API services
