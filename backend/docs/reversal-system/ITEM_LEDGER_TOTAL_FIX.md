# ✅ Item Ledger Total Field Fix

## 🐛 The Problem

When attempting to reverse an invoice, the following database error occurred:

```
❌ Error: null value in column "total" of relation "Item Ledger Entries"
violates not-null constraint
DETAIL: Failing row contains (..., null, ...)
Transaction Number: REV-CM-000001-20251031-F0C67D
```

## 🔍 Root Cause

The `ItemLedgerEntries` table has a `total` column with a **NOT NULL constraint**, but the reversal processor wasn't including this field when creating reversal entries.

### **Model Definition:**

```python
class ItemLedgerEntries(BaseModel):
    description = models.TextField(editable=False)
    quantity = models.IntegerField(editable=False)
    remaining_quantity = models.PositiveIntegerField(editable=False)
    total = models.FloatField(editable=False)  # ← NOT NULL! Required field
    unit_of_measure = models.CharField(max_length=255, default="PCS", editable=False)
```

### **Missing in Reversal:**

The `_find_and_reverse_item_entries` method wasn't extracting the `total` from original entries, and the posting processor wasn't providing it when creating new entries.

---

## ✅ The Solution

### **1. Extract Total from Original Entry**

Updated `_find_and_reverse_item_entries` in `SalesInvoiceReversalProcessor`:

```python
def _find_and_reverse_item_entries(self):
    """Find original item ledger entries and create opposite entries"""
    from decimal import Decimal

    original_entries = ItemLedgerEntries.objects.filter(
        document_no=self.posted_invoice.no
    )

    for entry in original_entries:
        # Convert to Decimal to ensure numeric type
        quantity = Decimal(str(entry.quantity)) if entry.quantity else Decimal("0")
        total = Decimal(str(entry.total)) if entry.total else Decimal("0")  # ✅ ADDED

        self.reversal_item_entries.append(
            {
                "posting_date": timezone.now().date(),
                "entry_type": "Positive Adjmt.",
                "original_entry_type": entry.entry_type,
                "item": entry.item,
                "document_no": f"CM-PREVIEW-{self.posted_invoice.no}",
                "description": f"Reversal of {entry.description}",
                "location": entry.location,
                "quantity": -quantity,  # OPPOSITE
                "quantity_before_reversal": quantity,  # For display
                "remaining_quantity": -quantity,
                "total": -total,  # ✅ ADDED: OPPOSITE total amount
                "total_before_reversal": total,  # ✅ ADDED: For display
                "unit_of_measure_code": entry.unit_of_measure_code,
                "dimension_1": entry.dimension_1,
                "user": self.user,
                "date": timezone.now().date(),
                "document_type": "Credit Memo",
                "transaction_no": f"REV-{entry.transaction_no}",
            }
        )
```

### **2. Include Total When Creating Entry**

Updated `SalesInvoiceReversalPostingProcessor.post()`:

```python
# Create reversing item entry with consistent transaction number
reversing_item = ItemLedgerEntries.objects.create(
    posting_date=item_entry["posting_date"],
    entry_type=item_entry["entry_type"],
    item=item_entry["item"],
    document_no=credit_memo_no,
    description=item_entry["description"],
    location=item_entry["location"],
    quantity=item_entry["quantity"],
    remaining_quantity=item_entry["remaining_quantity"],
    total=item_entry["total"],  # ✅ ADDED: Required field
    unit_of_measure_code=item_entry["unit_of_measure_code"],
    dimension_1=item_entry["dimension_1"],
    user=item_entry["user"],
    date=item_entry["date"],
    document_type=item_entry["document_type"],
    transaction_no=transaction_no,
    reverses_entry_no=(
        original_item.id if original_item else None
    ),
)
```

---

## 📊 What is the "total" Field?

The `total` field in `ItemLedgerEntries` represents the **total value/amount** of the inventory transaction:

```
total = quantity × unit_price (or unit_cost)
```

**For reversal entries:**

- Original: `total = +1000` (sale value)
- Reversal: `total = -1000` (opposite to nullify)

---

## 🔄 Complete Field Mapping

### **Original Entry (Sale):**

```python
ItemLedgerEntry:
  quantity: 3
  remaining_quantity: 0  # Items sold, none remaining
  total: 150000  # 3 items × 50000 each
  entry_type: "Sale"
```

### **Reversal Entry (Credit Memo):**

```python
ItemLedgerEntry:
  quantity: -3  # ✅ Opposite (restore inventory)
  remaining_quantity: -3  # ✅ Opposite
  total: -150000  # ✅ Opposite (nullify value)
  entry_type: "Positive Adjmt."
  reverses_entry_no: [original_entry.id]  # ✅ Link back
```

---

## 📝 Code Locations

**File:** `zentro-backend/sales/admin.py`

**Changes:**

1. **Reversal Processor** (lines ~1687-1704):

   - Added `total` extraction from original entry
   - Added `total` to reversal entry dict
   - Added `total_before_reversal` for display

2. **Posting Processor** (line ~2033):
   - Added `total` field when creating `ItemLedgerEntries`

---

## ✅ Impact

### **Before Fix:**

```python
ItemLedgerEntries.objects.create(
    quantity=-3,
    remaining_quantity=-3,
    # total=???  ❌ Missing! Database error!
)
```

### **After Fix:**

```python
ItemLedgerEntries.objects.create(
    quantity=-3,
    remaining_quantity=-3,
    total=-150000,  # ✅ Included! Database happy!
)
```

---

## 🧪 Testing

### **Verify Reversal:**

1. Check original `ItemLedgerEntry`:

   - `quantity: 3`
   - `total: 150000`

2. Reverse invoice

3. Check reversal `ItemLedgerEntry`:
   - `quantity: -3` ✅
   - `total: -150000` ✅
   - `reverses_entry_no: [original_id]` ✅

---

## 🎉 Summary

**Problem:** Missing required `total` field causing database constraint violation  
**Root Cause:** Field not extracted from original or included in creation  
**Solution:** Added `total` extraction and inclusion in both preview and posting  
**Result:** Item ledger reversal entries now created successfully

---

## 📋 Related Fixes

This is part of a series of fixes for the reversal system:

1. ✅ Credit Memo Number Series Setup
2. ✅ Transaction Number & Rollback
3. ✅ VAT Date Field
4. ✅ PostedSalesInvoice Linking via customer_invoice_no
5. ✅ Line Amount Field
6. ✅ **Item Ledger Total Field (THIS FIX)**

---

**Fixed:** October 31, 2024  
**Issue:** NOT NULL constraint violation on total field  
**Solution:** Added total field extraction and inclusion  
**Status:** ✅ Resolved
