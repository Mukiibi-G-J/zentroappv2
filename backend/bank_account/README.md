# Bank Account Module

This module implements a complete Bank Account management system following the project's existing patterns and architecture.

## Overview

The Bank Account module provides:
- Bank Account management with automatic number generation
- Bank Account Ledger Entries for transaction tracking
- Bank Account Posting Groups for G/L account mapping
- FlowFields for calculated balances
- Full reversal tracking support
- Dimension integration

## Models

### 1. BankAccountPostingGroup

Defines posting groups that map bank accounts to G/L accounts.

**Fields:**
- `code` (CharField, Primary Key) - Unique code for the posting group
- `description` (CharField) - Description of the posting group
- `bank_account` (ForeignKey to G_LAccount) - G/L account for bank transactions

**Location:** `bank_account/models.py`

### 2. BankAccount

Main model for bank accounts with automatic number generation and FlowFields.

**Fields:**
- `no` (CharField, Primary Key) - Bank account number (auto-generated from No. Series)
- `name` (CharField) - Name of the bank account
- `address` (TextField) - Bank address
- `contact` (TextField) - Contact information
- `bank_account_no` (CharField) - Bank account number at the bank
- `min_balance` (DecimalField) - Minimum balance required
- `bank_account_posting_group` (ForeignKey) - Posting group for this account

**FlowFields (Properties):**
- `debit_amount` - Sum of debit amounts from ledger entries
- `credit_amount` - Sum of credit amounts from ledger entries
- `balance` - Current balance (debit_amount - credit_amount)
- `balance_at_date(date)` - Balance at a specific date

**No. Series Integration:**
- Automatically generates `no` from `BankAccountSetup.bank_account_no_series`
- Uses `increment_item_number` helper function
- Updates `NoSeriesLines.last_used_number` and `last_used_date`

**Location:** `bank_account/models.py`

### 3. BankAccountLedgerEntry

Tracks all transactions for bank accounts with full reversal support.

**Fields:**
- `entry_no` (AutoField, Primary Key) - Automatic entry number
- `bank_account_no` (ForeignKey to BankAccount) - Bank account for this entry
- `posting_date` (DateField) - Date when entry was posted
- `document_type` (CharField) - Type of document (Payment, Invoice, Credit Memo, etc.)
- `description` (TextField) - Transaction description
- `amount` (DecimalField) - Transaction amount (positive=debit, negative=credit)
- `remaining_amount` (DecimalField) - Remaining amount to be applied
- `bank_account_posting_group` (ForeignKey) - Posting group from bank account
- `bal_account_type` (CharField) - Balancing account type (G/L Account, Customer, Vendor, Bank Account)
- `bal_account_no` (CharField) - Balancing account number
- `statement_status` (CharField) - Statement reconciliation status
- `statement_no` (CharField) - Bank statement number
- `statement_line_no` (IntegerField) - Line number on bank statement
- `document_date` (DateField) - Date of source document
- `document_no` (CharField) - Document number
- `dimension_1` (ForeignKey to DimensionValue) - Dimension integration
- `user` (ForeignKey to User) - User who created the entry

**Reversal Tracking Fields:**
- `reversed` (BooleanField) - Indicates if entry has been reversed
- `reversed_by_entry_no` (IntegerField) - Entry number that reversed this entry
- `reversed_entry_no` (IntegerField) - Entry number this entry reverses
- `reversed_by_user` (ForeignKey to User) - User who performed reversal
- `reversed_date` (DateField) - Date when entry was reversed

**FlowFields (Properties):**
- `debit_amount` - Positive amount (debit)
- `credit_amount` - Absolute value of negative amount (credit)
- `is_reversal_entry` - Check if this is a reversal entry
- `can_be_reversed` - Check if entry can be reversed

**Location:** `bank_account/models.py`

## Enums

### BankAccountDocumentType

Document types for bank account ledger entries:
- Payment
- Invoice
- Credit Memo
- Finance Charge Memo
- Reminder
- Refund

**Location:** `bank_account/enums.py`

### BankAccountStatementStatus

Statement reconciliation status:
- Open
- Closed
- Bank Acc. Entry Applied
- Check Entry Applied

**Location:** `bank_account/enums.py`

## Setup

### BankAccountSetup

Configuration model for bank account number series.

**Fields:**
- `bank_account_no_series` (ForeignKey to NoSeries) - Number series for bank accounts

**Location:** `setup/models.py`

**Admin:** Registered in `setup/admin.py`

## Admin Interfaces

### BankAccountPostingGroupAdmin

- List display: code, description, bank_account
- Search: code, description, bank_account
- Autocomplete: bank_account
- Sync actions available

### BankAccountAdmin

