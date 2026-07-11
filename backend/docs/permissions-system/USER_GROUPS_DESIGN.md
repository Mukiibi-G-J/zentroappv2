# 👥 User Groups Design - Enhanced Permission System

## 🎯 The Three-Layer Permission System

Instead of just **Users → Roles → Permissions**, we'll have:

**Users → User Groups → Roles → Permission Sets → Permission Lines**

This gives maximum flexibility and easier management!

---

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                           USER                                   │
│                      (John Doe)                                  │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         │ belongs to (ManyToMany)
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                       USER GROUP                                 │
│                  (Sales Department)                              │
│  ├─ Code: SALES_DEPT                                            │
│  ├─ Name: Sales Department                                      │
│  ├─ Default Profile (Role): Cashier ←─────┐                     │
│  ├─ Description: All sales team members   │                     │
│  └─ Permission Sets: [CASHIER, SALES_BASIC]                     │
└────────────────────────┬────────────────────┬───────────────────┘
                         │                    │
                         │ has default        │ has many
                         ▼                    ▼
┌────────────────────────────┐    ┌──────────────────────────────┐
│         ROLE               │    │     PERMISSION SETS          │
│      (Cashier)             │    │   (CASHIER, SALES_BASIC)     │
│                            │    │                              │
│  Module permissions:       │    │  Object-level permissions:   │
│  - sales ✅                │    │  - Customer: RIMD            │
│  - customers ✅            │    │  - Invoice: RI               │
│  - inventory ❌            │    │  - Item: R                   │
└────────────────────────────┘    └──────────────┬───────────────┘
                                                  │
                                                  │ contains
                                                  ▼
                                   ┌──────────────────────────────┐
                                   │   PERMISSION SET LINES       │
                                   │                              │
                                   │  Customer Table (2600):      │
                                   │  ├─ Read: ✅                │
                                   │  ├─ Insert: ✅              │
                                   │  ├─ Modify: ✅              │
                                   │  └─ Delete: ❌              │
                                   │                              │
                                   │  Invoice Table (2700):       │
                                   │  ├─ Read: ✅                │
                                   │  ├─ Insert: ✅              │
                                   │  └─ Modify: ❌              │
                                   └──────────────────────────────┘
```

---

## 📊 Database Models

### **1. UserGroup Model**

```python
# authentication/models.py or new user_groups/models.py

from django.db import models
from django.contrib.auth import get_user_model
from utils.utils import BaseModel

User = get_user_model()

class UserGroup(BaseModel):
    """
    User Group - A collection of users with shared permissions.
    Each tenant can create and manage their own user groups.
    """

    code = models.CharField(
        max_length=50,
        unique=True,
        help_text="Unique code for the user group (e.g., SALES_DEPT, WAREHOUSE_TEAM)"
    )

    name = models.CharField(
        max_length=100,
        help_text="Display name for the user group"
    )

    description = models.TextField(
        blank=True,
        help_text="Description of this user group's purpose"
    )

    default_profile = models.ForeignKey(
        'Role',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='user_groups_default',
        help_text="Default role assigned to users in this group"
    )

    permission_sets = models.ManyToManyField(
        'permissions.PermissionSet',
        related_name='user_groups',
        blank=True,
        help_text="Permission sets assigned to this user group"
    )

    members = models.ManyToManyField(
        User,
        related_name='user_groups',
        blank=True,
        help_text="Users who belong to this group"
    )

    is_active = models.BooleanField(
        default=True,
        help_text="Whether this user group is active"
    )

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_user_groups'
    )

    class Meta:
        db_table = 'authentication_usergroup'
        verbose_name = 'User Group'
        verbose_name_plural = 'User Groups'
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.code})"

    def get_all_permission_sets(self):
        """
        Get all permission sets for this group.
        Includes both directly assigned sets and sets from default profile.
        """
        permission_sets = list(self.permission_sets.all())

        # Add permission sets from default profile (role)
        if self.default_profile:
            role_sets = PermissionSet.objects.filter(
                linked_role=self.default_profile,
                is_active=True
            )
            permission_sets.extend(role_sets)

        # Remove duplicates
        return list(set(permission_sets))

    def add_member(self, user):
        """Add a user to this group and apply default profile"""
        self.members.add(user)

        # Apply default profile (role) if set
        if self.default_profile:
            user.roles.add(self.default_profile)
            user.save()

    def remove_member(self, user):
        """Remove a user from this group"""
        self.members.remove(user)
