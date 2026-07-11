# Customer Creation Guide

## Overview

This guide explains how customer creation works in ZentroApp across **web and mobile platforms**. This is a **high-level implementation guide** that focuses on architecture, data flow, and key considerations for implementing customer creation in both web and mobile applications.

## Customer Creation Flow

```
┌─────────────────────────────────────────────────────────┐
│ USER INITIATES CUSTOMER CREATION                         │
│ - Web: Click "Create New Customer" button                │
│ - Mobile: Tap "+" button or "Add Customer" action        │
└──────────────────┬──────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────┐
│ FRONTEND: OPEN CREATION MODAL/FORM                      │
│ - Web: BaseCard modal with CustomerForm                 │
│ - Mobile: Full-screen form or bottom sheet              │
│ - Initialize empty form with default values             │
└──────────────────┬──────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────┐
│ USER FILLS FORM FIELDS                                   │
│ - Required: name (unique)                                │
│ - Optional: contact, phone, address, city, etc.         │
│ - Auto-save on blur (web) or manual save (mobile)       │
└──────────────────┬──────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────┐
│ FRONTEND: VALIDATE & SUBMIT                              │
│ - Validate required fields                               │
│ - Check for duplicate customer name                      │
│ - Send POST request to /api/customers/                  │
└──────────────────┬──────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────┐
│ BACKEND: PROCESS CREATION                                │
│ - Check INSERT permission (Page Object ID: 10101)        │
│ - Validate data                                          │
│ - Auto-generate customer number (no-series)             │
│ - Assign default posting groups if missing               │
│ - Create customer record                                  │
└──────────────────┬──────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────┐
│ BACKEND: RETURN CREATED CUSTOMER                         │
│ - Full customer object with generated fields             │
│ - Includes: id, system_id, no, balance, etc.            │
└──────────────────┬──────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────┐
│ FRONTEND: UPDATE UI                                      │
│ - Update form with response data                        │
│ - Add customer to list/table                            │
│ - Show success notification                             │
│ - Close modal (web) or navigate back (mobile)           │
└─────────────────────────────────────────────────────────┘
```

## Backend API Structure

### Endpoint

```
POST /api/customers/
```

### Authentication & Permissions

- **Authentication**: Required (JWT or Session)
- **Permission Check**: INSERT permission on Page Object ID `10101`
- **Permission Source**: User's permission sets via User Groups

### Request Payload

```json
{
  "name": "Customer Name",                    // REQUIRED, unique
  "contact": "Contact Person",                // Optional
  "phone_number": "+256700000000",            // Optional, validated format
  "address": "Street Address",               // Optional
  "address_2": "Additional Address",         // Optional
  "city": "City Name",                        // Optional
  "credit_limit": 1000000.00,                // Optional, decimal
  "payment_method": 1,                        // Optional, FK to PaymentMethod
  "customer_posting_group": 1,                // Optional, FK to CustomerPostingGroup
  "general_business_posting_group": 1,       // Optional, FK to GeneralBusinessPostingGroup
  "customer_type": "GENERAL",                 // Optional, enum: GENERAL, CORPORATE, INDIVIDUAL
  "user": 1                                    // Optional, FK to CustomUser
}
```

### Response Payload

```json
{
  "id": 123,
  "system_id": "uuid-string",
  "no": "CUST-20240101001",                   // Auto-generated
  "name": "Customer Name",
  "contact": "Contact Person",
  "phone_number": "+256700000000",
  "address": "Street Address",
  "address_2": "Additional Address",
  "city": "City Name",
  "credit_limit": "1000000.00",
  "balance": "0.00",                          // Calculated property
  "payment_method": 1,
  "payment_method_name": "Cash",
  "customer_posting_group": 1,
  "customer_posting_group_name": "DOMESTIC",
  "general_business_posting_group": 1,
  "general_business_posting_group_name": "DOMESTIC",
  "customer_type": "GENERAL",
  "user": null,
  "user_name": null
}
```

### Backend Auto-Generated Fields

1. **Customer Number (`no`)**: 
   - Generated from No-Series if configured
   - Falls back to `CUST-{timestamp}` if no-series missing
   - Format: `CUST-YYYYMMDDHHMMSS` (fallback)

