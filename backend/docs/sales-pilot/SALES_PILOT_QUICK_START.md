# 🚀 Sales Permission Pilot - Quick Start Guide

## ✅ Status: Backend Setup Complete!

The Sales permission pilot is ready to use. Here's how to get started quickly.

---

## 🎯 Quick Setup (Already Done!)

```bash
# Run this command for any tenant
python manage.py setup_sales_pilot_tenant --schema=hardwareworld
```

This automatically:

- ✅ Registers 5 sales objects
- ✅ Creates 3 permission sets
- ✅ Creates 3 user groups
- ✅ Links everything together

---

## 👥 User Groups Created

### **1. Sales - Cashiers** (Code: SALES_CASHIERS)

**Who**: Cashiers, front-line sales staff  
**Can Do**:

- ✅ View customers
- ✅ Add new customers
- ✅ Edit customer information
- ✅ View sales invoices
- ✅ Create new invoices
- ❌ Cannot delete customers
- ❌ Cannot edit/delete invoices

### **2. Sales Team** (Code: SALES_TEAM)

**Who**: Sales representatives, sales managers  
**Can Do**:

- ✅ Everything with customers (full access)
- ✅ Everything with invoices (full access)
- ✅ Edit sales setup

### **3. Sales - Viewers** (Code: SALES_VIEWERS)

**Who**: Accountants, managers who need to view data  
**Can Do**:

- ✅ View all sales data
- ❌ Cannot create, edit, or delete anything

---

## 🔧 How To Assign Users

### **Method 1: Django Admin (Recommended)**

1. Visit: `http://ekk.localhost:8000/admin/`
2. Go to: **Authentication > User Groups**
3. Click on "Sales - Cashiers" (or any group)
4. Scroll to "Members" section
5. Select users from the left box
6. Click the arrow to move them to the right box
7. Click "Save"

**What Happens**:

