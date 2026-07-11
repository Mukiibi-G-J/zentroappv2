# ✅ Line Amount Field Fix

## 🐛 The Problem

When attempting to reverse an invoice, the following error occurred:

```
❌ Error: 'SalesInvoiceLine' object has no attribute 'amount'
Transaction Number: REV-CM-000001-20251031-827ABE
```

## 🔍 Root Cause

`SalesInvoiceLine` doesn't have an `amount` **field** - it has a `total_amount` **property**!

```python
class SalesInvoiceLine(BaseModel):
    quantity = models.IntegerField(default=0)
    unit_price = models.IntegerField(default=0)

    # NO 'amount' field!

    @property
    def total_amount(self):  # ✅ This is a property, not a field
        if not self.quantity or not self.unit_price:
            return 0
        return self.quantity * self.unit_price
```

But the credit memo line creation was trying to access `line.amount`:

```python
SalesCreditMemoLine.objects.create(
    amount=line.amount,  # ❌ AttributeError!
)
```

---

## ✅ The Solution

Changed `line.amount` to `line.total_amount`:

```python
# 5. Create credit memo lines
for line in self.posted_invoice.posted_sales_invoice_lines.all():
    SalesCreditMemoLine.objects.create(
        credit_memo=credit_memo,
        item=line.item,
        description=line.description,
        location_code=line.location_code,
        quantity=line.quantity,
        item_unit_of_measure=line.item_unit_of_measure,
        unit_of_measure=line.unit_of_measure,
        unit_price=line.unit_price,
        amount=line.total_amount,  # ✅ FIXED: Use property, not field
        dimension_1=line.dimension_1,
    )
```

---

## 📊 Field vs Property

### **SalesInvoiceLine Structure:**

**Fields (stored in database):**

- ✅ `quantity` - Integer field
- ✅ `unit_price` - Integer field
- ❌ `amount` - **Does NOT exist!**

**Properties (computed):**

- ✅ `total_amount` - Computed from quantity × unit_price
- ✅ `line_amount` - Same as total_amount

---

## 🔄 Similar Models

This pattern is consistent across invoice line models:

### **PostedSalesInvoiceLine:**

```python
class PostedSalesInvoiceLine(BaseModel):
    quantity = models.IntegerField()
    unit_price = models.IntegerField()
    amount = models.IntegerField()  # ✅ Has 'amount' field
```

### **SalesInvoiceLine:**

```python
class SalesInvoiceLine(BaseModel):
    quantity = models.IntegerField()
    unit_price = models.IntegerField()
    # NO 'amount' field

    @property
    def total_amount(self):  # ✅ Computed property
        return self.quantity * self.unit_price
```

### **SalesCreditMemoLine:**

```python
class SalesCreditMemoLine(BaseModel):
    quantity = models.IntegerField()
    unit_price = models.IntegerField()
    amount = models.IntegerField()  # ✅ Has 'amount' field
```

---

## 📝 Code Location

**File:** `zentro-backend/sales/admin.py`

**Line:** ~1904

**Change:**

```python
# BEFORE
amount=line.amount,  # ❌ AttributeError

# AFTER
amount=line.total_amount,  # ✅ Works!
```

---

## ✅ Why This Works

When reversing from `SalesInvoice`:

1. Wrapper's `posted_sales_invoice_lines` → `SalesInvoice.lines` (SalesInvoiceLine objects)
2. Each line is a `SalesInvoiceLine` instance
3. `SalesInvoiceLine` has `total_amount` property
4. Credit memo created with `line.total_amount`

---

## 🎉 Summary

**Problem:** Trying to access non-existent `amount` field  
**Root Cause:** `SalesInvoiceLine` uses `total_amount` property, not `amount` field  
**Solution:** Changed to `line.total_amount`  
**Result:** Credit memo lines now created correctly

---

## 📋 Related Fixes

This is part of a series of fixes for the reversal system:

1. ✅ Credit Memo Number Series Setup
2. ✅ Transaction Number & Rollback
3. ✅ VAT Date Field
4. ✅ PostedSalesInvoice Linking via customer_invoice_no
5. ✅ **Line Amount Field (THIS FIX)**

---

**Fixed:** October 31, 2024  
**Issue:** AttributeError on line.amount  
**Solution:** Use line.total_amount property  
**Status:** ✅ Resolved
