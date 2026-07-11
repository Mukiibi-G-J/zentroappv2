# 🔍 Finding Permission Sets in Django Admin

## ✅ Server Started Successfully

The Django server is now running at: **http://localhost:8000**

---

## 📍 Where to Find Permission Sets

### Step-by-Step:

1. **Open your browser**

   ```
   Go to: http://localhost:8000/admin/
   ```

2. **Login**

   - Use your superuser credentials
   - If you don't have a superuser, see below ⬇️

3. **Look for the "Base" section**

   ```
   Django Administration
   ├── Authentication and Authorization
   ├── Authentication (your app)
   ├── BASE  ← 🎯 LOOK HERE!
   │   ├── Object Types
   │   ├── Objects
   │   ├── Permission Sets  ← 🎯 THIS IS WHAT YOU WANT!
   │   └── Permission Set Lines
   ├── Company
   ├── Config Packages
   ├── Customers
   └── ... other apps
   ```

4. **Click on "Permission Sets"**
   - You should see 5 permission sets:
     - Admin - Full Access
     - Cashier
     - Inventory
     - Manager
     - Sales

---

## 🚨 If You Don't See "Base" Section

### Problem 1: Server Not Restarted

**Solution**: Server is now restarted (just did it for you!)

Refresh your browser: **Ctrl + F5** (hard refresh)

### Problem 2: Not Logged In as Superuser

**Solution**: Create a superuser or login with existing one

```bash
# Create new superuser
python manage.py createsuperuser

# Follow prompts:
Email: admin@zentroapp.com
Username: admin
Full name: Admin User
Phone number: 1234567890
Password: (your password)
```

### Problem 3: Cache Issues

**Solution**: Clear browser cache

1. Press **Ctrl + Shift + Delete**
2. Clear cache and cookies
3. Refresh page

Or use incognito/private mode:

- Chrome: **Ctrl + Shift + N**
- Firefox: **Ctrl + Shift + P**

---

## 🎯 What You Should See

### In the "BASE" Section:

#### 1. Object Types (6 entries)

```
Table
Page
Report
Codeunit
Query
API
```

#### 2. Objects (62+ entries)

```
Item (2500)
Customer (2600)
Sale (2701)
... and many more
```

#### 3. Permission Sets (5 entries) ⭐

```
Admin - Full Access
Cashier
Inventory
Manager
Sales
```

#### 4. Permission Set Lines (75+ entries)

```
Admin - Full Access - Item
Admin - Full Access - Customer
Cashier - Item
... and many more
```

---

## 🔍 Screenshot Reference

When you open admin, it should look like this:

```
┌─────────────────────────────────────────────────┐
│  Django administration                          │
├─────────────────────────────────────────────────┤
│                                                 │
│  AUTHENTICATION AND AUTHORIZATION               │
│    ├── Groups                                   │
│    └── Users                                    │
│                                                 │
│  AUTHENTICATION (YOUR APP)                      │
│    ├── Custom users                            │
│    ├── Otps                                    │
│    ├── Profiles                                │
│    └── Roles                                   │
│                                                 │
│  BASE  ← 🎯 THIS SECTION                       │
│    ├── Object Types                            │
│    ├── Objects                                 │
│    ├── Permission Set Lines                    │
│    └── Permission Sets  ← 🎯 CLICK HERE        │
│                                                 │
│  COMPANY                                        │
│    └── ...                                     │
└─────────────────────────────────────────────────┘
```

---

## 🧪 Quick Verification

### Test 1: Check in Shell

```bash
python manage.py shell
```

```python
from base.models import PermissionSet
PermissionSet.objects.all()

# Should output:
# <QuerySet [
#   <PermissionSet: Admin - Full Access>,
#   <PermissionSet: Cashier>,
#   <PermissionSet: Inventory>,
#   <PermissionSet: Manager>,
#   <PermissionSet: Sales>
# ]>
```

**If this works**: Models exist in database ✅  
**If admin doesn't show them**: Server/cache issue

### Test 2: Check Admin Registration

```bash
python manage.py shell
```

```python
from django.contrib import admin
from base.models import PermissionSet

# Check if registered
print(admin.site.is_registered(PermissionSet))
# Should print: True

# List all registered models
for model, model_admin in admin.site._registry.items():
    if 'base' in str(model):
        print(f"{model} -> {model_admin}")

# Should show:
# <class 'base.models.ObjectType'> -> base.admin.ObjectTypeAdmin
# <class 'base.models.Objects'> -> base.admin.ObjectsAdmin
# <class 'base.models.PermissionSet'> -> base.admin.PermissionSetAdmin
# <class 'base.models.PermissionSetLine'> -> base.admin.PermissionSetLineAdmin
```

---

## 🛠️ Troubleshooting Steps

### Step 1: Restart Server (Already Done!)

Server is running in background. Refresh your browser!

### Step 2: Hard Refresh Browser

- **Windows**: Press **Ctrl + F5**
- **Mac**: Press **Cmd + Shift + R**

### Step 3: Check Superuser Access

```bash
# In a new terminal
cd zentro-backend
.\env\Scripts\Activate.ps1
python manage.py shell

from authentication.models import CustomUser
user = CustomUser.objects.filter(is_superuser=True).first()
print(user)

# If None, create superuser:
exit()
python manage.py createsuperuser
```

### Step 4: Verify Models Are Loaded

```bash
python manage.py shell

from django.apps import apps
base_app = apps.get_app_config('base')
print(base_app.models)

# Should show: dict with ObjectType, Objects, PermissionSet, PermissionSetLine
```

---

## ⚡ Quick Fix

**Most likely issue**: Server needs to see the new admin registrations

1. **Server is now running**: Check http://localhost:8000/admin/
2. **Login as superuser**
3. **Press Ctrl + F5** to hard refresh
4. **Look for "BASE" section** in the admin sidebar
5. **Click "Permission Sets"**

---

## 🎯 Alternative: Access Directly via URL

If you still can't find it in the sidebar, go directly to the URL:

```
http://localhost:8000/admin/base/permissionset/
http://localhost:8000/admin/base/objects/
http://localhost:8000/admin/base/objecttype/
http://localhost:8000/admin/base/permissionsetline/
```

---

## 📞 Still Not Working?

### Check 1: Is base app installed?

```bash
python manage.py shell
from django.conf import settings
print('base' in settings.INSTALLED_APPS)
# Should print: True
```

### Check 2: Are models in database?

```bash
python manage.py shell
from base.models import PermissionSet
PermissionSet.objects.count()
# Should return: 5
```

### Check 3: Are admins registered?

```bash
python manage.py shell
from django.contrib.admin.sites import site
print(site.is_registered('base.PermissionSet'))
# If error, import the model first:
from base.models import PermissionSet
print(site.is_registered(PermissionSet))
# Should print: True
```

---

## ✅ Expected Result

After following these steps, you should see:

1. ✅ "BASE" section in Django admin sidebar
2. ✅ "Permission Sets" link under BASE
3. ✅ 5 permission sets when you click it
4. ✅ Ability to add/edit permission sets

---

## 🎉 Once You See It

You can then:

1. **View existing permission sets**
2. **Click into any set** (e.g., "Cashier")
3. **See the permission lines** inline
4. **Edit permissions** directly
5. **Add new permission lines**
6. **Create new permission sets**

---

**The server is running now! Go to http://localhost:8000/admin/ and check!** 🚀

