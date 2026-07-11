# Vendor/Supplier Creation Guide

## Overview

This guide explains how vendor (supplier) creation works in ZentroApp across **web and mobile platforms**. This is a **high-level implementation guide** that focuses on architecture, data flow, and key considerations for implementing vendor creation in both web and mobile applications.

**Note**: The terms "vendor" and "supplier" are used interchangeably in this guide. The system uses "vendor" internally, but the UI may display "supplier" to users.

## Vendor Creation Flow

```
┌─────────────────────────────────────────────────────────┐
│ USER INITIATES VENDOR CREATION                         │
│ - Web: Click "Create New Vendor" button                 │
│ - Mobile: Tap "+" button or "Add Vendor" action         │
└──────────────────┬──────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────┐
│ FRONTEND: OPEN CREATION MODAL/FORM                      │
│ - Web: BaseCard modal with VendorForm                   │
│ - Mobile: Full-screen form or bottom sheet              │
│ - Initialize empty form with default values             │
└──────────────────┬──────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────┐
│ USER FILLS FORM FIELDS                                   │
│ - Required: name (unique)                                │
│ - Optional: contact info, address, payment method, etc. │
│ - Manual save button (web and mobile)                   │
└──────────────────┬──────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────┐
│ FRONTEND: VALIDATE & SUBMIT                              │
│ - Validate required fields                               │
│ - Check for duplicate vendor name                       │
│ - Send POST request to /api/vendors/                   │
└──────────────────┬──────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────┐
│ BACKEND: PROCESS CREATION                                │
│ - Check INSERT permission (Page Object ID: 10303)        │
│ - Validate data                                          │
│ - Auto-generate vendor number (no-series)              │
│ - Assign default posting groups if missing               │
│ - Create vendor record                                    │
└──────────────────┬──────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────┐
│ BACKEND: RETURN CREATED VENDOR                          │
│ - Full vendor object with generated fields               │
│ - Includes: id, system_id, no, balance, etc.           │
└──────────────────┬──────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────┐
│ FRONTEND: UPDATE UI                                      │
│ - Update form with response data                        │
│ - Add vendor to list/table                              │
│ - Show success notification                             │
│ - Close modal (web) or navigate back (mobile)           │
└─────────────────────────────────────────────────────────┘
```

## Backend API Structure

### Endpoint

```
POST /api/vendors/
```

### Authentication & Permissions

- **Authentication**: Required (JWT or Session)
- **Permission Check**: INSERT permission on Page Object ID `10303`
- **Permission Source**: User's permission sets via User Groups

### Request Payload

```json
{
  "name": "Vendor Name",                    // REQUIRED, unique
  "blocked": false,                         // Optional, boolean (default: false)
  "address": "Street Address",              // Optional
  "address_2": "Additional Address",        // Optional
  "country": "Country Name",                // Optional
  "city": "City Name",                      // Optional
  "state": "State Name",                    // Optional
  "post_code": "12345",                    // Optional
  "phone": "+256700000000",                // Optional
  "mobile": "+256700000001",               // Optional
  "email": "vendor@example.com",           // Optional, validated email format
  "website": "https://vendor.com",         // Optional, validated URL format
  "payment_method": 1,                     // Optional, FK to PaymentMethod
  "vendor_posting_group": 1,               // Optional, FK to VendorPostingGroup (auto-assigned if missing)
  "business_posting_group": 1              // Optional, FK to GeneralBusinessPostingGroup (auto-assigned if missing)
}
```

### Response Payload

```json
{
  "id": 123,
  "system_id": "uuid-string",
  "no": "VENDOR-20240101001",              // Auto-generated
  "name": "Vendor Name",
  "blocked": false,
  "balance": "0.00",                       // Calculated property
  "address": "Street Address",
  "address_2": "Additional Address",
  "country": "Country Name",
  "city": "City Name",
  "state": "State Name",
  "post_code": "12345",
  "phone": "+256700000000",
  "mobile": "+256700000001",
  "email": "vendor@example.com",
  "website": "https://vendor.com",
  "payment_method": 1,
  "vendor_posting_group": 1,
  "business_posting_group": 1
}
```

### Backend Auto-Generated Fields

1. **Vendor Number (`no`)**: 
   - Generated from No-Series if configured (PurchasePayable.vendor_no.no_series)
   - Format: `VENDOR-{incremented_number}` (from no-series)
   - Falls back to default if no-series missing

2. **Posting Groups**:
   - `vendor_posting_group`: First available VendorPostingGroup
   - `business_posting_group`: First available GeneralBusinessPostingGroup
   - Only assigned if not provided in request

