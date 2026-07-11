# ✅ Sales Permission Pilot - Verification Checklist

Use this checklist to verify the implementation is working correctly.

---

## 🔍 Step-by-Step Verification

### **✅ Step 1: Check Django Admin**

1. Visit: `http://ekk.localhost:8000/admin/`
2. Login with your admin account

**Check these sections exist**:

- [ ] Base > Objects (should see 5 sales objects: 2600, 2610, 2700, 2710, 2720)
- [ ] Permissions > Permission Sets (should see 3: SALES_CASHIER, SALES_FULL, SALES_VIEW_ONLY)
- [ ] Permissions > Permission Set Lines (should see 15 permission lines)
- [ ] Authentication > User Groups (should see 3: SALES_CASHIERS, SALES_TEAM, SALES_VIEWERS)

---

### **✅ Step 2: Verify Permission Sets**

1. Go to: **Permissions > Permission Sets**
2. Click on "Sales - Cashier"

**Verify**:

- [ ] Code: SALES_CASHIER
- [ ] Linked Role: Cashier
- [ ] Is Active: ✅
- [ ] Permission Lines: 5

**Click on Permission Lines tab, should see**:

- [ ] Customer (2600): R=✅, I=✅, M=✅, D=❌
- [ ] Customer Ledger Entry (2610): R=✅, I=❌, M=❌, D=❌
- [ ] Sales Invoice (2700): R=✅, I=✅, M=❌, D=❌
- [ ] Sales Invoice Line (2710): R=✅, I=✅, M=❌, D=❌
- [ ] Sales Setup (2720): R=✅, I=❌, M=❌, D=❌

---

### **✅ Step 3: Verify User Groups**

1. Go to: **Authentication > User Groups**
2. Click on "Sales - Cashiers"

**Verify**:

- [ ] Code: SALES_CASHIERS
- [ ] Name: Sales - Cashiers
- [ ] Default Profile: Cashier
- [ ] Permission Sets: Contains "Sales - Cashier"
- [ ] Members: (empty for now)
- [ ] Is Active: ✅

---

### **✅ Step 4: Add Test User to Group**

1. Still in "Sales - Cashiers" group edit page
2. Scroll to **Members** section
3. Select a test user from the left box
4. Click the arrow (→) to move to right box
5. Click "Save"

**Verify**:

- [ ] User appears in "Members" list
- [ ] Go to: Authentication > Users
- [ ] Open the test user
- [ ] Check "Roles" field - should now have "Cashier" ✅

---

### **✅ Step 5: Test Permissions in Django Shell**

Open Django shell:

```bash
python manage.py shell
```

Run this test:

```python
from authentication.models import CustomUser

# Get the test user you just added to the group
user = CustomUser.objects.get(email='YOUR_TEST_USER_EMAIL')

# Test 1: Check user groups
print(f"User Groups: {user.user_groups.all()}")
# Should show: <QuerySet [<UserGroup: Sales - Cashiers (SALES_CASHIERS)>]>

# Test 2: Check roles
print(f"Roles: {user.roles.all()}")
# Should show: <QuerySet [<Role: Cashier>]>

# Test 3: Check permissions
print("\nPermission Tests:")
print("-" * 50)

# Can read customers? (Should be YES)
can_read, source = user.check_object_permission(2600, 'read')
print(f"Read Customer: {can_read} - {source}")

# Can delete customers? (Should be NO)
can_delete, source = user.check_object_permission(2600, 'delete')
print(f"Delete Customer: {can_delete} - {source}")

# Can create invoices? (Should be YES)
can_insert, source = user.check_object_permission(2700, 'insert')
print(f"Create Invoice: {can_insert} - {source}")

# Can modify invoices? (Should be NO)
can_modify, source = user.check_object_permission(2700, 'modify')
print(f"Modify Invoice: {can_modify} - {source}")
```

**Expected Output**:

```
✅ User Groups: Sales - Cashiers
✅ Roles: Cashier
✅ Read Customer: True - Sales - Cashier permission set
❌ Delete Customer: False - No matching permission found
✅ Create Invoice: True - Sales - Cashier permission set
❌ Modify Invoice: False - No matching permission found
```