```

---

## 🔄 How It Works

### **Scenario 1: Creating a Sales Department**

```python
# Admin creates a user group
sales_dept = UserGroup.objects.create(
    code='SALES_DEPT',
    name='Sales Department',
    description='All sales team members',
    default_profile=Role.objects.get(name='Cashier'),  # Default role
    is_active=True
)

# Assign permission sets to the group
sales_dept.permission_sets.add(
    PermissionSet.objects.get(code='CASHIER'),
    PermissionSet.objects.get(code='SALES_BASIC')
)

# Add users to the group
sarah = CustomUser.objects.get(email='sarah@company.com')
sales_dept.add_member(sarah)

# What Sarah gets:
# 1. Role: Cashier (from default_profile)
# 2. Permission Sets: CASHIER + SALES_BASIC (from group)
# 3. Module Access: From Cashier role
# 4. Object Permissions: From both permission sets (merged)
```

### **Scenario 2: Different User Groups, Same Role**

```python
# Warehouse Group - uses Inventory role
warehouse_group = UserGroup.objects.create(
    code='WAREHOUSE',
    name='Warehouse Team',
    default_profile=Role.objects.get(name='Inventory')
)
warehouse_group.permission_sets.add(
    PermissionSet.objects.get(code='INVENTORY'),
    PermissionSet.objects.get(code='WAREHOUSE_ADVANCED')  # Extra permissions!
)

# Store Group - also uses Inventory role BUT different permissions
store_group = UserGroup.objects.create(
    code='STORE_TEAM',
    name='Store Team',
    default_profile=Role.objects.get(name='Inventory')
)
store_group.permission_sets.add(
    PermissionSet.objects.get(code='INVENTORY')  # Only basic inventory
)

# Result: Both groups have same module access (Inventory role)
#         BUT warehouse team has more object-level permissions!
```

---

## 🎨 Updated CustomUser Methods

```python
# authentication/models.py - Update CustomUser

class CustomUser(AbstractBaseUser, PermissionsMixin):
    # ... existing fields ...

    def get_all_permission_sets(self):
        """
        Get all permission sets for this user from:
        1. User groups (highest priority)
        2. Direct role assignments (fallback)
        """
        permission_sets = []

        # 1. Get permission sets from user groups
        for group in self.user_groups.filter(is_active=True):
            permission_sets.extend(group.get_all_permission_sets())

        # 2. Get permission sets from direct role assignments
        for role in self.roles.all():
            role_sets = PermissionSet.objects.filter(
                linked_role=role,
                is_active=True
            )
            permission_sets.extend(role_sets)

        # Remove duplicates
        return list(set(permission_sets))

    def check_object_permission(self, object_id, permission_type):
        """
        Updated to check permissions from user groups first,
        then fall back to direct role permissions.
        """
        from permissions.models import PermissionSetLine

        # Get all permission sets (groups + roles)
        permission_sets = self.get_all_permission_sets()

        if not permission_sets:
            return False, "No permission sets assigned"

        # Check if user has the permission
        permission_field = f"{permission_type}_permission"

        permission_lines = PermissionSetLine.objects.filter(
            permissionset__in=permission_sets,
            application_object__object_id=object_id,
            **{permission_field: True}
        ).select_related('permissionset', 'application_object')

        if permission_lines.exists():
            line = permission_lines.first()
            return True, f"{line.permissionset.name} permission set"

        return False, "No matching permission found"

    def get_user_groups_info(self):
        """Get user's group membership info"""
        groups = []
        for group in self.user_groups.filter(is_active=True):
            groups.append({
                'code': group.code,
                'name': group.name,
                'default_role': group.default_profile.name if group.default_profile else None,
                'permission_sets': [ps.name for ps in group.permission_sets.all()]
            })
        return groups
```

---

## 🎯 Benefits of This Approach

### **1. Easier Management**

```
Instead of:
- Assigning permissions to 50 individual sales people ❌

