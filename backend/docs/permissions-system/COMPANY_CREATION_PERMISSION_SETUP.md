# Company Creation - Permission System Setup

## Overview

This document outlines all the automatic setup steps that occur during company creation to ensure the permission system is properly configured.

---

## **Company Creation Flow (Updated)**

### **Progress: 68% - Creating Default Roles**

```python
create_default_roles(company.schema_name)
```

**Creates 7 default roles:**

- Admin (full access)
- Manager (comprehensive access)
- Sales (sales & customer access)
- Cashier (POS access)
- Inventory (stock management)
- Accountant (financial access)
- User (view-only access)

---

### **Progress: 69% - Creating Default Role Centers**

```python
call_command("setup_default_role_centers")
```

**Creates 7 role centers:**

- Admin Center (all 12 modules)
- Manager Center (11 modules - all except profile)
- Accountant Center (financials, expenses, payments, reports)
- Sales Center (sales, customers, items, reports)
- Cashier Center (sales, customers, items)
- Inventory Center (items, purchases, sales reports)
- User Center (view-only access to sales, customers, items)

**Links role centers to roles:**

- Each Role has a `role_center` ForeignKey pointing to its RoleCenter

---

### **Progress: 70% - Setting Up Page Objects** ✨ **NEW**

```python
call_command("populate_page_objects")
```

**Creates 17 Page Objects** with IDs in 10xxx range:

- **Sales Module** (10001-10004):

  - Sales Dashboard (10001)
  - Sales (10002)
  - Sales Invoice Page (10003)
  - Sales History (10004)

- **Customer Module** (10101):

  - Customer Management (10101)

- **Items Module** (10201-10203):

  - Items (10201)
  - Adjust Inventory (10202)
  - Adjust Inventory History (10203)

- **Purchases Module** (10301):

  - Purchases (10301)

- **Payments Module** (10401):

  - Payments (10401)

- **Financials Module** (10501-10503):

  - Chart of Accounts (10501)
  - Financial Reports (10502)
  - Profit & Loss (10503)

- **Expenses Module** (10601):

  - Expenses (10601)

- **Other Modules** (10701-10703):
  - Company Management (10701)
  - Role Management (10702)
  - Profile Settings (10703)

---

### **Progress: 71% - Setting Up Permission Sets** ✨ **NEW**

```python
call_command("setup_page_permissions")
```

**Creates 19 Permission Sets:**

**Sales Permissions (5 sets):**

- SALES_FULL - Complete CRUD access
- SALES_BASIC - Dashboard + New Sales only
- SALES_CASHIER - POS operations
- SALES_HISTORY_ONLY - Read-only history
- SALES_VIEW_ONLY - View-only access

**Customer Permissions (3 sets):**

- CUSTOMER_FULL - Complete CRUD access
- CUSTOMER_BASIC - View + Create only
- CUSTOMER_VIEW_ONLY - Read-only access

**Items Permissions (2 sets):**

- ITEMS_FULL - Complete CRUD access
- ITEMS_VIEW_ONLY - Read-only access

**Purchases Permissions (2 sets):**

- PURCHASES_FULL - Complete CRUD access
- PURCHASES_CREATE - Create only

**Payments Permissions (2 sets):**

- PAYMENTS_FULL - Complete CRUD access
- PAYMENTS_VIEW_ONLY - Read-only access

**Expenses Permissions (2 sets):**

- EXPENSES_FULL - Complete CRUD access
- EXPENSES_CREATE - Create only

**Financials Permissions (2 sets):**

- FINANCIALS_FULL - Complete CRUD access
- FINANCIALS_VIEW_ONLY - Read-only access

**Cashier Permission (1 set):**

- Cashier - Cashier-specific permissions

---

### **Progress: 72% - Creating User Groups** ✨ **NEW**

```python
# Create and configure 7 user groups with permission sets
```

**Creates 7 User Groups with permissions:**

1. **Admin User Group**

   - Default Profile: Admin Role
   - Permission Sets: **ALL 19 permission sets**
   - Access Level: FULL ACCESS

2. **Manager User Group**

   - Default Profile: Manager Role
   - Permission Sets: 7 FULL access sets
     - SALES_FULL, CUSTOMER_FULL, ITEMS_FULL
     - PURCHASES_FULL, PAYMENTS_FULL, EXPENSES_FULL
     - FINANCIALS_FULL
   - Access Level: COMPREHENSIVE

3. **Sales User Group**

   - Default Profile: Sales Role
   - Permission Sets:
     - SALES_FULL, CUSTOMER_FULL, ITEMS_VIEW_ONLY
   - Access Level: SALES FOCUSED

4. **Cashier User Group**

   - Default Profile: Cashier Role
   - Permission Sets:
     - SALES_CASHIER, CUSTOMER_BASIC, ITEMS_VIEW_ONLY
   - Access Level: POS OPERATIONS

5. **Inventory User Group**

   - Default Profile: Inventory Role
   - Permission Sets:
     - ITEMS_FULL, PURCHASES_FULL
   - Access Level: STOCK MANAGEMENT

