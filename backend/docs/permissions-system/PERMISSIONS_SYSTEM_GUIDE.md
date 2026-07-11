# Permission System Guide - ZentroApp

## Overview

ZentroApp uses a **3-Layer Hybrid Access Control System** inspired by Microsoft Business Central, combining Role Centers for module visibility with Permission Sets for granular page-level access control.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│ LAYER 1: ROLE CENTER (Module Visibility)                │
│ Controls: Which modules show in sidebar                 │
│ Example: ["sales", "customers", "payments"]             │
│ Location: authentication.RoleCenter model               │
└──────────────────┬──────────────────────────────────────┘
                   ↓
         Sidebar shows: Sales, Customers, Payments
                   ↓
┌─────────────────────────────────────────────────────────┐
│ LAYER 2: PERMISSION SETS (Page Visibility)              │
│ Controls: Which pages within modules are accessible     │
│ Example: Only "Sales Dashboard" & "Sales History"       │
│ Location: permissions.PermissionSet model               │
└──────────────────┬──────────────────────────────────────┘
                   ↓
         Sales submenu shows: Dashboard, History only
                   ↓
┌─────────────────────────────────────────────────────────┐
│ LAYER 3: CRUD PERMISSIONS (Action Control)              │
│ Controls: What actions user can perform                 │
│ Example: Read ✓, Insert ✓, Modify ✗, Delete ✗         │
│ Location: permissions.PermissionSetLine model           │
└─────────────────────────────────────────────────────────┘
```

---

## Data Model

### User Access Hierarchy

```
User
  └─ User Groups (authentication.UserGroup)
      ├─ Default Profile (Role) → Role Center → Modules
      └─ Permission Sets → Permission Set Lines → Page Objects
```

### Key Models

#### 1. **RoleCenter** (`authentication/models.py`)

```python
class RoleCenter(models.Model):
    code = CharField(max_length=50, unique=True)
    name = CharField(max_length=100)
    description = TextField(blank=True)
    modules = JSONField(default=list)  # ["sales", "customers", "items"]
    features = JSONField(default=dict)
    dashboard_widgets = JSONField(default=list)
    is_active = BooleanField(default=True)
```

**Purpose**: Defines which **modules** appear in the sidebar navigation.

#### 2. **Role** (`authentication/models.py`)

```python
class Role(models.Model):
    name = CharField(max_length=100)
    description = TextField(blank=True)
    permissions = JSONField(default=list)  # Legacy module permissions
    role_center = ForeignKey(RoleCenter)  # Link to Role Center
    is_active = BooleanField(default=True)
```

**Purpose**: Links to a Role Center to define module access.

#### 3. **UserGroup** (`authentication/models.py`)

```python
class UserGroup(models.Model):
    code = CharField(max_length=50, unique=True)
    name = CharField(max_length=100)
    default_profile = ForeignKey(Role)  # The role for this group
    permission_sets = ManyToManyField(PermissionSet)  # Page permissions
    members = ManyToManyField(CustomUser)
    is_active = BooleanField(default=True)
```

**Purpose**: Groups users and assigns them a role + permission sets.

#### 4. **PermissionSet** (`permissions/models.py`)

```python
class PermissionSet(models.Model):
    code = CharField(max_length=50, unique=True)
    name = CharField(max_length=100)
    description = TextField(blank=True)
    is_active = BooleanField(default=True)
```

**Purpose**: A collection of page permissions (e.g., "SALES_FULL", "CUSTOMER_BASIC").

**Note**: Permission Sets are assigned to User Groups, **NOT** to Roles directly.

#### 5. **PermissionSetLine** (`permissions/models.py`)

```python
class PermissionSetLine(models.Model):
    permissionset = ForeignKey(PermissionSet)
    application_object = ForeignKey(Objects)  # The page object
    read_permission = BooleanField(default=False)
    insert_permission = BooleanField(default=False)
    modify_permission = BooleanField(default=False)
    delete_permission = BooleanField(default=False)
    execute_permission = BooleanField(default=False)
```

**Purpose**: Defines CRUD permissions for a specific page within a permission set.

#### 6. **Objects** (`base/models.py`)

```python
class Objects(models.Model):
    object_id = IntegerField(primary_key=True)
    object_type = CharField(max_length=100)  # "Page", "Table", "Report"
    object_name = CharField(max_length=255, unique=True)
    object_caption = CharField(max_length=255)
    object_subtype = CharField(max_length=50)
    app_label = CharField(max_length=255)  # Module code
    object_type_ref = ForeignKey(ObjectType)
    is_active = BooleanField(default=True)
    requires_permission = BooleanField(default=True)
