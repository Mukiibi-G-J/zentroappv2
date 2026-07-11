# PaymentJournal Model

The PaymentJournal model is a comprehensive payment tracking system that supports generic foreign key relationships to Customer, Vendor, and GLAccount models. It provides flexible payment journal entries with proper status tracking and application management.

## Features

- **Generic Foreign Key Support**: References Customer, Vendor, and GLAccount models
- **Multiple Document Types**: Payment, Invoice, Credit Memo, Finance Charge Memo, Reminder, Refund
- **Status Tracking**: Open, Posted, Void, Cancelled
- **Application Status**: Applied, Unapplied, Partially Applied
- **Comprehensive Validation**: Ensures data integrity and proper relationships
- **REST API Support**: Full CRUD operations with filtering and search
- **Admin Interface**: Django admin integration with optimized display

## Model Fields

### Basic Document Information

- `posting_date` (DateField): The date when the payment is posted
- `document_type` (CharField): Type of document (see DocumentType enum)
- `document_no` (CharField): Unique document number
- `external_document_no` (CharField, optional): External reference number
- `description` (TextField, optional): Description of the payment

### Account Information (Generic Foreign Key)

- `account_type` (CharField): Type of account (Customer, Vendor, GL)
- `account_content_type` (ForeignKey to ContentType): Content type for generic relationship
- `account_object_id` (PositiveIntegerField): Object ID for generic relationship
- `account_no` (GenericForeignKey): The actual account object

### Payment Information

- `payment_method` (ForeignKey to PaymentMethod): Method used for payment
- `amount` (DecimalField): Payment amount with validation

### Balancing Account Information (Generic Foreign Key)

- `bal_account_type` (CharField): Type of balancing account
- `bal_account_content_type` (ForeignKey to ContentType): Content type for balancing account
- `bal_account_object_id` (PositiveIntegerField): Object ID for balancing account
- `bal_account_no` (GenericForeignKey): The actual balancing account object

### Status and Application

- `status` (CharField): Payment status (see PaymentStatus enum)
- `application_status` (CharField): Application status (see ApplicationStatus enum)
- `applies_to_doc_type` (CharField, optional): Document type this payment applies to
- `applies_to_content_type` (ForeignKey to ContentType, optional): Content type of the document this payment applies to
- `applies_to_object_id` (PositiveIntegerField, optional): Object ID of the document this payment applies to
- `applies_to_doc` (GenericForeignKey, optional): Generic foreign key to the document this payment applies to (can reference Customer, Vendor, or any other model)

## Enums

### DocumentType

```python
class DocumentType(Enum):
    PAYMENT = "Payment"
    INVOICE = "Invoice"
    CREDIT_MEMO = "Credit Memo"
    FINANCE_CHARGE_MEMO = "Finance Charge Memo"
    REMINDER = "Reminder"
    REFUND = "Refund"
```

### AccountType

```python
class AccountType(Enum):
    CUSTOMER = "Customer"
    VENDOR = "Vendor"
    GL = "G/L Account"
```

### PaymentStatus

```python
class PaymentStatus(Enum):
    OPEN = "Open"
    POSTED = "Posted"
    VOID = "Void"
    CANCELLED = "Cancelled"
```

### ApplicationStatus

```python
class ApplicationStatus(Enum):
    APPLIED = "Applied"
    UNAPPLIED = "Unapplied"
    PARTIALLY_APPLIED = "Partially Applied"
```

## Usage Examples

### Creating a Customer Payment

```python
from payments.models import PaymentJournal
from payments.enums import DocumentType, AccountType
from django.contrib.contenttypes.models import ContentType

# Get content types
customer_content_type = ContentType.objects.get_for_model(Customer)
gl_content_type = ContentType.objects.get_for_model(G_LAccount)

# Create payment journal entry
payment_journal = PaymentJournal.objects.create(
    posting_date="2024-01-15",
    document_type=DocumentType.PAYMENT.value,
    document_no="PAY-001",
    account_type=AccountType.CUSTOMER.value,
    account_content_type=customer_content_type,
    account_object_id=customer.id,
    payment_method=payment_method,
    amount=Decimal("1000.00"),
    bal_account_type=AccountType.GL.value,
    bal_account_content_type=gl_content_type,
    bal_account_object_id=gl_account.no,
    description="Payment from customer"
)
```

### Creating a Vendor Payment

```python
payment_journal = PaymentJournal.objects.create(
    posting_date="2024-01-15",
    document_type=DocumentType.PAYMENT.value,
    document_no="PAY-002",
    account_type=AccountType.VENDOR.value,
    account_content_type=vendor_content_type,
    account_object_id=vendor.id,
    payment_method=payment_method,
    amount=Decimal("500.00"),
    bal_account_type=AccountType.GL.value,
    bal_account_content_type=gl_content_type,
    bal_account_object_id=gl_account.no,
    description="Payment to vendor"
)
```

