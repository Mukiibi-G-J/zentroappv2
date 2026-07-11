# 🚀 Business Central Style Role Centers - Quick Reference

## ✅ The Correct Pattern

```
Role → specifies → Role Center ID
```

Just like Business Central! ✨

---

## 📋 3-Step Usage

### **Step 1: Create Role Center**

```
Admin Panel → Role Centers → Add

Code: DISPENSER_CENTER
Name: Dispenser Center
Modules: ["sales", "customers", "items"]
Save
```

### **Step 2: Assign to Role**

```
Admin Panel → Roles → Edit "Dispenser"

Name: Dispenser
Role Center: Dispenser Center  ← Select from dropdown!
Save
```

### **Step 3: Assign Role to User**

```
Admin Panel → Users → Edit user

Roles: Dispenser  ← Assign
Save
```

**Result**: User sees only Sales, Customers, Items! 🎉

---

## 🎯 Key Concepts

### **Role** (WHO):

- Defines user's position/authority
- Example: Admin, Manager, Cashier, Dispenser
- **Has a**: `role_center` field

### **Role Center** (WHAT):

- Defines available modules/features
- Example: Admin Center, Sales Center, Dispenser Center
- **Defines**: `modules` list

### **User** (THE PERSON):

- Has one or more **Roles**
- Gets **modules** from Role → Role Center

---

## 🔗 Relationship Flow

```
User
  ↓ has
Role (e.g., "Dispenser")
  ↓ specifies
Role Center (e.g., "Dispenser Center")
  ↓ defines
Modules (e.g., ["sales", "customers", "items"])
  ↓ controls
Navigation (Frontend shows only these modules)
```

---

## 💻 Admin Panel URLs

```bash
# View/Create Role Centers
http://ekk.localhost:8000/admin/authentication/rolecenter/

# View/Edit Roles (assign role center here!)
http://ekk.localhost:8000/admin/authentication/role/

# View/Edit Users (assign roles here!)
http://ekk.localhost:8000/admin/authentication/customuser/
```

---

## 📊 What You'll See

### **Role Centers List**:

```
Name               | Code              | Assigned to Roles    | Modules
-------------------|-------------------|----------------------|------------------
Admin Center       | ADMIN_CENTER      | Admin                | sales, customers, items (+9)
Cashier Center     | CASHIER_CENTER    | Cashier              | sales, customers, profile
Dispenser Center   | DISPENSER_CENTER  | Dispenser            | sales, customers, items
```

### **Roles List**:

```
Name      | Role Center        | Description         | Is Active
----------|--------------------|--------------------|----------
Admin     | Admin Center       | System admin...     | ✅
Cashier   | Cashier Center     | POS access...       | ✅
Dispenser | Dispenser Center   | Custom role...      | ✅
```

---

## 🎨 Real-World Examples

### **Example 1: Pharmacy**

```python
# Create Dispenser role center
Role Center:
  Code: PHARMACY_DISPENSER
  Name: Pharmacy Dispenser Center
  Modules: ["sales", "customers", "items"]

# Create Dispenser role
Role:
  Name: Dispenser
  Role Center: Pharmacy Dispenser Center  ← Link!

# Assign to user
User:
  Name: John
  Roles: [Dispenser]

# Result: John sees Sales, Customers, Items only!
```

### **Example 2: Restaurant**

```python
# Create Waiter role center
Role Center:
  Code: WAITER_CENTER
  Name: Waiter Center
  Modules: ["sales", "customers"]

# Create Waiter role
Role:
  Name: Waiter
  Role Center: Waiter Center  ← Link!

# Assign to multiple users
Users:
  Sarah: [Waiter]
  Mike: [Waiter]
  Lisa: [Waiter]

# Result: All 3 see Sales, Customers only!
```

### **Example 3: Reusing Centers**

```python
# One role center for multiple roles!

Role Center:
  Code: SALES_CENTER
  Modules: ["sales", "customers", "items", "reports"]

Roles:
  Sales Person → Sales Center  ← Reuse!
  Senior Sales → Sales Center  ← Reuse!
  Sales Manager → Sales Center  ← Reuse!

# All 3 roles get the same modules!
# Change center → All 3 roles updated automatically!
```

---

## 🔧 Commands

### **Setup Default Centers (Automatic for new companies)**:

```bash
# Already runs automatically during company creation!
# No action needed for new companies
```

### **Setup for Existing Companies**:

```bash
# All companies (already done!)
python manage.py setup_role_centers_all_tenants

# Single tenant
python manage.py setup_default_role_centers
```

### **Create Migration** (if you modify models):

```bash
python manage.py makemigrations authentication
python manage.py migrate_schemas
```

---

## 📝 Available Modules

When creating role centers, use these module codes:

```json
[
  "sales", // Sales & invoicing
  "customers", // Customer management
  "items", // Inventory & items
  "purchases", // Purchase orders
  "financials", // Accounting & GL
  "payments", // Payment processing
  "expenses", // Expense tracking
  "reports", // Reports & analytics
  "settings", // System settings
  "profile", // User profile
  "company", // Company management
  "roles" // Role management
]
```

---

## 🎯 Quick Troubleshooting

### **Q: User sees wrong modules**

```bash
A: Check:
   1. User's roles (Admin → Users → Select user)
   2. Role's role center (Admin → Roles → Select role)
   3. Role center's modules (Admin → Role Centers → Select center)
   4. Ask user to logout and login again (JWT refresh)
```

### **Q: Role has no role center**

```bash
A: Fix:
   1. Admin → Roles → Select role
   2. Role Center: Select from dropdown
   3. Save
```

### **Q: Want to change modules for all cashiers**

```bash
A: Easy!
   1. Admin → Role Centers → Cashier Center
   2. Edit modules: ["sales", "customers", "items"]  ← Add items!
   3. Save
   4. All cashier users get items module on next login!
```

---

## ✨ Key Benefits

### **✅ Reusability**:

- Create once, use for many roles
- Multiple roles can share same center

### **✅ Flexibility**:

- Change center → All roles updated
- No need to update each role individually

### **✅ Professional**:

- Matches Business Central exactly
- Industry-standard approach
- Intuitive for admins

### **✅ Zero Hardcoding**:

- All configuration in admin panel
- No code changes needed
- Non-developers can manage

---

## 🎉 Success Checklist

- [x] Migration applied to all tenants ✅
- [x] All roles linked to role centers ✅
- [x] Admin panel shows correct relationships ✅
- [x] JWT token includes role_center_modules ✅
- [x] Frontend filters navigation by modules ✅
- [x] Matches Business Central pattern exactly ✅

---

## 📞 Quick Help

### **Check JWT Token**:

```javascript
// Browser console (F12)
const token = localStorage.getItem("accessToken");
const decoded = JSON.parse(atob(token.split(".")[1]));
console.log("Modules:", decoded.role_center_modules);
// Output: ["sales", "customers", "profile"]
```

### **Check User's Modules**:

```bash
# Django shell
python manage.py shell

from authentication.models import CustomUser
user = CustomUser.objects.get(email="user@example.com")

# Get modules
modules = []
for role in user.roles.all():
    if role.role_center:
        modules.extend(role.role_center.modules)

print(list(set(modules)))
# Output: ['sales', 'customers', 'profile']
```

---

**Perfect Business Central implementation!** 🚀✨

**Next**: Test it in the admin panel! → http://ekk.localhost:8000/admin/
