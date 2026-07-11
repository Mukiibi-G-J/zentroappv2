# Zentro Starter Pack Installment Payment System - Architecture Diagram

## 1. Database Model Relationships

```
┌─────────────────────────────────────────────────────────────────┐
│                    ZentroStarterOffer                          │
├─────────────────────────────────────────────────────────────────┤
│ • payment_plan (one_time/installments)                        │
│ • allows_installments (Boolean)                                │
│ • default_installment_count                                    │
│ • device_price (800,000 UGX)                                   │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             │ 1:N
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                  ZentroStarterOrder                            │
├─────────────────────────────────────────────────────────────────┤
│ • payment_plan (one_time/installments)                        │
│ • total_amount (800,000 UGX)                                   │
│ • amount_paid (Running total)                                  │
│ • amount_remaining (Calculated)                                │
│ • installment_schedule (JSON)                                  │
│   └─ {"installments": [                                        │
│        {"amount": 100000, "due_date": "2024-02-01", ...},     │
│        {"amount": 200000, "due_date": "2024-03-01", ...}      │
│      ]}                                                        │
│ • stripe_subscription_id (For auto-charge)                    │
└─────────────────┬──────────────────────┬───────────────────────┘
                  │                      │
                  │ 1:N                  │ 1:N
                  │                      │
                  ▼                      ▼
┌────────────────────────────┐  ┌──────────────────────────────┐
│  ZentroStarterPayment      │  │ ZentroStarterInstallment     │
│                            │  │ Reminder                     │
├────────────────────────────┤  ├──────────────────────────────┤
│ • payment_method           │  │ • reminder_type              │
│   (stripe/mobile_money/    │  │ • scheduled_date             │
│    cash/bank_transfer)     │  │ • sent_at                    │
│ • amount                   │  │ • email_sent                 │
│ • receipt_number (STP-001) │  │ • sms_sent                   │
│ • reference_number         │  │                              │
│ • mobile_money_number      │  │                              │
│ • mobile_money_provider    │  │                              │
│ • invoice_pdf_path         │  │                              │
│ • is_confirmed             │  │                              │
│ • receipt_sent             │  │                              │
└────────────────────────────┘  └──────────────────────────────┘
```

## 2. Payment Flow Diagram

### Scenario A: Stripe Auto-Installments

```
User selects "Installment Plan"
         │
         ▼
┌────────────────────────────┐
│ Create Order with          │
│ payment_plan="installments"│
│ installment_schedule=[...] │
└────────────┬───────────────┘
             │
             ▼
┌────────────────────────────┐
│ Create Stripe Subscription │
│ (4 x 200,000 UGX/month)    │
└────────────┬───────────────┘
             │
             ▼
┌────────────────────────────┐
│ First Payment (200,000)    │
│ Auto-charged by Stripe     │
└────────────┬───────────────┘
             │
             ▼
┌────────────────────────────┐
│ Create ZentroStarterPayment│
│ - receipt_number: STP-001  │
│ - amount: 200,000          │
│ - is_confirmed: True       │
└────────────┬───────────────┘
             │
             ▼
┌────────────────────────────┐
│ Update Order:              │
│ - amount_paid: 200,000     │
│ - amount_remaining: 600,000│
│ - status: "active"         │
└────────────┬───────────────┘
             │
             ▼
┌────────────────────────────┐
│ Activate Subscription      │
│ (3 months free period)     │
└────────────┬───────────────┘
             │
             ▼
┌────────────────────────────┐
│ Generate Receipt PDF       │
│ (receipt_utils.py)         │
└────────────┬───────────────┘
             │
             ▼
┌────────────────────────────┐
│ Send Receipt Email         │
│ (TODO: Implement)          │
└────────────────────────────┘
             │
             ▼
┌────────────────────────────┐
│ Subsequent Payments        │
│ (Monthly auto-charge)      │
│ - Month 2: 200,000         │
│ - Month 3: 200,000         │
│ - Month 4: 200,000         │
└────────────────────────────┘
```

### Scenario B: Manual Payment (Mobile Money/Cash)

```
Admin/User receives payment
         │
         ▼
┌────────────────────────────┐
│ POST /api/company/         │
│ starter-register-payment/  │
│ {                          │
│   order_id: 123,           │
│   amount: 100000,          │
│   payment_method:          │
│     "mobile_money",        │
│   mobile_money_number:     │
│     "256700000000",        │
│   mobile_money_reference:  │
│     "MM123456789"          │
│ }                          │
└────────────┬───────────────┘
             │
             ▼
┌────────────────────────────┐
│ Validate Payment           │
│ - Check order exists       │
│ - Check amount <= remaining│
│ - Validate payment_method  │
└────────────┬───────────────┘
             │
             ▼
┌────────────────────────────┐
│ Create ZentroStarterPayment│
│ - receipt_number: STP-002  │
│ - amount: 100,000          │
│ - payment_method:          │
│   "mobile_money"           │
│ - received_by: admin_user  │
│ - is_confirmed: True       │
└────────────┬───────────────┘
             │
             ▼
┌────────────────────────────┐
│ Update Order               │
│ - amount_paid += 100,000   │
│ - amount_remaining -=      │
│   100,000                  │
└────────────┬───────────────┘
             │
             ▼
┌────────────────────────────┐
│ Generate Receipt PDF       │
│ - Auto-saved to disk       │
│ - Path stored in           │
│   invoice_pdf_path         │
└────────────┬───────────────┘
             │
             ▼
┌────────────────────────────┐
│ Return Response            │
│ {                          │
│   receipt_number: STP-002, │
│   amount_paid: 100000,     │
│   amount_remaining: 700000 │
│ }                          │
└────────────────────────────┘
```