- [ ] All tests show expected results

---

### **✅ Step 6: Test Different User Groups**

Create 3 test users and test each group:

#### **Test User 1: Cashier**

```python
cashier = CustomUser.objects.get(email='cashier@test.com')
cashiers_group = UserGroup.objects.get(code='SALES_CASHIERS')
cashiers_group.add_member(cashier)

# Should be able to:
can_create_invoice, _ = cashier.check_object_permission(2700, 'insert')
print(f"Cashier can create invoice: {can_create_invoice}")  # True

# Should NOT be able to:
can_delete_customer, _ = cashier.check_object_permission(2600, 'delete')
print(f"Cashier can delete customer: {can_delete_customer}")  # False
```

- [ ] Cashier has correct permissions

#### **Test User 2: Sales Rep**

```python
sales_rep = CustomUser.objects.get(email='sales@test.com')
sales_group = UserGroup.objects.get(code='SALES_TEAM')
sales_group.add_member(sales_rep)

# Should be able to do EVERYTHING:
can_delete_customer, _ = sales_rep.check_object_permission(2600, 'delete')
print(f"Sales Rep can delete customer: {can_delete_customer}")  # True

can_modify_invoice, _ = sales_rep.check_object_permission(2700, 'modify')
print(f"Sales Rep can modify invoice: {can_modify_invoice}")  # True
```

- [ ] Sales rep has full access

#### **Test User 3: Viewer**

```python
viewer = CustomUser.objects.get(email='viewer@test.com')
viewers_group = UserGroup.objects.get(code='SALES_VIEWERS')
viewers_group.add_member(viewer)

# Should only be able to READ:
can_read, _ = viewer.check_object_permission(2600, 'read')
print(f"Viewer can read customers: {can_read}")  # True

can_insert, _ = viewer.check_object_permission(2600, 'insert')
print(f"Viewer can create customers: {can_insert}")  # False
```

- [ ] Viewer has read-only access

---

### **✅ Step 7: Verify Settings**

Check `core/settings.py`:

- [ ] `authentication` is NOT in SHARED_APPS (line 91 should be commented)
- [ ] `authentication` IS in TENANT_APPS (line 108)
- [ ] `permissions` IS in TENANT_APPS (line 106)
- [ ] `base` IS in SHARED_APPS (line 94)

---

### **✅ Step 8: Check No Errors**

```bash
python manage.py check
```

- [ ] Shows: "System check identified no issues (0 silenced)."

---

## 🎯 If All Checks Pass...

**🎉 Congratulations! The backend is working perfectly!**

### **You're Ready For**:

1. **Day 2**: API Integration (add permission checks to views)
2. **Day 3**: Frontend Integration (update UI based on permissions)

---

## ❌ If Something Fails...

### **Issue: Can't see User Groups in admin**

```bash
# Re-run migrations
python manage.py migrate authentication
```

### **Issue: Permission check returns False**

```python
# Check if permission sets are linked to group
group = UserGroup.objects.get(code='SALES_CASHIERS')
print(group.permission_sets.all())  # Should show SALES_CASHIER

# Check if user is in group
user = CustomUser.objects.get(email='test@test.com')
print(user.user_groups.all())  # Should show Sales - Cashiers
```

### **Issue: "Relation does not exist"**

```bash
# Make sure you're testing on a tenant, not public schema
# Use: python manage.py setup_sales_pilot_tenant --schema=hardwareworld
```

---

## 📞 Quick Commands Reference

```bash
# Run full setup for a tenant
python manage.py setup_sales_pilot_tenant --schema=hardwareworld

# Access Django shell
python manage.py shell

# Check migrations
python manage.py showmigrations authentication permissions

# Restart server
python manage.py runserver
```

---

## 🎯 Summary

**If all checkboxes are ticked** ✅:

- Backend implementation is COMPLETE
- Permission system is WORKING
- Ready for Day 2 (API integration)

**If any checkbox is unchecked** ❌:

- Review the specific step
- Check error messages
- Re-run setup commands if needed

---

**Next Document**: `SALES_PILOT_DAY2_PLAN.md` (Coming next!)  
**Need Help**: Check `SALES_PILOT_QUICK_START.md` for detailed guides
