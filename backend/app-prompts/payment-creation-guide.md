# Payment Creation Guide

## Overview

This guide explains how payment creation works in ZentroApp across **web and mobile platforms**. This is a **high-level implementation guide** that focuses on architecture, data flow, and key considerations for implementing payment creation in both web and mobile applications.

**Note**: The system uses **PaymentJournal** model which provides flexible payment tracking with support for Customer, Vendor, and G/L Account payments through Generic Foreign Keys.

## Payment Creation Flow

```
┌─────────────────────────────────────────────────────────┐
│ USER INITIATES PAYMENT CREATION                         │
│ - Web: Click "Create New Payment" button                 │
│ - Mobile: Tap "+" button or "Add Payment" action         │
└──────────────────┬──────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────┐
│ FRONTEND: OPEN CREATION MODAL/FORM                      │
│ - Web: BaseCard modal with PaymentForm                  │
│ - Mobile: Full-screen form or bottom sheet              │
│ - Initialize empty form with default values             │
│ - Load dropdown data (payment methods, accounts, etc.)  │
└──────────────────┬──────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────┐
│ USER FILLS FORM FIELDS                                   │
│ - Required: posting_date, account_type, amount           │
│ - Required: account selection (customer/vendor/gl)      │
│ - Required: balancing account selection                  │
│ - Optional: description, payment_method, applies_to     │
│ - Manual save button (web and mobile)                   │
└──────────────────┬──────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────┐
│ FRONTEND: VALIDATE & SUBMIT                              │
│ - Validate required fields                               │
│ - Validate account selection based on account_type       │
│ - Validate balancing account selection                   │
│ - Send POST request to /api/payments/payment-journal/  │
└──────────────────┬──────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────┐
│ BACKEND: PROCESS CREATION                                │
│ - Check INSERT permission (Page Object ID: 10401)        │
│ - Validate data                                          │
│ - Auto-generate document number (no-series)             │
│ - Auto-generate external_document_no from description    │
│ - Auto-populate balancing account from payment method    │
│ - Create payment journal entry                           │
└──────────────────┬──────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────┐
│ BACKEND: RETURN CREATED PAYMENT                         │
│ - Full payment journal object with generated fields      │
│ - Includes: id, system_id, document_no, etc.           │
└──────────────────┬──────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────┐
│ FRONTEND: UPDATE UI                                      │
│ - Update form with response data                        │
│ - Add payment to list/table                             │
│ - Show success notification                             │
│ - Close modal (web) or navigate back (mobile)           │
└─────────────────────────────────────────────────────────┘
```

## Backend API Structure

### Endpoint

```
POST /api/payments/payment-journal/
```

### Authentication & Permissions

- **Authentication**: Required (JWT or Session)
- **Permission Check**: INSERT permission on Page Object ID `10401`
- **Permission Source**: User's permission sets via User Groups

### Request Payload

```json
{
  "posting_date": "2024-01-15",              // REQUIRED, date
  "document_type": "Payment",                // Optional, enum: Payment, Invoice, Credit Memo, etc. (default: Payment)
  "description": "Payment description",      // Optional, used to generate external_document_no
  "account_type": "Customer",                // REQUIRED, enum: Customer, Vendor, G/L Account
  "account_content_type_id": 15,            // REQUIRED if account_type set, ContentType ID
  "account_object_id": 123,                  // REQUIRED if account_type set, Account object ID
  "payment_method": 1,                      // Optional, FK to PaymentMethod (auto-populates balancing account)
  "amount": 100000,                          // REQUIRED, positive integer
  "bal_account_type": "G/L Account",        // Optional, auto-populated from payment_method
  "bal_account_content_type_id": 12,         // Optional, auto-populated from payment_method
  "bal_account_object_id": 456,             // Optional, auto-populated from payment_method
  "applies_to_doc_type": "Invoice",         // Optional, document type this payment applies to
  "applies_to_content_type_id": 16,         // Optional, ContentType ID for applies_to document
  "applies_to_object_id": 789,               // Optional, Object ID for applies_to document
  "status": "Open",                          // Optional, enum: Open, Posted, Void, Cancelled (default: Open)
  "application_status": "Unapplied"          // Optional, enum: Applied, Unapplied, Partially Applied (default: Unapplied)
}
```

