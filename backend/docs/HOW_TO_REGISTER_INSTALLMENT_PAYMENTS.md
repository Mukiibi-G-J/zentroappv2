# How to Register Installment Payments in Production

This guide explains how to register installment payments for Zentro Starter Pack orders from the Django Admin interface.

## Overview

- Each company can have **only one active ZentroStarterOrder** at a time
- Payments are registered as individual `ZentroStarterPayment` records
- The `amount_paid` field is **automatically calculated** from the sum of all confirmed payments
- Receipt numbers are **auto-generated** (STP-001, STP-002, etc.)
- PDF receipts are **automatically generated** when payments are confirmed

## Prerequisites

1. Access to Django Admin with superuser or staff permissions
2. A ZentroStarterOrder exists for the company (status: pending, paid, or active)

## Step-by-Step: Registering an Installment Payment

### Method 1: Using Inline Form in Order Page (Recommended)

1. **Navigate to Django Admin**
   - Go to: `http://your-domain.com/admin/`
   - Login with admin credentials

2. **Find the Order**
   - In the left sidebar, go to **COMPANY** → **Zentro Starter Orders**
   - Find and click on the order for the company (e.g., "Order 14 - jom2 - pending")
   - Or search by company name/email in the search box

3. **Scroll to Payment Section**
   - Scroll down to the bottom of the order edit page
   - Find the **"Zentro Starter Payments"** section (appears after all fieldsets)

4. **Add Payment**
   - You should see an empty payment form row
   - If not, click **"Add another Payment"** button
   - Fill in the following fields:

   **Required Fields:**
   - **Payment method**: Select from dropdown:
     - `mobile_money` - For mobile money payments
     - `cash` - For cash payments
     - `bank_transfer` - For bank transfer payments
   - **Amount**: Enter the installment amount (e.g., `200000.00` for 200,000 UGX)
   - **Payment date**: Select the date when payment was received
   - **is_confirmed**: ✓ **Check this box** (important - this confirms the payment)

   **Optional Fields (for Mobile Money):**
   - **Mobile money number**: Phone number used for payment (e.g., `0777123456`)
   - **Mobile money provider**: Provider name (e.g., `MTN`, `Airtel`)
   - **Mobile money reference**: Transaction reference number

   **Optional Fields:**
   - **Notes**: Any additional notes about the payment

   **Auto-Generated Fields (leave empty):**
   - **Receipt number**: Will be auto-generated (e.g., STP-001)
   - **Reference number**: Will be auto-generated

5. **Save**
   - Click **"SAVE"** at the bottom of the page
   - Or click **"Save and continue editing"** if you want to add more payments

### Method 2: Using Standalone Payment Form

1. **Navigate to Starter Pack Payments**
   - In the left sidebar, go to **COMPANY** → **Starter Pack Payments**
   - Click **"+ Add"** next to "Starter Pack Payments"

2. **Select Order**
   - **Order**: Select the ZentroStarterOrder from the dropdown
   - Fill in the payment details as described in Method 1

3. **Save**

## What Happens After Saving

When you save a confirmed payment (with `is_confirmed` checked):

1. ✅ **Receipt number is auto-generated** (e.g., STP-001, STP-002)
2. ✅ **Reference number is auto-generated** (e.g., PAY-ABC123XYZ)
3. ✅ **PDF receipt is automatically generated** and saved
4. ✅ **Order's `amount_paid` is automatically updated** (calculated from all confirmed payments)
5. ✅ **Order's `amount_remaining` is automatically updated**
6. ✅ **Order status updates to "active"** if this is the first payment
7. ✅ **Subscription is automatically activated** if this is the first payment
8. ✅ **Subscription dates are set** (1 year free period starts)

## Important Notes

### After Registering Payments

⚠️ **IMPORTANT**: After registering a payment, the user needs to **log out and log back in** for the changes to take effect. This is because:
- The JWT token contains starter pack status information
- The token is generated at login time
- A new login generates a fresh token with updated subscription status

**What to tell users:**
> "I've registered your payment. Please log out and log back in to see the updated status."

### Order Status Flow

- **pending** → Payment pending (no payments yet)
- **active** → First payment received, subscription activated
- **paid** → Order fully paid (all installments completed)
- **cancelled** → Order cancelled
- **expired** → Subscription expired

### Payment Status

- **pending** → Payment pending confirmation
- **completed** → Payment confirmed
- **processing** → Payment being processed
- **failed** → Payment failed
- **refunded** → Payment refunded

### Amount Calculation

