# Item Creation Guide

## Overview

This guide explains how item creation works in ZentroApp across **web and mobile platforms**. This is a **high-level implementation guide** that focuses on architecture, data flow, and key considerations for implementing item creation in both web and mobile applications.

## Item Creation Flow

```
┌─────────────────────────────────────────────────────────┐
│ USER INITIATES ITEM CREATION                            │
│ - Web: Click "Create New Item" button                    │
│ - Mobile: Tap "+" button or "Add Item" action            │
└──────────────────┬──────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────┐
│ FRONTEND: OPEN CREATION MODAL/FORM                      │
│ - Web: BaseCard modal with ItemForm                     │
│ - Mobile: Full-screen form or bottom sheet              │
│ - Initialize empty form with default values             │
└──────────────────┬──────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────┐
│ USER FILLS FORM FIELDS                                   │
│ - Required: item_name (unique)                          │
│ - Optional: description, type, unit_price, category, etc.│
│ - Auto-save on blur (web) or manual save (mobile)       │
└──────────────────┬──────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────┐
│ FRONTEND: VALIDATE & SUBMIT                              │
│ - Validate required fields                               │
│ - Check for duplicate item name                          │
│ - Send POST request to /api/items/upsert/              │
└──────────────────┬──────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────┐
│ BACKEND: PROCESS CREATION                                │
│ - Check INSERT permission (Page Object ID: 10201)        │
│ - Validate data                                          │
│ - Auto-generate item number (no-series)                │
│ - Auto-generate barcode (13-digit random)               │
│ - Assign default posting groups if missing               │
│ - Assign default unit of measure if missing              │
│ - Create item record                                      │
└──────────────────┬──────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────┐
│ BACKEND: RETURN CREATED ITEM                            │
│ - Full item object with generated fields                 │
│ - Includes: id, system_id, no, bar_code_no, etc.      │
└──────────────────┬──────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────┐
│ FRONTEND: UPDATE UI                                      │
│ - Update form with response data                        │
│ - Add item to list/table                                │
│ - Show success notification                             │
│ - Close modal (web) or navigate back (mobile)           │
└─────────────────────────────────────────────────────────┘
```

## Backend API Structure

### Endpoint

```
POST /api/items/upsert/
```

**Note**: The endpoint is `/upsert/` which handles both create and update operations. For new items, omit `system_id` in the request.

### Authentication & Permissions

- **Authentication**: Required (JWT or Session)
- **Permission Check**: INSERT permission on Page Object ID `10201`
- **Permission Source**: User's permission sets via User Groups

### Request Payload

```json
{
  "item_name": "Item Name",                    // REQUIRED, unique
  "description": "Item description",           // Optional
  "type": "Inventory",                          // Optional, enum: Inventory, Service, Non-Inventory (default: Inventory)
  "costing_method": "FIFO",                    // Optional, enum: FIFO, Average, Standard (default: FIFO)
  "unit_price": 10000,                         // Optional, positive integer (default: 0)
  "unit_cost": 8000,                           // Optional, for Service/Non-Inventory items
  "item_category": "CAT001",                   // Optional, FK to ItemCategory (code)
  "unit_of_measure": "PCS",                    // Optional, FK to UnitOfMeasure (code, default: PCS)
  "tracking_code": "uuid-string",              // Optional, FK to ItemTrackingCodes (system_id)
  "bar_code_no": "1234567890123",              // Optional, auto-generated if not provided
  "shelf_no": "A-01-01",                       // Optional
  "blocked": false,                            // Optional, boolean (default: false)
  "general_product_posting_group": "RETAIL",   // Optional, auto-assigned if missing
  "inventory_posting_group": "MAIN",          // Optional, auto-assigned for Inventory type
  "production_bom": null                       // Optional, FK to ProductionBOM (Service/Non-Inventory only)
}
```

### Response Payload