```

**Purpose**: Defines application objects (Pages, Tables, Reports) that can be controlled by permissions.

---

## Page Object ID Ranges

Page objects use IDs in the 10000+ range:

| Range       | Module           | Example                               |
| ----------- | ---------------- | ------------------------------------- |
| 10001-10099 | Sales            | 10001: Sales Dashboard, 10002: Sales  |
| 10101-10199 | Customers        | 10101: Customer Management            |
| 10201-10299 | Items            | 10201: Items, 10202: Adjust Inventory |
| 10301-10399 | Purchases        | 10301: Purchases                      |
| 10401-10499 | Payments         | 10401: Payments                       |
| 10501-10599 | Financials       | 10501: Chart of Accounts              |
| 10601-10699 | Expenses         | 10601: Expenses                       |
| 10701-10799 | Company/Settings | 10701: Company Management             |

---

## JWT Token Structure

```json
{
  "username": "jom@hrpsolutions.com",
  "roles": ["Dispenser"],
  "user_groups": [
    {
      "code": "Dispenser",
      "name": "Dispenser",
      "default_role": "Dispenser",
      "permission_sets": ["SALES_FULL", "CUSTOMER_BASIC"]
    }
  ],
  "permission_sets": ["SALES_FULL", "CUSTOMER_BASIC"],
  "role_center_modules": ["sales", "customers", "payments"],
  "page_permissions": {
    "Sales Dashboard": {
      "read": true,
      "insert": false,
      "modify": false,
      "delete": false
    },
    "Customer Management": {
      "read": true,
      "insert": true,
      "modify": false,
      "delete": false
    }
  }
}
```

---

## Frontend Implementation

### 1. Navigation Filtering

**File**: `zentro-frontend/src/components/template/VerticalMenuContent/VerticalMenuContent.tsx`

```typescript
// 3-layer filtering:
// 1. Module enabled check (legacy)
// 2. Role center module check (Layer 1)
// 3. Page permission check (Layer 2)

if (nav.moduleCode && !isModuleVisible(nav.moduleCode)) {
  return false; // Hide if module not in role center
}

if (nav.pageName && !hasAnyPageAccess(nav.pageName)) {
  return false; // Hide if no page permission
}
```

### 2. Route Protection

**File**: `zentro-frontend/src/components/route/AppRoute.tsx`

```typescript
// Check page permission before rendering route
if (route.pageName) {
  const hasPermission = canAccessPage(route.pageName, "read");

  if (!hasPermission) {
    return <Navigate to="/access-denied" replace />;
  }
}
```

### 3. usePermissions Hook

**File**: `zentro-frontend/src/hooks/usePermissions.ts`

```typescript
// Module visibility (Layer 1)
const isModuleVisible = (moduleCode: string): boolean => {
  return user?.role_center_modules?.includes(moduleCode) || false;
};

// Page access (Layer 2)
const canAccessPage = (
  pageName: string,
  action: "read" | "insert" | "modify" | "delete"
): boolean => {
  const pagePermissions = user?.page_permissions?.[pageName];
  return pagePermissions?.[action] === true;
};

// Get all page permissions
const getPagePermissions = (pageName: string) => {
  return user?.page_permissions?.[pageName] || null;
};

// Check if user has ANY access to a page
const hasAnyPageAccess = (pageName: string): boolean => {
  const perms = getPagePermissions(pageName);
  return (
    perms?.read || perms?.insert || perms?.modify || perms?.delete || false
  );
};
```

### 4. Navigation Configuration

**File**: `zentro-frontend/src/configs/navigation.config/apps.navigation.config.ts`

```typescript
{
  key: "appsSales.salesHistory",
  path: `${APP_PREFIX_PATH}/sales/sales-history`,
  title: "Sales History",
  translateKey: "nav.appsSales.salesHistory",
  icon: "",
  type: NAV_ITEM_TYPE_ITEM,
  authority: [],
  pageName: "Sales History", // Maps to Page object
  subMenu: [],
}
```

### 5. Route Configuration

**File**: `zentro-frontend/src/configs/routes.config/appsRoute.ts`

```typescript
{
  key: "appsCustomers.customers",
  path: `${APP_PREFIX_PATH}/customers`,
  component: lazy(() => import("@/views/customers/Customers")),
  authority: [],
  pageName: "Customer Management", // Maps to Page object for permission check
  meta: {
    header: "Customer Management",
  },
}
```

---

## Backend Implementation

### 1. JWT Token Generation

**File**: `zentro-backend/authentication/serializers.py`

```python
# Add page-level permissions to JWT token
page_permissions = {}