### Response Payload

```json
{
  "id": 123,
  "system_id": "uuid-string",
  "posting_date": "2024-01-15",
  "document_type": "Payment",
  "document_no": "PAY-20240115001",         // Auto-generated
  "external_document_no": "Payment description-20240115123456", // Auto-generated
  "description": "Payment description",
  "account_type": "Customer",
  "account_content_type_id": 15,
  "account_object_id": 123,
  "account_name": "CUST-001 - Customer Name", // Computed property
  "payment_method": 1,
  "payment_method_name": "CASH - Cash Payment", // Computed property
  "amount": 100000,
  "bal_account_type": "G/L Account",
  "bal_account_content_type_id": 12,
  "bal_account_object_id": 456,
  "bal_account_name": "10100 - Cash Account", // Computed property
  "status": "Open",
  "application_status": "Unapplied",
  "applies_to_doc_type": "Invoice",
  "applies_to_content_type_id": 16,
  "applies_to_object_id": 789,
  "applies_to_doc_name": "INV-20240101001",  // Computed property
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:30:00Z"
}
```

### Backend Auto-Generated Fields

1. **Document Number (`document_no`)**: 
   - Generated from No-Series if configured (JournalSetup.journal_no_series for Payment journal type)
   - Falls back to `PAY-{timestamp}` if no-series missing
   - Format: `PAY-YYYYMMDDHHMMSS` (fallback)

2. **External Document Number (`external_document_no`)**: 
   - Auto-generated from description and timestamp
   - Format: `{description}-{YYYYMMDDHHMMSS}`
   - Updated on every save

3. **Balancing Account**:
   - Auto-populated from `payment_method.bal_account_no` if payment method is selected
   - Sets `bal_account_type`, `bal_account_content_type_id`, and `bal_account_object_id`
   - Only if balancing account fields are not already set

4. **Account Type Defaults**:
   - If account_type is "Vendor": Sets `applies_to_doc_type` to "Invoice" and `bal_account_type` to "G/L Account"
   - If account_type is "Customer": Sets `applies_to_doc_type` to "Invoice" and `bal_account_type` to "G/L Account"

### Validation Rules

- **Posting Date**: Required, date field
- **Account Type**: Required, enum: "Customer", "Vendor", "G/L Account"
- **Account Selection**: Required if account_type is set
  - `account_content_type_id` and `account_object_id` must be provided
- **Amount**: Required, positive integer (can be 0)
- **Balancing Account**: Required if bal_account_type is set
  - `bal_account_content_type_id` and `bal_account_object_id` must be provided
- **Applies To**: If `applies_to_doc_type` is set, both `applies_to_content_type_id` and `applies_to_object_id` must be provided

### Error Responses

```json
// Permission Denied (403)
{
  "error": "Insufficient permissions",
  "detail": "You need insert permission to create payments",
  "reason": "permission_set"
}

// Validation Error (400)
{
  "account_content_type_id": ["Account content type and object ID are required when account type is specified"],
  "account_object_id": ["Account content type and object ID are required when account type is specified"]
}

// Missing Required Field (400)
{
  "posting_date": ["This field is required."],
  "amount": ["This field is required."]
}

// Invalid Account Selection (400)
{
  "account_no": ["Account number is required for account type Customer"]
}
```

## Frontend Implementation (High-Level)

### Web Application Architecture

#### Component Structure

```
Payments.tsx (Main Page)
  ├── BaseCard (Modal Container)
  │   └── PaymentForm
  │       ├── BasicInformationSection
  │       │   └── Form fields (posting_date, document_type, description)
  │       ├── AccountInformationSection
  │       │   └── Form fields (account_type, account selection)
  │       ├── PaymentInformationSection
  │       │   └── Form fields (payment_method, amount)
  │       └── BalancingAccountSection
  │           └── Form fields (bal_account_type, balancing account selection)
  └── BaseTable (Payment List)
```

