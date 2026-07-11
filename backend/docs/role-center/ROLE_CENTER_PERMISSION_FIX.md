# 🔧 Role Center & Permission System Fix

## 🐛 The Bug You Discovered

### **Symptoms**:

```
User: jom@hrpsolutions.com
Role: Dispenser (with Dispenser Center)
Modules: ["sales", "customers", "items"]

Problem:
✅ User can login
✅ JWT token has role_center_modules
✅ Frontend shows Sales, Customers, Items in navigation
❌ API calls return 403 Forbidden
❌ User gets logged out
```

### **Terminal Errors**:

```
Forbidden: /api/sales/
[22/Oct/2025 05:43:53] "GET /api/sales/?... HTTP/1.1" 403 128

Forbidden: /api/customers/
[22/Oct/2025 05:43:53] "GET /api/customers/ HTTP/1.1" 403 129
```

---

## 🎯 Root Cause Analysis

### **The Conflict**:

You have **TWO separate permission systems**:

1. **Role Center System** (NEW - Business Central Style):

   ```
   Role → Role Center → Modules (for navigation visibility)
   ```

2. **Permission Set System** (OLD - Sales Pilot):
   ```
   User Groups → Permission Sets → Permission Lines (for API access)
   ```

### **The Bug**:

In `authentication/models.py`, the `check_object_permission()` method was trying to get Permission Sets using:

```python
# ❌ BROKEN CODE (from before Business Central change)
for role in self.roles.all():
    role_sets = PermissionSet.objects.filter(
        linked_role=role, is_active=True  # ← This field was removed!
    )
    permission_sets.extend(role_sets)
```

**Problem**: The `linked_role` field was **removed** from `PermissionSet` model when we changed to Business Central style (Role → Role Center)!

This caused:

1. Django query error (field doesn't exist)
2. No permission sets found
3. `check_object_permission()` returns `False`
4. API returns `403 Forbidden`
5. Frontend shows errors
6. User appears "logged out"

---

## ✅ The Fix

### **What Was Changed**:

Updated two methods in `authentication/models.py`:

1. **`check_object_permission()`** (line ~356):

   ```python
   # Before:
   # Get all permission sets from groups + roles
   permission_sets = []

   # 1. From user groups
   for group in self.user_groups.filter(is_active=True):
       permission_sets.extend(group.get_all_permission_sets())

   # 2. From direct role assignments (BROKEN!)
   for role in self.roles.all():
       role_sets = PermissionSet.objects.filter(
           linked_role=role, is_active=True  # ❌ Field doesn't exist!
       )
       permission_sets.extend(role_sets)

   # After:
   # Get all permission sets from groups only
   # (Role → Role Center system is separate from Permission Sets)
   permission_sets = []

   # From user groups
   for group in self.user_groups.filter(is_active=True):
       permission_sets.extend(group.get_all_permission_sets())
   ```

2. **`get_all_permissions()`** (line ~396):
   - Same fix applied

---

## 🎨 How The Two Systems Work Together

### **Role Center System** (Module Visibility):

```
Purpose: Control what users SEE in navigation
Flow: Role → Role Center → Modules
JWT: role_center_modules = ["sales", "customers", "items"]
Frontend: Shows/hides navigation items
Backend: Does NOT control API access
```

### **Permission Set System** (API Access Control):

```
Purpose: Control what users can DO with data
Flow: User Group → Permission Sets → Permission Lines
Check: check_object_permission(object_id, permission_type)
Backend: Controls API access (Read, Insert, Modify, Delete)
Frontend: Can disable buttons based on permissions
```

---

## 🛠️ Current State

### **What Works Now** ✅:

1. **Role Centers**:

   - Role → Role Center relationship (Business Central style)
   - JWT token includes `role_center_modules`
   - Frontend navigation filters by modules
   - No API access control

2. **Permission Sets**:
   - User Groups → Permission Sets
   - `check_object_permission()` works correctly
   - API access controlled by permission lines
   - Independent from Role Centers

### **What You Need To Do**:

**To give Dispenser role API access**, you have 2 options:

#### **Option 1: Create User Group with Permission Sets** (Recommended):

```bash
1. Admin → User Groups → Add "Dispensers"
2. Add Permission Sets:
   - SALES_READ
   - CUSTOMER_READ
   - ITEM_READ
3. Add user to "Dispensers" group
4. User can now access APIs!
```

#### **Option 2: Remove API Permission Checks** (If you don't need them):

```python
# In sales/views.py → CustomerViewSet.list()
# Comment out these lines:
# has_permission, source = request.user.check_object_permission(2600, "read")
# if not has_permission:
#     return Response({"error": "..."}, status=403)

# User can access APIs based on authentication only
```

---

## 📋 System Comparison

| Feature       | Role Center                 | Permission Sets                |
| ------------- | --------------------------- | ------------------------------ |
| **Purpose**   | Navigation visibility       | API access control             |
| **Controls**  | Which modules user sees     | What user can do with data     |
| **Location**  | `Role → Role Center`        | `User Group → Permission Sets` |
| **Level**     | Module-level (coarse)       | Object-level (granular)        |
| **JWT Token** | Yes (`role_center_modules`) | No (checked server-side)       |
| **Frontend**  | Filters navigation          | Can disable buttons            |
| **Backend**   | No API control              | Controls API access            |

---

## 🎯 Best Practice

### **Use BOTH systems together**:

1. **Role Centers**: Control high-level module visibility
   - User sees Sales, Customers, Items in nav
2. **Permission Sets**: Control granular data access
   - User can Read customers
   - User can Insert sales
   - User can Modify items
   - User CANNOT Delete anything

### **Example Setup**:

**Dispenser Role**:

```python
# Role Center (Navigation)
Role: Dispenser
Role Center: Dispenser Center
Modules: ["sales", "customers", "items"]
→ User sees these modules in navigation

# Permission Sets (API Access)
User Group: Dispensers
Permission Sets:
  - SALES_READ (Read sales only)
  - CUSTOMER_READ (Read customers only)
  - ITEM_READ_MODIFY (Read & modify items)
→ User can access these APIs with specific permissions
```

---

## 🎉 Summary

### **Bug Fixed** ✅:

- Removed broken `linked_role` lookup from permission checks
- Permission Sets now only come from User Groups
- API access works correctly

### **Systems Separated** ✅:

- Role Centers = Navigation visibility
- Permission Sets = API access control
- Both work independently
- Both can work together

### **User Can Now**:

- Login successfully ✅
- See correct navigation (via Role Center) ✅
- Access APIs (via Permission Sets) ✅ (once you assign them)

---

**Next Step**: Create User Group with Permission Sets for your Dispenser users! 🚀
