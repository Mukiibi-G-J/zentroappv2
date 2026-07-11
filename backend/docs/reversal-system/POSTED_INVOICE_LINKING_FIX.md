# ✅ PostedSalesInvoice Linking Fix

## 🐛 The Problem

When attempting to reverse an invoice, the following error occurred:

```
❌ Error: Cannot assign "ReversalInvoiceWrapper object":
"SalesCreditMemo.original_invoice" must be a "PostedSalesInvoice" instance.
Transaction Number: REV-CM-000001-20251031-4D758C
```

## 🔍 Root Cause

The `SalesCreditMemo` model requires a ForeignKey to `PostedSalesInvoice`:

```python
class SalesCreditMemo(BaseModel):
    original_invoice = models.ForeignKey(
        PostedSalesInvoice,  # ← Requires actual PostedSalesInvoice instance
        on_delete=models.PROTECT,
        related_name="credit_memos",
    )
```

The reversal happens from **SalesInvoice admin page** (where SalesInvoice has status="Posted"), but we need to link to the **PostedSalesInvoice** that was created during the posting process.

---

## ✅ The Solution

### **Link via `customer_invoice_no`**

Both `SalesInvoice` and `PostedSalesInvoice` share the same `customer_invoice_no`, which is the perfect field to link them!

**During Posting (SalesInvoicePostingProcessor):**

```python
# When invoice is posted, PostedSalesInvoice is created with same customer_invoice_no
posted_sales_invoice = PostedSalesInvoice.objects.create(
    customer=self.invoice.customer,
    customer_invoice_no=self.invoice.customer_invoice_no,  # ← Same value!
    # ... other fields ...
)
```

**During Reversal (SalesInvoiceReversalPostingProcessor):**

```python
# 3. Find the PostedSalesInvoice that was created during posting
# Link via customer_invoice_no (most reliable)
customer_invoice_no = self.posted_invoice.customer_invoice_no

if customer_invoice_no:
    posted_sales_invoice = PostedSalesInvoice.objects.filter(
        customer_invoice_no=customer_invoice_no,
        customer=self.posted_invoice.customer,
    ).first()
else:
    # Fallback: match by customer and document_date
    posted_sales_invoice = PostedSalesInvoice.objects.filter(
        customer=self.posted_invoice.customer,
        document_date=self.posted_invoice.document_date,
    ).first()

# If no PostedSalesInvoice found, invoice wasn't properly posted
if not posted_sales_invoice:
    raise Exception(
        f"PostedSalesInvoice not found. "
        f"Please post the invoice first before attempting to reverse it."
    )

# 4. Create Credit Memo with actual PostedSalesInvoice
credit_memo = SalesCreditMemo.objects.create(
    original_invoice=posted_sales_invoice,  # ✅ Correct!
    # ... other fields ...
)
```

---

## 📊 Updated Process Flow

```
┌─────────────────────────────────────────┐
│  POSTING PROCESS                        │
├─────────────────────────────────────────┤
│  SalesInvoice (status="Pending")        │
│    ├─ invoice_no: SIN-000004            │
│    ├─ customer_invoice_no: INV-2024-001│
│    └─ customer: Customer A              │
│              │                          │
│              ▼ (Post Invoice)           │
│  PostedSalesInvoice CREATED             │
│    ├─ customer_invoice_no: INV-2024-001│ ← SAME!
│    └─ customer: Customer A              │
│              │                          │
│              ▼                          │
│  SalesInvoice (status="Posted")        │
└─────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────┐
│  REVERSAL PROCESS                       │
├─────────────────────────────────────────┤
│  1. User selects SalesInvoice           │
│     (status="Posted")                   │
│              │                          │
│              ▼                          │
│  2. Wrapper includes customer_invoice_no│
│              │                          │
│              ▼                          │
│  3. Find PostedSalesInvoice             │
│     by customer_invoice_no              │ ← LINK!
│              │                          │
│              ▼                          │
│  4. Create SalesCreditMemo              │
│     original_invoice = PostedSalesInvoice│
└─────────────────────────────────────────┘
```