## 3. Reminder System Flow

```
┌─────────────────────────────────────────────────────────────┐
│         Celery Beat (Daily 9:00 AM)                         │
│  send_installment_reminders() Task                          │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
         ┌─────────────────────────┐
         │ Get all orders with     │
         │ payment_plan=           │
         │ "installments"          │
         └────────────┬────────────┘
                      │
                      ▼
         ┌─────────────────────────┐
         │ For each order:         │
         │ - Read installment_     │
         │   schedule              │
         │ - Check pending         │
         │   installments          │
         └────────────┬────────────┘
                      │
          ┌───────────┴───────────┐
          │                       │
          ▼                       ▼
┌──────────────────┐    ┌──────────────────┐
│ Due in 3 days?   │    │ Due in 1 day?    │
│ (reminder_type:  │    │ (reminder_type:  │
│  "payment_due")  │    │  "overdue")      │
└────────┬─────────┘    └────────┬─────────┘
         │                       │
         │                       │
         └───────────┬───────────┘
                     │
                     ▼
         ┌─────────────────────────┐
         │ Create ZentroStarter    │
         │ InstallmentReminder     │
         │ - reminder_type         │
         │ - scheduled_date        │
         │ - notes                 │
         └────────────┬────────────┘
                      │
                      ▼
         ┌─────────────────────────┐
         │ Send Email Reminder     │
         │ (TODO: Implement)       │
         │ - Due date              │
         │ - Amount due            │
         │ - Payment link          │
         └─────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│         Celery Beat (Daily 2:00 PM)                         │
│  send_overdue_notices() Task                                │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
         ┌─────────────────────────┐
         │ Find orders with        │
         │ overdue installments    │
         │ (due_date < today)      │
         └────────────┬────────────┘
                      │
                      ▼
         ┌─────────────────────────┐
         │ Create Overdue Notice   │
         │ (reminder_type:         │
         │  "overdue")             │
         └────────────┬────────────┘
                      │
                      ▼
         ┌─────────────────────────┐
         │ Send Overdue Email      │
         │ - Amount overdue        │
         │ - Days overdue          │
         │ - Consequences          │
         └─────────────────────────┘
```

## 4. Receipt Generation Flow

```
Payment Created/Saved
         │
         ▼
┌────────────────────────────┐
│ ZentroStarterPayment.save()│
│ Auto-triggers receipt gen  │
└────────────┬───────────────┘
             │
             ▼
┌────────────────────────────┐
│ generate_receipt_pdf()     │
│ (receipt_utils.py)         │
└────────────┬───────────────┘
             │
             ▼
┌────────────────────────────┐
│ Generate PDF using         │
│ ReportLab:                 │
│ - Company header           │
│ - Receipt number           │
│ - Payment details          │
│ - Amount paid              │
│ - Amount remaining         │
│ - Payment method           │
│ - Footer                   │
└────────────┬───────────────┘
             │
             ▼
┌────────────────────────────┐
│ Save PDF to:               │
│ media/receipts/            │
│   starter_pack/            │
│   receipt_STP-001.pdf      │
└────────────┬───────────────┘
             │
             ▼
┌────────────────────────────┐
│ Update payment:            │
│ invoice_pdf_path =         │
│ "receipts/starter_pack/    │
│  receipt_STP-001.pdf"      │
└────────────┬───────────────┘
             │
             ▼
┌────────────────────────────┐
│ Send Receipt Email         │
│ (Optional - TODO)          │
│ - Attach PDF               │
│ - Payment summary          │
└────────────────────────────┘

Alternative: Manual Download
         │
         ▼
┌────────────────────────────┐
│ GET /api/company/          │
│ starter-payment-receipt/   │
│ <payment_id>/              │
└────────────┬───────────────┘
             │
             ▼
┌────────────────────────────┐
│ Check if PDF exists        │
│ If not, generate it        │
└────────────┬───────────────┘
             │
             ▼
┌────────────────────────────┐
│ Return HttpResponse        │
│ (PDF file)                 │
│ Content-Type:              │
│ application/pdf            │
└────────────────────────────┘
```

## 5. Admin Interface Flow