#### Key Features

1. **Manual Save**:
   - User fills form fields
   - Clicks "Save" button to submit
   - Shows "Saving..." and "Saved" status indicators
   - Single API call on save

2. **Form State Management**:
   - Uses Formik for form state
   - Redux for payment data management
   - Real-time sync between form and table

3. **Permission-Based UI**:
   - Create button only visible if user has INSERT permission
   - Uses `usePermissions` hook to check `canCreate("Payments")`

4. **Generic Foreign Key Handling**:
   - Account selection uses ContentType and Object ID
   - Dynamic dropdowns based on account_type
   - Auto-population of balancing account from payment method

5. **Posting Functionality**:
   - Payments can be posted after creation
   - Posting creates ledger entries
   - Status changes from "Open" to "Posted"

#### Implementation Pattern

```typescript
// High-level flow
1. User clicks "Create New Payment"
2. Modal opens with empty PaymentForm
3. Load dropdown data (payment methods, customers, vendors, GL accounts, content types)
4. User selects account_type (Customer/Vendor/G/L Account)
5. User selects specific account based on account_type
6. User fills payment details (amount, payment_method, etc.)
7. User clicks "Save" button
8. Form validates and submits POST /api/payments/payment-journal/
9. Response updates form and Redux store
10. Table refreshes to show new payment
```

### Mobile Application Architecture

#### Key Differences from Web

1. **Manual Save**:
   - Mobile uses manual "Save" button (same as web)
   - All fields collected before submission
   - Single API call on save

2. **Form Presentation**:
   - Full-screen form or bottom sheet
   - Scrollable form with sections
   - Native input components

3. **Navigation**:
   - Navigate to payment detail after creation
   - Or return to payment list with new payment highlighted

4. **Account Selection**:
   - Native picker for account type
   - Searchable dropdown for account selection
   - Clear visual indication of selected account

#### Implementation Pattern

```typescript
// High-level flow
1. User taps "+" or "Add Payment" button
2. Navigate to PaymentCreateScreen
3. Load dropdown data
4. User selects account_type
5. User selects specific account
6. User fills payment details
7. User taps "Save" button
8. Validate form
9. POST /api/payments/payment-journal/ with complete data
10. On success:
    - Navigate to PaymentDetailScreen (new payment)
    - Or navigate back to PaymentListScreen
    - Show success toast/notification
11. On error:
    - Show error message
    - Keep form open for correction
```

## PaymentJournal Model Fields

### Required Fields

- **posting_date** (date): Payment posting date
- **account_type** (string, enum): "Customer", "Vendor", or "G/L Account"
- **account_content_type_id** (integer): ContentType ID for the account
- **account_object_id** (integer): Object ID for the account
- **amount** (integer): Payment amount (can be 0)

### Optional Fields

- **document_type** (string, enum): "Payment", "Invoice", "Credit Memo", "Finance Charge Memo", "Reminder", "Refund" (default: "Payment")
- **description** (text): Payment description
- **payment_method** (FK): Payment method reference (auto-populates balancing account)
- **bal_account_type** (string, enum): Balancing account type (auto-populated from payment_method)
- **bal_account_content_type_id** (integer): Balancing account ContentType ID (auto-populated)
- **bal_account_object_id** (integer): Balancing account Object ID (auto-populated)
- **applies_to_doc_type** (string): Document type this payment applies to
- **applies_to_content_type_id** (integer): ContentType ID for applies_to document
- **applies_to_object_id** (integer): Object ID for applies_to document
- **status** (string, enum): "Open", "Posted", "Void", "Cancelled" (default: "Open")
- **application_status** (string, enum): "Applied", "Unapplied", "Partially Applied" (default: "Unapplied")