Do this:
- Create "Sales Department" group ✅
- Assign permissions to the group ✅
- Add users to the group ✅
```

### **2. Flexibility**

```
Same Role, Different Permissions:
├─ Warehouse Team (Inventory role)
│  └─ Has: Item management + Stock transfers + Physical counts
└─ Store Team (Inventory role)
   └─ Has: Item management only

Same Group, Different Users:
├─ Sales Department
│  ├─ Senior Sales (gets extra permissions via additional groups)
│  └─ Junior Sales (only gets department defaults)
```

### **3. Organization Structure**

```
Company
├─ Sales Department
│  ├─ Inside Sales Team
│  └─ Field Sales Team
├─ Operations Department
│  ├─ Warehouse Team
│  └─ Store Team
└─ Finance Department
   ├─ Accounting Team
   └─ Payroll Team

Each team = User Group with specific permissions!
```

---

## 💼 Real-World Examples

### **Example 1: Retail Company**

```python
# Create departments/teams as user groups

# 1. Store Managers Group
store_managers = UserGroup.objects.create(
    code='STORE_MGR',
    name='Store Managers',
    default_profile=Role.objects.get(name='Manager')
)
store_managers.permission_sets.add(
    PermissionSet.objects.get(code='MANAGER'),
    PermissionSet.objects.get(code='SALES_FULL'),
    PermissionSet.objects.get(code='INVENTORY_FULL')
)

# 2. Cashiers Group
cashiers = UserGroup.objects.create(
    code='CASHIERS',
    name='Cashiers',
    default_profile=Role.objects.get(name='Cashier')
)
cashiers.permission_sets.add(
    PermissionSet.objects.get(code='CASHIER')
)

# 3. Inventory Team Group
inventory_team = UserGroup.objects.create(
    code='INVENTORY',
    name='Inventory Team',
    default_profile=Role.objects.get(name='Inventory')
)
inventory_team.permission_sets.add(
    PermissionSet.objects.get(code='INVENTORY'),
    PermissionSet.objects.get(code='WAREHOUSE')
)
```

### **Example 2: Hotel Management**

```python
# Front Desk Group
front_desk = UserGroup.objects.create(
    code='FRONT_DESK',
    name='Front Desk Staff',
    default_profile=Role.objects.get(name='User')
)
front_desk.permission_sets.add(
    PermissionSet.objects.get(code='HOTEL_RECEPTION')
)

# Housekeeping Group
housekeeping = UserGroup.objects.create(
    code='HOUSEKEEPING',
    name='Housekeeping Staff',
    default_profile=Role.objects.get(name='User')
)
housekeeping.permission_sets.add(
    PermissionSet.objects.get(code='HOTEL_HOUSEKEEPING')
)

# Management Group
hotel_mgmt = UserGroup.objects.create(
    code='HOTEL_MGMT',
    name='Hotel Management',
    default_profile=Role.objects.get(name='Manager')
)
hotel_mgmt.permission_sets.add(
    PermissionSet.objects.get(code='HOTEL_FULL_ACCESS')
)
```

---

## 🔧 Frontend Integration

### **Updated Route Protection**

```typescript
// appsRoute.ts - Now check user groups too!

const appsRoute: Routes = [
  {
    key: "appsSales.dashboard",
    path: `${APP_PREFIX_PATH}/sales/dashboard`,
    component: lazy(() => import("@/views/sales/SalesDashboard")),
    authority: [ADMIN], // Role-based (existing)
    requiredGroups: ["SALES_DEPT", "STORE_MGR"], // NEW: Group-based
    requiredPermissions: [
      // NEW: Object-level permissions
      { objectId: 2600, action: "read" }, // Can read customers
      { objectId: 2700, action: "read" }, // Can read invoices
    ],
  },
  {
    key: "appsSales.customers",
    path: `${APP_PREFIX_PATH}/sales/customers`,
    component: lazy(() => import("@/views/customers/Customers")),
    authority: [], // Open to all with module access
    requiredGroups: ["SALES_DEPT", "CASHIERS"], // Must be in these groups
    requiredPermissions: [
      { objectId: 2600, action: "read" }, // Must be able to read customers
    ],
  },
];
```

### **Updated Auth Token**

```typescript
// types/auth.ts - Add user groups to token