### Validation Rules

- **Name**: Required, max 100 characters
- **Email**: Optional, validated email format if provided
- **Website**: Optional, validated URL format if provided
- **Duplicate Check**: Backend checks for existing vendor with same name
- **General Vendor**: Vendor with number "VENDOR-000001" is protected (cannot be edited/deleted)

### Error Responses

```json
// Permission Denied (403)
{
  "error": "Insufficient permissions",
  "detail": "You need insert permission to create vendors",
  "reason": "permission_set"
}

// Validation Error (400)
{
  "name": ["Vendor with this name already exists."]
}

// Missing Required Field (400)
{
  "name": ["This field is required."]
}

// Email Validation Error (400)
{
  "email": ["Enter a valid email address."]
}

// Website Validation Error (400)
{
  "website": ["Enter a valid URL."]
}
```

## Frontend Implementation (High-Level)

### Web Application Architecture

#### Component Structure

```
Vendors.tsx (Main Page)
  ├── BaseCard (Modal Container)
  │   └── VendorForm
  │       ├── BasicInformationSection
  │       │   └── Form fields (name, blocked)
  │       ├── ContactInformationSection
  │       │   └── Form fields (address, phone, email, etc.)
  │       └── PaymentInformationSection
  │           └── Form fields (payment_method)
  └── BaseTable (Vendor List)
```

#### Key Features

1. **Manual Save**:
   - User fills form fields
   - Clicks "Save" button to submit
   - Shows "Saving..." and "Saved" status indicators
   - Single API call on save

2. **Form State Management**:
   - Uses Formik for form state
   - Redux for vendor data management
   - Real-time sync between form and table

3. **Permission-Based UI**:
   - Create button only visible if user has INSERT permission
   - Uses `usePermissions` hook to check `canCreate("Suppliers")`

4. **General Vendor Protection**:
   - Vendor with number "VENDOR-000001" cannot be edited or deleted
   - UI disables edit/delete buttons for this vendor
   - Shows warning message if user attempts to modify

#### Implementation Pattern

```typescript
// High-level flow
1. User clicks "Create New Vendor"
2. Modal opens with empty VendorForm
3. User fills form fields
4. User clicks "Save" button
5. Form validates and submits POST /api/vendors/
6. Response updates form and Redux store
7. Table refreshes to show new vendor
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
   - Navigate to vendor detail after creation
   - Or return to vendor list with new vendor highlighted

#### Implementation Pattern

```typescript
// High-level flow
1. User taps "+" or "Add Vendor" button
2. Navigate to VendorCreateScreen
3. User fills all required fields
4. User taps "Save" button
5. Validate form
6. POST /api/vendors/ with complete data
7. On success:
   - Navigate to VendorDetailScreen (new vendor)
   - Or navigate back to VendorListScreen
   - Show success toast/notification
8. On error:
   - Show error message
   - Keep form open for correction
```

## Vendor Model Fields

### Required Fields

- **name** (string, max 100 chars): Vendor name

### Optional Fields

- **blocked** (boolean): Whether vendor is blocked from purchases (default: false)
- **address** (string, max 100 chars): Street address
- **address_2** (string, max 100 chars): Additional address line
- **country** (string, max 100 chars): Country name
- **city** (string, max 50 chars): City name
- **state** (string, max 50 chars): State/province name
- **post_code** (string, max 20 chars): Postal/ZIP code
- **phone** (string, max 20 chars): Phone number
- **mobile** (string, max 20 chars): Mobile number
- **email** (email): Email address (validated format)
- **website** (URL): Website URL (validated format)
- **payment_method** (FK): Payment method reference
- **vendor_posting_group** (FK): Vendor posting group (auto-assigned if missing)
- **business_posting_group** (FK): General business posting group (auto-assigned if missing)

### Auto-Generated Fields (Read-Only)

- **id** (integer): Primary key
- **system_id** (UUID): System identifier
- **no** (string): Vendor number (auto-generated)
- **balance** (decimal): Calculated from vendor ledger entries

### Computed Properties

- **full_address** (string): Formatted complete address combining all address fields

## Permission Requirements

### Backend Permission Check

- **Page Object ID**: `10303` (Suppliers)
- **Required Action**: `insert`
- **Check Location**: `VendorViewSet.create()` method (if implemented)

**Note**: Currently, the VendorViewSet may not have explicit permission checks in the `create()` method. Permission checks should be added following the pattern used in CustomerViewSet.

### Frontend Permission Check

- **Page Name**: `"Suppliers"` (must match Page Object name)
- **Check Method**: `canCreate("Suppliers")`
- **Hook**: `usePermissions()` from `@/hooks/usePermissions`

### Permission Flow

```
User Action
    ↓
