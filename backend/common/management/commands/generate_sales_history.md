# Sales History Generation Plan

## Overview

Generate sales records for testing the sales history feature with date filtering.

## Specifications

### Dates

- **Start Date**: November 3, 2025
- **End Date**: November 7, 2025
- **Total Days**: 5 days

### Sales Per Day

- **Varying sales per day** (10, 12, 18, 20, 15)
- **Total Sales**: 75 sales records

### Date Distribution

- November 3, 2025: 10 sales
- November 4, 2025: 12 sales
- November 5, 2025: 18 sales
- November 6, 2025: 20 sales
- November 7, 2025: 15 sales

## Implementation Plan

### Step 1: Query Available Resources

1. Get items with stock available (already checked - 99 items available)
2. Get "General" customer specifically (not random)
3. Get payment methods (need to query)
4. Get default location
5. Get a user for posting

### Step 2: Create Sales Invoices

For each day (Nov 3-7, 2025) with varying counts:

1. Create SalesInvoice records (10, 12, 18, 20, 15 respectively) with:
   - "General" customer (fixed, not random)
   - Random payment method
   - Date set to the specific day (document_date, posting_date, vat_date, due_date)
   - Status: "Open"
   - Random items (1-3 items per invoice) with quantities that don't exceed stock
   - Calculate total_amount from lines
   - Set amount_received = total_amount (for cash payments)
   - Set change_amount = 0

### Step 3: Post Sales Invoices

For each created invoice:

1. Use the SalesInvoicePostingProcessor to post the invoice
2. This will:
   - Reduce inventory
   - Create GL entries
   - Create customer ledger entries
   - Update invoice status to "Posted"

### Step 4: Verification and Totals

After generation:

1. Count sales per day to verify distribution
2. Calculate total sales amount per day using:
   ```python
   from django.db.models import Sum, Count
   SalesInvoice.objects.filter(
       posting_date=date,
       status="Posted"
   ).aggregate(
       count=Count('id'),
       total_amount=Sum('total_amount')
   )
   ```
3. Display summary showing:
   - Number of sales per day
   - Total amount per day
   - Average per sale
   - Grand total across all days
4. Verify all invoices are posted
5. Check inventory was reduced correctly

## Technical Details

### Items Selection

- Use items from the top 30 items with stock
- Randomly select 1-3 items per invoice
- Quantity per item: 1-5 units (ensure stock is available)
- Use default unit of measure (PCS)

### Customer Selection

- Use "General" customer specifically (searches for customer with "general" in name)
- Fallback to first available customer if "General" not found

### Payment Method

- Randomly select from available payment methods
- Default to first payment method if none exist

### Location

- Use first available location or create default

### User

- Use first active user or superuser for posting

## Expected Results

- 75 posted sales invoices
- 15 invoices per day from Nov 3-7, 2025
- All invoices with status "Posted"
- Inventory reduced appropriately
- Sales history filterable by date range