- List display: no, name, bank_account_no, posting_group, min_balance, debit_amount, credit_amount, balance
- Search: no, name, bank_account_no, posting_group, address, contact
- Filters: bank_account_posting_group
- Inline: BankAccountLedgerEntryInline
- Readonly: no, debit_amount, credit_amount, balance
- Fieldsets: General, Posting, Balance Information

### BankAccountLedgerEntryAdmin

- List display: entry_no, bank_account_no, posting_date, document_type, document_no, description, amount, debit_amount, credit_amount, remaining_amount, statement_status, reversal_status
- Search: entry_no, bank_account_no, document_no, description, statement_no
- Filters: ReversalStatusFilter, reversed, posting_date, document_type, statement_status, bank_account_no
- Readonly: entry_no, debit_amount, credit_amount, reversal fields
- Autocomplete: bank_account_no, bank_account_posting_group, dimension_1, user
- Fieldsets: General, Amounts, Posting, Statement, Dimensions, Reversal, System

**Location:** `bank_account/admin.py`

## Patterns Followed

1. **BaseModel Inheritance** - All models inherit from `utils.utils.BaseModel`
2. **No. Series Pattern** - Uses `NoSeries` and `NoSeriesLines` with `increment_item_number` helper
3. **FlowFields** - Implemented as `@property` methods that aggregate from related tables
4. **Posting Groups** - Follows same pattern as `CustomerPostingGroup` and `VendorPostingGroup`
5. **Ledger Entry Pattern** - Similar structure to `CustomerLedgerEntry` and `GeneralLedgerEntry`
6. **Reversal Tracking** - Complete reversal tracking with all required fields
7. **Dimension Integration** - Uses `dimension_1` ForeignKey to `DimensionValue`
8. **Admin Patterns** - Follows existing admin interface patterns with fieldsets, filters, and readonly fields

## Database Indexes

### BankAccount
- Index on `no`
- Index on `bank_account_posting_group`

### BankAccountLedgerEntry
- Index on `bank_account_no` + `posting_date`
- Index on `document_no`
- Index on `statement_no` + `statement_line_no`
- Index on `reversed`
- Index on `reversed_entry_no`

## Next Steps

1. **Run Migrations:**
   ```bash
   python manage.py makemigrations bank_account
   python manage.py makemigrations setup
   python manage.py migrate
   ```

2. **Create No. Series:**
   - Go to Django Admin → Setup → No Series
   - Create a No Series (e.g., "BANK" with description "Bank Account")
   - Create No Series Lines with start_number (e.g., "BANK-000001")

3. **Configure Bank Account Setup:**
   - Go to Django Admin → Setup → Bank Account Setup
   - Select the No Series created above

4. **Create Bank Account Posting Groups:**
   - Go to Django Admin → Bank Account → Bank Account Posting Groups
   - Create posting groups with codes and G/L accounts

5. **Create Bank Accounts:**
   - Go to Django Admin → Bank Account → Bank Accounts
   - Create bank accounts (numbers will be auto-generated)

## Usage Examples

### Creating a Bank Account

```python
from bank_account.models import BankAccount, BankAccountPostingGroup

# Get or create posting group
posting_group = BankAccountPostingGroup.objects.get(code="CASH")

# Create bank account (no will be auto-generated)
bank_account = BankAccount.objects.create(
    name="Main Cash Account",
    bank_account_no="1234567890",
    bank_account_posting_group=posting_group,
    min_balance=1000.00
)
```

### Creating a Ledger Entry

```python
from bank_account.models import BankAccountLedgerEntry
from bank_account.enums import BankAccountDocumentType

entry = BankAccountLedgerEntry.objects.create(
    bank_account_no=bank_account,
    posting_date=datetime.now().date(),
    document_type=BankAccountDocumentType.Payment.name,
    document_no="PAY-001",
    description="Payment received",
    amount=1000.00,  # Positive = debit
    user=request.user
)
```

### Accessing FlowFields

```python
# Get balance
balance = bank_account.balance

# Get debit/credit amounts
debit = bank_account.debit_amount
credit = bank_account.credit_amount

# Get balance at specific date
balance_at_date = bank_account.balance_at_date(datetime(2024, 1, 1).date())
```

## Files Created/Modified

### Created:
- `bank_account/models.py` - All models
- `bank_account/enums.py` - Enum definitions
- `bank_account/admin.py` - Admin interfaces
- `bank_account/README.md` - This file

### Modified:
- `setup/models.py` - Added `BankAccountSetup` model
- `setup/admin.py` - Added `BankAccountSetupAdmin`

## Notes

- All models follow Django Tenants multi-tenancy (no company ForeignKey needed)
- FlowFields are calculated on-the-fly and not stored in database
- Reversal tracking follows the same pattern as other ledger entries in the project
- Dimension integration uses `dimension_1` field (following project pattern)
- All field names use camelCase in API responses (following project convention)

