# Item Category Creation Guide

## Overview

This guide explains how item category creation works in ZentroApp across **web and mobile platforms**. This is a **high-level implementation guide** that focuses on architecture, data flow, and key considerations for implementing item category creation in both web and mobile applications.

**Note**: Item categories use a **hierarchical structure** (parent-child relationships) using MPTT (Modified Preorder Tree Traversal) for efficient tree management. Categories can have attributes assigned to them, which act as templates for items in that category.

## Item Category Creation Flow

```
┌─────────────────────────────────────────────────────────┐
│ USER INITIATES CATEGORY CREATION                        │
│ - Web: Click "Add Category" in ItemCategoryModal         │
│ - Mobile: Tap "+" button or "Add Category" action         │
└──────────────────┬──────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────┐
│ FRONTEND: OPEN CREATION MODAL/FORM                      │
│ - Web: Dialog modal with category form                  │
│ - Mobile: Full-screen form or bottom sheet              │
│ - Initialize empty form with default values             │
│ - Load existing categories for parent selection         │
└──────────────────┬──────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────┐
│ USER FILLS FORM FIELDS                                   │
│ - Required: code (unique, primary key)                  │
│ - Optional: description (auto-uppercased, unique)        │
│ - Optional: parent_id (for subcategories)               │
│ - Manual save button (web and mobile)                   │
└──────────────────┬──────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────┐
│ FRONTEND: VALIDATE & SUBMIT                              │
│ - Validate required fields                               │
│ - Check for duplicate code                              │
│ - Check for duplicate description                        │
│ - Send POST request to /api/categories/                │
└──────────────────┬──────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────┐
│ BACKEND: PROCESS CREATION                                │
│ - Check INSERT permission (Page Object ID: 10204)         │
│ - Validate data                                          │
│ - Auto-uppercase description                             │
│ - Check for duplicate code and description              │
│ - Validate parent category (if provided)                 │
│ - Create category record                                  │
└──────────────────┬──────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────┐
│ BACKEND: RETURN CREATED CATEGORY                        │
│ - Full category object with computed fields              │
│ - Includes: code, description, parent_id, level, etc.  │
└──────────────────┬──────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────┐
│ FRONTEND: UPDATE UI                                      │
│ - Add category to list (hierarchical display)            │
│ - Show success notification                             │
│ - Reset form for next entry                             │
│ - Close modal (web) or navigate back (mobile)           │
└─────────────────────────────────────────────────────────┘
```

## Backend API Structure

### Endpoint

```
POST /api/categories/
```

**Note**: The endpoint is registered under the items app router, so the full path is `/api/categories/` (BaseService adds `/api/` prefix automatically).

### Authentication & Permissions

- **Authentication**: Required (JWT or Session)
- **Permission Check**: INSERT permission on Page Object ID `10204`
- **Permission Source**: User's permission sets via User Groups

### Request Payload

```json
{
  "code": "CAT001", // REQUIRED, unique, primary key, max 255 chars
  "description": "Category Description", // Optional, unique, auto-uppercased, max 255 chars
  "parent_id": "PARENT001" // Optional, FK to ItemCategory (code), for subcategories
}
```

### Response Payload

```json
{
  "system_id": "uuid-string",
  "code": "CAT001",
  "description": "CATEGORY DESCRIPTION", // Auto-uppercased
  "parent_id": "PARENT001", // null for root categories
  "level": 0, // Computed property (0 = root, 1 = child, etc.)
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:30:00Z"
}
```

### Backend Auto-Generated Fields

1. **Description Auto-Uppercase**:

   - Description is automatically converted to uppercase
   - Validation checks for duplicate description (case-insensitive)

2. **Level Calculation**:

   - Computed property from MPTT tree structure
   - Root categories have level 0
   - Child categories have level 1, 2, etc. based on depth

3. **System ID**:
   - Auto-generated UUID for system identifier

### Validation Rules