for group in user.user_groups.filter(is_active=True):
    for perm_set in group.permission_sets.filter(is_active=True):
        page_lines = perm_set.permissionsetline_set.filter(
            application_object__object_type="Page"
        )

        for line in page_lines:
            page_name = line.application_object.object_name

            if page_name not in page_permissions:
                page_permissions[page_name] = {
                    "read": False,
                    "insert": False,
                    "modify": False,
                    "delete": False,
                }

            # OR logic - if any permission set grants access, user has it
            page_permissions[page_name]["read"] = (
                page_permissions[page_name]["read"] or line.read_permission
            )
            page_permissions[page_name]["insert"] = (
                page_permissions[page_name]["insert"] or line.insert_permission
            )
            page_permissions[page_name]["modify"] = (
                page_permissions[page_name]["modify"] or line.modify_permission
            )
            page_permissions[page_name]["delete"] = (
                page_permissions[page_name]["delete"] or line.delete_permission
            )

token["page_permissions"] = page_permissions
```

### 2. API Permission Checks

**File**: `zentro-backend/sales/views.py`

```python
class CustomerViewSet(viewsets.ModelViewSet):
    """
    Customer ViewSet with granular page permissions
    Page ID: 10101 (Customer Management Page)
    """

    def list(self, request, *args, **kwargs):
        """List customers - requires READ permission"""
        has_permission, source = request.user.check_object_permission(10101, "read")
        if not has_permission:
            return Response({
                "error": "Insufficient permissions",
                "detail": "You need read permission to view customers"
            }, status=status.HTTP_403_FORBIDDEN)
        return super().list(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        """Create customer - requires INSERT permission"""
        has_permission, source = request.user.check_object_permission(10101, "insert")
        if not has_permission:
            return Response({
                "error": "Insufficient permissions",
                "detail": "You need insert permission to create customers"
            }, status=status.HTTP_403_FORBIDDEN)
        return super().create(request, *args, **kwargs)
```

**Note**: Use **Page Object IDs** (10xxx), not Table IDs (2xxx).

---

## Management Commands

### 1. Populate Page Objects

**File**: `base/management/commands/populate_page_objects.py`

**Usage**:

```bash
# For specific tenant
python manage.py tenant_command populate_page_objects --schema=hardwareworld

# Or use the helper script
cd zentro-backend
python -c "from django.db import connection; connection.set_schema('ekk'); from django.core.management import call_command; call_command('populate_page_objects')"
```

**What it does**: Creates Page objects for all routes in the system (Sales Dashboard, Customer Management, etc.)

### 2. Setup Page Permissions

**File**: `permissions/management/commands/setup_page_permissions.py`

**Usage**:

```bash
# For specific tenant
python manage.py tenant_command setup_page_permissions --schema=hardwareworld

# Or use the helper script
cd zentro-backend
python -c "from django.db import connection; connection.set_schema('ekk'); from django.core.management import call_command; call_command('setup_page_permissions')"
```

**What it does**: Creates default permission sets with page-level permissions (SALES_FULL, CUSTOMER_BASIC, etc.)

---

## Available Permission Sets

### Sales

- **SALES_FULL**: All sales pages, full CRUD access
- **SALES_BASIC**: Dashboard + New Sale (create only)
- **SALES_HISTORY_ONLY**: Dashboard + History (view only)

### Customers

- **CUSTOMER_FULL**: Full CRUD access
- **CUSTOMER_BASIC**: View + Create only
- **CUSTOMER_VIEW_ONLY**: Read-only access

### Items

- **ITEMS_FULL**: Full inventory management
- **ITEMS_VIEW_ONLY**: View only

### Purchases

- **PURCHASES_FULL**: Full CRUD
- **PURCHASES_CREATE**: Create only

### Payments

- **PAYMENTS_FULL**: Full CRUD
- **PAYMENTS_VIEW_ONLY**: View only

### Financials

- **FINANCIALS_FULL**: Full access
- **FINANCIALS_VIEW_ONLY**: Reports only

### Expenses

- **EXPENSES_FULL**: Full CRUD
- **EXPENSES_CREATE**: Create only

---

## How To Use (Admin Guide)

### Scenario 1: Give User Access to Sales Module Only

1. **Go to**: `http://ekk.localhost:8000/admin/authentication/usergroup/`
2. **Create/Edit User Group**: "Sales Team"
3. **Set**:
   - Default Profile: Select "Sales" role
   - Permission Sets: Select "SALES_FULL"
   - Members: Add users
4. **Save**

**Result**:

- Sidebar shows: Sales module only
- Sales submenu shows: All 4 sales pages
- Full CRUD access on all sales pages

### Scenario 2: Give User Limited Sales Access (View History Only)

1. **Create/Edit User Group**: "Sales Auditor"
2. **Set**:
   - Default Profile: Select a role with Role Center containing "sales"
   - Permission Sets: Select "SALES_HISTORY_ONLY"
3. **Save**

**Result**:

- Sidebar shows: Sales module
- Sales submenu shows: Only "Sales Dashboard" and "Sales History"
- "New Sale" and "Sales Invoice" are hidden
- Read-only access (no create/edit/delete)

### Scenario 3: Multi-Module Access with Different Permission Levels

1. **Create/Edit User Group**: "Dispenser"
2. **Set**:
   - Default Profile: "Dispenser" role (with Role Center: ["sales", "customers", "items"])
   - Permission Sets: Select multiple:
     - "SALES_BASIC" (create sales only)
     - "CUSTOMER_BASIC" (view and create customers)
     - "ITEMS_VIEW_ONLY" (view items only)
3. **Save**

**Result**:

- Sidebar shows: Sales, Customers, Items
- Sales: Dashboard + New Sale only (can create)
- Customers: Full page (can view and create, no edit/delete)
- Items: Full page (view only, no create/edit/delete)

---

## Adding a New Module - Step by Step

### Step 1: Create Page Objects

**File**: `base/management/commands/populate_page_objects.py`

Add to `pages_to_create` list:

```python
# ============================================
# NEW MODULE PAGES (IDs: 10801-10899)
# ============================================
(
    10801,
    "My New Module",
    "mymodule",  # module code
    "Main page for my new module",
    "/app/mymodule",
),
```

Run: `python manage.py tenant_command populate_page_objects --schema=hardwareworld`

### Step 2: Create Permission Sets

**File**: `permissions/management/commands/setup_page_permissions.py`

Add to `permission_sets_config` list:

```python
(
    "MYMODULE_FULL",
    "My Module - Full Access",
    "Complete access to my module",
    [
        ("My New Module", "RIMD"),  # R=Read, I=Insert, M=Modify, D=Delete
    ],
),
(
    "MYMODULE_VIEW_ONLY",
    "My Module - View Only",
    "Read-only access to my module",
    [
        ("My New Module", "R"),
    ],
),
```

Run: `python manage.py tenant_command setup_page_permissions --schema=hardwareworld`

### Step 3: Add to Role Center

1. Go to Django Admin: `http://ekk.localhost:8000/admin/authentication/rolecenter/`
2. Edit the Role Center
3. Add `"mymodule"` to the `modules` array:
   ```json
   ["sales", "customers", "items", "mymodule"]
   ```
4. Save

### Step 4: Add Frontend Navigation

**File**: `zentro-frontend/src/configs/navigation.config/apps.navigation.config.ts`

```typescript
{
  key: "apps.mymodule",
  path: "",
  title: "My Module",
  translateKey: "nav.appsMyModule.mymodule",
  icon: "mymodule", // Add icon to navigation-icon.config.tsx
  type: NAV_ITEM_TYPE_COLLAPSE,
  authority: [],
  moduleCode: "mymodule", // Layer 1: Role center filtering
  subMenu: [
    {
      key: "appsMyModule.mymodule",
      path: `${APP_PREFIX_PATH}/mymodule`,
      title: "My Module",
      translateKey: "nav.appsMyModule.mymodule",
      icon: "",
      type: NAV_ITEM_TYPE_ITEM,
      authority: [],
      pageName: "My New Module", // Layer 2: Page permission filtering
      subMenu: [],
    },
  ],
}
```

### Step 5: Add Frontend Route

**File**: `zentro-frontend/src/configs/routes.config/appsRoute.ts`

```typescript
{
  key: "appsMyModule.mymodule",
  path: `${APP_PREFIX_PATH}/mymodule`,
  component: lazy(() => import("@/views/mymodule/MyModule")),
  authority: [],
  pageName: "My New Module", // Route protection
  meta: {
    header: "My Module",
  },
}
```

### Step 6: Add Icon

**File**: `zentro-frontend/src/configs/navigation-icon.config.tsx`

```typescript
import { HiOutlineNewIcon } from "react-icons/hi";

const navigationIcon: NavigationIcons = {
  // ... existing icons
  mymodule: <HiOutlineNewIcon />,
};
```

### Step 7: Create Backend API with Page Permission Checks

**File**: `mymodule/views.py`

```python
from authentication.decorators import require_object_permission

class MyModuleViewSet(viewsets.ModelViewSet):
    """
    My Module ViewSet with page permissions
    Page ID: 10801 (My New Module Page)
    """

    def list(self, request, *args, **kwargs):
        has_permission, source = request.user.check_object_permission(10801, "read")
        if not has_permission:
            return Response({
                "error": "Insufficient permissions"
            }, status=status.HTTP_403_FORBIDDEN)
        return super().list(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        has_permission, source = request.user.check_object_permission(10801, "insert")
        if not has_permission:
            return Response({
                "error": "Insufficient permissions"
            }, status=status.HTTP_403_FORBIDDEN)
        return super().create(request, *args, **kwargs)
```

### Step 8: Add to Home Page (Optional)

**File**: `zentro-frontend/src/views/Home/Home.tsx`

```typescript
const allModules = [
  // ... existing modules
  {
    code: "mymodule",
    title: "My Module",
    description: "Description of my module",
    icon: HiOutlineNewIcon,
    path: "/app/mymodule",
    pageName: "My New Module",
    color: "text-purple-600 bg-purple-100 hover:bg-purple-200",
  },
];
```

---

## Testing Checklist

### ✅ Layer 1: Module Visibility

- [ ] Module shows in sidebar when in role center
- [ ] Module hidden when not in role center
- [ ] Module shows on home page when in role center

### ✅ Layer 2: Page Visibility

- [ ] Pages show in submenu when permission set grants access
- [ ] Pages hidden when no permission set
- [ ] Direct URL redirects to /access-denied when no permission
- [ ] Home page card shows when permission set grants access

### ✅ Layer 3: CRUD Control

- [ ] Create button shows when insert permission = true
- [ ] Edit button shows when modify permission = true
- [ ] Delete button shows when delete permission = true
- [ ] Buttons hidden when permissions = false
- [ ] API returns 403 when user lacks permission

---

## Common Issues & Solutions

### Issue: Module shows in sidebar but clicking gives "Access Denied"

**Cause**: User has module in role center but no page permissions.

**Solution**: Assign a permission set for that module's pages to the user group.

### Issue: User can access page via direct URL even without permission

**Cause**: Route doesn't have `pageName` field.

**Solution**: Add `pageName` to the route in `appsRoute.ts`.

### Issue: Permission set doesn't show up in JWT token

**Cause**: Permission set not assigned to user group.

**Solution**: Go to Django Admin → User Groups → Edit group → Add permission set.

### Issue: All modules hidden even though user has role center access

**Cause**: No permission sets assigned, so page filtering blocks everything.

**Solution**: Assign appropriate permission sets to the user group.

---

## Architecture Decisions

### Why Page Objects Instead of Table Objects?

**Decision**: Use Page objects that map to frontend routes/components.

**Reason**:

- Your architecture uses ONE page per module (e.g., `/app/customers` handles all customer CRUD)
- Easier to understand: "Can user access Customer Management page?"
- Clearer admin experience: Permission names match what users see
- Simpler implementation: One page = one permission object

### Why Permission Sets on User Groups, Not Roles?

**Decision**: Removed `linked_role` from PermissionSet. Permission sets are only assigned to User Groups.

**Reason**:

- Eliminates redundancy: User Group already has a default_profile (role)
- Cleaner data model: `User → Group → Role + Permission Sets`
- Matches Business Central pattern
- Easier to manage: Change group permissions, all members update

### Why 3 Layers Instead of 2 or 1?

**Decision**: Use hybrid approach with Role Centers AND Permission Sets.

**Reason**:

- **Layer 1 (Role Center)**: Quick module-level access control (already working)
- **Layer 2 (Permission Sets)**: Granular page-level control (just added)
- **Layer 3 (CRUD)**: Fine-grained action control (already working)
- Separation of concerns: Module visibility vs Page access vs Action permissions
- Flexibility: Can use just Layer 1, or Layer 1+2, or all 3 layers

---

## Maintenance

### When Adding a New Page to Existing Module

1. Add page object (populate_page_objects.py)
2. Add to relevant permission sets (setup_page_permissions.py)
3. Add to navigation config with `pageName`
4. Add to routes config with `pageName`
5. Run the management commands

### When Creating a New Permission Set

1. Add to `setup_page_permissions.py`
2. Run command
3. Assign to user groups in Django Admin

### When Updating Role Centers

1. Edit in Django Admin
2. Users logout/login to refresh JWT token
3. Navigation updates automatically

---

## Quick Reference

### User Access Flow

```
1. User logs in
2. JWT token generated with:
   - role_center_modules (from User Group → Role → Role Center)
   - page_permissions (from User Group → Permission Sets → Permission Set Lines)
3. Frontend stores in Redux
4. Navigation filtered by:
   - moduleCode + isModuleVisible() → Layer 1
   - pageName + hasAnyPageAccess() → Layer 2
5. Routes protected by:
   - AppRoute checks pageName permission
6. UI elements controlled by:
   - getPagePermissions() → shows/hides buttons
```

### Permission Check Quick Reference

```typescript
// Module visible?
isModuleVisible("sales"); // true/false

// Page accessible?
canAccessPage("Customer Management", "read"); // true/false

// Can create on page?
canAccessPage("Customer Management", "insert"); // true/false

// Can edit on page?
canAccessPage("Customer Management", "modify"); // true/false

// Get all page permissions
getPagePermissions("Customer Management"); // { read, insert, modify, delete }

// Has any access to page?
hasAnyPageAccess("Customer Management"); // true/false
```

---

## Files Modified Summary

### Backend (8 files)

1. `base/models.py` - Objects model (page objects)
2. `permissions/models.py` - Removed linked_role field
3. `permissions/admin.py` - Removed linked_role from admin
4. `authentication/models.py` - Updated get_all_permission_sets()
5. `authentication/serializers.py` - JWT includes page_permissions
6. `authentication/admin.py` - Removed roles field from user admin
7. `sales/views.py` - Updated to use page IDs (10101, 10002)
8. `base/management/commands/populate_page_objects.py` - NEW
9. `permissions/management/commands/setup_page_permissions.py` - NEW

### Frontend (9 files)

1. `@types/auth.ts` - Added PagePermissions interface
2. `@types/routes.ts` - Added pageName to Route type
3. `@types/navigation.ts` - Added pageName to NavigationTree
4. `store/slices/auth/userSlice.ts` - Added page_permissions to state
5. `utils/hooks/useAuth.ts` - Populate page_permissions from JWT
6. `hooks/usePermissions.ts` - Added canAccessPage, getPagePermissions, hasAnyPageAccess
7. `configs/navigation.config/apps.navigation.config.ts` - Added pageName to all nav items
8. `configs/routes.config/appsRoute.ts` - Added pageName to all routes
9. `components/route/AppRoute.tsx` - Added page permission check
10. `views/Views.tsx` - Pass pageName to AppRoute
11. `components/template/VerticalMenuContent/VerticalMenuContent.tsx` - Filter by pageName
12. `views/Home/Home.tsx` - Filter quick access by page permissions
13. `configs/navigation-icon.config.tsx` - Added home, customers, chart-bar icons

---

## Production Deployment Checklist

- [ ] Run `populate_page_objects` for all tenants
- [ ] Run `setup_page_permissions` for all tenants
- [ ] Migrate database (removes linked_role field)
- [ ] Assign permission sets to existing user groups
- [ ] Test with different user roles
- [ ] Verify direct URL protection works
- [ ] Verify sidebar filtering works
- [ ] Verify home page filtering works
- [ ] Verify API 403 errors for unauthorized access

---

**Last Updated**: October 25, 2025  
**Version**: 1.0  
**Status**: Production Ready ✅
