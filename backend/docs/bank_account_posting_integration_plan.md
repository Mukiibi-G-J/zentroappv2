# Bank Account Posting Integration Plan

## Overview

This document outlines the plan to integrate Bank Account posting logic into all payment-related document posting processes (Sales Invoices, Purchase Invoices, Payment Journals, Payments, Prepayments).

## Current State

### Current Posting Flow (G/L Account Only)

1. **Sales Invoice Posting:**
   - Uses `payment_method.bal_account_no` (G/L Account)
   - Creates G/L entry: Debit Cash/Bank G/L Account, Credit Receivables
   - Location: `sales/admin.py` - `SalesInvoiceProcessor._generate_cash_payment_entries()`

2. **Payment Journal Posting:**
   - Uses `payment_journal.bal_account_no` (G/L Account)
   - Creates G/L entries based on account type (Vendor/Customer/G/L)
   - Location: `payments/admin.py` - `PaymentJournalProcessor._generate_gl_entries()`

3. **Payment Posting (financials):**
   - Uses `payment_method.bal_account_no` (G/L Account)
   - Creates G/L entries for vendor/customer/G/L payments
   - Location: `financials/admin.py` - `PaymentProcessor._process_*_payment()`

4. **Purchase Invoice Posting:**
   - Similar pattern to sales invoices
   - Location: `purchases/admin.py` - `PurchaseInvoiceProcessor`

5. **Prepayment Posting:**
   - Similar pattern
   - Location: `prepayment/admin.py` - Various processors

## New Requirements

### Bank Account Posting Flow

When `payment_method.bal_account_type == "Bank Account"` (or `BalacingAccountType.Bank_Account.name`):

1. **Get Bank Account:**
   - `bank_account = payment_method.bal_bank_account_no`

2. **Get G/L Account from Bank Account Posting Group:**
   - `gl_account = bank_account.bank_account_posting_group.bank_account`
   - This is the G/L account that represents the bank account in the chart of accounts

3. **Create Bank Account Ledger Entry:**
   - `BankAccountLedgerEntry` with:
     - `bank_account_no` = bank_account
     - `posting_date` = document posting date
     - `document_type` = "Payment" (or appropriate type)
     - `document_no` = document number
     - `description` = transaction description
     - `amount` = payment amount (positive for debit, negative for credit)
     - `remaining_amount` = amount (initially)
     - `bank_account_posting_group` = bank_account.bank_account_posting_group
     - `bal_account_type` = type of account being paid (Customer, Vendor, G/L Account)
     - `bal_account_no` = account number being paid
     - `dimension_1` = user's dimension
     - `user` = request.user

4. **Create G/L Entry:**
   - Use the G/L account from the bank account posting group
   - Same amount and opposite sign as the bank account ledger entry
   - All other fields same as current G/L entry creation

## Implementation Plan

### Step 1: Create Helper Function

**Location:** `bank_account/utils.py` (new file)

**Function:** `create_bank_account_posting_entries()`

```python
def create_bank_account_posting_entries(
    bank_account,
    posting_date,
    document_type,
    document_no,
    description,
    amount,
    bal_account_type,
    bal_account_no,
    user,
    dimension_1=None,
    transaction_no=None
):
    """
    Create Bank Account Ledger Entry and return G/L account for G/L entry creation.
    
    Returns:
        dict with:
            - 'gl_account': G/L Account from bank account posting group
            - 'bank_account_entry': Created BankAccountLedgerEntry instance
    """
```

### Step 2: Update Sales Invoice Posting

**File:** `sales/admin.py`
**Class:** `SalesInvoiceProcessor`
**Method:** `_generate_cash_payment_entries()`

**Changes:**
- Check if `payment_method.bal_account_type == BalacingAccountType.Bank_Account.name`
- If yes, call helper function to create bank account entry
- Use returned G/L account for G/L entry instead of `bal_account_no`
- Keep existing G/L Account logic for backward compatibility

### Step 3: Update Payment Journal Posting

**File:** `payments/admin.py`
**Class:** `PaymentJournalProcessor`
**Method:** `_generate_gl_entries()`

**Changes:**
- Check `payment_journal.bal_account_type` (or get from payment_method)
- If Bank Account, create bank account ledger entry
- Use G/L account from bank account posting group for G/L entry

### Step 4: Update Payment Posting (financials)

**File:** `financials/admin.py`
**Class:** `PaymentProcessor`
**Methods:** 
- `_process_vendor_payment()`
- `_process_customer_payment()`
- `_process_gl_payment()`

**Changes:**
- Check `payment.payment_method.bal_account_type`
- If Bank Account, create bank account ledger entry
- Use G/L account from bank account posting group

### Step 5: Update Purchase Invoice Posting

**File:** `purchases/admin.py`
**Class:** `PurchaseInvoiceProcessor`

**Changes:**
- Similar to sales invoice posting
- Create bank account entries when payment method uses bank account

### Step 6: Update Prepayment Posting

**File:** `prepayment/admin.py`
**Classes:** Various posting processors

**Changes:**
- Add bank account posting support to all prepayment posting flows

### Step 7: Update Preview Posting

**Files:** All preview posting methods

**Changes:**
- Add bank account ledger entries to preview output
- Show bank account entries in preview templates

## Key Considerations

1. **Amount Sign Convention:**
   - Bank Account Ledger Entry: Positive = Debit (money in), Negative = Credit (money out)
   - For customer payments (receiving money): Positive amount
   - For vendor payments (paying money): Negative amount
   - For G/L payments: Depends on context

2. **G/L Account Mapping:**
   - Always use `bank_account.bank_account_posting_group.bank_account` (G_LAccount)
   - This ensures the bank account is properly represented in the chart of accounts

3. **Transaction Numbers:**
   - Use same transaction number for both Bank Account Ledger Entry and G/L Entry
   - Maintains audit trail consistency

4. **Backward Compatibility:**
   - Keep existing G/L Account posting logic
   - Only add new logic when `bal_account_type == "Bank Account"`

5. **Validation:**
   - Ensure bank account has posting group configured
   - Ensure posting group has G/L account linked
   - Validate bank account exists before posting

## Testing Checklist

- [ ] Sales Invoice with Bank Account payment method
- [ ] Sales Invoice with G/L Account payment method (existing - should still work)
- [ ] Payment Journal with Bank Account balancing account
- [ ] Payment Journal with G/L Account balancing account (existing)
- [ ] Payment (financials) with Bank Account payment method
- [ ] Payment (financials) with G/L Account payment method (existing)
- [ ] Purchase Invoice with Bank Account payment method
- [ ] Prepayment with Bank Account payment method
- [ ] Preview posting shows bank account entries correctly
- [ ] Bank account balance updates correctly after posting
- [ ] G/L account balance updates correctly after posting

## Files to Create/Modify

### New Files:
- `bank_account/utils.py` - Helper functions for bank account posting

### Modified Files:
- `sales/admin.py` - SalesInvoiceProcessor
- `payments/admin.py` - PaymentJournalProcessor
- `financials/admin.py` - PaymentProcessor
- `purchases/admin.py` - PurchaseInvoiceProcessor
- `prepayment/admin.py` - Prepayment processors
- Preview posting templates (if needed)

## Next Steps

1. Create helper function in `bank_account/utils.py`
2. Start with Sales Invoice posting (most common use case)
3. Test thoroughly
4. Apply same pattern to other document types
5. Update preview posting logic
6. Comprehensive testing across all document types