- **Code**: Required, unique, max 255 characters, primary key
- **Description**: Optional, unique (case-insensitive), max 255 characters, auto-uppercased
- **Parent ID**: Optional, must reference existing category code if provided
- **Duplicate Check**: Backend checks for existing category with same code or description
- **Unique Constraint**: Description must be unique per parent (`unique_together = ("description", "parent")`)

### Error Responses

```json
// Permission Denied (403)
{
  "error": "You do not have permission to create item categories"
}

// Validation Error (400)
{
  "code": ["Item category with this code already exists."]
}

// Duplicate Description (400)
{
  "description": ["This category already exists"]
}

// Missing Required Field (400)
{
  "code": ["This field is required."]
}

// Invalid Parent (400)
{
  "parent_id": ["Invalid pk \"INVALID\" - object does not exist."]
}
```

## Frontend Implementation (High-Level)

### Web Application Architecture

#### Component Structure

```
ItemCategoryModal.tsx (Modal Component)
  ├── Add/Edit Form Section
  │   ├── Code Input (required, disabled when editing)
  │   ├── Description Input (optional, auto-uppercased)
  │   └── Parent Category Select (optional)
  └── Categories List Section
      └── Hierarchical display of existing categories
```

#### Key Features

1. **Modal-Based Creation**:

   - Uses Dialog component for modal display
   - Inline form within modal
   - Shows existing categories in same modal
   - Can add, edit, and delete categories in one place

2. **Hierarchical Display**:

   - Categories displayed in tree structure
   - Indentation shows parent-child relationships
   - Level-based visual hierarchy

3. **Code as Primary Key**:

   - Code field is disabled when editing
   - Code cannot be changed after creation
   - Code must be unique

4. **Parent Selection**:

   - Dropdown shows all existing categories
   - Excludes current category from parent options (prevents circular references)
   - Optional - can create root categories

5. **Permission-Based UI**:
   - Modal access controlled by INSERT permission
   - Uses `usePermissions` hook to check `canCreate("Item Categories")`

#### Implementation Pattern

```typescript
// High-level flow
1. User opens ItemCategoryModal (from Items page or standalone)
2. Modal loads existing categories
3. User fills code and description
4. User optionally selects parent category
5. User clicks "Add" button
6. Form validates and submits POST /api/categories/
7. Response updates category list
8. Form resets for next entry
9. Success notification appears
```

### Mobile Application Architecture

#### Key Differences from Web

1. **Full-Screen Form**:

   - Mobile uses full-screen form or bottom sheet
   - Separate screen for category creation
   - Navigation-based flow

2. **Hierarchical Navigation**:

   - Navigate to parent category detail to create subcategory
   - Or create root category from main list
   - Tree view for browsing categories

3. **Manual Save**:
   - Mobile uses manual "Save" button (same as web)
   - All fields collected before submission
   - Single API call on save

#### Implementation Pattern

```typescript
// High-level flow
1. User taps "+" or "Add Category" button
2. Navigate to CategoryCreateScreen
3. Load existing categories for parent selection
4. User fills code and description
5. User optionally selects parent category
6. User taps "Save" button
7. Validate form
8. POST /api/categories/ with complete data
9. On success:
   - Navigate back to CategoryListScreen
   - Show success toast/notification
   - Refresh category list
10. On error:
    - Show error message
    - Keep form open for correction
```

## ItemCategory Model Fields

### Required Fields

- **code** (string, max 255 chars, unique, primary key): Category code/identifier

### Optional Fields

- **description** (string, max 255 chars, unique): Category description (auto-uppercased)
- **parent_id** (FK, code): Parent category reference (for subcategories)

### Auto-Generated Fields (Read-Only)

- **system_id** (UUID): System identifier
- **level** (integer): Tree level (0 = root, 1 = child, etc.) - computed from MPTT
- **created_at** (datetime): Creation timestamp
- **updated_at** (datetime): Last update timestamp

### Related Fields