2. **Posting Groups**:
   - `customer_posting_group`: First available CustomerPostingGroup
   - `general_business_posting_group`: First available GeneralBusinessPostingGroup
   - Only assigned if not provided in request

### Validation Rules

- **Name**: Required, unique, max 100 characters
- **Phone Number**: Optional, validated format (numbers, +, -, (), spaces only)
- **Credit Limit**: Optional, decimal (max 18 digits, 2 decimal places)
- **Duplicate Check**: Backend checks for existing customer with same name

### Error Responses

```json
// Permission Denied (403)
{
  "error": "Insufficient permissions",
  "detail": "You need insert permission to create customers",
  "reason": "permission_set"
}

// Validation Error (400)
{
  "name": ["Customer with this name already exists."]
}

// Missing Required Field (400)
{
  "name": ["This field is required."]
}
```

## Frontend Implementation (High-Level)

### Web Application Architecture

#### Component Structure

```
Customers.tsx (Main Page)
  ├── BaseCard (Modal Container)
  │   └── CustomerForm
  │       ├── BasicInformationSection
  │       │   └── AutoSaveField components
  │       └── PaymentInformationSection
  │           └── AutoSaveField components
  └── BaseTable (Customer List)
```

#### Key Features

1. **Auto-Save on Blur**:
   - Each field auto-saves when user leaves the field
   - For new customers: Creates customer on first field save
   - For existing customers: Updates only changed field
   - Shows "Saving..." and "Saved" status indicators

2. **Form State Management**:
   - Uses Formik for form state
   - Redux for customer data management
   - Real-time sync between form and table

3. **Permission-Based UI**:
   - Create button only visible if user has INSERT permission
   - Uses `usePermissions` hook to check `canCreate("Customer Management")`

#### Implementation Pattern

```typescript
// High-level flow
1. User clicks "Create New Customer"
2. Modal opens with empty CustomerForm
3. User types in any field (e.g., name)
4. On blur, AutoSaveField triggers:
   - If no customer.id: POST /api/customers/ with all form data
   - If customer.id exists: PATCH /api/customers/{id}/ with changed field
5. Response updates form and Redux store
6. Table refreshes to show new customer
```

### Mobile Application Architecture

#### Key Differences from Web

1. **No Auto-Save**:
   - Mobile uses manual "Save" button
   - All fields collected before submission
   - Single API call on save

2. **Form Presentation**:
   - Full-screen form or bottom sheet
   - Scrollable form with sections
   - Native input components

3. **Navigation**:
   - Navigate to customer detail after creation
   - Or return to customer list with new customer highlighted

#### Implementation Pattern

```typescript
// High-level flow
1. User taps "+" or "Add Customer" button
2. Navigate to CustomerCreateScreen
3. User fills all required fields
4. User taps "Save" button
5. Validate form
6. POST /api/customers/ with complete data
7. On success:
   - Navigate to CustomerDetailScreen (new customer)
   - Or navigate back to CustomerListScreen
   - Show success toast/notification
8. On error:
   - Show error message
   - Keep form open for correction
```

## Customer Model Fields

### Required Fields

- **name** (string, max 100 chars, unique): Customer name

### Optional Fields

- **contact** (string, max 100 chars): Contact person name
- **phone_number** (string, max 30 chars): Phone number (validated format)
- **address** (string, max 100 chars): Street address
- **address_2** (string, max 50 chars): Additional address line
- **city** (string, max 30 chars): City name
- **credit_limit** (decimal, 18 digits, 2 decimals): Credit limit amount
- **payment_method** (FK): Payment method reference
- **customer_posting_group** (FK): Customer posting group (auto-assigned if missing)
- **general_business_posting_group** (FK): General business posting group (auto-assigned if missing)
- **customer_type** (enum): GENERAL, CORPORATE, or INDIVIDUAL (default: GENERAL)
- **user** (FK): Associated user account (optional)

### Auto-Generated Fields (Read-Only)

- **id** (integer): Primary key
- **system_id** (UUID): System identifier
- **no** (string): Customer number (auto-generated)
- **balance** (decimal): Calculated from customer ledger entries

## Permission Requirements

### Backend Permission Check

