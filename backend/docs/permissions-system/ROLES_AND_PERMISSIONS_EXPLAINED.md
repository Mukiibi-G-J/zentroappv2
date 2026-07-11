# 🔐 Roles & Permissions - How They Work Together

## 📋 Overview

Your ZentroApp has **TWO complementary permission systems** that work hand-in-hand:

1. **Existing Role System** (Module-Level) - Broad access control
2. **New Permission System** (Object-Level) - Granular access control

Think of them as **layers of security**:

- **Roles** = "What modules can you access?" (Sales, Inventory, etc.)
- **Permissions** = "What specific actions can you do in those modules?" (Read customers, Create invoices, etc.)

---

## 🎯 The Two Systems Explained

### **1. Existing Role System (Module-Level)**

**Location**: `authentication/models.py` - `Role` model

**What it does**:

```python
# Each role has module-level permissions
class Role:
    name = "Cashier"
    permissions = {
        "sales": True,      # Can access Sales module
        "customers": True,  # Can access Customers module
        "inventory": False, # Cannot access Inventory module
        "reports": False    # Cannot access Reports
    }
```

**Current Implementation**:

```python
user = CustomUser.objects.get(email='cashier@example.com')
user.roles.add(cashier_role)

# Check module access
authority = user.get_authority()
# Returns: ['sales', 'customers', 'items', 'hotel']
```

**Limitation**:

- ❌ All or nothing per module
- ❌ If you can access "Sales", you can do EVERYTHING in Sales
- ❌ Can't say "view customers but not delete them"

---

### **2. New Permission System (Object-Level)**

**Location**: `permissions/models.py` - `PermissionSet` & `PermissionSetLine`

**What it does**:

```python
# Each permission set has granular object-level permissions
class PermissionSet:
    name = "Cashier"
    code = "CASHIER"
    linked_role = cashier_role  # Links to existing role!

    permission_lines = [
        {
            "object": "Customer Table (ID: 2600)",
            "read": True,      # ✅ Can view customers
            "insert": True,    # ✅ Can add customers
            "modify": True,    # ✅ Can edit customers
            "delete": False,   # ❌ Cannot delete customers
            "execute": False
        },
        {
            "object": "Sales Invoice Table (ID: 2700)",
            "read": True,      # ✅ Can view invoices
            "insert": True,    # ✅ Can create invoices
            "modify": False,   # ❌ Cannot edit invoices
            "delete": False,   # ❌ Cannot delete invoices
            "execute": False
        }
    ]
```

**Advantage**:

- ✅ Precise control per object
- ✅ Different permissions for different tables
- ✅ Can say "read but not delete"

---

## 🔗 How They Work Together

### **The Integration Flow**

```
┌─────────────────────────────────────────────────────────────┐
│                         USER                                 │
│                    (John - Cashier)                          │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       │ has roles
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                    ROLE SYSTEM                               │
│              (Existing - Module Level)                       │
│                                                              │
│  Role: "Cashier"                                            │
│  Modules: sales, customers, items                           │
│  ├─ Can access Sales module? ✅                             │
│  ├─ Can access Inventory module? ❌                         │
│  └─ Can access Reports module? ❌                           │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       │ linked to
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              PERMISSION SET SYSTEM                           │
│           (New - Object/Action Level)                        │
│                                                              │
│  Permission Set: "CASHIER" (linked to Cashier role)        │
│  Objects & Actions:                                         │
│  ├─ Customer Table (2600)                                   │
│  │  ├─ Read: ✅ Insert: ✅ Modify: ✅ Delete: ❌           │
│  ├─ Sales Invoice Table (2700)                             │
│  │  ├─ Read: ✅ Insert: ✅ Modify: ❌ Delete: ❌           │
│  ├─ Item Table (2800)                                       │
│  │  ├─ Read: ✅ Insert: ❌ Modify: ❌ Delete: ❌           │
│  └─ Sales Order Page (10001)                               │
│     ├─ Read: ✅ Insert: ✅ Execute: ✅                     │
└─────────────────────────────────────────────────────────────┘
```

---

## 💡 Real-World Example

### **Scenario: Sarah the Cashier**

**Step 1: Assign Role (Existing System)**

```python
# Admin assigns Sarah the "Cashier" role
sarah = CustomUser.objects.get(email='sarah@company.com')
cashier_role = Role.objects.get(name='Cashier')
sarah.roles.add(cashier_role)

# Now Sarah can access these modules:
sarah.get_authority()
# Returns: ['sales', 'customers', 'items']
```

**Step 2: Permission Set Auto-Applied (New System)**