- **attributes** (ManyToMany): Item attributes assigned to this category (managed separately)
- **children** (reverse relation): Child categories (via MPTT)

## Permission Requirements

### Backend Permission Check

- **Page Object ID**: `10204` (Item Categories)
- **Required Action**: `insert`
- **Check Location**: `ItemCategoryViewSet.create()` method

### Frontend Permission Check

- **Page Name**: `"Item Categories"` (must match Page Object name)
- **Check Method**: `canCreate("Item Categories")`
- **Hook**: `usePermissions()` from `@/hooks/usePermissions`

### Permission Flow

```
User Action
    ↓
Frontend: Check canCreate("Item Categories")
    ├─ If false → Hide create button/modal access
    └─ If true → Show create button/modal
        ↓
User clicks create
    ↓
API Request: POST /api/categories/
    ↓
Backend: Check user.check_object_permission(10204, "insert")
    ├─ If false → Return 403 Forbidden
    └─ If true → Create category
```

## Key Implementation Considerations

### 1. Code as Primary Key

- **Unique Identifier**: Code is the primary key, not a separate ID
- **Immutable**: Code cannot be changed after creation
- **Lookup Field**: API uses `code` for lookups (not `id` or `system_id`)
- **Format**: Typically uppercase alphanumeric (e.g., "CAT001", "ELECTRONICS")

### 2. Description Auto-Uppercase

- **Backend Processing**: Description is automatically converted to uppercase
- **Validation**: Duplicate check is case-insensitive
- **Frontend**: Can show lowercase in UI, but backend stores uppercase
- **Best Practice**: Frontend can auto-uppercase on input for consistency

### 3. Hierarchical Structure (MPTT)

- **Tree Structure**: Categories can have parent-child relationships
- **Unlimited Depth**: Can create multiple levels of subcategories
- **Root Categories**: Categories without parent are root categories (level 0)
- **Subcategories**: Categories with parent are subcategories (level 1+)
- **Tree Ordering**: Categories ordered by tree structure (`tree_id`, `lft`)

### 4. Parent Selection

- **Optional**: Parent category is optional
- **Validation**: Parent must exist if provided
- **Circular Prevention**: Cannot select self or descendants as parent
- **Use Case**: Organize categories hierarchically (e.g., Electronics > Phones > Smartphones)

### 5. Unique Constraints

- **Code**: Must be unique across all categories
- **Description**: Must be unique per parent (`unique_together = ("description", "parent")`)
- **Meaning**: Same description can exist under different parents, but not under same parent
- **Example**: "Phones" can exist under "Electronics" and "Accessories" separately

### 6. Attributes Assignment

- **ManyToMany Relationship**: Categories can have multiple attributes
- **Template Function**: Attributes assigned to category act as templates for items
- **Separate Management**: Attributes are managed separately (not in creation form)
- **Use Case**: All items in "T-Shirts" category can have "Color" and "Size" attributes

### 7. Code Immutability

- **Cannot Change**: Code field is disabled when editing
- **Reason**: Code is primary key and used in foreign key relationships
- **Workaround**: Delete and recreate if code change is needed (with caution)

### 8. Description Default

- **Auto-Fill**: If description is empty, frontend can auto-fill with code value
- **Backend**: Backend does not auto-fill, description can be empty
- **Best Practice**: Encourage users to provide meaningful descriptions

### 9. Category Deletion

- **Cascade Behavior**: Deleting parent category deletes all children (CASCADE)
- **Item Impact**: Items with deleted category will have null category
- **Warning**: Should warn users before deleting categories with children or items

### 10. Search and Filtering

- **Search**: Can search by code or description
- **Parent Filter**: Can filter by parent_id (use "0" for root categories)
- **Tree Ordering**: Results ordered by tree structure

## Error Handling

### Common Errors

1. **403 Forbidden**: User lacks INSERT permission

   - **Action**: Show permission error message
   - **UI**: Disable create button (should be hidden by permission check)