```json
{
  "id": 123,
  "system_id": "uuid-string",
  "no": "ITM-20240101001",                     // Auto-generated
  "item_name": "Item Name",
  "bar_code_no": "1234567890123",              // Auto-generated if not provided
  "type": "Inventory",
  "blocked": false,
  "shelf_no": "A-01-01",
  "unit_price": 10000,
  "unit_cost": 8000,                           // Calculated for Inventory, manual for Service/Non-Inventory
  "costing_method": "FIFO",
  "description": "Item description",
  "unit_of_measure": "PCS",
  "unit_of_measure_description": "Pieces",
  "purchase_unit_of_measure": 1,              // FK to ItemUnitOfMeasure
  "sales_unit_of_measure": 1,                  // FK to ItemUnitOfMeasure
  "item_category": "CAT001",
  "item_category_description": "Category Name",
  "general_product_posting_group": "RETAIL",
  "inventory_posting_group": "MAIN",
  "tracking_code": {
    "system_id": "uuid-string",
    "code": "LOT",
    "description": "Lot Tracking",
    "require_serial_no": false,
    "require_lot_no": true,
    "require_expiry_date": true
  },
  "inventory": 0,                              // Calculated property
  "profit_percentage": 25.0,                  // Calculated property
  "item_images": [],                           // Array of image objects
  "item_units_of_measure": [],                // Array of ItemUnitOfMeasure objects
  "uom_options": [],                          // Available unit of measure options
  "attribute_entries": []                      // Item attribute entries
}
```

### Backend Auto-Generated Fields

1. **Item Number (`no`)**: 
   - Generated from No-Series if configured (InventorySetup.item_no_series)
   - Falls back to `ITM-{timestamp}` if no-series missing
   - Format: `ITM-YYYYMMDDHHMMSS` (fallback)

2. **Barcode (`bar_code_no`)**: 
   - Auto-generated 13-digit random number if not provided
   - Ensures uniqueness across all items
   - Format: 13 digits (e.g., "1234567890123")

3. **Posting Groups**:
   - `general_product_posting_group`: 
     - Service type → "SERVICE" posting group
     - Inventory/Non-Inventory → Default (RETAIL) posting group
   - `inventory_posting_group`: 
     - Only for Inventory type items
     - Default posting group if not provided
     - Cleared for Service/Non-Inventory items

4. **Unit of Measure**:
   - Defaults to "PCS" if not provided
   - Creates ItemUnitOfMeasure relationships automatically
   - Sets `sales_unit_of_measure` and `purchase_unit_of_measure`

### Validation Rules

- **Item Name**: Required, unique, max 225 characters
- **Type**: Optional, enum: "Inventory", "Service", "Non-Inventory" (default: "Inventory")
- **Costing Method**: Optional, enum: "FIFO", "Average", "Standard" (default: "FIFO")
- **Unit Price**: Optional, positive integer (default: 0)
- **Unit Cost**: Optional, for Service/Non-Inventory items (stored in `manual_unit_cost`)
- **Duplicate Check**: Backend checks for existing item with same name
- **Tracking Code**: Cannot be changed if item has ledger entries

### Error Responses

```json
// Permission Denied (403)
{
  "error": "Insufficient permissions",
  "detail": "You do not have permission to create items",
  "reason": "permission_set"
}

// Validation Error (400)
{
  "item_name": ["Item with this name already exists."]
}

// Missing Required Field (400)
{
  "item_name": ["This field is required."]
}

// Tracking Code Change Error (400)
{
  "detail": "Item has entries, you can't change tracking code"
}
```

## Frontend Implementation (High-Level)

### Web Application Architecture

#### Component Structure

```
Items.tsx (Main Page)
  ├── BaseCard (Modal Container)
  │   └── ItemForm
  │       ├── BasicInformationSection
  │       │   └── AutoSaveField components
  │       ├── PricingInformationSection
  │       │   └── AutoSaveField components
  │       ├── InventoryInformationSection
  │       │   └── AutoSaveField components
  │       └── ImageUploadSection
  │           └── Image upload components
  └── BaseTable (Item List)
```

#### Key Features

1. **Auto-Save on Blur**:
   - Each field auto-saves when user leaves the field
   - For new items: Creates item on first field save
   - For existing items: Updates only changed field
   - Shows "Saving..." and "Saved" status indicators

2. **Form State Management**:
   - Uses Formik for form state
   - Redux for item data management
   - Real-time sync between form and table