### Auto-Generated Fields (Read-Only)

- **id** (integer): Primary key
- **system_id** (UUID): System identifier
- **document_no** (string): Document number (auto-generated)
- **external_document_no** (string): External document number (auto-generated from description)

### Computed Properties (Read-Only)

- **account_name** (string): Name of the account (computed from GenericForeignKey)
- **bal_account_name** (string): Name of the balancing account (computed from GenericForeignKey)
- **payment_method_name** (string): Name of the payment method (computed)
- **applies_to_doc_name** (string): Name of the document this payment applies to (computed)

## Permission Requirements

### Backend Permission Check

- **Page Object ID**: `10401` (Payments)
- **Required Action**: `insert`
- **Check Location**: `PaymentJournalViewSet.create()` method (if implemented)

**Note**: Currently, the PaymentJournalViewSet may not have explicit permission checks in the `create()` method. Permission checks should be added following the pattern used in CustomerViewSet.

### Frontend Permission Check

- **Page Name**: `"Payments"` (must match Page Object name)
- **Check Method**: `canCreate("Payments")`
- **Hook**: `usePermissions()` from `@/hooks/usePermissions`

### Permission Flow

```
User Action
    ↓
Frontend: Check canCreate("Payments")
    ├─ If false → Hide create button
    └─ If true → Show create button
        ↓
User clicks create
    ↓
API Request: POST /api/payments/payment-journal/
    ↓
Backend: Check user.check_object_permission(10401, "insert")
    ├─ If false → Return 403 Forbidden
    └─ If true → Create payment
```

## Key Implementation Considerations

### 1. Document Number Generation

- **Backend handles automatically**: No need to send `document_no` field
- **No-Series System**: Uses JournalSetup.journal_no_series for Payment journal type if configured
- **Fallback**: Timestamp-based number if no-series missing
- **Format**: `PAY-YYYYMMDDHHMMSS` (fallback)

### 2. External Document Number Generation

- **Auto-generated**: Created from description and timestamp
- **Format**: `{description}-{YYYYMMDDHHMMSS}`
- **Updated on save**: Regenerated on every update

### 3. Generic Foreign Key Handling

- **Account Selection**: Uses ContentType and Object ID pattern
- **Dynamic Dropdowns**: Account options change based on account_type
- **Content Types**: Available via `/api/payments/payment-journal/content_types/`
- **Account Resolution**: Backend resolves GenericForeignKey to get account name

### 4. Account Type Selection

- **Three Types**: Customer, Vendor, G/L Account
- **Required Selection**: User must select account_type first
- **Account Options**: Load appropriate accounts based on type
  - Customer: Load from `/api/customers/`
  - Vendor: Load from `/api/vendors/`
  - G/L Account: Load from `/api/financials/gl-accounts/`

### 5. Balancing Account Auto-Population

- **From Payment Method**: If payment_method is selected, balancing account is auto-populated
- **Payment Method Fields**: `bal_account_type`, `bal_account_content_type_id`, `bal_account_object_id`
- **Override Allowed**: User can manually change balancing account if needed
- **Default Behavior**: If payment_method has balancing account, it's used automatically

### 6. Payment Method Selection

- **Optional**: Payment method is not required for creation
- **Auto-Population**: Selecting payment method auto-populates balancing account
- **Endpoint**: `/api/financials/payment-methods/`
- **Use Case**: Required for posting, optional for creation

### 7. Applies To Functionality

- **Optional**: Payment can be created without applying to a document
- **Application**: Can be applied to invoices or other documents later
- **Status Tracking**: `application_status` tracks if payment is applied
- **Use Case**: Link payment to specific invoice or document

### 8. Posting Functionality

- **Separate Action**: Posting is a separate action after creation
- **Endpoint**: `POST /api/payments/payment-journal/{id}/post_payment_journal/`
- **Status Change**: Changes status from "Open" to "Posted"
- **Ledger Entries**: Creates ledger entries when posted
- **Restriction**: Only "Open" payments can be posted