2. **400 Bad Request - Duplicate Code**:

   - **Action**: Show error on code field
   - **Message**: "Item category with this code already exists."
   - **Suggestion**: Allow user to edit code or cancel

3. **400 Bad Request - Duplicate Description**:

   - **Action**: Show error on description field
   - **Message**: "This category already exists"
   - **Note**: Check is case-insensitive and per parent

4. **400 Bad Request - Missing Required Field**:

   - **Action**: Show error on code field
   - **Message**: "This field is required."

5. **400 Bad Request - Invalid Parent**:

   - **Action**: Show error on parent_id field
   - **Message**: "Invalid pk \"{code}\" - object does not exist."
   - **Suggestion**: Refresh parent list or select valid parent

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

### After Category Creation

1. **Update Category List**: Refresh category list to show new category
2. **Reset Form**: Clear form fields for next entry
3. **Update Parent Dropdown**: Refresh parent options if needed
4. **Show Success**: Display success notification

### Implementation Pattern

```typescript
// After successful creation
const response = await ItemServices.createItemCategory(data);

// Update category list
await fetchCategories(); // Reload all categories

// Reset form
setNewCategory({ code: "", description: "", parent_id: null });

// Show success
toast.push(
  <Notification title="Success" type="success">
    Category created successfully
  </Notification>
);
```

## Mobile-Specific Considerations

### 1. Form Layout

- **Full-screen form**: Better for mobile UX
- **Bottom sheet**: Alternative for quick creation
- **Simple fields**: Code, description, parent selection
- **Scrollable**: Handle keyboard overlap

### 2. Input Types

- **Text inputs**: Standard text fields for code and description
- **Dropdown**: Native picker for parent category selection
- **Auto-uppercase**: Consider auto-uppercasing code and description on input

### 3. Hierarchical Navigation

- **Tree View**: Show categories in tree structure
- **Expandable**: Allow expanding/collapsing parent categories
- **Breadcrumbs**: Show path when creating subcategory
- **Parent Selection**: Navigate to parent detail to create child

### 4. Validation

- **Real-time**: Show errors as user types (optional)
- **On submit**: Validate all fields before API call
- **Error display**: Inline errors below fields
- **Duplicate check**: Consider checking for duplicates before submit (optional)

### 5. Offline Support (Future)

- **Queue requests**: Store creation requests if offline
- **Sync when online**: Submit queued requests
- **Conflict resolution**: Handle duplicate codes on sync

### 6. Performance

- **Lazy load**: Load parent categories only when needed
- **Search**: Implement search for large category lists
- **Tree optimization**: Use virtual scrolling for large trees
- **Caching**: Cache category list for faster access

## Testing Checklist

### Functional Tests

- [ ] Create category with only required field (code)
- [ ] Create category with code and description
- [ ] Create root category (no parent)
- [ ] Create subcategory (with parent)
- [ ] Verify duplicate code error handling
- [ ] Verify duplicate description error handling
- [ ] Verify permission check (403 for unauthorized users)
- [ ] Verify description auto-uppercase
- [ ] Verify form updates after creation
- [ ] Verify category list refresh after creation
- [ ] Verify hierarchical display works correctly
- [ ] Test multiple levels of nesting

### UI/UX Tests

- [ ] Create button visibility based on permissions
- [ ] Form validation messages display correctly
- [ ] Success notification appears
- [ ] Error messages are user-friendly
- [ ] Manual save works (web and mobile)
- [ ] Code field disabled when editing
- [ ] Parent dropdown excludes current category
- [ ] Hierarchical display shows correct indentation
- [ ] Form resets after successful creation

### Mobile-Specific Tests

- [ ] Form is scrollable
- [ ] Keyboard doesn't cover inputs
- [ ] Native input types work correctly
- [ ] Navigation after creation works
- [ ] Tree view works on mobile
- [ ] Parent selection works correctly
- [ ] Offline error handling (if implemented)

## API Service Methods

### ItemServices (Frontend)

