# Permissions Implementation Guide

## Overview

This guide explains how to implement the 3-layer permission system in ZentroApp for any module. This is a **general guide** that can be applied to any new module or feature.

## Permission System Architecture

ZentroApp uses a **3-Layer Hybrid Access Control System** inspired by Microsoft Business Central:

```
┌─────────────────────────────────────────────────────────┐
│ LAYER 1: ROLE CENTER (Module Visibility)                │
│ Controls: Which modules show in sidebar                 │
│ Example: ["sales", "customers", "expenses"]             │
│ Location: authentication.RoleCenter model               │
└──────────────────┬──────────────────────────────────────┘
                   ↓
         Sidebar shows: Sales, Customers, Expenses
                   ↓
┌─────────────────────────────────────────────────────────┐
│ LAYER 2: PERMISSION SETS (Page Visibility)              │
│ Controls: Which pages within modules are accessible     │
│ Example: Only "Expenses" page (not "Expense Setup")     │
│ Location: permissions.PermissionSet model               │
└──────────────────┬──────────────────────────────────────┘
                   ↓
         Expenses submenu shows: Expenses only
                   ↓
┌─────────────────────────────────────────────────────────┐
│ LAYER 3: CRUD PERMISSIONS (Action Control)              │
│ Controls: What actions user can perform                 │
│ Example: Can read and create, but not edit/delete        │
│ Location: permissions.PermissionSetLine model            │
└─────────────────────────────────────────────────────────┘
```

## Implementation Steps for Any Module

### Step 1: Create Page Objects

**File**: `base/management/commands/populate_page_objects.py`

Add page objects to the `pages_to_create` list:

```python
# Format: (object_id, name, module_code, description, route)
(
    10601,  # Use appropriate ID range (see ID ranges below)
    "Expenses",  # Page name (must match frontend pageName)
    "expenses",  # Module code (must match frontend moduleCode)
    "Expense tracking and management",  # Description
    "/app/expenses",  # Frontend route
),
```

**Page Object ID Ranges:**

- **10001-10099**: Sales module
- **10101-10199**: Customers module
- **10201-10299**: Items module
- **10301-10399**: Purchases module
- **10401-10499**: Payments module
- **10501-10599**: Financials module
- **10601-10699**: Expenses module
- **10701-10799**: Company/Settings
- **10801-10899**: Available for new modules

**Command to run:**

```bash
python manage.py tenant_command populate_page_objects --schema=<tenant_schema>
```

### Step 2: Create Permission Sets

**File**: `permissions/management/commands/setup_page_permissions.py`

Add permission sets to the `permission_sets_config` list:

```python
# Format: (code, name, description, [(page_name, permissions)])
(
    "MODULE_FULL",  # Permission set code (uppercase, underscore)
    "Module - Full Access",  # Display name
    "Complete access to module features",  # Description
    [
        ("Page Name", "RIMD"),  # R=Read, I=Insert, M=Modify, D=Delete
    ],
),
(
    "MODULE_CREATE",
    "Module - Create Only",
    "Can create records but not edit/delete",
    [
        ("Page Name", "RI"),  # Read and Insert only
    ],
),
(
    "MODULE_VIEW_ONLY",
    "Module - View Only",
    "Read-only access to module",
    [
        ("Page Name", "R"),  # Read only
    ],
),
```

**Permission String Format:**