6. **Accountant User Group**

   - Default Profile: Accountant Role
   - Permission Sets:
     - FINANCIALS_FULL, PAYMENTS_FULL, EXPENSES_FULL
     - SALES_VIEW_ONLY, PURCHASES_VIEW_ONLY
   - Access Level: FINANCIAL FOCUS

7. **User User Group**
   - Default Profile: User Role
   - Permission Sets:
     - SALES_VIEW_ONLY, CUSTOMER_VIEW_ONLY
     - ITEMS_VIEW_ONLY, FINANCIALS_VIEW_ONLY
   - Access Level: VIEW ONLY

**Assigns initial admin user to Admin User Group:**

```python
user.user_groups.add(admin_group)
```

---

### **Progress: 73% - Starting Data Import**

```python
# Continue with existing data import process
```

---

## **Permission System Architecture**

### **3-Layer Access Control:**

**Layer 1: Role Center (Module Visibility)**

- Controls which modules appear in sidebar
- Stored in `RoleCenter.modules` (JSONField)
- Linked to Role via `Role.role_center`
- Included in JWT: `role_center_modules: ["sales", "customers", ...]`

**Layer 2: Permission Sets (Page Visibility)**

- Controls which specific pages within modules are accessible
- Stored in `PermissionSet` and `PermissionSetLine` models
- Assigned to User Groups
- Included in JWT: `page_permissions: {"Sales": {...}}`

**Layer 3: CRUD Permissions (Action Control)**

- Controls what actions (create, edit, delete) user can perform
- Stored in `PermissionSetLine` (read, insert, modify, delete fields)
- Checked in frontend components
- Used to conditionally render UI buttons

---

## **Data Flow:**

```
Company Creation
    ↓
Create Roles (Admin, Manager, Sales, Cashier, Inventory, Accountant, User)
    ↓
Create Role Centers (7 centers with module definitions)
    ↓
Link Role Centers to Roles (role.role_center = role_center)
    ↓
Create Page Objects (17 objects for all routes)
    ↓
Create Permission Sets (19 sets with CRUD permissions)
    ↓
Create User Groups (7 groups)
    ↓
Assign Permission Sets to User Groups
    ↓
Assign Admin User to Admin User Group
    ↓
Continue with Data Import...
```

---

## **User Login Flow:**

```
User logs in
    ↓
JWT Token generated with:
    - role_center_modules (from role.role_center.modules)
    - page_permissions (from user_groups → permission_sets → lines)
    - user_groups info
    - permission_sets codes
    ↓
Frontend receives token
    ↓
Navigation filtered by role_center_modules (Layer 1)
    ↓
Subitems filtered by page_permissions (Layer 2)
    ↓
CRUD buttons filtered by page_permissions (Layer 3)
```

---

## **Testing New Company Creation:**

1. **Create a new company** via the onboarding flow
2. **Log in as the admin user** (created during onboarding)
3. **Check JWT token** - should contain:
   ```json
   {
     "role_center_modules": ["sales", "customers", "items", ...],
     "page_permissions": {
       "Sales": {"read": true, "insert": true, "modify": true, "delete": true},
       "Customer Management": {...},
       ...
     },
     "user_groups": [{"code": "Admin", "name": "Admin", ...}],
     "permission_sets": ["SALES_FULL", "CUSTOMER_FULL", ...]
   }
   ```
4. **Verify Home page** - should show all 12 modules
5. **Verify sidebar** - all modules and pages visible
6. **Verify CRUD buttons** - Add, Edit, Delete buttons all visible

---

## **Files Modified:**

- **`company/tasks.py`**: Updated `create_company_task()` function
  - Added Page Objects population (progress 70%)
  - Added Permission Sets setup (progress 71%)
  - Added User Groups creation (progress 72%)
  - Added permission set assignments
  - Added admin user → Admin group assignment

---

## **Error Handling:**

All new setup steps are wrapped in try-except blocks:

- Errors are logged but don't fail the entire company creation
- This ensures backward compatibility
- Allows company creation to succeed even if permission setup partially fails

---

## **Manual Fix for Existing Companies:**

If you need to fix permissions for an existing company:

```bash
# 1. Populate Page Objects
python manage.py tenant_command populate_page_objects --schema=SCHEMA_NAME

# 2. Setup Permission Sets
python manage.py tenant_command setup_page_permissions --schema=SCHEMA_NAME

# 3. Fix Admin permissions (creates user groups and assigns permissions)
python manage.py tenant_command setup_admin_permissions --schema=SCHEMA_NAME
```

Or use the Python script directly:

```bash
python fix_admin_permissions.py  # For ekk schema
```

---

## **Summary:**

✅ **Automatic Setup** during company creation now includes:

1. Roles (7)
2. Role Centers (7)
3. Page Objects (17)
4. Permission Sets (19)
5. User Groups (7)
6. Permission Set Assignments (automatic)
7. Admin User → Admin Group Assignment (automatic)

✅ **Complete permission system** ready on day 1
✅ **No manual configuration required**
✅ **Admin user has full access immediately**
