# How to Register Installment Payments and Generate Receipts

## Overview

This guide explains how to register partial payments for Zentro Starter Pack orders and generate receipts for clients.

## Methods to Register Payments

### Method 1: Django Admin Interface (Recommended for Manual Entry)

#### Step 1: Navigate to Order

1. Log into Django Admin
2. Go to **Company → Zentro Starter Orders**
3. Find and click on the order you want to register a payment for

#### Step 2: Add Payment via Inline

1. In the order detail page, scroll down to the **Zentro Starter Payments** section
2. Click **"Add another Zentro Starter Payment"** or use the empty form row
3. Fill in the payment details:
   - **Payment Method**: Select from dropdown (mobile_money, cash, bank_transfer)
   - **Amount**: Enter payment amount (e.g., 200000.00)
   - **Payment Date**: Select the date payment was received
   - **Mobile Money Number**: (if payment_method is mobile_money)
   - **Mobile Money Provider**: MTN or AIRTEL (if mobile_money)
   - **Mobile Money Reference**: Transaction reference (if mobile_money)
   - **Received By**: Automatically set to current admin user
   - **Is Confirmed**: Check this box (default: checked)
   - **Notes**: Optional notes about the payment
4. Click **Save** at the bottom of the page

#### What Happens Automatically:

- Receipt number is automatically generated (STP-001, STP-002, etc.)
- Reference number is automatically generated
- Order `amount_paid` is updated
- Subscription is activated if this is the first payment
- PDF receipt is automatically generated and saved to media/receipts/starter_pack/
- Receipt path is stored in `invoice_pdf_path` field

#### Step 3: View/Download Receipt

1. After saving, the payment will appear in the payments list
2. Click on the payment to view details
3. The `invoice_pdf_path` field shows where the PDF is stored
4. You can download it from: `http://your-domain.com/media/receipts/starter_pack/receipt_STP_001.pdf`

Or use the API endpoint to download:
```
GET /api/company/starter-payment-receipt/<payment_id>/
```

### Method 2: API Endpoint (For Programmatic Access)

#### Endpoint

```
POST /api/company/starter-register-payment/
```

#### Authentication

Requires authentication token in header:
```
Authorization: Bearer <your_token>
```

#### Request Body

```json
{
  "order_id": 123,
  "amount": "200000.00",
  "payment_method": "mobile_money",
  "mobile_money_number": "0777123456",
  "mobile_money_provider": "MTN",
  "mobile_money_reference": "MM123456789",
  "notes": "Partial payment - first installment"
}
```

**Payment Method Options:**
- `"mobile_money"` - Requires `mobile_money_number`, `mobile_money_provider`, and optionally `mobile_money_reference`
- `"cash"` - No additional fields required
- `"bank_transfer"` - No additional fields required (can add reference in notes)

#### Response

```json
{
  "success": true,
  "payment_id": 456,
  "receipt_number": "STP-001",
  "amount_paid": 200000.00,
  "total_amount": 800000.00,
  "amount_remaining": 600000.00,
  "message": "Payment registered successfully"
}
```

#### Example using cURL

```bash
curl -X POST http://your-domain.com/api/company/starter-register-payment/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "order_id": 123,
    "amount": "200000.00",
    "payment_method": "cash",
    "notes": "First installment payment"
  }'
```

### Method 3: Python Shell (For Scripting)

```python
from company.models import ZentroStarterOrder, ZentroStarterPayment
from django.utils import timezone
from decimal import Decimal
from authentication.models import CustomUser

# Get the order
order = ZentroStarterOrder.objects.get(id=123)

# Get admin user (or the user receiving the payment)
admin_user = CustomUser.objects.get(username='admin')

# Create payment
payment = ZentroStarterPayment.objects.create(
    order=order,
    payment_method='mobile_money',
    amount=Decimal('200000.00'),
    payment_date=timezone.now(),
    received_by=admin_user,
    is_confirmed=True,
    confirmed_by=admin_user,
    confirmed_at=timezone.now(),
    mobile_money_number='0777123456',
    mobile_money_provider='MTN',
    mobile_money_reference='MM123456789',
    notes='Partial payment - first installment'
)

# Receipt PDF is automatically generated in payment.save()
print(f"Receipt number: {payment.receipt_number}")
print(f"Receipt path: {payment.invoice_pdf_path}")
```

## Receipt Generation

### Automatic Generation

Receipts are **automatically generated** when:
- A payment is saved with `is_confirmed=True`
- The payment is created through admin interface or API
- Receipt PDF is saved to: `media/receipts/starter_pack/receipt_STP_001.pdf`

### Receipt Content

The receipt PDF includes:
- Receipt number (STP-001, STP-002, etc.)
- Company name and details
- Payment amount
- Payment method
- Payment date
- Order total amount
- Amount paid so far
- Amount remaining
- Payment reference number

### Downloading Receipts

#### Via Admin Interface

1. Go to **Company → Zentro Starter Payments**
2. Find the payment
3. View the `invoice_pdf_path` field
4. Access the PDF at: `http://your-domain.com/media/{invoice_pdf_path}`

#### Via API

```
GET /api/company/starter-payment-receipt/<payment_id>/
```

Returns PDF file for download/view in browser.

#### Resend Receipt Email (Future Feature)

```
POST /api/company/starter-resend-receipt/
Body: {"payment_id": 456}
```

Note: Email sending is not yet implemented (TODO).

## Payment Tracking

### View All Payments for an Order

#### Via Admin Interface

1. Open the Zentro Starter Order
2. View payments in the **Zentro Starter Payments** inline section
3. Payments are listed with receipt numbers, amounts, and dates

#### Via API

```
GET /api/company/starter-order-payments/<order_id>/
```

Response:
```json
{
  "order_id": 123,
  "total_amount": 800000.00,
  "amount_paid": 200000.00,
  "amount_remaining": 600000.00,
  "payments": [
    {
      "id": 456,
      "receipt_number": "STP-001",
      "amount": 200000.00,
      "payment_method": "mobile_money",
      "payment_date": "2024-01-15T10:30:00Z",
      "is_confirmed": true,
      "receipt_sent": false,
      "mobile_money_number": "0777123456",
      "mobile_money_provider": "MTN",
      "mobile_money_reference": "MM123456789",
      "notes": "First installment"
    }
  ]
}
```

## Important Notes

1. **Receipt Numbers**: Automatically generated, unique per order (STP-001, STP-002, etc.)
2. **Subscription Activation**: Subscription is automatically activated when first payment is received
3. **Amount Validation**: Payment amount cannot exceed `amount_remaining` on the order
4. **Order Status**: Order status updates automatically based on payments:
   - `pending` → `active` (after first payment)
   - `active` → (remains active while payments are made)
5. **PDF Generation**: Receipts are generated automatically, stored in `media/receipts/starter_pack/`
6. **Cannot Delete Payments**: Payments can be marked as unconfirmed, but not deleted (for audit trail)

## Troubleshooting

### Receipt PDF Not Generated

1. Check that `is_confirmed=True` when creating payment
2. Check Django logs for PDF generation errors
3. Verify ReportLab is installed: `pip install reportlab`
4. Check media directory permissions: `media/receipts/starter_pack/` must be writable

### Payment Amount Exceeds Remaining Balance

- Ensure payment amount is less than or equal to `amount_remaining`
- Check order `total_amount` and `amount_paid` values

### Subscription Not Activating

- Verify payment has `is_confirmed=True`
- Check that this is the first payment (`amount_paid` was 0 before)
- Check order `subscription_start_date` is set after payment




