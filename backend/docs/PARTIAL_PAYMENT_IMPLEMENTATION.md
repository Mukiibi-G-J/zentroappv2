# Partial Payment Implementation for Zentro Starter Packs

## Overview

This document describes the implementation of partial payment support for Zentro Starter Pack orders. This allows companies to pay for starter packs in installments, with manual payment tracking through the admin interface.

## Problem Statement

Previously, when a user selected a starter pack plan, the system would create an order with `payment_status="completed"` and `status="paid"` even if no actual payment was made. This caused issues when tracking partial payments manually.

## Solution

The system now creates orders with `status="pending"` and `payment_status="pending"` when a plan is selected, allowing for manual payment registration through the admin interface.

## Key Changes

### Backend Changes

#### 1. Updated `create_starter_order` Endpoint
- **File**: `zentro-backend/company/views.py`
- **Changes**:
  - Now accepts `schema_name` (for logged-in users) OR `company_email`
  - Creates order with `status="pending"` and `payment_status="pending"`
  - Sets `total_amount = offer.device_price` (e.g., 800,000 UGX)
  - Sets `amount_paid = 0`
  - Prevents duplicate orders for the same offer

#### 2. Updated `company_overview` API
- **File**: `zentro-backend/company/views.py`
- **Changes**:
  - Includes "pending" orders in starter pack query
  - Returns `total_amount`, `amount_paid`, and `amount_remaining` in response

#### 3. Updated `register_manual_payment` Endpoint
- **File**: `zentro-backend/company/views.py`
- **Changes**:
  - Activates subscription when first payment is received
  - Refreshes order to get updated `amount_paid`
  - Returns payment summary with amounts

### Frontend Changes

#### 1. Subscription Page
- **File**: `zentro-frontend/src/views/Subscription/SubscriptionPage.tsx`
- **Changes**:
  - Changed from creating payment intent to creating pending order
  - Redirects to company page after order creation

#### 2. Company Page
- **File**: `zentro-frontend/src/views/company/Company.tsx`
- **Changes**:
  - Displays `total_amount`, `amount_paid`, and `amount_remaining`
  - Shows payment breakdown instead of single payment amount

## Database Model Fields

### ZentroStarterOrder
- `total_amount`: Total amount due for the starter pack (e.g., 800,000)
- `amount_paid`: Total amount paid so far (calculated from ZentroStarterPayment records)
- `amount_remaining`: Calculated as `total_amount - amount_paid`
- `status`: Order status ("pending", "paid", "active", "free_period_ended", "expired", "cancelled")
- `payment_status`: Payment status ("pending", "processing", "completed", "failed", "refunded")

## Workflow

1. **Company Creation**: User creates company account on landing page
2. **Plan Selection**: User selects starter pack plan on subscription page
   - System creates order with `status="pending"`, `payment_status="pending"`
   - `total_amount` = offer price (e.g., 800,000)
   - `amount_paid` = 0
3. **Manual Payment Registration**: Admin records partial payment via `register_manual_payment` API
   - Creates `ZentroStarterPayment` record
   - Updates order `amount_paid`
   - Activates subscription if this is the first payment
4. **Payment Tracking**: Company page shows:
   - Total Amount: 800,000 UGX
   - Amount Paid: 200,000 UGX (in green)
   - Amount Remaining: 600,000 UGX (in orange)

## API Endpoints

### Create Starter Order
```
POST /api/company/starter-order/create/
Body: {
  "schema_name": "company_name" OR "company_email": "email@example.com",
  "offer_id": 1,
  "delivery_address": "",
  "phone_number": ""
}
Response: {
  "success": true,
  "order_id": 123,
  "message": "Order created successfully",
  "order_summary": {...}
}
```

### Register Manual Payment
```
POST /api/company/starter-register-payment/
Body: {
  "order_id": 123,
  "amount": "200000.00",
  "payment_method": "mobile_money" | "cash" | "bank_transfer",
  "mobile_money_number": "0777123456" (if mobile_money),
  "mobile_money_provider": "MTN" | "AIRTEL" (if mobile_money),
  "notes": "Partial payment - first installment"
}
Response: {
  "success": true,
  "payment_id": 456,
  "receipt_number": "STP-001",
  "amount_paid": 200000.00,
  "total_amount": 800000.00,
  "amount_remaining": 600000.00,
  "message": "Payment registered successfully"
}
```

## Migration Steps for Production

### Step 1: Deploy Code Changes
Deploy all code changes to production environment.

### Step 2: Update Existing Orders
Run the management command to update existing orders to pending status:

**For single tenant:**
```bash
python manage.py update_orders_to_pending --schema=public
```

**For all tenants:**
```bash
python manage.py migrate_schemas --command=update_orders_to_pending
```

**Dry run first (recommended):**
```bash
python manage.py update_orders_to_pending --schema=public --dry-run
```

This will:
- Find all orders with `status="paid"` or `status="active"` but `amount_paid=0`
- Exclude orders that have ZentroStarterPayment records
- Update them to `status="pending"` and `payment_status="pending"`
- Preserve orders that already have payments recorded

### Step 3: Verify Data
After running the command, verify that orders are properly updated by checking:
- Orders with `status="pending"` and `payment_status="pending"`
- Orders that had payments should still show `status="active"` or `status="paid"`

## Testing Checklist

- [ ] Create company account
- [ ] Select starter pack plan on subscription page
- [ ] Verify order is created with pending status
- [ ] Record partial payment via admin/API
- [ ] Verify subscription is activated after first payment
- [ ] Check company page shows correct amounts (total, paid, remaining)
- [ ] Record additional payments
- [ ] Verify amounts update correctly

## Notes

- Orders are automatically activated when first payment is received
- Subscription start date is set when first payment activates the order
- Free period (12 months) starts from subscription activation date
- Multiple payments can be recorded for the same order
- Payment amount cannot exceed remaining balance
- Receipt PDFs are automatically generated when payments are saved
- Receipts are saved to `media/receipts/starter_pack/receipt_STP_XXX.pdf`

## Registering Payments

See [HOW_TO_REGISTER_PAYMENTS.md](HOW_TO_REGISTER_PAYMENTS.md) for detailed instructions on:
- Registering payments via Django Admin
- Using the API endpoint to register payments
- Generating and downloading receipts
- Payment tracking and viewing