### 9. Document Types

- **Payment**: Standard payment (default)
- **Invoice**: Invoice document
- **Credit Memo**: Credit memo document
- **Finance Charge Memo**: Finance charge memo
- **Reminder**: Reminder document
- **Refund**: Refund document

### 10. Status Management

- **Open**: Payment is created but not posted (default)
- **Posted**: Payment has been posted to ledger
- **Void**: Payment has been voided
- **Cancelled**: Payment has been cancelled

### 11. Application Status

- **Unapplied**: Payment is not applied to any document (default)
- **Applied**: Payment is fully applied to a document
- **Partially Applied**: Payment is partially applied to documents

## Error Handling

### Common Errors

1. **403 Forbidden**: User lacks INSERT permission
   - **Action**: Show permission error message
   - **UI**: Disable create button (should be hidden by permission check)

2. **400 Bad Request - Missing Account Selection**:
   - **Action**: Show error on account selection fields
   - **Message**: "Account content type and object ID are required when account type is specified"

3. **400 Bad Request - Missing Balancing Account**:
   - **Action**: Show error on balancing account fields
   - **Message**: "Balancing account content type and object ID are required when balancing account type is specified"

4. **400 Bad Request - Validation Error**:
   - **Action**: Show field-specific errors
   - **UI**: Highlight invalid fields

5. **400 Bad Request - Invalid Account Type**:
   - **Action**: Show error on account_type field
   - **Message**: "Account number is required for account type {account_type}"

6. **500 Server Error**:
   - **Action**: Show generic error message
   - **Log**: Log error for debugging
   - **Recovery**: Allow user to retry

### Error Display Pattern

```typescript
// Web: Toast notification + inline field errors
// Mobile: Alert dialog + inline field errors
```

## Data Refresh Strategy

### After Payment Creation

1. **Update Form**: Populate form with response data (especially `id`, `system_id`, `document_no`)
2. **Update Redux Store**: Add payment to payment list
3. **Refresh Table**: Reload payment list to show new payment
4. **Update Current Record**: Set created payment as current record

### Implementation Pattern

```typescript
// After successful creation
const response = await PaymentJournalServices.createPaymentJournal(data);

// Update form
setFieldValue('id', response.data.id);
setFieldValue('system_id', response.data.system_id);
setFieldValue('document_no', response.data.document_no);
// ... other fields

// Update Redux
dispatch(paymentActions.setCurrentRec(response.data));
dispatch(paymentActions.addPayment(response.data));

// Refresh list
const listResponse = await PaymentJournalServices.getPaymentJournals({ status: "Open" });
dispatch(paymentActions.setPaymentJournalList(listResponse.data.results));
```

## Mobile-Specific Considerations

### 1. Form Layout

- **Full-screen form**: Better for mobile UX
- **Bottom sheet**: Alternative for quick creation
- **Sections**: Group related fields (Basic Info, Account Info, Payment Info, Balancing Account)
- **Scrollable**: Handle keyboard overlap

### 2. Input Types

- **Date picker**: Native date picker for posting_date
- **Dropdowns**: Native picker for account_type, document_type, payment_method
- **Number input**: Use numeric keyboard for amount
- **Text input**: Standard text fields for description

### 3. Account Selection

- **Two-step process**: First select account_type, then select specific account
- **Searchable dropdown**: Allow searching for accounts
- **Visual feedback**: Show selected account name clearly
- **Loading states**: Show loading while fetching account options

### 4. Validation

- **Real-time**: Show errors as user types (optional)
- **On submit**: Validate all fields before API call
- **Error display**: Inline errors below fields
- **Account validation**: Validate account selection matches account_type

### 5. Offline Support (Future)

- **Queue requests**: Store creation requests if offline
- **Sync when online**: Submit queued requests
- **Conflict resolution**: Handle duplicate document numbers on sync

### 6. Performance

