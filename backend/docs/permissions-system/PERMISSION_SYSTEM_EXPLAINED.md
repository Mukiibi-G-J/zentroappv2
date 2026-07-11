# Permission System - Complete Explanation

## 📋 Overview

This document explains a **Business Central-inspired permission system** for the ZentroApp. It's a granular, flexible way to control what users can do with different parts of your application.

---

## 🎯 Core Concept

Instead of simple "can user edit customers?", this system asks:

- **What type of object?** (Table, Page, Report, etc.)
- **Which specific object?** (Customer Table = ID 18, Sales Page = ID 42)
- **What action?** (Read, Insert, Modify, Delete, Execute)
- **Permission level?** (None, Yes, Indirect)

---

## 🏗️ System Architecture

### 1. **ObjectType** - Categories of Things

```
Examples:
- TABLE (database tables)
- PAGE (UI pages)
- REPORT (reports)
- CODEUNIT (business logic)
- QUERY (data queries)
```

**Purpose**: Groups similar objects together.

---

### 2. **ApplicationObject** - Specific Things

```
Examples:
- Customer Table (Type: TABLE, ID: 18)
- Sales Order Page (Type: PAGE, ID: 42)
- Invoice Report (Type: REPORT, ID: 206)
```

**Purpose**: Represents actual components in your system that need permissions.

---

### 3. **PermissionSet** - Named Permission Bundles

```
Examples:
- "SALES-MANAGER" - Full sales access
- "CASHIER" - POS and payment access
- "ACCOUNTANT" - Financial data access
- "INVENTORY-CLERK" - Stock management only
```

**Purpose**: Logical groupings of permissions that can be assigned to user groups.

---

### 4. **PermissionSetLine** - The Actual Permissions ⭐

This is the **heart of the system**. Each line defines permissions for ONE specific object.

#### Structure:

```python
PermissionSetLine {
    permission_set: "SALES-MANAGER"
    object_type: TABLE
    object_id: 18
    object_name: "Customer"

    # Permissions (for TABLE types)
    read_permission: "yes"      # Can view customer data
    insert_permission: "yes"    # Can create new customers
    modify_permission: "yes"    # Can edit customer data
    delete_permission: "yes"    # Can delete customers
    execute_permission: "none"  # Not applicable for tables
}
```

---

## 🎨 Permission Values

### For Read, Insert, Modify, Delete:

- **None**: No permission
- **Yes**: Direct permission
- **Indirect**: Permission through related objects (e.g., can modify orders = indirect modify for customers)

### For Execute:

- **None**: Cannot execute
- **Yes**: Can execute

---

## 📊 Real-World Example

### Scenario: Setting up a "Cashier" role

```python
# Permission Set
PermissionSet(
    name="CASHIER",
    code="CASHIER",
    description="POS and basic customer access"
)

# Permission Set Lines
PermissionSetLine(
    permission_set="CASHIER",
    object_type=TABLE,
    object_id=18,
    object_name="Customer",
    read_permission="yes",      # Can view customers
    insert_permission="yes",    # Can add customers
    modify_permission="yes",    # Can edit customers
    delete_permission="none",   # Cannot delete customers
    execute_permission="none"
)

PermissionSetLine(
    permission_set="CASHIER",
    object_type=PAGE,
    object_id=42,
    object_name="Sales Order",
    read_permission="yes",      # Can view orders
    insert_permission="yes",    # Can create orders
    modify_permission="yes",    # Can edit orders
    delete_permission="none",   # Cannot delete orders
    execute_permission="none"
)

PermissionSetLine(
    permission_set="CASHIER",
    object_type=PAGE,
    object_id=50,
    object_name="Financial Settings",
    read_permission="none",     # Cannot view financial settings
    insert_permission="none",
    modify_permission="none",
    delete_permission="none",
    execute_permission="none"
)
```

---

## 🔗 How It Works in Practice

### 1. **Setup Phase**

```
Administrator → Creates PermissionSet "CASHIER"
             → Adds PermissionSetLines for each object
             → Links PermissionSet to Django Group "Cashiers"
```

### 2. **User Assignment**

```
User "John" → Added to Group "Cashiers"
           → Automatically gets all permissions from "CASHIER" PermissionSet
```

### 3. **Permission Check**

```python
# When John tries to delete a customer:
PermissionUtility.check_object_permission(
    user=john,
    object_type_code='TABLE',
    object_id=18,
    permission_type='delete'
)
# Returns: False (Cashiers can't delete customers)
```

---

## 🎯 Key Features

### ✅ Granular Control

Control permissions at the object level, not just module level.

### ✅ Flexible Combinations

Mix and match permissions for different objects in one set.

### ✅ Hierarchical

- ObjectType → ApplicationObject → PermissionSetLine
- Easy to understand and manage

### ✅ Auditable

Track who has access to what, when permissions were granted.

### ✅ Reusable

Create permission sets once, assign to multiple groups.

---

## 💻 Implementation Components

### Backend (Django)

1. **Models** (`models.py`)

   - ObjectType
   - ApplicationObject
   - PermissionSet
   - PermissionSetLine
   - UserGroup

2. **Serializers** (`serializers.py`)

   - Convert models to JSON for API

3. **Views** (`views.py`)

   - API endpoints to manage permissions
   - PermissionUtility class for checking permissions