3. **Permission-Based UI**:
   - Create button only visible if user has INSERT permission
   - Uses `usePermissions` hook to check `canCreate("Items")`

4. **Image Upload**:
   - Support for multiple images per item
   - Upload via `/api/item-images/` endpoint
   - Images displayed in form and item list

5. **Unit of Measure Management**:
   - Default unit of measure selection
   - Support for multiple units of measure per item
   - Purchase and sales unit of measure configuration

#### Implementation Pattern

```typescript
// High-level flow
1. User clicks "Create New Item"
2. Modal opens with empty ItemForm
3. User types in any field (e.g., item_name)
4. On blur, AutoSaveField triggers:
   - If no item.system_id: POST /api/items/upsert/ with all form data
   - If item.system_id exists: POST /api/items/upsert/ with changed field
5. Response updates form and Redux store
6. Table refreshes to show new item
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
   - Navigate to item detail after creation
   - Or return to item list with new item highlighted

4. **Image Upload**:
   - Native camera integration
   - Image picker from gallery
   - Multiple image selection

#### Implementation Pattern

```typescript
// High-level flow
1. User taps "+" or "Add Item" button
2. Navigate to ItemCreateScreen
3. User fills all required fields
4. User uploads images (optional)
5. User taps "Save" button
6. Validate form
7. POST /api/items/upsert/ with complete data
8. On success:
   - Navigate to ItemDetailScreen (new item)
   - Or navigate back to ItemListScreen
   - Show success toast/notification
9. On error:
   - Show error message
   - Keep form open for correction
```

## Item Model Fields

### Required Fields

- **item_name** (string, max 225 chars, unique): Item name

### Optional Fields

- **description** (text): Item description
- **type** (string, enum): "Inventory", "Service", or "Non-Inventory" (default: "Inventory")
- **costing_method** (string, enum): "FIFO", "Average", or "Standard" (default: "FIFO")
- **unit_price** (positive integer): Selling price (default: 0)
- **unit_cost** (positive integer): Cost price (for Service/Non-Inventory items, stored as `manual_unit_cost`)
- **item_category** (FK, code): Item category reference
- **unit_of_measure** (FK, code): Base unit of measure (default: "PCS")
- **purchase_unit_of_measure** (FK): Purchase unit of measure (auto-created from `unit_of_measure`)
- **sales_unit_of_measure** (FK): Sales unit of measure (auto-created from `unit_of_measure`)
- **tracking_code** (FK, system_id): Item tracking code (lot/serial/expiry tracking)
- **bar_code_no** (string, max 225 chars): Barcode number (auto-generated if not provided)
- **shelf_no** (string, max 225 chars): Shelf location
- **blocked** (boolean): Whether item is blocked from transactions (default: false)
- **general_product_posting_group** (FK, code): General product posting group (auto-assigned)
- **inventory_posting_group** (FK, code): Inventory posting group (auto-assigned for Inventory type)
- **production_bom** (FK): Production BOM reference (Service/Non-Inventory only)

### Auto-Generated Fields (Read-Only)

- **id** (integer): Primary key
- **system_id** (UUID): System identifier
- **no** (string): Item number (auto-generated)
- **bar_code_no** (string): Barcode (auto-generated if not provided)
- **inventory** (integer): Calculated from item ledger entries
- **unit_cost** (integer): Calculated for Inventory items, manual for Service/Non-Inventory
- **profit_percentage** (decimal): Calculated profit percentage
- **item_images** (array): Related item images
- **item_units_of_measure** (array): Related unit of measure configurations
- **uom_options** (array): Available unit of measure options
- **attribute_entries** (array): Item attribute entries

## Permission Requirements

### Backend Permission Check

- **Page Object ID**: `10201` (Items)
- **Required Action**: `insert`
- **Check Location**: `ItemsModalViewSet.upsert()` method

### Frontend Permission Check

- **Page Name**: `"Items"` (must match Page Object name)
- **Check Method**: `canCreate("Items")`
- **Hook**: `usePermissions()` from `@/hooks/usePermissions`

### Permission Flow

```
User Action
    ↓