interface User {
  id: string;
  email: string;
  username: string;
  authority: string[]; // Existing: module access
  roles: string[]; // Existing: role names
  userGroups: UserGroup[]; // NEW: User groups
  permissions: {
    // NEW: Object-level permissions
    sets: string[]; // Permission set codes
    objects: {
      [objectId: string]: {
        read: boolean;
        insert: boolean;
        modify: boolean;
        delete: boolean;
        execute: boolean;
      };
    };
  };
}

interface UserGroup {
  code: string;
  name: string;
  defaultRole: string;
  permissionSets: string[];
}
```

---

## 🎬 Complete Implementation Flow

### **Step 1: User Creation & Group Assignment**

```python
# Admin creates new user
new_user = CustomUser.objects.create_user(
    email='john@company.com',
    username='john',
    full_name='John Doe'
)

# Add user to Sales Department group
sales_dept = UserGroup.objects.get(code='SALES_DEPT')
sales_dept.add_member(new_user)

# User automatically gets:
# 1. Cashier role (from group's default_profile)
# 2. CASHIER permission set (from role)
# 3. SALES_BASIC permission set (from group)
```

### **Step 2: Login & Token Generation**

```python
# authentication/serializers.py - Update JWT token

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)

        # Existing
        token['authority'] = user.get_authority()
        token['roles'] = [role.name for role in user.roles.all()]

        # NEW: User groups
        token['user_groups'] = user.get_user_groups_info()

        # NEW: Permission sets
        permission_sets = user.get_all_permission_sets()
        token['permission_sets'] = [ps.code for ps in permission_sets]

        # NEW: Object-level permissions summary
        token['permissions'] = user.get_all_permissions()

        return token
```

### **Step 3: Frontend Permission Check**

```typescript
// hooks/useAuth.ts - Add permission checking

export function useAuth() {
  const user = useSelector((state) => state.auth.user);

  const hasPermission = (objectId: number, action: string) => {
    return user?.permissions?.objects?.[objectId]?.[action] === true;
  };

  const isInGroup = (groupCode: string) => {
    return user?.userGroups?.some((group) => group.code === groupCode);
  };

  const hasAnyGroup = (groupCodes: string[]) => {
    return groupCodes.some((code) => isInGroup(code));
  };

  return {
    user,
    hasPermission,
    isInGroup,
    hasAnyGroup,
    // ... existing methods
  };
}
```

---

## 📋 Migration Path

### **Phase 1: Add UserGroup Model**

```bash
# Create the model in authentication/models.py
python manage.py makemigrations authentication
python manage.py migrate
```

### **Phase 2: Create Default Groups**

```python
# Create management command: create_default_user_groups.py

# Creates groups like:
# - ADMIN_GROUP
# - MANAGER_GROUP
# - SALES_DEPT
# - CASHIERS
# - WAREHOUSE
```

### **Phase 3: Migrate Existing Users**

```python
# Move users from direct role assignment to groups
# Maintain backward compatibility
```

---

## ✨ Key Advantages

1. **Organizational Clarity**

   - Groups match real company structure
   - Easy to explain to end users
   - Clear hierarchy

2. **Simplified Management**

   - Change group permissions → all members affected
   - Add/remove users easily
   - No individual permission management

3. **Flexibility**

   - Multiple groups per user
   - Override permissions when needed
   - Mix and match permission sets

4. **Scalability**
   - Add new departments as groups
   - Assign bulk permissions
   - Easy onboarding/offboarding

---

## 🎯 Summary

```
USER
└─ Member of: Sales Department (User Group)
   ├─ Default Profile: Cashier (Role)
   │  └─ Module Access: sales, customers, items
   │
   └─ Permission Sets: CASHIER + SALES_BASIC
      ├─ CASHIER:
      │  ├─ Customer: Read, Insert, Modify
      │  └─ Invoice: Read, Insert
      │
      └─ SALES_BASIC:
         ├─ Sales Order: Read, Insert
         └─ Item: Read

= COMBINED PERMISSIONS:
  ✅ Can access Sales, Customers, Items modules
  ✅ Can view, add, edit customers (but not delete)
  ✅ Can view, add invoices (but not edit or delete)
  ✅ Can view, add sales orders
  ✅ Can view items (but not add, edit, or delete)
```

This is **powerful, flexible, and matches real-world organizational structures!** 🎉

Would you like me to implement this UserGroup model?
