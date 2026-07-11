# Document-Level Prepayment Migration

## Overview

This document describes the migration from **line-level prepayment** to **document-level prepayment** functionality.

## Key Changes

### 1. Header-Level Fields (Moved from Lines)

The following fields are now managed at the document header level:

- **Prepmt. Amt. Inv.** (`total_prepayment_invoiced`) - Portion of deposit already invoiced
- **Preview Deposit Total** (`preview_deposit_total`) - Calculated preview showing posted + draft installments
- **Prepmt. Line Amount** (`total_prepayment`) - Total deposit collected from customer
- **Prepmt. Line Amount %** (`deposit_percent`) - Percentage of deposit vs document total
- **Prepmt. Amt. to Deduct** (`total_prepayment_to_deduct`) - Amount of invoiced prepayment to apply next
- **Prepmt. Amt. Deducted** (`total_prepayment_deducted`) - Cumulative prepayment applied to final invoices

### 2. Installment Management

- **Installments belong to the document header**, not individual lines
- **Installment Table**: Modal with table showing installment history
- **Installment Input**: Single input field for new installment amount
- **Edit Flow**: Click edit → populates input above table with prepayment number (disabled) and installment amount
- **Save Logic**: If installment record doesn't exist, create it; if exists, update it
- **Installment models**:
  - `PreaymentInstallmentDraft` - One draft installment per document (replaces line-level drafts)
  - `PreaymentInstallmentHistory` - History of applied installments at document level

### 3. Line Simplification

Lines now only contain:
- Item selection
- Quantity
- Unit Price
- Amount (calculated: qty × unit_price)
- Unit of Measure
- Tracking Code

**Removed from lines:**
- `deposit_amount` (moved to header)
- `deposit_percent` (moved to header)
- `prepayment_amount_invoiced` (moved to header)
- `prepayment_amount_to_deduct` (moved to header)
- `prepayment_amount_deducted` (moved to header)
- `installment_amount` (moved to header)
- `preview_deposit_total` (moved to header)
- `installment_draft` relationship (moved to header)

### 4. Business Rules

#### Deposit Collection
- User enters deposit amount in header
- Lines are added with items, quantities, and prices
- Document total = sum of all line amounts
- Deposit % = (total_prepayment / total_amount) × 100

#### Installment Flow
1. User clicks "Add Installment" button in header
2. Modal opens with:
   - Prepayment number (disabled, read-only)
   - Installment amount input field
   - Table showing installment history
3. User enters new installment amount
4. On save:
   - If draft doesn't exist → create `PreaymentInstallmentDraft`
   - If draft exists → update amount
5. Preview Deposit Total = `total_prepayment_invoiced` + `installment_draft.amount` (clamped to `total_amount`)

#### Posting Behavior
- Posting creates invoice for the installment amount (draft + any remaining collected)
- Installment draft is applied to `total_prepayment` during posting
- History record created in `PreaymentInstallmentHistory`

#### Editing Validation
- **Cannot reduce document total below already posted amount**
- Example: If 200,000 already posted, cannot reduce total_amount below 200,000
- Validation error: "Cannot reduce document total below already posted amount of {amount}"

### 5. API Changes

#### New Endpoints
- `POST /api/prepayments/<id>/installments/` - Create/update installment draft
  - Payload: `{ "amount": 200000 }`
  - Returns: Updated prepayment detail

#### Modified Endpoints
- `PATCH /api/prepayments/<id>/` - Now accepts header-level deposit fields
- `POST /api/prepayments/<id>/update_lines/` - Only accepts qty/price/UOM (no deposit fields)

#### Serializer Changes
- `PreaymentDetailSerializer`: Adds header deposit fields, installment_draft, installment_history
- `PreaymentLineSerializer`: Removes all deposit-related fields

### 6. Frontend Changes

#### Header Form
- New fields:
  - "Deposit Amount" input (total_prepayment)
  - "Prepmt. Amt. Inv." (read-only)
  - "Preview Deposit Total" (read-only)
  - "Deposit %" (read-only)
  - "Add Installment" button

#### Installment Modal
- Prepayment number (disabled)
- Installment amount input
- Table showing installment history (date, amount, transaction_no, applied_by)
- Save/Cancel buttons

#### Lines Table
- Removed columns:
  - Prepmt. Line Amount
  - Preview Deposit Total
  - Prepmt. Amt. Inv.
  - New Installment
- Kept columns:
  - Item Name
  - Quantity
  - Unit Price
  - Amount
  - Unit of Measure

### 7. Migration Strategy

1. **Data Migration**:
   - Sum all line `deposit_amount` → header `total_prepayment`
   - Sum all line `prepayment_amount_invoiced` → header `total_prepayment_invoiced`
   - Sum all line `prepayment_amount_deducted` → header `total_prepayment_deducted`
   - Create header-level `PreaymentInstallmentDraft` from line drafts (sum amounts)
   - Migrate line `PreaymentLineInstallmentHistory` → header `PreaymentInstallmentHistory`

2. **Schema Changes**:
   - Add header fields to `Preayment` model
   - Add `PreaymentInstallmentDraft` (OneToOne with document)
   - Add `PreaymentInstallmentHistory` (ForeignKey to document)
   - Mark line deposit fields as deprecated (keep for historical data, make read-only)

3. **Backward Compatibility**:
   - Keep line fields in database (for historical data)
   - Make line deposit fields read-only in serializers
   - Display warnings for old documents with line-level deposits

### 8. Example Scenario

**User creates prepayment:**
1. Selects customer
2. Adds lines: Item A (qty: 10, price: 50,000) = 500,000 total
3. Enters deposit: 200,000 in header
4. Clicks "Add Installment" → enters 200,000
5. Preview shows: 200,000 (posted) + 200,000 (draft) = 400,000 preview

**Posting:**
- Creates posted invoice for 200,000
- Applies draft to total_prepayment
- Updates total_prepayment_invoiced to 200,000
- Creates history record

**Editing:**
- User can change line total from 500,000 → 300,000 ✅
- User cannot change line total from 500,000 → 190,000 ❌ (below posted 200,000)