Frontend: Check canCreate("Items")
    ├─ If false → Hide create button
    └─ If true → Show create button
        ↓
User clicks create
    ↓
API Request: POST /api/items/upsert/
    ↓
Backend: Check user.check_object_permission(10201, "insert")
    ├─ If false → Return 403 Forbidden
    └─ If true → Create item
```

## Key Implementation Considerations

### 1. Item Number Generation

- **Backend handles automatically**: No need to send `no` field
- **No-Series System**: Uses InventorySetup.item_no_series if configured
- **Fallback**: Timestamp-based number if no-series missing
- **Format**: `ITM-YYYYMMDDHHMMSS` (fallback)

### 2. Barcode Generation

- **Auto-generated**: 13-digit random number if not provided
- **Uniqueness**: Backend ensures barcode is unique
- **Manual override**: Can provide custom barcode in request

### 3. Duplicate Name Handling

- **Backend validation**: Checks for existing item with same name
- **Error response**: `{"item_name": ["Item with this name already exists."]}`
- **Frontend should**: Show user-friendly error message
- **Suggestion**: Check before submit (optional, for better UX)

### 4. Auto-Save vs Manual Save

- **Web**: Auto-save on blur (better for desktop)
- **Mobile**: Manual save button (better for mobile UX)
- **Consideration**: Mobile may want auto-save as optional feature

### 5. Posting Groups

- **Auto-assignment**: Backend assigns defaults based on item type
- **Service items**: Get "SERVICE" general product posting group
- **Inventory items**: Get default general product and inventory posting groups
- **Best practice**: Fetch available options and let user choose
- **Endpoints**: 
  - `/api/general-product-posting-groups/`
  - `/api/inventory-posting-groups/`

### 6. Unit of Measure

- **Default**: "PCS" if not provided
- **Auto-creation**: Backend creates ItemUnitOfMeasure relationships
- **Multiple UOMs**: Items can have multiple units of measure
- **Default UOM**: First UOM is set as default for sales and purchase
- **Endpoints**: 
  - `/api/units-of-measure/` (for base UOM selection)
  - `/api/item-units-of-measure/` (for item-specific UOMs)

### 7. Item Types

- **Inventory**: Physical items with inventory tracking
- **Service**: Services without inventory (uses `manual_unit_cost`)
- **Non-Inventory**: Items without inventory tracking (uses `manual_unit_cost`)
- **Type-specific behavior**: 
  - Inventory items: Require inventory posting group, use FIFO costing
  - Service/Non-Inventory: Use manual unit cost, no inventory posting group

### 8. Tracking Codes

- **Optional**: Link item to tracking code for lot/serial/expiry tracking
- **Restriction**: Cannot change tracking code if item has ledger entries
- **Endpoints**: `/api/item-tracking-codes/`
- **Use case**: Required for items that need lot numbers, serial numbers, or expiry dates

### 9. Item Images

- **Multiple images**: Items can have multiple images
- **Upload endpoint**: `/api/item-images/`
- **Delete endpoint**: `/api/item-images/{id}/`
- **Form data**: Use multipart/form-data for image uploads

### 10. Item Categories

- **Optional**: Categorize items for organization
- **Hierarchical**: Categories can have parent categories
- **Endpoints**: `/api/categories/`
- **Use case**: Organizing items, filtering, reporting

### 11. Unit Cost Handling

- **Inventory items**: Unit cost calculated from ledger entries (read-only in API)
- **Service/Non-Inventory items**: Unit cost stored in `manual_unit_cost` field
- **API field**: Both use `unit_cost` field in API, backend handles mapping
- **Permission**: May be hidden based on user permissions (UserSetup.can_see_buying_price)

## Error Handling

### Common Errors

1. **403 Forbidden**: User lacks INSERT permission
   - **Action**: Show permission error message
   - **UI**: Disable create button (should be hidden by permission check)

2. **400 Bad Request - Duplicate Name**:
   - **Action**: Show error on item_name field
   - **Suggestion**: Allow user to edit name or cancel

3. **400 Bad Request - Validation Error**:
   - **Action**: Show field-specific errors
   - **UI**: Highlight invalid fields

4. **400 Bad Request - Tracking Code Change**:
   - **Action**: Show error message explaining restriction
   - **UI**: Disable tracking code field if item has entries

5. **500 Server Error**:
   - **Action**: Show generic error message
   - **Log**: Log error for debugging
   - **Recovery**: Allow user to retry

### Error Display Pattern

```typescript
// Web: Toast notification + inline field errors
// Mobile: Alert dialog + inline field errors
```

## Data Refresh Strategy

### After Item Creation

1. **Update Form**: Populate form with response data (especially `id`, `system_id`, `no`, `bar_code_no`)
2. **Update Redux Store**: Add item to item list
3. **Refresh Table**: Reload item list to show new item
4. **Update Current Record**: Set created item as current record

### Implementation Pattern

```typescript
// After successful creation
const response = await ItemServices.createItem(data);