- **Lazy load**: Load account options only when account_type is selected
- **Debounce**: Debounce search if implementing account search
- **Optimistic updates**: Show payment in list immediately (update on error)
- **Caching**: Cache payment methods and content types

## Testing Checklist

### Functional Tests

- [ ] Create payment with Customer account
- [ ] Create payment with Vendor account
- [ ] Create payment with G/L Account
- [ ] Verify document number auto-generation
- [ ] Verify external document number auto-generation
- [ ] Verify balancing account auto-population from payment method
- [ ] Verify permission check (403 for unauthorized users)
- [ ] Verify form updates after creation
- [ ] Verify table refresh after creation
- [ ] Verify account selection validation
- [ ] Verify balancing account validation
- [ ] Test posting functionality

### UI/UX Tests

- [ ] Create button visibility based on permissions
- [ ] Form validation messages display correctly
- [ ] Success notification appears
- [ ] Error messages are user-friendly
- [ ] Manual save works (web and mobile)
- [ ] Form state persists during navigation (mobile)
- [ ] Account selection dropdowns work correctly
- [ ] Balancing account auto-population works
- [ ] Content type loading works

### Mobile-Specific Tests

- [ ] Form is scrollable
- [ ] Keyboard doesn't cover inputs
- [ ] Native input types work correctly
- [ ] Navigation after creation works
- [ ] Account selection works on mobile
- [ ] Date picker works correctly
- [ ] Offline error handling (if implemented)

## API Service Methods

### PaymentJournalServices (Frontend)

```typescript
// Create payment journal
PaymentJournalServices.createPaymentJournal(data: Partial<PaymentJournal>): Promise<PaymentJournal>

// Get payment journals (for refresh)
PaymentJournalServices.getPaymentJournals(params?: PaymentJournalFilterQueries): Promise<PaginatedResponse<PaymentJournal>>

// Get single payment journal
PaymentJournalServices.getPaymentJournal(id: number): Promise<PaymentJournal>

// Update payment journal
PaymentJournalServices.updatePaymentJournal(id: number, data: Partial<PaymentJournal>): Promise<PaymentJournal>

// Delete payment journal
PaymentJournalServices.deletePaymentJournal(id: number): Promise<void>

// Post payment journal
PaymentJournalServices.postPaymentJournal(id: number): Promise<PaymentJournal>

// Get content types
PaymentJournalServices.getContentTypes(): Promise<ContentType[]>

// Get payment methods
PaymentJournalServices.getPaymentMethods(): Promise<PaymentMethod[]>

// Get customers
PaymentJournalServices.getCustomers(): Promise<PaginatedResponse<Customer>>

// Get vendors
PaymentJournalServices.getVendors(): Promise<PaginatedResponse<Vendor>>

// Get GL accounts
PaymentJournalServices.getGLAccounts(): Promise<GLAccount[]>
```

### Usage Example

```typescript
// Create payment journal
const response = await PaymentJournalServices.createPaymentJournal({
  posting_date: "2024-01-15",
  account_type: "Customer",
  account_content_type_id: 15,
  account_object_id: 123,
  payment_method: 1,
  amount: 100000,
  description: "Payment for invoice"
});

// Response includes all fields including auto-generated ones
console.log(response.data.document_no); // "PAY-20240115001"
console.log(response.data.external_document_no); // "Payment for invoice-20240115123456"
```

## Related Endpoints

### Supporting Data Endpoints

- **Payment Methods**: `GET /api/financials/payment-methods/`
- **Customers**: `GET /api/customers/`
- **Vendors**: `GET /api/vendors/`
- **GL Accounts**: `GET /api/financials/gl-accounts/`
- **Content Types**: `GET /api/payments/payment-journal/content_types/`
- **Customer Ledger Entries**: `GET /api/customer-ledger/{customerId}/ledger_entries/`
- **Vendor Ledger Entries**: `GET /api/purchases/vendor-ledger-entries/?vendor={vendorId}`

### Payment Management Endpoints