4. **API Endpoints**
   ```
   GET  /api/permission-sets/
   POST /api/permission-sets/
   GET  /api/permission-sets/{id}/permission-lines/
   POST /api/permission-sets/{id}/add_permission_line/
   GET  /api/user-permissions/
   POST /api/check-permission/
   ```

### Frontend (React)

1. **PermissionSetLinesManager Component**

   - UI to manage permission lines
   - Add, edit, delete permissions
   - Visual table interface

2. **PermissionContext**

   - Global permission state
   - `checkPermission()` function
   - `getObjectPermissions()` function

3. **Usage in Components**

   ```jsx
   const { checkPermission } = usePermissions();
   const canEdit = checkPermission("TABLE", 18, "modify");

   {
     canEdit && <button>Edit Customer</button>;
   }
   ```

---

## 🎓 Understanding the Sorting/Organization

### Default Sorting Order:

1. **Object Type** (ascending) - Tables first, then Pages, Reports, etc.
2. **Object ID** (ascending) - Lower IDs first
3. **Object Name** (alphabetical) - A to Z

### Why This Matters:

- Keeps related objects together
- Makes it easy to find specific objects
- Consistent across the system

---

## 🚀 Advantages Over Simple Role-Based Access

### Traditional RBAC:

```python
if user.has_role('manager'):
    # Can do everything manager-related
    # But what if they shouldn't delete invoices?
```

### This System:

```python
if checkPermission('TABLE', 112, 'delete'):  # Invoice Table
    # Only if explicitly granted delete on invoices
    # Even if they're a manager
```

---

## 📝 How to Use in ZentroApp

### Step 1: Define Your Objects

```python
# Create object types
ObjectType.objects.create(name="Table", code="TABLE")
ObjectType.objects.create(name="Page", code="PAGE")

# Create application objects
ApplicationObject.objects.create(
    name="Customer",
    object_type=table_type,
    object_id=18,
    code="CUSTOMER_TABLE"
)
```

### Step 2: Create Permission Sets

```python
# Create a permission set
cashier_set = PermissionSet.objects.create(
    name="CASHIER",
    code="CASHIER",
    description="POS Operations"
)
```

### Step 3: Add Permission Lines

```python
# Add specific permissions
PermissionSetLine.objects.create(
    permission_set=cashier_set,
    object_type=table_type,
    object_id=18,
    object_name="Customer",
    read_permission="yes",
    insert_permission="yes",
    modify_permission="yes",
    delete_permission="none"
)
```

### Step 4: Link to User Groups

```python
# Link to Django group
cashier_group = Group.objects.get(name="Cashiers")
user_group = UserGroup.objects.create(group=cashier_group)
user_group.permission_sets.add(cashier_set)
```

### Step 5: Check Permissions in Code

```python
# Backend
from .views import PermissionUtility

can_delete = PermissionUtility.check_object_permission(
    user=request.user,
    object_type_code='TABLE',
    object_id=18,
    permission_type='delete'
)
```

```jsx
// Frontend
const { checkPermission } = usePermissions();
const canDelete = checkPermission("TABLE", 18, "delete");

{
  canDelete && <button>Delete Customer</button>;
}
```

---

## 🎯 Integration with ZentroApp's Current System

### Current System:

- CustomUser with roles (ManyToMany to Role model)
- Role-based permissions via `user.get_authority()`

### This System:

- Complements existing roles
- Provides granular control within roles
- Can work alongside or replace current system

### Migration Path:

1. Keep current role system for high-level access
2. Add this system for granular permissions
3. Check both: `if user.has_role('manager') and checkPermission('TABLE', 18, 'delete')`

---

## 📚 Common Object IDs (Example Mapping)

```
Tables:
  18  - Customer
  23  - Vendor
  27  - Item
  36  - Sales Header
  37  - Sales Line
  112 - Sales Invoice Header

Pages:
  21  - Customer Card
  22  - Customer List
  42  - Sales Order
  43  - Purchase Order

Reports:
  206 - Sales Invoice
  207 - Sales Quote
```

---

## 🔒 Security Benefits

1. **Principle of Least Privilege**: Grant only what's needed
2. **Audit Trail**: Track who can do what
3. **Easy Revocation**: Remove permission sets without touching code
4. **Temporary Access**: Grant time-limited permissions
5. **Compliance**: Meet regulatory requirements for access control

---

## 🎉 Summary

This permission system gives you **Microsoft Business Central-level control** over your Django application:

- 🎯 **Precise**: Control access to specific objects
- 🔄 **Flexible**: Mix and match permissions
- 📊 **Organized**: Logical hierarchy
- 🚀 **Scalable**: Works for small and large apps
- 🛡️ **Secure**: Granular access control

Perfect for multi-tenant, enterprise-level applications like ZentroApp where different users need different levels of access to different parts of the system.

---

## 💡 Next Steps

1. **Implement Models**: Add to Django project
2. **Run Migrations**: Create database tables
3. **Seed Data**: Add initial object types and objects
4. **Create Permission Sets**: Define role-based sets
5. **Update Views**: Add permission checks
6. **Update Frontend**: Use permission context
7. **Test**: Verify permissions work correctly

---

**Questions?** This system might seem complex at first, but it provides unmatched flexibility for managing user permissions in a professional ERP-style application.