// Update form
setFieldValue('id', response.data.id);
setFieldValue('system_id', response.data.system_id);
setFieldValue('no', response.data.no);
setFieldValue('bar_code_no', response.data.bar_code_no);
// ... other fields

// Update Redux
dispatch(itemActions.setCurrentRec(response.data));
dispatch(itemActions.addItem(response.data));

// Refresh list
const listResponse = await ItemServices.getItems();
dispatch(itemActions.setItems(listResponse.data.results));
```

## Mobile-Specific Considerations

### 1. Form Layout

- **Full-screen form**: Better for mobile UX
- **Bottom sheet**: Alternative for quick creation
- **Sections**: Group related fields (Basic Info, Pricing, Inventory, Images)
- **Scrollable**: Handle keyboard overlap

### 2. Input Types

- **Text inputs**: Standard text fields
- **Number inputs**: Use numeric keyboard for prices and costs
- **Dropdowns**: Native picker for categories, units of measure, tracking codes
- **Image picker**: Native camera and gallery integration

### 3. Validation

- **Real-time**: Show errors as user types (optional)
- **On submit**: Validate all fields before API call
- **Error display**: Inline errors below fields

### 4. Image Upload

- **Camera integration**: Allow taking photos directly
- **Gallery selection**: Select from device gallery
- **Multiple images**: Support selecting multiple images
- **Image preview**: Show thumbnails before upload
- **Upload progress**: Show upload progress indicator

### 5. Offline Support (Future)

- **Queue requests**: Store creation requests if offline
- **Sync when online**: Submit queued requests
- **Conflict resolution**: Handle duplicate names on sync

### 6. Performance

- **Lazy load**: Load categories/units of measure only when needed
- **Debounce**: Debounce search if implementing item name check
- **Optimistic updates**: Show item in list immediately (update on error)
- **Image compression**: Compress images before upload

## Testing Checklist

### Functional Tests

- [ ] Create item with only required field (item_name)
- [ ] Create item with all fields
- [ ] Verify item number auto-generation
- [ ] Verify barcode auto-generation
- [ ] Verify duplicate name error handling
- [ ] Verify permission check (403 for unauthorized users)
- [ ] Verify posting groups auto-assignment
- [ ] Verify unit of measure auto-assignment
- [ ] Verify form updates after creation
- [ ] Verify table refresh after creation
- [ ] Verify image upload functionality
- [ ] Verify different item types (Inventory, Service, Non-Inventory)

### UI/UX Tests

- [ ] Create button visibility based on permissions
- [ ] Form validation messages display correctly
- [ ] Success notification appears
- [ ] Error messages are user-friendly
- [ ] Auto-save works (web)
- [ ] Manual save works (mobile)
- [ ] Form state persists during navigation (mobile)
- [ ] Image upload and preview works

### Mobile-Specific Tests

- [ ] Form is scrollable
- [ ] Keyboard doesn't cover inputs
- [ ] Native input types work correctly
- [ ] Navigation after creation works
- [ ] Image picker works (camera and gallery)
- [ ] Multiple image selection works
- [ ] Image upload progress displays correctly
- [ ] Offline error handling (if implemented)

## API Service Methods

### ItemServices (Frontend)

```typescript
// Create item
ItemServices.createItem(data: Partial<Item>): Promise<Item>