- **Page Object ID**: `10101` (Customer Management)
- **Required Action**: `insert`
- **Check Location**: `CustomerViewSet.create()` method

### Frontend Permission Check

- **Page Name**: `"Customer Management"` (must match Page Object name)
- **Check Method**: `canCreate("Customer Management")`
- **Hook**: `usePermissions()` from `@/hooks/usePermissions`

### Permission Flow

```
User Action
    ↓
Frontend: Check canCreate("Customer Management")
    ├─ If false → Hide create button
    └─ If true → Show create button
        ↓
User clicks create
    ↓
API Request: POST /api/customers/
    ↓
Backend: Check user.check_object_permission(10101, "insert")
    ├─ If false → Return 403 Forbidden
    └─ If true → Create customer
```

## Key Implementation Considerations

### 1. Customer Number Generation

- **Backend handles automatically**: No need to send `no` field
- **No-Series System**: Uses SalesReceivable setup if configured
- **Fallback**: Timestamp-based number if no-series missing
- **Format**: `CUST-YYYYMMDDHHMMSS` (fallback)

### 2. Duplicate Name Handling

- **Backend validation**: Checks for existing customer with same name
- **Error response**: `{"name": ["Customer with this name already exists."]}`
- **Frontend should**: Show user-friendly error message
- **Suggestion**: Check before submit (optional, for better UX)

### 3. Auto-Save vs Manual Save

- **Web**: Auto-save on blur (better for desktop)
- **Mobile**: Manual save button (better for mobile UX)
- **Consideration**: Mobile may want auto-save as optional feature

### 4. Posting Groups

- **Auto-assignment**: Backend assigns defaults if not provided
- **Best practice**: Fetch available options and let user choose
- **Endpoints**: 
  - `/api/customer-posting-groups/`
  - `/api/general-business-posting-groups/`

### 5. Payment Methods

- **Optional field**: Can be set during creation or later
- **Endpoint**: `/api/payment-methods/` (for dropdown options)
- **Use case**: Required for sales transactions, optional for customer record

### 6. Credit Limit

- **Default**: 0.00
- **Format**: Decimal with 2 decimal places
- **Validation**: Max 18 digits total
- **Use case**: Controls maximum credit allowed for customer

### 7. Customer Type

- **Options**: GENERAL, CORPORATE, INDIVIDUAL
- **Default**: GENERAL
- **Use case**: Categorization and reporting

### 8. User Association

- **Optional**: Link customer to user account
- **Use case**: When customer has login access to system
- **Relationship**: One user can have multiple customers

## Error Handling

### Common Errors

1. **403 Forbidden**: User lacks INSERT permission
   - **Action**: Show permission error message
   - **UI**: Disable create button (should be hidden by permission check)

2. **400 Bad Request - Duplicate Name**:
   - **Action**: Show error on name field
   - **Suggestion**: Allow user to edit name or cancel

3. **400 Bad Request - Validation Error**:
   - **Action**: Show field-specific errors
   - **UI**: Highlight invalid fields

4. **500 Server Error**:
   - **Action**: Show generic error message
   - **Log**: Log error for debugging
   - **Recovery**: Allow user to retry

### Error Display Pattern

```typescript
// Web: Toast notification + inline field errors
// Mobile: Alert dialog + inline field errors
```

## Data Refresh Strategy

### After Customer Creation

1. **Update Form**: Populate form with response data (especially `id`, `system_id`, `no`)
2. **Update Redux Store**: Add customer to customer list
3. **Refresh Table**: Reload customer list to show new customer
4. **Update Current Record**: Set created customer as current record

### Implementation Pattern

```typescript
// After successful creation
const response = await CustomerServices.createCustomer(data);

// Update form
setFieldValue('id', response.data.id);
setFieldValue('system_id', response.data.system_id);
setFieldValue('no', response.data.no);
// ... other fields

// Update Redux
dispatch(customerActions.setCurrentRec(response.data));
dispatch(customerActions.addCustomer(response.data));

// Refresh list
const listResponse = await CustomerServices.getCustomers();
dispatch(customerActions.setCustomerList(listResponse.data.results));
```

## Mobile-Specific Considerations

### 1. Form Layout