```
Admin Login
    │
    ▼
┌─────────────────────────────┐
│ Django Admin                │
│ - Zentro Starter Orders     │
│ - Zentro Starter Payments   │
│ - Installment Reminders     │
└────────────┬────────────────┘
             │
    ┌────────┴────────┐
    │                 │
    ▼                 ▼
┌──────────┐    ┌──────────┐
│ View     │    │ View     │
│ Order    │    │ Payment  │
│ Details  │    │ List     │
└────┬─────┘    └────┬─────┘
     │               │
     │               │
     ▼               ▼
┌─────────────────────────────┐
│ Order Detail Page           │
│ - Payment Plan Info         │
│ - Total/Paid/Remaining      │
│ - Installment Schedule      │
│ - Payments Inline           │
│   (List all payments)       │
│ - Actions:                  │
│   * Register Payment        │
│   * View Receipts           │
└─────────────────────────────┘

┌─────────────────────────────┐
│ Payment Detail Page         │
│ - Receipt Number            │
│ - Amount & Method           │
│ - Payment Date              │
│ - Mobile Money Details      │
│ - Receipt PDF Link          │
│ - Actions:                  │
│   * Resend Receipt Email    │
│   * Mark Confirmed/         │
│     Unconfirmed             │
│   * Download Receipt        │
└─────────────────────────────┘
```

## 6. API Endpoints Overview

```
┌──────────────────────────────────────────────────────────────┐
│                    API Endpoints                             │
└──────────────────────────────────────────────────────────────┘

POST   /api/company/starter-register-payment/
       │
       └─> Register manual payment (Mobile Money/Cash)
           Input: order_id, amount, payment_method, details
           Output: receipt_number, amount_paid, amount_remaining

GET    /api/company/starter-payment-receipt/<payment_id>/
       │
       └─> Download receipt PDF
           Output: PDF file

POST   /api/company/starter-resend-receipt/
       │
       └─> Resend receipt email
           Input: payment_id
           Output: success message

GET    /api/company/starter-order-payments/<order_id>/
       │
       └─> Get all payments for an order
           Output: payments list, totals

Existing Endpoints (Modified):
POST   /api/company/starter-payment-intent/
       └─> Create Stripe payment intent
           (Can be used for installment first payment)

POST   /api/company/verify-payment-unified/
       └─> Verify payment and create order
           (Can create ZentroStarterPayment records)
```

## 7. Complete System Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                        User/Frontend                         │
└────────────────────┬─────────────────────────────────────────┘
                     │
                     │ HTTP Requests
                     │
                     ▼
┌──────────────────────────────────────────────────────────────┐
│                      Django Backend                          │
│  ┌────────────────────────────────────────────────────────┐  │
│  │                    API Views                           │  │
│  │  - register_manual_payment()                           │  │
│  │  - get_payment_receipt()                               │  │
│  │  - resend_receipt_email()                              │  │
│  │  - get_order_payments()                                │  │
│  └──────────────────┬─────────────────────────────────────┘  │
│                     │                                         │
│  ┌──────────────────▼─────────────────────────────────────┐  │
│  │                  Models                                 │  │
│  │  - ZentroStarterOrder                                  │  │
│  │  - ZentroStarterPayment                                │  │
│  │  - ZentroStarterInstallmentReminder                    │  │
│  └──────────────────┬─────────────────────────────────────┘  │
│                     │                                         │
│  ┌──────────────────▼─────────────────────────────────────┐  │
│  │              Receipt Utils                              │  │
│  │  - generate_receipt_pdf()                              │  │
│  │  - get_receipt_http_response()                         │  │
│  └────────────────────────────────────────────────────────┘  │
└────────────────────┬─────────────────────────────────────────┘
                     │
                     │
        ┌────────────┴────────────┐
        │                         │
        ▼                         ▼
┌──────────────┐         ┌──────────────┐
│   Stripe     │         │  Celery Beat │
│  (Auto-charge│         │  (Scheduled) │
│   payments)  │         │              │
└──────────────┘         └──────┬───────┘
                                │
                ┌───────────────┼───────────────┐
                │               │               │
                ▼               ▼               ▼
    ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
    │  send_       │  │  send_       │  │  generate_   │
    │  installment │  │  overdue     │  │  pending_    │
    │  reminders() │  │  notices()   │  │  receipts()  │
    └──────────────┘  └──────────────┘  └──────────────┘
                                │
                                ▼
                    ┌──────────────────┐
                    │  Email Service   │
                    │  (TODO:          │
                    │   Implement)     │
                    └──────────────────┘
```

## Key Features Summary

✅ **Flexible Installments**: Variable amounts per installment
✅ **Multiple Payment Methods**: Stripe, Mobile Money, Cash, Bank Transfer
✅ **Admin Payment Registration**: Staff can register manual payments
✅ **Automatic Receipt Generation**: PDF receipts created automatically
✅ **Payment Tracking**: Each payment has unique receipt number
✅ **Reminder System**: Framework for sending payment reminders
✅ **Subscription Activation**: Activates after first payment
✅ **Payment History**: Complete audit trail of all payments




