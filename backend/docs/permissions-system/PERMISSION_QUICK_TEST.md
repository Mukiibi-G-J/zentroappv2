# 🧪 Permission System - Quick Test Guide

## ⚡ 5-Minute Test to Verify Everything Works

Follow these steps to verify the permission system is working correctly.

---

## Test 1: Admin Interface (2 minutes)

### Step 1: Start the server

```bash
cd zentro-backend
python manage.py runserver
```

### Step 2: Open admin

Visit: http://localhost:8000/admin/

### Step 3: Check new sections

You should see:

- ✅ **Base** section with:
  - Object Types
  - Objects
  - Permission Sets
  - Permission Set Lines

### Step 4: Click around

- **Object Types**: Should show 6 types (Table, Page, Report, etc.)
- **Objects**: Should show 62+ objects
- **Permission Sets**: Should show 5 sets (ADMIN_FULL, MANAGER, etc.)
- **Permission Set Lines**: Should show 75+ lines

**Expected Result**: All visible and working ✅

---

## Test 2: Django Shell Tests (2 minutes)

### Step 1: Open shell

```bash
python manage.py shell
```

### Step 2: Run these commands

```python
# Test ObjectType
from base.models import ObjectType
ObjectType.objects.all()
# Should show: [<ObjectType: Table>, <ObjectType: Page>, ...]

# Test Objects
from base.models import Objects
Objects.objects.count()
# Should return: 62 or more

# Test PermissionSet
from base.models import PermissionSet
PermissionSet.objects.all()
# Should show: [<PermissionSet: Admin - Full Access>, <PermissionSet: Cashier>, ...]

# Test PermissionSetLine
from base.models import PermissionSetLine
PermissionSetLine.objects.count()
# Should return: 75 or more

# Test User Permissions
from authentication.models import CustomUser, Role

# Get a user (or create one)
user = CustomUser.objects.first()
if not user:
    user = CustomUser.objects.create_user(
        email="test@test.com",
        username="testuser",
        full_name="Test User",
        phone_number="1234567890",
        password="test123"
    )

# Assign Cashier role
cashier_role = Role.objects.get(name="Cashier")
user.roles.add(cashier_role)

# Test permission check
user.check_object_permission(2500, 'read')    # Should be True (Cashier can read Item)
user.check_object_permission(2500, 'delete')  # Should be False (Cashier cannot delete Item)

# Test get all permissions
perms = user.get_all_permissions()
print(perms)
# Should show dict with obj_2500, etc.

# Test existing system
user.get_authority()
# Should still work and return list like ["sales", "customers"]
```

**Expected Result**: All commands work, returns correct values ✅

---

## Test 3: API Test (1 minute)

### Option A: Using Browser

1. Start server: `python manage.py runserver`
2. Get auth token (login via your existing auth system)
3. Visit in browser: `http://localhost:8000/api/permissions/object-types/`
4. Should see JSON with object types

### Option B: Using curl

```bash
# Replace YOUR_TOKEN with actual token
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8000/api/permissions/object-types/

# Should return:
# [
#   {"id": 1, "name": "Table", "code": "TABLE", ...},
#   {"id": 2, "name": "Page", "code": "PAGE", ...},
#   ...
# ]
```

### Option C: Using Python requests

```python
import requests

# Get token first (your existing auth)
token = "your_auth_token_here"

# Test API
response = requests.get(
    "http://localhost:8000/api/permissions/user-permissions/",
    headers={"Authorization": f"Bearer {token}"}
)

print(response.json())
# Should show your permissions
```

**Expected Result**: API returns JSON data ✅

---

## 🎯 Verification Checklist

Run through this checklist:

### Models & Database:

- [ ] ObjectType table has 6 records
- [ ] Objects table has 62+ records
- [ ] PermissionSet table has 5 records
- [ ] PermissionSetLine table has 75+ records
- [ ] All migrations applied to all tenants

### Admin Interface:

- [ ] Can view Object Types in admin
- [ ] Can view Objects in admin
- [ ] Can view Permission Sets in admin
- [ ] Can add Permission Lines inline in admin
- [ ] Can search and filter objects

### Code Integration:

- [ ] CustomUser has `check_object_permission()` method
- [ ] CustomUser has `get_all_permissions()` method
- [ ] Methods work correctly in shell
- [ ] No errors when calling methods

### API:

- [ ] `/api/permissions/object-types/` works
- [ ] `/api/permissions/objects/` works
- [ ] `/api/permissions/permission-sets/` works
- [ ] `/api/permissions/user-permissions/` works
- [ ] All endpoints return correct JSON

### Backward Compatibility:

- [ ] `get_authority()` still works
- [ ] Existing role checks still work
- [ ] No breaking changes in existing code

---

## 🐛 Troubleshooting

### Issue: "Objects not found" errors

**Solution**: This is normal for tenant-specific models. They'll work when accessed in tenant context.

### Issue: "Permission denied" in admin

**Solution**: Make sure you're logged in as superuser or have admin role.

### Issue: API returns 401

**Solution**: Check your authentication token is valid and included in headers.

### Issue: Shell can't import models

**Solution**: Make sure you're in the right directory and virtual environment is activated.

---

## ✅ If All Tests Pass

**Congratulations!** 🎊 Your permission system is working perfectly!

You can now:

1. ✅ Use permission checks in your views
2. ✅ Manage permissions via admin
3. ✅ Customize access for different users
4. ✅ Scale to any size application

---

## 🚀 Start Using It

### Add to Your First View:

```python
# Pick any view in your app
# Add this check:

def my_existing_view(request):
    # Add permission check
    if not request.user.check_object_permission(2600, 'read'):
        return JsonResponse({'error': 'Access denied'}, status=403)

    # Rest of your existing code...
    return JsonResponse({'data': 'success'})
```

**That's it!** You're now using the permission system! 🎉

---

## 📞 Need Help?

- **Read**: `PERMISSION_SYSTEM_EXPLAINED.md` for deep dive
- **Reference**: `OBJECT_MANAGEMENT_GUIDE.md` for adding objects
- **Compare**: `PERMISSION_COMPARISON.md` for why this is better
- **Complete guide**: `PERMISSION_IMPLEMENTATION_COMPLETE.md` for everything

---

**Happy testing! 🚀**