- User automatically gets the **Cashier role** (from group's default profile)
- User automatically gets **SALES_CASHIER permission set**
- User can now perform cashier operations!

### **Method 2: Django Shell**

```python
from authentication.models import CustomUser, UserGroup

# Get user
user = CustomUser.objects.get(email='cashier@company.com')

# Get group
cashiers_group = UserGroup.objects.get(code='SALES_CASHIERS')

# Add user to group
cashiers_group.add_member(user)

# Done! User now has cashier permissions
```

---

## 🧪 How To Test

### **Test 1: Check User's Groups**

```python
from authentication.models import CustomUser

user = CustomUser.objects.get(email='cashier@company.com')

# Check groups
print("User Groups:", user.user_groups.all())
# Output: <QuerySet [<UserGroup: Sales - Cashiers (SALES_CASHIERS)>]>

# Check roles (should have Cashier)
print("Roles:", user.roles.all())
# Output: <QuerySet [<Role: Cashier>]>
```

### **Test 2: Check Specific Permissions**

```python
from authentication.models import CustomUser

user = CustomUser.objects.get(email='cashier@company.com')

# Test Customer permissions
print("\nCustomer Table (2600) Permissions:")
print("-" * 50)

can_read, source = user.check_object_permission(2600, 'read')
print(f"  Read: {can_read} ({source})")

can_insert, source = user.check_object_permission(2600, 'insert')
print(f"  Insert: {can_insert} ({source})")

can_modify, source = user.check_object_permission(2600, 'modify')
print(f"  Modify: {can_modify} ({source})")

can_delete, source = user.check_object_permission(2600, 'delete')
print(f"  Delete: {can_delete} ({source})")

# Expected Output for Cashier:
# Read: True (Sales - Cashier permission set)
# Insert: True (Sales - Cashier permission set)
# Modify: True (Sales - Cashier permission set)
# Delete: False (No matching permission found)
```

### **Test 3: Check Invoice Permissions**

```python
# Test Sales Invoice permissions
print("\nSales Invoice Table (2700) Permissions:")
print("-" * 50)

can_read, source = user.check_object_permission(2700, 'read')
print(f"  Read: {can_read} ({source})")

can_insert, source = user.check_object_permission(2700, 'insert')
print(f"  Insert: {can_insert} ({source})")

can_modify, source = user.check_object_permission(2700, 'modify')
print(f"  Modify: {can_modify} ({source})")

# Expected Output for Cashier:
# Read: True (Sales - Cashier permission set)
# Insert: True (Sales - Cashier permission set)
# Modify: False (No matching permission found)
```

### **Test 4: Compare Different Users**

```python
# Cashier
cashier = CustomUser.objects.get(email='cashier@company.com')
can_delete_customer, _ = cashier.check_object_permission(2600, 'delete')
print(f"Cashier can delete customers: {can_delete_customer}")  # False

# Sales Rep (in SALES_TEAM group)
sales_rep = CustomUser.objects.get(email='sales@company.com')
can_delete_customer, _ = sales_rep.check_object_permission(2600, 'delete')
print(f"Sales Rep can delete customers: {can_delete_customer}")  # True

# Viewer (in SALES_VIEWERS group)
viewer = CustomUser.objects.get(email='viewer@company.com')
can_insert_customer, _ = viewer.check_object_permission(2600, 'insert')
print(f"Viewer can create customers: {can_insert_customer}")  # False
```

---

## 🎨 Visual Permission Matrix

### **Customer Table (ID: 2600)**

| User Group       | Read | Insert | Modify | Delete |
| ---------------- | ---- | ------ | ------ | ------ |
| Sales - Cashiers | ✅   | ✅     | ✅     | ❌     |
| Sales Team       | ✅   | ✅     | ✅     | ✅     |
| Sales - Viewers  | ✅   | ❌     | ❌     | ❌     |

### **Sales Invoice Table (ID: 2700)**

| User Group       | Read | Insert | Modify | Delete |
| ---------------- | ---- | ------ | ------ | ------ |
| Sales - Cashiers | ✅   | ✅     | ❌     | ❌     |
| Sales Team       | ✅   | ✅     | ✅     | ✅     |
| Sales - Viewers  | ✅   | ❌     | ❌     | ❌     |

---

## 🛠️ Admin URLs

- **User Groups**: `http://ekk.localhost:8000/admin/authentication/usergroup/`
- **Permission Sets**: `http://ekk.localhost:8000/admin/permissions/permissionset/`
- **Objects**: `http://ekk.localhost:8000/admin/base/objects/`
- **Users**: `http://ekk.localhost:8000/admin/authentication/customuser/`

---

## 🔄 Setup For Other Tenants

To setup the pilot for another tenant:

```bash
# For tenant 'semuna'
python manage.py setup_sales_pilot_tenant --schema=semuna

# For tenant 'jom'
python manage.py setup_sales_pilot_tenant --schema=jom

# etc...
```

---

## ⚡ Quick Commands

```bash
# Re-run setup (updates existing data)
python manage.py setup_sales_pilot_tenant --schema=hardwareworld

# Check migrations
python manage.py showmigrations authentication permissions

# Access Django shell
python manage.py shell

# View all user groups
from authentication.models import UserGroup
UserGroup.objects.all()
```

---

## 🎯 What's Next?

**Day 2 Tasks**:

1. Update JWT token to include user groups
2. Create permission check decorators
3. Apply decorators to sales API views
4. Test API endpoints with Postman/curl

**Day 3 Tasks**:

1. Update frontend TypeScript types
2. Create permission hooks
3. Update Customer and Invoice pages
4. User acceptance testing

---

## 📞 Need Help?

**Check These**:

- View permission sets: Django Admin > Permissions
- View user groups: Django Admin > Authentication > User Groups
- Test permissions: Use Django shell commands above
- Troubleshoot: Check `SALES_PILOT_DAY1_COMPLETE.md` for details

---

**Date**: October 21, 2025  
**Status**: ✅ READY FOR DAY 2  
**Pilot Tenant**: EKK  
**Next**: API Integration & Testing

🚀 **Backend is ready! Let's test and move to API integration!**