- **`amount_paid`**: Automatically calculated from sum of all confirmed payments (property, not stored field)
- **`amount_remaining`**: `total_amount - amount_paid`
- **`total_amount`**: Total amount due for the starter pack (from offer price)

### Multiple Installments

You can register multiple payments for the same order:
- First payment: 200,000 UGX
- Second payment: 300,000 UGX
- Third payment: 300,000 UGX
- Total: 800,000 UGX (order fully paid)

Each payment:
- Gets its own receipt number
- Generates its own PDF receipt
- Updates the total `amount_paid` automatically

## Viewing Payments

### For a Specific Order

1. Go to **Zentro Starter Orders**
2. Click on the order
3. Scroll to **"Zentro Starter Payments"** section
4. View all payments in the inline table

### All Payments

1. Go to **COMPANY** → **Starter Pack Payments**
2. View all payments across all orders
3. Filter by:
   - Payment method
   - Confirmed status
   - Payment date
   - Order
   - Receipt number

## Troubleshooting

### "Receipt number is required" Error

**Solution**: This should not happen anymore. If it does:
- The field is now optional (blank=True, null=True)
- Receipt numbers are auto-generated in the `save()` method
- Try refreshing the page (Ctrl+F5)
- Ensure you're running the latest migrations

### Payment Not Showing in amount_paid

**Check**:
1. Is `is_confirmed` checked? (Required for payment to count)
2. Refresh the order page to see updated `amount_paid`
3. Check that payment was saved successfully

### User Still Redirected to Subscription Page

**Solution**:
1. User must **log out and log back in** to get fresh JWT token
2. Check that order status is "active" (not "pending")
3. Check that subscription was activated (has `subscription_start_date`)

### Multiple Orders for Same Company

**Solution**: Use the cleanup command:
```bash
python manage.py cleanup_duplicate_orders
```

This will:
- Keep the most recent order (or order with payments)
- Move payments from duplicate orders to the kept order
- Cancel duplicate orders
- Prevent future duplicates

## Cleanup Commands

### Clean Up Duplicate Orders

```bash
# Preview changes (dry run)
python manage.py cleanup_duplicate_orders --dry-run

# Apply cleanup
python manage.py cleanup_duplicate_orders

# Delete duplicates instead of cancelling
python manage.py cleanup_duplicate_orders --delete-duplicates

# Keep oldest order instead of newest
python manage.py cleanup_duplicate_orders --keep-oldest
```

### Update Orders to Pending Status

If orders were marked as paid/active but have no actual payments:

```bash
python manage.py update_orders_to_pending
```

## API Endpoint (Alternative Method)

For programmatic payment registration, use the API endpoint:

**Endpoint**: `POST /api/company/starter-register-payment/`

**Request Body**:
```json
{
  "order_id": 14,
  "amount": 200000.00,
  "payment_method": "mobile_money",
  "mobile_money_number": "0777123456",
  "mobile_money_provider": "MTN",
  "mobile_money_reference": "MM123456789",
  "notes": "First installment payment"
}
```

**Response**:
```json
{
  "success": true,
  "payment_id": 1,
  "receipt_number": "STP-001",
  "amount_paid": 200000.00,
  "total_amount": 800000.00,
  "amount_remaining": 600000.00,
  "message": "Payment registered successfully"
}
```

## Production Deployment Checklist

When deploying to production, ensure:

1. ✅ **Migrations are applied**:
   ```bash
   python manage.py migrate company
   ```

2. ✅ **Clean up duplicate orders** (if any):
   ```bash
   python manage.py cleanup_duplicate_orders --dry-run  # Preview
   python manage.py cleanup_duplicate_orders  # Apply
   ```

3. ✅ **Test payment registration**:
   - Register a test payment
   - Verify receipt is generated
   - Verify order status updates
   - Verify subscription activates

4. ✅ **User communication**:
   - Inform users they need to log out/in after payment registration
   - Provide receipt PDFs to customers

## Security Notes

- Only authorized staff should have access to Django Admin
- Payment confirmation (`is_confirmed`) should be verified before checking
- Receipt numbers are unique and sequential
- All payment records are auditable (created_at, received_by, confirmed_by)

## Related Documentation

- [Partial Payment Implementation Guide](./PARTIAL_PAYMENT_IMPLEMENTATION.md)
- [How to Register Payments](./HOW_TO_REGISTER_PAYMENTS.md)
- [Starter Pack System Overview](../README.md)

## Support

If you encounter issues:
1. Check the Django Admin logs
2. Verify migrations are applied
3. Check order and payment records in database
4. Ensure user logs out/in after payment registration
5. Contact development team with specific error messages