### Creating a Refund

```python
payment_journal = PaymentJournal.objects.create(
    posting_date="2024-01-15",
    document_type=DocumentType.REFUND.value,
    document_no="REF-001",
    account_type=AccountType.CUSTOMER.value,
    account_content_type=customer_content_type,
    account_object_id=customer.id,
    payment_method=payment_method,
    amount=Decimal("200.00"),
    bal_account_type=AccountType.GL.value,
    bal_account_content_type=gl_content_type,
    bal_account_object_id=gl_account.no,
    description="Refund to customer"
)
```

### Applying a Payment to a Document

```python
from django.contrib.contenttypes.models import ContentType

# Get content type for the document you want to apply to
invoice_content_type = ContentType.objects.get_for_model(Invoice)

payment_journal.application_status = ApplicationStatus.APPLIED.value
payment_journal.applies_to_doc_type = "Invoice"
payment_journal.applies_to_content_type = invoice_content_type
payment_journal.applies_to_object_id = invoice.id
payment_journal.save()
```

## API Endpoints

### Base URL

```
/api/payments/payment-journal/
```

### Available Actions

- `GET /` - List payment journal entries
- `POST /` - Create new payment journal entry
- `GET /{id}/` - Retrieve specific payment journal entry
- `PUT /{id}/` - Update payment journal entry
- `DELETE /{id}/` - Delete payment journal entry
- `GET /summary/` - Get summary statistics
- `GET /by_account_type/?account_type=CUSTOMER` - Get entries by account type
- `GET /unapplied/` - Get unapplied entries
- `POST /{id}/apply/` - Apply payment to document
- `POST /{id}/unapply/` - Unapply payment

### Filtering Options

- `posting_date_from` - Filter by posting date from
- `posting_date_to` - Filter by posting date to
- `amount_min` - Filter by minimum amount
- `amount_max` - Filter by maximum amount
- `document_type` - Filter by document type
- `account_type` - Filter by account type
- `bal_account_type` - Filter by balancing account type
- `payment_method` - Filter by payment method
- `status` - Filter by payment status
- `application_status` - Filter by application status

### Search Fields

- `document_no` - Search by document number
- `external_document_no` - Search by external document number
- `description` - Search by description
- `applies_to_doc_type` - Search by applies to document type

## Validation Rules

1. **Account Information**: When `account_type` is specified, both `account_content_type` and `account_object_id` must be provided
2. **Balancing Account Information**: When `bal_account_type` is specified, both `bal_account_content_type` and `bal_account_object_id` must be provided
3. **Application Fields**: When `applies_to_doc_type` is specified, both `applies_to_content_type` and `applies_to_object_id` must be provided
4. **Amount Validation**: Amount must be greater than 0.01

## Properties

### account_name

Returns the name of the account (Customer name, Vendor name, or GL Account name)

### bal_account_name

Returns the name of the balancing account

### applies_to_doc_name

Returns the name of the document this payment applies to

## Database Indexes

The model includes optimized indexes for:

- `posting_date`
- `document_no`
- `account_type`
- `bal_account_type`
- `status`
- `application_status`
- Generic foreign key combinations:
  - `(account_content_type, account_object_id)` - For account lookups
  - `(bal_account_content_type, bal_account_object_id)` - For balancing account lookups
  - `(applies_to_content_type, applies_to_object_id)` - For applies to document lookups

## Admin Interface

The Django admin interface provides:

- Comprehensive list display with all key fields
- Filtering by date, document type, account type, status, etc.
- Search functionality
- Organized fieldsets for better data entry
- Read-only computed fields (account names)
- Optimized queryset with select_related for performance

## Testing

The model includes comprehensive tests covering:

- Creating entries with different account types
- Validation of required fields
- Generic foreign key relationships
- Status and application management
- String representation

Run tests with:

```bash
python manage.py test payments.tests.PaymentJournalModelTest
```

## Migration History

- `0001_initial.py` - Initial model creation
- `0002_remove_paymentjournal_payments_pa_applied_3e10cb_idx_and_more.py` - Updated to use enums and new status fields
- `0003_remove_paymentjournal_applies_to_doc_no_and_more.py` - Updated enum values to title case and converted applies_to_doc_no to GenericForeignKey

## Dependencies

- Django ContentTypes framework
- Django REST Framework
- Django Filter
- Financials app (for PaymentMethod)
- Sales app (for Customer)
- Purchases app (for Vendor)
- Utils app (for BaseModel)