```typescript
// Create item category
ItemServices.createItemCategory(data: Partial<ItemCategory>): Promise<ItemCategory>

// Get item categories (for refresh)
ItemServices.getItemCategories(params?: CategoryQueryParams): Promise<ItemCategory[]>

// Get single item category
ItemServices.getItemCategory(code: string): Promise<ItemCategory>

// Update item category
ItemServices.updateItemCategory(code: string, data: Partial<ItemCategory>): Promise<ItemCategory>

// Delete item category
ItemServices.deleteItemCategory(code: string): Promise<void>
```

### Usage Example

```typescript
// Create root category
const response = await ItemServices.createItemCategory({
  code: "CAT001",
  description: "Electronics",
});

// Create subcategory
const subcategory = await ItemServices.createItemCategory({
  code: "CAT002",
  description: "Phones",
  parent_id: "CAT001",
});

// Response includes all fields including computed ones
console.log(response.data.level); // 0 for root, 1 for child
```

## Related Endpoints

### Supporting Data Endpoints

- **Get Category Attributes**: `GET /api/categories/{code}/attributes/` (get attributes assigned to category)

### Category Management Endpoints

- **List Categories**: `GET /api/categories/`
- **Get Category**: `GET /api/categories/{code}/`
- **Create Category**: `POST /api/categories/`
- **Update Category**: `PUT /api/categories/{code}/`
- **Delete Category**: `DELETE /api/categories/{code}/`

### Query Parameters

- **parent_id**: Filter by parent (use "0" for root categories)
- **search**: Search by code or description

## Best Practices

### 1. Always Use Response Data

- **Don't assume**: Use data from API response
- **Computed fields**: `level` is computed, not sent
- **Auto-uppercase**: Description is auto-uppercased by backend

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
- **Tree navigation**: Provide intuitive tree navigation

### 5. Maintain Data Consistency

- **Refresh after creation**: Update category list
- **Reset form**: Clear form after successful creation
- **Handle errors**: Roll back optimistic updates on error

### 6. Code Management

- **Immutable Codes**: Never allow code changes after creation
- **Validation**: Validate code format (alphanumeric, uppercase)
- **Uniqueness**: Check for duplicate codes before submit (optional, for better UX)

### 7. Hierarchical Structure

- **Parent Selection**: Make parent selection intuitive
- **Tree Display**: Show clear visual hierarchy
- **Depth Limitation**: Consider limiting maximum depth (optional)
- **Circular Prevention**: Prevent selecting self or descendants as parent

### 8. Description Handling

- **Auto-Uppercase**: Consider auto-uppercasing in frontend for consistency
- **Default Value**: Auto-fill description with code if empty
- **Uniqueness**: Understand unique constraint (per parent)

### 9. Category Deletion

- **Warnings**: Warn before deleting categories with children or items
- **Cascade Impact**: Explain cascade deletion behavior
- **Confirmation**: Require confirmation for category deletion

### 10. Attributes Management

- **Separate Flow**: Manage attributes separately from category creation
- **Template Concept**: Explain that category attributes are templates
- **Item Inheritance**: Document how items inherit category attributes

## Summary

Item category creation in ZentroApp follows a standard CRUD pattern with these key features:

1. **Permission-based access**: INSERT permission required (Page Object ID: 10204)
2. **Code as primary key**: Unique, immutable identifier
3. **Hierarchical structure**: MPTT-based parent-child relationships
4. **Auto-uppercase description**: Description automatically converted to uppercase
5. **Manual save pattern**: Both web and mobile use manual save button
6. **Modal-based UI**: Web uses modal dialog for creation/editing
7. **Real-time updates**: Category list refreshes after creation
8. **Error handling**: Comprehensive validation and user-friendly error messages
9. **Attributes support**: Categories can have attributes assigned (managed separately)
10. **Tree structure**: Efficient hierarchical organization with unlimited depth

The implementation should focus on providing a smooth user experience while maintaining data integrity and respecting permission boundaries.