```python
# The Cashier role is linked to CASHIER permission set
permission_set = PermissionSet.objects.get(code='CASHIER')
permission_set.linked_role = cashier_role  # This link was created during setup

# Sarah automatically inherits all permissions from CASHIER set
```

**Step 3: Permission Checks in Code**

```python
# When Sarah tries to view a customer
can_view = sarah.check_object_permission(2600, 'read')  # 2600 = Customer Table
# Returns: True ✅

# When Sarah tries to delete a customer
can_delete = sarah.check_object_permission(2600, 'delete')
# Returns: False ❌

# When Sarah tries to edit an invoice
can_edit = sarah.check_object_permission(2700, 'modify')  # 2700 = Sales Invoice
# Returns: False ❌
```

---

## 🏗️ The Architecture

### **Database Relationships**

```
┌──────────────┐
│   User       │
│  (Sarah)     │
└──────┬───────┘
       │
       │ ManyToMany
       │
       ▼
┌──────────────────┐
│   Role           │
│  (Cashier)       │◄─────────┐
└──────────────────┘           │
                               │ ForeignKey (linked_role)
                               │
                        ┌──────┴───────────┐
                        │  PermissionSet   │
                        │   (CASHIER)      │
                        └──────┬───────────┘
                               │
                               │ OneToMany
                               │
                        ┌──────▼──────────────────┐
                        │  PermissionSetLine      │
                        │  - Customer: R,I,M      │
                        │  - Invoice: R,I         │
                        │  - Item: R              │
                        └─────────────────────────┘
```

---

## 🎬 Complete Workflow

### **1. Admin Creates Company & Users**

```python
# Admin creates a new company
company = Company.objects.create(name="Acme Corp")

# Default roles are automatically created:
# - Admin, Manager, Cashier, Sales, Inventory, Accountant, User
```

### **2. Admin Runs Setup Commands**

```bash
# Populate application objects (tables, pages, etc.)
python manage.py populate_objects_table

# Create default permission sets and link them to roles
python manage.py setup_default_permissions
```

**What happens:**

```python
# System creates permission sets:
ADMIN_FULL = PermissionSet.objects.create(
    name="Admin - Full Access",
    code="ADMIN_FULL",
    linked_role=Role.objects.get(name='Admin'),
    is_active=True
)

# For each application object, create permission lines:
for obj in Objects.objects.filter(requires_permission=True):
    PermissionSetLine.objects.create(
        permissionset=ADMIN_FULL,
        application_object=obj,
        read_permission=True,
        insert_permission=True,
        modify_permission=True,
        delete_permission=True,
        execute_permission=True
    )

# Same for CASHIER, MANAGER, etc. but with different permissions
```

### **3. Admin Assigns Users to Roles**

```python
# In Django admin or via API
user.roles.add(cashier_role)
# User automatically gets CASHIER permission set (linked via linked_role)
```

### **4. User Performs Actions**

```python
# Frontend makes request
POST /api/sales/customers/
{
    "name": "New Customer",
    "email": "customer@example.com"
}

# Backend checks permissions (in your view)
def create_customer(request):
    user = request.user

    # Option 1: Check using new permission system
    if not user.check_object_permission(2600, 'insert'):  # 2600 = Customer Table
        return Response({'error': 'No permission'}, status=403)

    # Option 2: Check using existing authority system (still works!)
    if 'customers' not in user.get_authority():
        return Response({'error': 'No module access'}, status=403)

    # Both checks can coexist!
    # Proceed with creating customer
    ...
```

---

## 🔄 Two-Layer Security

### **Layer 1: Module Access (Role System)**

```python
# First check: Does user have access to the module?
if 'sales' not in user.get_authority():
    return "You don't have access to Sales module"
```

### **Layer 2: Object Actions (Permission System)**

```python
# Second check: Can user perform this specific action?
if not user.check_object_permission(2700, 'delete'):
    return "You can't delete invoices"
```

**Combined Check Example**:

```python
def delete_invoice(request, invoice_id):
    user = request.user

    # Layer 1: Module access
    if 'sales' not in user.get_authority():
        return Response({'error': 'No Sales module access'}, status=403)

    # Layer 2: Specific action permission
    if not user.check_object_permission(2700, 'delete'):  # 2700 = Invoice Table
        return Response({'error': 'Cannot delete invoices'}, status=403)

    # Both checks passed - proceed
    invoice = SalesInvoice.objects.get(id=invoice_id)
    invoice.delete()
    return Response({'message': 'Invoice deleted'})
```

---

## 🎨 Visual Example

### **Scenario: Three Users, Different Permissions**