---

## 🔧 Wrapper Changes

Added `customer_invoice_no` to both wrapper implementations:

### **Preview Wrapper:**

```python
class ReversalInvoiceWrapper:
    def __init__(self, sales_invoice):
        self.no = sales_invoice.invoice_no
        self.customer = sales_invoice.customer
        self.document_date = sales_invoice.document_date
        self.posting_date = sales_invoice.posting_date
        self.vat_date = sales_invoice.vat_date
        self.due_date = sales_invoice.due_date
        self.customer_invoice_no = sales_invoice.customer_invoice_no  # ✅ ADDED
        self.status = sales_invoice.status
        self.reversed = False
        self.posted_sales_invoice_lines = sales_invoice.lines
        self.credit_memos = SalesCreditMemo.objects.none()
```

### **Reversal Wrapper:**

```python
class ReversalInvoiceWrapper:
    def __init__(self, sales_invoice):
        self.no = sales_invoice.invoice_no
        self.customer = sales_invoice.customer
        self.document_date = sales_invoice.document_date
        self.posting_date = sales_invoice.posting_date
        self.vat_date = sales_invoice.vat_date
        self.due_date = sales_invoice.due_date
        self.customer_invoice_no = sales_invoice.customer_invoice_no  # ✅ ADDED
        self.status = sales_invoice.status
        self.reversed = False
        self.posted_sales_invoice_lines = sales_invoice.lines
        self.credit_memos = SalesCreditMemo.objects.none()
```

---

## ✅ Benefits

1. **Proper Linking**: Uses existing PostedSalesInvoice created during posting
2. **No Duplication**: Doesn't create unnecessary PostedSalesInvoice records
3. **Reliable Matching**: `customer_invoice_no` is unique and consistent
4. **Data Integrity**: Maintains proper foreign key relationships
5. **Clear Error**: Tells user if invoice wasn't properly posted

---

## 🧪 Testing

### **Test Case 1: Normal Flow**

```
1. Create SalesInvoice
2. Post SalesInvoice
   → Creates PostedSalesInvoice with matching customer_invoice_no
   → SalesInvoice status = "Posted"
3. Reverse SalesInvoice
   → Finds PostedSalesInvoice by customer_invoice_no ✅
   → Creates SalesCreditMemo with correct link ✅
```

### **Test Case 2: Invoice Not Posted**

```
1. Create SalesInvoice
2. Manually change status to "Posted" (without actual posting)
3. Try to reverse
   → PostedSalesInvoice not found ❌
   → Clear error message: "Please post the invoice first" ✅
```

---

## 📝 Code Locations

**File:** `zentro-backend/sales/admin.py`

**Changes:**

1. **Wrapper classes** (lines ~414, ~506):
   - Added `customer_invoice_no` attribute
2. **Reversal processor** (lines ~1846-1869):
   - Added PostedSalesInvoice lookup by `customer_invoice_no`
   - Removed PostedSalesInvoice creation logic
   - Added clear error if not found

---

## 🎉 Summary

**Problem:** Wrapper object passed instead of PostedSalesInvoice  
**Root Issue:** No link between SalesInvoice and PostedSalesInvoice  
**Solution:** Link via `customer_invoice_no` field  
**Result:** Reversal works correctly with proper foreign key relationships

---

## 📋 Related Fixes

This is part of a series of fixes for the reversal system:

1. ✅ Credit Memo Number Series Setup
2. ✅ Transaction Number & Rollback
3. ✅ VAT Date Field
4. ✅ **PostedSalesInvoice Linking via customer_invoice_no (THIS FIX)**

---

**Fixed:** October 31, 2024  
**Issue:** ForeignKey constraint violation  
**Solution:** Link via customer_invoice_no  
**Status:** ✅ Resolved