Frontend: Check canCreate("Suppliers")
    ├─ If false → Hide create button
    └─ If true → Show create button
        ↓
User clicks create
    ↓
API Request: POST /api/vendors/
    ↓
Backend: Check user.check_object_permission(10303, "insert")
    ├─ If false → Return 403 Forbidden
    └─ If true → Create vendor
```

## Key Implementation Considerations

### 1. Vendor Number Generation

- **Backend handles automatically**: No need to send `no` field
- **No-Series System**: Uses PurchasePayable.vendor_no.no_series if configured
- **Format**: `VENDOR-{incremented_number}` (from no-series)
- **Fallback**: Default number if no-series missing

### 2. Duplicate Name Handling

- **Backend validation**: Checks for existing vendor with same name
- **Error response**: `{"name": ["Vendor with this name already exists."]}`
- **Frontend should**: Show user-friendly error message
- **Suggestion**: Check before submit (optional, for better UX)

### 3. Manual Save Pattern

- **Web and Mobile**: Both use manual save button
- **No auto-save**: Unlike items, vendors use traditional form submission
- **Single API call**: All data sent in one request

### 4. Posting Groups

- **Auto-assignment**: Backend assigns defaults if not provided
- **Best practice**: Fetch available options and let user choose
- **Endpoints**: 
  - `/api/vendor-posting-groups/`
  - `/api/general-business-posting-groups/`

### 5. Payment Methods

- **Optional field**: Can be set during creation or later
- **Endpoint**: `/api/payment-methods/` (for dropdown options)
- **Use case**: Required for purchase transactions, optional for vendor record

### 6. General Vendor Protection

- **Protected Vendor**: Vendor with number "VENDOR-000001" is system vendor
- **Restrictions**: Cannot be edited or deleted
- **UI Handling**: Disable edit/delete buttons for this vendor
- **Error Handling**: Show warning message if user attempts modification

### 7. Address Fields

- **Multiple fields**: address, address_2, city, state, post_code, country
- **Computed property**: `full_address` combines all address fields
- **Optional**: All address fields are optional
- **Use case**: Complete address information for purchase orders and invoices

### 8. Contact Information

- **Phone and Mobile**: Separate fields for phone and mobile numbers
- **Email**: Validated email format
- **Website**: Validated URL format
- **All optional**: Contact information is not required

### 9. Blocked Status

- **Purpose**: Prevent new purchases from blocked vendors
- **Default**: false (vendor is active)
- **Use case**: Temporarily disable vendor without deleting record

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

4. **400 Bad Request - Email Format**:
   - **Action**: Show error on email field
   - **Message**: "Enter a valid email address."

5. **400 Bad Request - Website Format**:
   - **Action**: Show error on website field
   - **Message**: "Enter a valid URL."

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

### After Vendor Creation

1. **Update Form**: Populate form with response data (especially `id`, `system_id`, `no`)
2. **Update Redux Store**: Add vendor to vendor list
3. **Refresh Table**: Reload vendor list to show new vendor
4. **Update Current Record**: Set created vendor as current record

### Implementation Pattern

```typescript
// After successful creation
const response = await VendorServices.createVendor(data);

// Update form
setFieldValue('id', response.data.id);
setFieldValue('system_id', response.data.system_id);
setFieldValue('no', response.data.no);
// ... other fields

// Update Redux
dispatch(vendorActions.setCurrentRec(response.data));
dispatch(vendorActions.addVendor(response.data));