- `"R"` = Read permission
- `"I"` = Insert (Create) permission
- `"M"` = Modify (Update) permission
- `"D"` = Delete permission
- `"RIMD"` = Full access
- `"RI"` = Can read and create
- `"R"` = Read-only
- `""` = No access (page won't appear)

**Command to run:**

```bash
python manage.py tenant_command setup_page_permissions --schema=<tenant_schema>
```

### Step 3: Add Module to Role Center

1. Go to Django Admin: `http://<tenant>.localhost:8000/admin/authentication/rolecenter/`
2. Edit the Role Center
3. Add module code to the `modules` array:
   ```json
   ["sales", "customers", "items", "expenses"]
   ```
4. Save

**Note**: The module code must match the `moduleCode` in frontend navigation config.

### Step 4: Frontend Navigation Configuration

**File**: `zentro-frontend/src/configs/navigation.config/apps.navigation.config.ts`

Add navigation item with **both** `moduleCode` and `pageName`:

```typescript
{
  key: "apps.module",
  path: "/module",
  title: "Module Name",
  translateKey: "nav.appsModule.module",
  icon: "module",
  type: NAV_ITEM_TYPE_COLLAPSE,
  authority: [],
  moduleCode: "module", // REQUIRED: For Layer 1 (module visibility)
  subMenu: [
    {
      key: "appsModule.page",
      path: `${APP_PREFIX_PATH}/module`,
      title: "Page Title",
      translateKey: "nav.appsModule.page",
      icon: "",
      type: NAV_ITEM_TYPE_ITEM,
      authority: [],
      pageName: "Page Name", // REQUIRED: For Layer 2 (page visibility)
      // Must match the page name in populate_page_objects.py
      subMenu: [],
    },
  ],
}
```

**Critical Requirements:**

- ✅ **MUST include** `moduleCode` for Layer 1 filtering
- ✅ **MUST include** `pageName` for Layer 2 filtering
- ❌ **DO NOT** omit either field

### Step 5: Frontend Route Configuration

**File**: `zentro-frontend/src/configs/routes.config/appsRoute.ts`

Add route with `pageName` for route protection:

```typescript
{
  key: "appsModule.page",
  path: `${APP_PREFIX_PATH}/module`,
  component: lazy(() => import("@/views/module/Page")),
  authority: [],
  pageName: "Page Name", // REQUIRED: For route protection
  // Must match the page name in populate_page_objects.py
}
```

### Step 6: Frontend Permission Checks

**File**: `zentro-frontend/src/views/module/Page.tsx`

Use the `usePermissions` hook:

```typescript
import { usePermissions } from "@/hooks/usePermissions";

function ModulePage() {
  const { canCreate, canEdit, canDelete, canAccessPage } = usePermissions();
  const PAGE_NAME = "Page Name"; // Must match page object name

  // Check if user can access the page at all
  const hasAccess = canAccessPage(PAGE_NAME, "read");
  if (!hasAccess) {
    return <div>Access Denied</div>;
  }

  // Check specific actions
  const showCreateButton = canCreate(PAGE_NAME);
  const showEditButton = canEdit(PAGE_NAME);
  const showDeleteButton = canDelete(PAGE_NAME);

  return (
    <>
      {showCreateButton && <Button onClick={handleCreate}>Create</Button>}
      {showEditButton && <EditButton />}
      {showDeleteButton && <DeleteButton />}
    </>
  );
}
```

**Available Permission Methods:**

- `canAccessPage(pageName, action)` - Check specific action (read, insert, modify, delete)
- `canCreate(pageName)` - Check create permission
- `canEdit(pageName)` - Check edit permission
- `canDelete(pageName)` - Check delete permission
- `hasAnyPageAccess(pageName)` - Check if user has any access to page
- `getPagePermissions(pageName)` - Get all permissions for a page

### Step 7: Backend API Protection

**File**: `zentro-backend/module/views.py`

Add permission checks to ViewSet:

```python
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.authentication import SessionAuthentication

class ModuleViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Module model with permission checks.
    """

    # REQUIRED: Set the Page Object ID (from populate_page_objects.py)
    PAGE_OBJECT_ID = 10601  # Replace with your page object ID

    queryset = Model.objects.all()
    serializer_class = ModelSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication, SessionAuthentication]

    # ------------------------------------------------------------------
    # Permission helpers
    # ------------------------------------------------------------------
    def _has_permission(self, user, action: str):
        """Check if user has permission for the action"""
        has_permission, source = user.check_object_permission(
            self.PAGE_OBJECT_ID, action
        )
        return has_permission, source

    def _deny(self, source, detail):
        """Return permission denied response"""
        return Response(
            {
                "error": "Insufficient permissions",
                "detail": detail,
                "reason": source
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    # ------------------------------------------------------------------
    # CRUD overrides with permission checks
    # ------------------------------------------------------------------
    def list(self, request, *args, **kwargs):
        """List all records - requires read permission"""
        allowed, source = self._has_permission(request.user, "read")
        if not allowed:
            return self._deny(source, "You need read permission to view records.")
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        """Get single record - requires read permission"""
        allowed, source = self._has_permission(request.user, "read")
        if not allowed:
            return self._deny(source, "You need read permission to view records.")
        return super().retrieve(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        """Create new record - requires insert permission"""
        allowed, source = self._has_permission(request.user, "insert")
        if not allowed:
            return self._deny(source, "You need insert permission to create records.")
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        """Update record - requires modify permission"""
        allowed, source = self._has_permission(request.user, "modify")
        if not allowed:
            return self._deny(source, "You need modify permission to update records.")
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        """Partial update - requires modify permission"""
        allowed, source = self._has_permission(request.user, "modify")
        if not allowed:
            return self._deny(source, "You need modify permission to update records.")
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        """Delete record - requires delete permission"""
        allowed, source = self._has_permission(request.user, "delete")
        if not allowed:
            return self._deny(source, "You need delete permission to remove records.")
        return super().destroy(request, *args, **kwargs)

    # ------------------------------------------------------------------
    # Custom actions with permission checks
    # ------------------------------------------------------------------
    @action(detail=True, methods=["post"])
    def custom_action(self, request, pk=None):
        """Custom action - requires appropriate permission"""
        allowed, source = self._has_permission(request.user, "modify")
        if not allowed:
            return self._deny(source, "You need modify permission for this action.")

        # Your custom action logic here
        return Response({"message": "Action completed"})
```

**Important Notes:**

- ✅ Use **Page Object IDs** (10xxx range), NOT Table Object IDs (2xxx range)
- ✅ Always check permissions in all CRUD methods
- ✅ Check permissions in custom actions too
- ✅ Return consistent error format with `_deny()` helper

### Step 8: Assign Permission Sets to User Groups

1. Go to Django Admin: `http://<tenant>.localhost:8000/admin/authentication/usergroup/`
2. Edit a User Group
3. In the "Permission Sets" field, select the appropriate permission sets
4. Save

**Users in that group will automatically inherit the permissions.**

## Permission Check Flow

```
User Request
    ↓
Frontend Route Check (AppRoute.tsx)
    ├─ Checks: hasAnyPageAccess(pageName)
    └─ If no access → Redirect or show error
    ↓
Frontend Component Check (usePermissions hook)
    ├─ Checks: canCreate(pageName), canEdit(pageName), etc.
    └─ Hides/shows buttons based on permissions
    ↓
API Request Sent
    ↓
Backend ViewSet Permission Check
    ├─ Checks: user.check_object_permission(PAGE_OBJECT_ID, action)
    └─ If no permission → Returns 403 Forbidden
    ↓
Business Logic Executes
```

## Common Patterns

### Pattern 1: Full CRUD Module

**Permission Sets:**

- `MODULE_FULL` - RIMD access
- `MODULE_VIEW_ONLY` - R access only

**Use Case:** Standard module with full functionality

### Pattern 2: Create-Only Module

**Permission Sets:**

- `MODULE_CREATE` - RI access (can create, view, but not edit/delete)
- `MODULE_VIEW_ONLY` - R access only

**Use Case:** Users can submit records but not modify them

### Pattern 3: Multi-Page Module

**Permission Sets:**

- `MODULE_FULL` - RIMD on all pages
- `MODULE_BASIC` - RIMD on main page, R only on reports
- `MODULE_REPORTS_ONLY` - R only on report pages

**Use Case:** Module with main page and separate report pages

## Testing Permissions

### Test Checklist

1. **Module Visibility (Layer 1)**

   - [ ] Module appears in sidebar for users with module in role center
   - [ ] Module hidden for users without module in role center

2. **Page Visibility (Layer 2)**

   - [ ] Page appears in navigation for users with page permission
   - [ ] Page hidden for users without page permission
   - [ ] Direct URL access blocked for users without permission

3. **Action Permissions (Layer 3)**
   - [ ] Create button visible/hidden based on insert permission
   - [ ] Edit button visible/hidden based on modify permission
   - [ ] Delete button visible/hidden based on delete permission
   - [ ] API returns 403 for unauthorized actions

### Test User Setup

1. Create test user
2. Assign to User Group with specific permission set
3. Login and verify:
   - Navigation visibility
   - Button visibility
   - API access

## Troubleshooting

### Module Not Showing in Sidebar

**Check:**

- ✅ Role Center includes module code in `modules` array
- ✅ User's role center is assigned to their user group
- ✅ Frontend navigation includes `moduleCode` field

### Page Not Showing in Navigation

**Check:**

- ✅ Page object exists in database
- ✅ Permission set includes the page
- ✅ User group has the permission set assigned
- ✅ Frontend navigation includes `pageName` field

### API Returns 403 Forbidden

**Check:**

- ✅ Page Object ID is correct in ViewSet
- ✅ Permission set has the required permission (R/I/M/D)
- ✅ User group has the permission set assigned
- ✅ User is authenticated

### Buttons Not Showing/Hiding

**Check:**

- ✅ Component uses `usePermissions` hook
- ✅ `PAGE_NAME` matches page object name exactly
- ✅ Permission checks use correct method (`canCreate`, `canEdit`, etc.)

## Important Rules

1. **Page Object IDs** (10xxx) are for backend permission checks
2. **Table Object IDs** (2xxx) are for legacy code - DO NOT use for new modules
3. **Permission Sets belong to User Groups**, not Roles or Users directly
4. **Users inherit permissions** from their User Groups
5. **Navigation requires both** `moduleCode` and `pageName`
6. **Routes require** `pageName` for protection
7. **Backend must check** permissions in all CRUD methods

## Files Reference

### Backend Files:

- `base/management/commands/populate_page_objects.py` - Page objects
- `permissions/management/commands/setup_page_permissions.py` - Permission sets
- `authentication/models.py` - RoleCenter model
- `permissions/models.py` - PermissionSet, PermissionSetLine models
- `module/views.py` - ViewSet with permission checks

### Frontend Files:

- `src/configs/navigation.config/apps.navigation.config.ts` - Navigation
- `src/configs/routes.config/appsRoute.ts` - Routes
- `src/hooks/usePermissions.ts` - Permission hooks
- `src/components/route/AppRoute.tsx` - Route protection
- `src/components/shared/VerticalMenuContent.tsx` - Navigation filtering

## Quick Reference

```python
# Backend Permission Check
PAGE_OBJECT_ID = 10601
has_permission, source = request.user.check_object_permission(PAGE_OBJECT_ID, "read")
```

```typescript
// Frontend Permission Check
const { canCreate, canEdit, canDelete } = usePermissions();
const PAGE_NAME = "Expenses";
const showCreate = canCreate(PAGE_NAME);
```

```python
# Permission Set Format
("CODE", "Name", "Description", [("Page Name", "RIMD")])
```

```typescript
// Navigation Format
{
  moduleCode: "expenses",  // Layer 1
  subMenu: [{
    pageName: "Expenses",  // Layer 2
  }]
}
```