```
┌─────────────────────────────────────────────────────────────┐
│                      CUSTOMER TABLE (2600)                   │
└─────────────────────────────────────────────────────────────┘

User: John (Admin)
Role: Admin → Permission Set: ADMIN_FULL
├─ Read: ✅ (Can view all customers)
├─ Insert: ✅ (Can add new customers)
├─ Modify: ✅ (Can edit any customer)
├─ Delete: ✅ (Can delete customers)
└─ Module Access: ✅ (Has 'customers' in authority)

User: Sarah (Cashier)
Role: Cashier → Permission Set: CASHIER
├─ Read: ✅ (Can view customers)
├─ Insert: ✅ (Can add customers)
├─ Modify: ✅ (Can edit customers)
├─ Delete: ❌ (Cannot delete customers)
└─ Module Access: ✅ (Has 'customers' in authority)

User: Mike (Inventory)
Role: Inventory → Permission Set: INVENTORY
├─ Read: ✅ (Can view customers - need for stock orders)
├─ Insert: ❌ (Cannot add customers)
├─ Modify: ❌ (Cannot edit customers)
├─ Delete: ❌ (Cannot delete customers)
└─ Module Access: ❌ (Does NOT have 'customers' in authority)
     └─ BUT can still READ via granular permission!
```

---

## 🚀 Benefits of This Dual System

### **1. Backward Compatibility**

- ✅ Existing role system still works
- ✅ `get_authority()` still returns module list
- ✅ No breaking changes to existing code

### **2. Progressive Enhancement**

- ✅ Start with broad role-based access
- ✅ Add granular permissions where needed
- ✅ Mix both approaches

### **3. Flexibility**

- ✅ Quick module-level checks for navigation
- ✅ Precise object-level checks for actions
- ✅ Can override or combine as needed

### **4. User-Friendly**

- ✅ Simple role assignment (Admin, Cashier, etc.)
- ✅ Complex permissions handled automatically
- ✅ Easy to explain to end users

---

## 📝 Implementation Patterns

### **Pattern 1: Module Gate + Action Check**

```python
def update_customer(request, customer_id):
    user = request.user

    # Gate: Module access
    if 'customers' not in user.get_authority():
        return redirect('no_access')

    # Fine-grained: Can they modify?
    if not user.check_object_permission(2600, 'modify'):
        messages.error(request, 'You can view but not edit customers')
        return redirect('customer_detail', customer_id)

    # Proceed with update
    ...
```

### **Pattern 2: Permission-Only Check**

```python
def delete_customer(request, customer_id):
    user = request.user

    # Single check - permission system handles everything
    if not user.check_object_permission(2600, 'delete'):
        return Response({'error': 'Insufficient permissions'}, status=403)

    # Proceed with delete
    ...
```

### **Pattern 3: Role-Based Menu + Permission Actions**

```python
# In your template/frontend
def get_user_menu(user):
    menu = []

    # Use roles for menu items
    if 'sales' in user.get_authority():
        menu.append({
            'name': 'Sales',
            'items': [
                {
                    'name': 'Customers',
                    'url': '/customers/',
                    'can_create': user.check_object_permission(2600, 'insert'),
                    'can_delete': user.check_object_permission(2600, 'delete')
                },
                {
                    'name': 'Invoices',
                    'url': '/invoices/',
                    'can_create': user.check_object_permission(2700, 'insert'),
                    'can_delete': user.check_object_permission(2700, 'delete')
                }
            ]
        })

    return menu
```

---

## 🎯 Key Takeaways

1. **Roles = Module Access** (broad)

   - Quick checks
   - Menu navigation
   - Feature visibility

2. **Permissions = Action Control** (precise)

   - Specific operations
   - Data protection
   - Audit trails

3. **Automatic Linking**

   - Assign role → User gets permission set automatically
   - No manual permission assignment needed
   - Update permission set → All users with that role affected

4. **Flexible Implementation**
   - Use roles only (simpler)
   - Use permissions only (more secure)
   - Use both (recommended)

---

## 📚 Next Steps

1. **Run Setup**:

   ```bash
   python manage.py populate_objects_table
   python manage.py setup_default_permissions
   ```

2. **Test in Admin**:

   - Visit `http://ekk.localhost:8000/admin/`
   - See Permission Sets linked to Roles
   - View Permission Lines for each set

3. **Implement in Code**:
   - Add permission checks to your views
   - Update frontend to show/hide actions
   - Test with different user roles

---

**The beauty of this system**: You get the simplicity of role-based access with the power of granular permissions, working seamlessly together! 🎉