// Refresh list
const listResponse = await VendorServices.getVendors();
dispatch(vendorActions.setVendorList(listResponse.data.results));
```

## Mobile-Specific Considerations

### 1. Form Layout

- **Full-screen form**: Better for mobile UX
- **Bottom sheet**: Alternative for quick creation
- **Sections**: Group related fields (Basic Info, Contact Info, Payment Info)
- **Scrollable**: Handle keyboard overlap

### 2. Input Types

- **Text inputs**: Standard text fields
- **Email input**: Use email keyboard
- **Phone input**: Use phone number keyboard
- **URL input**: Use URL keyboard for website field
- **Dropdowns**: Native picker for payment methods, posting groups

### 3. Validation

- **Real-time**: Show errors as user types (optional)
- **On submit**: Validate all fields before API call
- **Error display**: Inline errors below fields

### 4. Offline Support (Future)

- **Queue requests**: Store creation requests if offline
- **Sync when online**: Submit queued requests
- **Conflict resolution**: Handle duplicate names on sync

### 5. Performance

- **Lazy load**: Load payment methods/posting groups only when needed
- **Debounce**: Debounce search if implementing vendor name check
- **Optimistic updates**: Show vendor in list immediately (update on error)

## Testing Checklist

### Functional Tests

- [ ] Create vendor with only required field (name)
- [ ] Create vendor with all fields
- [ ] Verify vendor number auto-generation
- [ ] Verify duplicate name error handling
- [ ] Verify permission check (403 for unauthorized users)
- [ ] Verify posting groups auto-assignment
- [ ] Verify form updates after creation
- [ ] Verify table refresh after creation
- [ ] Verify email validation
- [ ] Verify website URL validation
- [ ] Verify general vendor protection (VENDOR-000001)

### UI/UX Tests

- [ ] Create button visibility based on permissions
- [ ] Form validation messages display correctly
- [ ] Success notification appears
- [ ] Error messages are user-friendly
- [ ] Manual save works (web and mobile)
- [ ] Form state persists during navigation (mobile)
- [ ] General vendor edit/delete buttons are disabled

### Mobile-Specific Tests

- [ ] Form is scrollable
- [ ] Keyboard doesn't cover inputs
- [ ] Native input types work correctly
- [ ] Navigation after creation works
- [ ] Offline error handling (if implemented)

## API Service Methods

### VendorServices (Frontend)

```typescript
// Create vendor
VendorServices.createVendor(data: Partial<Vendor>): Promise<Vendor>

// Get vendors (for refresh)
VendorServices.getVendors(params?: VendorQueryParams): Promise<PaginatedResponse<Vendor>>

// Get single vendor
VendorServices.getVendor(vendorId: string): Promise<Vendor>

// Update vendor
VendorServices.updateVendor(vendorId: string, data: Partial<Vendor>): Promise<Vendor>

// Delete vendor
VendorServices.deleteVendor(vendorId: string): Promise<void>
```

### Usage Example

```typescript
// Create vendor
const response = await VendorServices.createVendor({
  name: "New Vendor",
  email: "vendor@example.com",
  phone: "+256700000000",
  address: "123 Main St",
  city: "Kampala"
});

// Response includes all fields including auto-generated ones
console.log(response.data.no); // "VENDOR-20240101001"
```

## Related Endpoints

### Supporting Data Endpoints

- **Payment Methods**: `GET /api/payment-methods/`
- **Vendor Posting Groups**: `GET /api/vendor-posting-groups/`
- **General Business Posting Groups**: `GET /api/general-business-posting-groups/`

### Vendor Management Endpoints

- **List Vendors**: `GET /api/vendors/`
- **Get Vendor**: `GET /api/vendors/{id}/`
- **Update Vendor**: `PATCH /api/vendors/{id}/`
- **Delete Vendor**: `DELETE /api/vendors/{id}/`

### Vendor Ledger Endpoints

- **Get Vendor Ledger Entries**: `GET /api/vendor-ledger/{vendorId}/ledger_entries/`

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

### 6. General Vendor Protection

- **Check vendor number**: Always check if vendor is "VENDOR-000001"
- **Disable actions**: Disable edit/delete buttons for general vendor
- **Show warnings**: Inform user why general vendor cannot be modified

### 7. Address Handling

- **Complete address**: Encourage users to fill all address fields
- **Format display**: Use `full_address` property for display
- **Validation**: Validate address fields if required by business rules

### 8. Contact Information

- **Email validation**: Always validate email format
- **URL validation**: Always validate website URL format
- **Phone format**: Consider phone number formatting for better UX

## Summary

Vendor creation in ZentroApp follows a standard CRUD pattern with these key features:

1. **Permission-based access**: INSERT permission required (Page Object ID: 10303)
2. **Auto-generated fields**: Vendor number and posting groups handled by backend
3. **Flexible creation**: Only name required, all other fields optional
4. **Manual save pattern**: Both web and mobile use manual save button
5. **Real-time updates**: Form and table sync after creation
6. **Error handling**: Comprehensive validation and user-friendly error messages
7. **General vendor protection**: System vendor (VENDOR-000001) cannot be modified
8. **Address management**: Multiple address fields with computed full address

The implementation should focus on providing a smooth user experience while maintaining data integrity and respecting permission boundaries.