- **List Payment Journals**: `GET /api/payments/payment-journal/`
- **Get Payment Journal**: `GET /api/payments/payment-journal/{id}/`
- **Create Payment Journal**: `POST /api/payments/payment-journal/`
- **Update Payment Journal**: `PUT /api/payments/payment-journal/{id}/`
- **Delete Payment Journal**: `DELETE /api/payments/payment-journal/{id}/`
- **Post Payment Journal**: `POST /api/payments/payment-journal/{id}/post_payment_journal/`
- **Apply Payment**: `POST /api/payments/payment-journal/{id}/apply/`
- **Unapply Payment**: `POST /api/payments/payment-journal/{id}/unapply/`

### Summary Endpoints

- **Payment Summary**: `GET /api/payments/payment-journal/summary/`
- **By Account Type**: `GET /api/payments/payment-journal/by_account_type/?account_type={type}`
- **Unapplied Payments**: `GET /api/payments/payment-journal/unapplied/`

## Best Practices

### 1. Always Use Response Data

- **Don't assume**: Use data from API response
- **Auto-generated fields**: `id`, `system_id`, `document_no`, `external_document_no` come from backend
- **Computed properties**: `account_name`, `bal_account_name` are computed, not sent

### 2. Handle Permissions Gracefully

- **Check before showing UI**: Hide create button if no permission
- **Handle 403 errors**: Show appropriate message
- **Don't rely on UI only**: Backend always validates permissions

### 3. Provide User Feedback

- **Loading states**: Show "Saving..." during API call
- **Success feedback**: Show "Saved" or success toast
- **Error feedback**: Show specific error messages

### 4. Optimize for Mobile

- **Single API call**: Collect all data before submitting
- **Native components**: Use platform-native input types
- **Keyboard handling**: Ensure inputs aren't covered by keyboard
- **Lazy loading**: Load account options only when needed

### 5. Maintain Data Consistency

- **Refresh after creation**: Update list/table
- **Sync form state**: Keep form and Redux in sync
- **Handle errors**: Roll back optimistic updates on error

### 6. Generic Foreign Key Handling

- **Content Type Pattern**: Always use ContentType and Object ID for GenericForeignKey fields
- **Account Resolution**: Use computed properties (account_name) for display
- **Validation**: Validate both content_type_id and object_id are provided together

### 7. Balancing Account Management

- **Auto-Population**: Let payment method auto-populate balancing account when possible
- **Manual Override**: Allow users to manually change balancing account if needed
- **Validation**: Ensure balancing account is set before posting

### 8. Account Selection UX

- **Two-Step Process**: First select account_type, then select specific account
- **Clear Labels**: Show account names clearly in dropdowns
- **Search Functionality**: Implement search for large account lists
- **Loading States**: Show loading while fetching account options

### 9. Posting Workflow

- **Separate Action**: Keep posting as separate action from creation
- **Status Check**: Only allow posting of "Open" payments
- **User Feedback**: Show clear feedback after posting
- **Error Handling**: Handle posting errors gracefully

### 10. Application Management

- **Optional Application**: Don't require payment to be applied during creation
- **Later Application**: Allow applying payment to documents after creation
- **Status Tracking**: Track application status accurately
- **Partial Application**: Support partially applied payments

## Summary

Payment creation in ZentroApp follows a standard CRUD pattern with these key features:

1. **Permission-based access**: INSERT permission required (Page Object ID: 10401)
2. **Auto-generated fields**: Document number and external document number handled by backend
3. **Flexible account selection**: Generic Foreign Keys support Customer, Vendor, and G/L Account payments
4. **Auto-population**: Balancing account auto-populated from payment method
5. **Manual save pattern**: Both web and mobile use manual save button
6. **Real-time updates**: Form and table sync after creation
7. **Error handling**: Comprehensive validation and user-friendly error messages
8. **Posting functionality**: Separate posting action creates ledger entries
9. **Application tracking**: Support for applying payments to documents

The implementation should focus on providing a smooth user experience while maintaining data integrity and respecting permission boundaries.


