# ✅ Credit Memo Number Series Setup

## 🐛 The Problem

When trying to reverse an invoice, you got this error:

```
❌ Error reversing invoice: Field 'credit_memo_no' is not configured in SalesReceivable.
```

## 🔍 Root Cause

The `SalesReceivable` configuration was missing the credit memo number series. It only had:

- ✅ Customer No (CUSTOMER series)
- ✅ Invoice No (SALESINV series)
- ✅ Posted Invoice No (PSIN series)
- ❌ Credit Memo No (missing!)
- ❌ Posted Credit Memo No (missing!)

## ✅ The Solution

### Step 1: Created Number Series

Created two new number series:

- **CM** (Credit Memo) - For credit memo documents
- **POSTCM** (Posted Credit Memo) - For posted credit memos

### Step 2: Created Number Series Lines

- CM: `CM-000001` to `CM-999999`
- POSTCM: `POSTCM-000001` to `POSTCM-999999`

### Step 3: Updated SalesReceivable

Linked the new series to the SalesReceivable configuration.

---

## 📊 Number Series Created

### CM (Credit Memo)

```
Code: CM
Description: Credit Memo
Start Number: CM-000001
End Number: CM-999999
Last Used: CM-000000
Increment: 1
```

### POSTCM (Posted Credit Memo)

```
Code: POSTCM
Description: Posted Credit Memo
Start Number: POSTCM-000001
End Number: POSTCM-999999
Last Used: POSTCM-000000
Increment: 1
```

---

## 🔧 For Future Tenants

If you create a new tenant, you need to set up these series. Two options:

### Option 1: Manual Setup (Django Admin)

1. Go to: **Setup → No Series**
2. Create **CM** series:
   - Code: `CM`
   - Description: `Credit Memo`
3. Create **POSTCM** series:
   - Code: `POSTCM`
   - Description: `Posted Credit Memo`
4. Go to: **Sales → Sales Receivable**
5. Run action: **Setup default configuration**

### Option 2: Automated Setup

Run these management commands:

```bash
# For specific tenant
python manage.py tenant_command shell --schema=<tenant_name> --command="exec(open('setup_scripts/create_credit_memo_series.py', encoding='utf-8').read())"

# Or create a management command
python manage.py setup_credit_memo_series --schema=<tenant_name>
```

---

## ✅ Verification

After setup, your SalesReceivable should show:

```
✅ Customer No: CUSTOMER series
✅ Invoice No: SALESINV (or INV) series
✅ Posted Invoice No: PSIN (or POSTINV) series
✅ Credit Memo No: CM series ← NEW!
✅ Posted Credit Memo No: POSTCM series ← NEW!
```

---

## 🧪 Test Reversal Now

1. Go to: **Sales → Sales Invoices**
2. Filter: **Status = Posted**
3. Select an invoice
4. Actions → **🔍 Preview Reversal**
5. Click → **❌ Confirm Reversal**
6. **Should work now!** ✅

Credit memos will be generated with numbers like:

- `CM-000001`
- `CM-000002`
- etc.

---

## 📋 Updated Setup Action

The `setup_default_configuration` action in SalesReceivableAdmin now includes credit memo series:

```python
required_series = ["CUSTOMER", "INV", "POSTINV", "CM", "POSTCM"]

SalesReceivable.objects.create(
    customer_no=customer_series,
    invoice_no=invoice_series,
    posted_invoice_no=posted_invoice_series,
    credit_memo_no=credit_memo_series,  # ← Added
    posted_credit_memo_no=posted_credit_memo_series,  # ← Added
)
```

---

**Fixed:** October 30, 2024  
**Issue:** Missing credit memo number series  
**Solution:** Created CM and POSTCM series  
**Status:** ✅ Ready to reverse invoices!