// Update item
ItemServices.updateItem(data: Partial<Item>): Promise<Item>

// Get items (for refresh)
ItemServices.getItems(params?: ItemQueryParams): Promise<PaginatedResponse<Item>>

// Get single item
ItemServices.getItem(itemSystemId: string): Promise<Item>

// Upload item image
ItemServices.uploadItemImage(itemId: string, file: File): Promise<ItemImage>

// Delete item image
ItemServices.deleteItemImage(imageId: string): Promise<void>
```

### Usage Example

```typescript
// Create item
const response = await ItemServices.createItem({
  item_name: "New Item",
  description: "Item description",
  type: "Inventory",
  unit_price: 10000,
  item_category: "CAT001",
  unit_of_measure: "PCS"
});

// Response includes all fields including auto-generated ones
console.log(response.data.no); // "ITM-20240101001"
console.log(response.data.bar_code_no); // "1234567890123"
```

## Related Endpoints

### Supporting Data Endpoints

- **Item Categories**: `GET /api/categories/`
- **Units of Measure**: `GET /api/units-of-measure/`
- **Item Tracking Codes**: `GET /api/item-tracking-codes/`
- **General Product Posting Groups**: `GET /api/general-product-posting-groups/`
- **Inventory Posting Groups**: `GET /api/inventory-posting-groups/`
- **Item Units of Measure**: `GET /api/item-units-of-measure/?item={itemId}`

### Item Management Endpoints

- **List Items**: `GET /api/items/`
- **Get Item**: `GET /api/items/{system_id}/`
- **Create/Update Item**: `POST /api/items/upsert/`
- **Delete Item**: `POST /api/items/upsert/` (with `deleted: true`)
- **Bulk Delete Items**: `POST /api/items/bulk-delete/`
- **Export Items**: `POST /api/items/export/`

### Image Management Endpoints

- **Upload Item Image**: `POST /api/item-images/`
- **Delete Item Image**: `DELETE /api/item-images/{id}/`

## Best Practices

### 1. Always Use Response Data

- **Don't assume**: Use data from API response
- **Auto-generated fields**: `id`, `system_id`, `no`, `bar_code_no` come from backend
- **Calculated fields**: `inventory`, `unit_cost`, `profit_percentage` are calculated, not sent

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
- **Image compression**: Compress images before upload

### 5. Maintain Data Consistency

- **Refresh after creation**: Update list/table
- **Sync form state**: Keep form and Redux in sync
- **Handle errors**: Roll back optimistic updates on error

### 6. Image Upload Best Practices

- **Validate file types**: Only allow image formats (JPEG, PNG, WebP)
- **Validate file size**: Limit image size (e.g., 5MB max)
- **Compress images**: Reduce file size before upload
- **Show progress**: Display upload progress indicator
- **Handle errors**: Show error if upload fails

### 7. Unit of Measure Handling

- **Default UOM**: Always set a default unit of measure
- **Multiple UOMs**: Support multiple units of measure per item
- **UOM relationships**: Understand purchase vs sales unit of measure

### 8. Item Type Considerations

- **Inventory items**: Require inventory posting group, use FIFO costing
- **Service items**: Use manual unit cost, no inventory tracking
- **Non-Inventory items**: Use manual unit cost, no inventory tracking
- **Type restrictions**: Some fields are type-specific (e.g., inventory_posting_group)

## Summary

Item creation in ZentroApp follows a standard CRUD pattern with these key features:

1. **Permission-based access**: INSERT permission required (Page Object ID: 10201)
2. **Auto-generated fields**: Item number, barcode, and posting groups handled by backend
3. **Flexible creation**: Only item_name required, all other fields optional
4. **Platform-specific UX**: Auto-save for web, manual save for mobile
5. **Real-time updates**: Form and table sync after creation
6. **Error handling**: Comprehensive validation and user-friendly error messages
7. **Image support**: Multiple images per item with upload functionality
8. **Type-specific behavior**: Different handling for Inventory, Service, and Non-Inventory items

The implementation should focus on providing a smooth user experience while maintaining data integrity and respecting permission boundaries.


