# Expense Management System

## Overview

The Expense Management System is designed to handle expense recording and posting with automatic G/L account mapping. It follows a similar pattern to the Payment system but is specifically tailored for expense transactions.

## Key Features

### 🔧 **Automatic G/L Account Mapping**

- Expense types automatically map to specific G/L accounts
- No manual G/L account selection required
- Configurable mapping in `ExpenseType.get_gl_account_mapping()`

### 📊 **Preview Posting**

- Preview journal entries before posting
- Shows debit and credit entries that will be created
- Validates G/L accounts before posting

### ✅ **Final Posting**

- Creates actual G/L entries when posted
- Debits expense account, credits Cash/Bank account
- Updates expense status to "Posted"

### 🔄 **Void Functionality**

- Void posted expenses with reversing entries
- Maintains audit trail
- Updates expense status to "Void"

## Models

### Expense Model

```python
class Expense(BaseModel):
    # Basic Document Information
    document_no = models.CharField(max_length=50, unique=True)
    posting_date = models.DateField()
    document_type = models.CharField(choices=ExpenseDocumentType.choices())
    external_document_no = models.CharField(max_length=50)

    # Expense Information
    expense_type = models.CharField(choices=ExpenseType.choices())
    description = models.TextField()
    amount = models.IntegerField(validators=[MinValueValidator(1)])

    # Payment Method
    payment_method = models.ForeignKey(PaymentMethod)

    # Status
    status = models.CharField(choices=ExpenseStatus.choices())

    # G/L Accounts (auto-determined)
    gl_account = models.ForeignKey(G_LAccount)  # Expense account
    balancing_account = models.ForeignKey(G_LAccount)  # Cash/Bank account

    # Posted Information
    posted_at = models.DateTimeField()
    posted_by = models.ForeignKey(CustomUser)
```

## Expense Types and G/L Account Mapping

| Expense Type    | G/L Account No | G/L Account Name        |
| --------------- | -------------- | ----------------------- |
| Office Supplies | 6100           | Office Supplies         |
| Utilities       | 6101           | Utilities               |
| Rent            | 6102           | Rent Expense            |
| Salary          | 6103           | Salaries and Wages      |
| Advertising     | 6104           | Advertising             |
| Travel          | 6105           | Travel Expense          |
| Meals           | 6106           | Meals and Entertainment |
| Insurance       | 6107           | Insurance               |
| Maintenance     | 6108           | Maintenance and Repairs |
| Legal Fees      | 6109           | Legal Fees              |
| Accounting Fees | 6112           | Accounting Fees         |
| Bank Charges    | 6113           | Bank Charges            |
| Interest        | 6114           | Interest Expense        |
| Depreciation    | 6115           | Depreciation            |
| Other           | 6116           | Other Expenses          |

## API Endpoints

### Base URL: `/api/expenses/`

#### CRUD Operations

- `GET /api/expenses/` - List expenses
- `POST /api/expenses/` - Create expense
- `GET /api/expenses/{id}/` - Get expense details
- `PUT /api/expenses/{id}/` - Update expense
- `DELETE /api/expenses/{id}/` - Delete expense

#### Special Actions

- `GET /api/expenses/{id}/preview_posting/` - Preview posting entries
- `POST /api/expenses/{id}/post_expense/` - Post expense to G/L

#### Utility Endpoints

- `GET /api/expenses/expense_types/` - Get expense types with G/L mappings
- `GET /api/expenses/payment_methods/` - Get available payment methods
- `GET /api/expenses/dashboard_summary/` - Get dashboard statistics
- `GET /api/expenses/expense_report/` - Generate expense report

## Usage Examples

### Creating an Expense

```python
# POST /api/expenses/
{
    "posting_date": "2024-01-15",
    "expense_type": "Office Supplies",
    "description": "Purchase of office stationery",
    "amount": 50000,
    "payment_method": 1,
    "external_document_no": "INV-001"
}
```

### Preview Posting

```python
# GET /api/expenses/1/preview_posting/
{
    "expense_id": 1,
    "document_no": "EXP-000001",
    "posting_date": "2024-01-15",
    "description": "Purchase of office stationery",
    "amount": 50000,
    "expense_type": "Office Supplies",
    "payment_method": "Cash",
    "debit_entry": {
        "gl_account": "6100",
        "gl_account_name": "Office Supplies",
        "description": "Expense: Purchase of office stationery",
        "amount": 50000,
        "type": "debit"
    },
    "credit_entry": {
        "gl_account": "1000",
        "gl_account_name": "Cash",
        "description": "Payment for: Purchase of office stationery",
        "amount": 50000,
        "type": "credit"
    }
}
```

### Posting an Expense

```python
# POST /api/expenses/1/post_expense/
{
    "expense_id": 1,
    "success": true,
    "message": "Expense EXP-000001 posted successfully",
    "posted_entries": [
        {
            "id": 123,
            "gl_account": "6100",
            "gl_account_name": "Office Supplies",
            "amount": 50000,
            "description": "Expense: Purchase of office stationery"
        },
        {
            "id": 124,
            "gl_account": "1000",
            "gl_account_name": "Cash",
            "amount": -50000,
            "description": "Payment for: Purchase of office stationery"
        }
    ]
}
```

## Workflow

### 1. Create Expense (Open)

1. User selects expense type
2. System automatically determines G/L account
3. User enters amount, description, payment method
4. System generates document number
5. Expense saved with "Open" status

### 2. Preview Posting

1. User requests posting preview
2. System validates G/L accounts are set
3. System shows debit and credit entries
4. User reviews before posting

### 3. Post Expense

1. User confirms posting
2. System creates G/L entries:
   - Debit: Expense account
   - Credit: Cash/Bank account
3. System updates expense status to "Posted"
4. System records posting timestamp and user

## Status Flow

```
Open → Posted
```

- **Open**: Initial state, can be edited
- **Posted**: Posted to G/L, cannot be edited

## Admin Interface

The admin interface provides:

- List view with filtering and search
- Detail view with organized fieldsets
- Bulk actions for posting and voiding
- Color-coded status display
- Links to related G/L accounts

## Configuration

### Adding New Expense Types

1. Add new enum value in `ExpenseType`
2. Add G/L account mapping in `get_gl_account_mapping()`
3. Create corresponding G/L account in the system

### Customizing G/L Account Mapping

Modify the mapping in `ExpenseType.get_gl_account_mapping()`:

```python
@classmethod
def get_gl_account_mapping(cls):
    return {
        cls.NEW_EXPENSE_TYPE.value: "6120",  # New G/L account number
        # ... existing mappings
    }
```

## Error Handling

The system includes comprehensive error handling:

- Validation of required fields
- G/L account existence checks
- Posting status validation
- Rollback on posting failures
- User-friendly error messages

## Security

- Company-based data isolation
- User-based posting tracking
- Audit trail for all changes
- Permission-based access control

## Integration

The expense system integrates with:

- **Financials**: G/L accounts and entries
- **Payments**: Payment methods
- **Setup**: NoSeries for document numbering
- **Authentication**: User management and company isolation