- **Full-screen form**: Better for mobile UX
- **Bottom sheet**: Alternative for quick creation
- **Sections**: Group related fields (Basic Info, Payment Info)
- **Scrollable**: Handle keyboard overlap

### 2. Input Types

- **Text inputs**: Standard text fields
- **Phone input**: Use phone number keyboard
- **Number input**: Use numeric keyboard for credit_limit
- **Dropdowns**: Native picker for posting groups, payment methods

### 3. Validation

- **Real-time**: Show errors as user types (optional)
- **On submit**: Validate all fields before API call
- **Error display**: Inline errors below fields

### 4. Offline Support (Future)

- **Queue requests**: Store creation requests if offline
- **Sync when online**: Submit queued requests
- **Conflict resolution**: Handle duplicate names on sync

### 5. Performance

- **Lazy load**: Load posting groups/payment methods only when needed
- **Debounce**: Debounce search if implementing customer name check
- **Optimistic updates**: Show customer in list immediately (update on error)

## Testing Checklist

### Functional Tests

- [ ] Create customer with only required field (name)
- [ ] Create customer with all fields
- [ ] Verify customer number auto-generation
- [ ] Verify duplicate name error handling
- [ ] Verify permission check (403 for unauthorized users)
- [ ] Verify posting groups auto-assignment
- [ ] Verify form updates after creation
- [ ] Verify table refresh after creation

### UI/UX Tests

- [ ] Create button visibility based on permissions
- [ ] Form validation messages display correctly
- [ ] Success notification appears
- [ ] Error messages are user-friendly
- [ ] Auto-save works (web)
- [ ] Manual save works (mobile)
- [ ] Form state persists during navigation (mobile)

### Mobile-Specific Tests

- [ ] Form is scrollable
- [ ] Keyboard doesn't cover inputs
- [ ] Native input types work correctly
- [ ] Navigation after creation works
- [ ] Offline error handling (if implemented)

## API Service Methods

### CustomerServices (Frontend)

```typescript
// Create customer
CustomerServices.createCustomer(data: Partial<Customer>): Promise<Customer>

// Get customers (for refresh)
CustomerServices.getCustomers(params?: CustomerQueryParams): Promise<PaginatedResponse<Customer>>

// Get single customer
CustomerServices.getCustomer(customerId: string): Promise<Customer>
```

### Usage Example

```typescript
// Create customer
const response = await CustomerServices.createCustomer({
  name: "New Customer",
  contact: "John Doe",
  phone_number: "+256700000000",
  address: "123 Main St",
  city: "Kampala"
});

// Response includes all fields including auto-generated ones
console.log(response.data.no); // "CUST-20240101001"
```

## Related Endpoints

### Supporting Data Endpoints

- **Payment Methods**: `GET /api/payment-methods/`
- **Customer Posting Groups**: `GET /api/customer-posting-groups/`
- **General Business Posting Groups**: `GET /api/general-business-posting-groups/`
- **Users** (for user association): `GET /api/users/`

### Customer Management Endpoints

- **List Customers**: `GET /api/customers/`
- **Get Customer**: `GET /api/customers/{id}/`
- **Update Customer**: `PATCH /api/customers/{id}/`
- **Delete Customer**: `DELETE /api/customers/{id}/`

## Best Practices

### 1. Always Use Response Data

- **Don't assume**: Use data from API response
- **Auto-generated fields**: `id`, `system_id`, `no` come from backend
- **Calculated fields**: `balance` is calculated, not sent

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

### 5. Maintain Data Consistency

- **Refresh after creation**: Update list/table
- **Sync form state**: Keep form and Redux in sync
- **Handle errors**: Roll back optimistic updates on error

## Summary

Customer creation in ZentroApp follows a standard CRUD pattern with these key features:

1. **Permission-based access**: INSERT permission required (Page Object ID: 10101)
2. **Auto-generated fields**: Customer number and posting groups handled by backend
3. **Flexible creation**: Only name required, all other fields optional
4. **Platform-specific UX**: Auto-save for web, manual save for mobile
5. **Real-time updates**: Form and table sync after creation
6. **Error handling**: Comprehensive validation and user-friendly error messages

The implementation should focus on providing a smooth user experience while maintaining data integrity and respecting permission boundaries.















































