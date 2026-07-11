# 🎯 Sales Module Permission Pilot - Implementation Plan

## 📋 Overview

**Objective**: Implement the new permission system for the **Sales module ONLY** as a pilot project.

**Why Pilot with Sales?**

- ✅ Sales is actively used
- ✅ Has clear user roles (Cashier, Sales, Manager)
- ✅ Has multiple tables (Customer, Invoice, etc.)
- ✅ Real-world testing with actual users
- ✅ If it works, roll out to other modules

**Timeline**: 2-3 days

---

## 🎯 Phase 1: Backend Setup (Day 1)

### **Step 1.1: Create UserGroup Model** ⏱️ 30 mins

**File**: `authentication/models.py`

Add the UserGroup model:

```python
class UserGroup(BaseModel):
    """User Group - Collections of users with shared permissions"""

    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    default_profile = models.ForeignKey(
        'Role',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='user_groups_default'
    )
    permission_sets = models.ManyToManyField(
        'permissions.PermissionSet',
        related_name='user_groups',
        blank=True
    )
    members = models.ManyToManyField(
        'CustomUser',
        related_name='user_groups',
        blank=True
    )
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        'CustomUser',
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
```

**Commands**:

```bash
python manage.py makemigrations authentication
python manage.py migrate
```

---

### **Step 1.2: Register Sales Tables as Objects** ⏱️ 45 mins

**File**: `base/management/commands/populate_sales_objects.py` (NEW)

Create a simplified command for Sales only:

```python
from django.core.management.base import BaseCommand
from base.models import Objects, ObjectType

class Command(BaseCommand):
    help = 'Register Sales module tables as objects'

    def handle(self, *args, **options):
        # Get Table object type
        table_obj_type, _ = ObjectType.objects.get_or_create(
            name='Table',
            defaults={'description': 'Database tables'}
        )

        # Sales module tables
        SALES_TABLES = [
            (2600, "Customer", "sales.Customer"),
            (2610, "Customer Ledger Entry", "sales.CustomerLedgerEntry"),
            (2700, "Sales Invoice", "sales.SalesInvoice"),
            (2710, "Sales Invoice Line", "sales.SalesInvoiceLine"),
            (2720, "Sales Receivable Setup", "sales.SalesReceivable"),
        ]

        created_count = 0
        updated_count = 0

        for object_id, object_name, related_model in SALES_TABLES:
            obj, created = Objects.objects.update_or_create(
                object_id=object_id,
                defaults={
                    'object_type_ref': table_obj_type,
                    'object_name': object_name,
                    'requires_permission': True,
                    'related_model': related_model,
                }
            )

            if created:
                created_count += 1
                self.stdout.write(f'  ✓ Created: {object_name} (ID: {object_id})')
            else:
                updated_count += 1
                self.stdout.write(f'  🔄 Updated: {object_name} (ID: {object_id})')

        self.stdout.write(self.style.SUCCESS(
            f'\n✅ Sales objects setup complete!'
            f'\n📝 Created: {created_count} objects'
            f'\n🔄 Updated: {updated_count} objects'
        ))
```

**Run it**:

```bash
python manage.py populate_sales_objects
```

---

### **Step 1.3: Create Sales Permission Sets** ⏱️ 45 mins

**File**: `permissions/management/commands/setup_sales_permissions.py` (NEW)

```python
from django.core.management.base import BaseCommand
from permissions.models import PermissionSet, PermissionSetLine
from authentication.models import Role
from base.models import Objects

class Command(BaseCommand):
    help = 'Create permission sets for Sales module'

    def handle(self, *args, **options):
        self.stdout.write('🔐 Setting up Sales permission sets...\n')

        # Get Sales-related objects
        sales_objects = Objects.objects.filter(
            object_id__in=[2600, 2610, 2700, 2710, 2720]
        )

        if not sales_objects.exists():
            self.stdout.write(self.style.ERROR(
                '⚠️  No sales objects found! Run populate_sales_objects first.'
            ))
            return

        # Define permission sets
        permission_configs = [
            {
                'code': 'SALES_CASHIER',
                'name': 'Sales - Cashier',
                'description': 'Cashier permissions for sales operations',
                'role': 'Cashier',
                'permissions': {
                    2600: ['read', 'insert', 'modify'],      # Customer
                    2610: ['read'],                          # Customer Ledger Entry
                    2700: ['read', 'insert'],                # Sales Invoice
                    2710: ['read', 'insert'],                # Sales Invoice Line
                    2720: ['read'],                          # Sales Setup
                }
            },
            {
                'code': 'SALES_FULL',
                'name': 'Sales - Full Access',
                'description': 'Full access to all sales operations',
                'role': 'Sales',
                'permissions': {
                    2600: ['read', 'insert', 'modify', 'delete'],  # Customer
                    2610: ['read', 'insert', 'modify'],            # Customer Ledger Entry
                    2700: ['read', 'insert', 'modify', 'delete'],  # Sales Invoice
                    2710: ['read', 'insert', 'modify', 'delete'],  # Sales Invoice Line
                    2720: ['read', 'modify'],                      # Sales Setup
                }
            },
            {
                'code': 'SALES_VIEW_ONLY',
                'name': 'Sales - View Only',
                'description': 'Read-only access to sales data',
                'role': None,  # Not linked to a default role
                'permissions': {
                    2600: ['read'],  # Customer
                    2610: ['read'],  # Customer Ledger Entry
                    2700: ['read'],  # Sales Invoice
                    2710: ['read'],  # Sales Invoice Line
                    2720: ['read'],  # Sales Setup
                }
            }
        ]

        created_count = 0

        for config in permission_configs:
            # Get or create role
            role = None
            if config['role']:
                role, _ = Role.objects.get_or_create(
                    name=config['role'],
                    defaults={'description': f'{config["role"]} role'}
                )

            # Create permission set
            perm_set, created = PermissionSet.objects.get_or_create(
                code=config['code'],
                defaults={
                    'name': config['name'],
                    'description': config['description'],
                    'linked_role': role,
                    'is_active': True,
                }
            )

            if created:
                created_count += 1
                self.stdout.write(f'  ✓ Created: {perm_set.name}')
            else:
                self.stdout.write(f'  ⚠️  {perm_set.name} already exists')
                # Clear existing lines if updating
                PermissionSetLine.objects.filter(permissionset=perm_set).delete()

            # Create permission lines
            lines_created = 0
            for obj_id, perms in config['permissions'].items():
                try:
                    obj = Objects.objects.get(object_id=obj_id)

                    line_data = {
                        'read_permission': 'read' in perms,
                        'insert_permission': 'insert' in perms,
                        'modify_permission': 'modify' in perms,
                        'delete_permission': 'delete' in perms,
                        'execute_permission': False,  # Not used for tables
                    }

                    PermissionSetLine.objects.create(
                        permissionset=perm_set,
                        application_object=obj,
                        **line_data
                    )
                    lines_created += 1

                except Objects.DoesNotExist:
                    self.stdout.write(f'  ⚠️  Object {obj_id} not found')

            self.stdout.write(f'    └── Created {lines_created} permission lines')

        self.stdout.write('\n' + '='*50)
        self.stdout.write(self.style.SUCCESS(
            f'✅ Sales permission sets setup complete!'
            f'\n📝 Created: {created_count} permission sets'
        ))
```

**Run it**:

```bash
python manage.py setup_sales_permissions
```

---

### **Step 1.4: Create Sales User Groups** ⏱️ 30 mins

**File**: `authentication/management/commands/create_sales_groups.py` (NEW)

```python
from django.core.management.base import BaseCommand
from authentication.models import UserGroup, Role
from permissions.models import PermissionSet

class Command(BaseCommand):
    help = 'Create user groups for Sales module'

    def handle(self, *args, **options):
        self.stdout.write('👥 Creating Sales user groups...\n')

        # Define user groups
        groups_config = [
            {
                'code': 'SALES_CASHIERS',
                'name': 'Sales - Cashiers',
                'description': 'All sales cashiers',
                'default_role': 'Cashier',
                'permission_sets': ['SALES_CASHIER']
            },
            {
                'code': 'SALES_TEAM',
                'name': 'Sales Team',
                'description': 'Sales representatives with full sales access',
                'default_role': 'Sales',
                'permission_sets': ['SALES_FULL']
            },
            {
                'code': 'SALES_VIEWERS',
                'name': 'Sales - Viewers',
                'description': 'Users who can only view sales data',
                'default_role': None,
                'permission_sets': ['SALES_VIEW_ONLY']
            }
        ]

        created_count = 0

        for config in groups_config:
            # Get role if specified
            default_role = None
            if config['default_role']:
                default_role, _ = Role.objects.get_or_create(
                    name=config['default_role']
                )

            # Create user group
            group, created = UserGroup.objects.get_or_create(
                code=config['code'],
                defaults={
                    'name': config['name'],
                    'description': config['description'],
                    'default_profile': default_role,
                    'is_active': True
                }
            )

            if created:
                created_count += 1
                self.stdout.write(f'  ✓ Created: {group.name}')

                # Add permission sets
                for perm_code in config['permission_sets']:
                    try:
                        perm_set = PermissionSet.objects.get(code=perm_code)
                        group.permission_sets.add(perm_set)
                        self.stdout.write(f'    └── Added permission set: {perm_code}')
                    except PermissionSet.DoesNotExist:
                        self.stdout.write(f'    ⚠️  Permission set {perm_code} not found')
            else:
                self.stdout.write(f'  ⚠️  {group.name} already exists')

        self.stdout.write('\n' + '='*50)
        self.stdout.write(self.style.SUCCESS(
            f'✅ Sales user groups setup complete!'
            f'\n📝 Created: {created_count} user groups'
        ))
```

**Run it**:

```bash
python manage.py create_sales_groups
```

---

### **Step 1.5: Update CustomUser Methods** ⏱️ 30 mins

**File**: `authentication/models.py`

Update existing `check_object_permission` method:

```python
def check_object_permission(self, object_id, permission_type):
    """
    Check if user has specific permission for an object.
    Now checks user groups first, then direct roles.
    """
    from permissions.models import PermissionSetLine

    # Get all permission sets from groups + roles
    permission_sets = []

    # 1. From user groups (priority)
    for group in self.user_groups.filter(is_active=True):
        permission_sets.extend(group.permission_sets.all())
        # Also get sets from group's default role
        if group.default_profile:
            from permissions.models import PermissionSet
            role_sets = PermissionSet.objects.filter(
                linked_role=group.default_profile,
                is_active=True
            )
            permission_sets.extend(role_sets)

    # 2. From direct role assignments (fallback)
    for role in self.roles.all():
        from permissions.models import PermissionSet
        role_sets = PermissionSet.objects.filter(
            linked_role=role,
            is_active=True
        )
        permission_sets.extend(role_sets)

    # Remove duplicates
    permission_sets = list(set(permission_sets))

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
```

Add new method:

```python
def get_user_groups_info(self):
    """Get user's group membership info for JWT token"""
    groups = []
    for group in self.user_groups.filter(is_active=True):
        groups.append({
            'code': group.code,
            'name': group.name,
            'default_role': group.default_profile.name if group.default_profile else None,
            'permission_sets': [ps.code for ps in group.permission_sets.all()]
        })
    return groups
```

---

### **Step 1.6: Setup Django Admin** ⏱️ 20 mins

**File**: `authentication/admin.py`

Add UserGroup admin:

```python
from django.contrib import admin
from .models import UserGroup

@admin.register(UserGroup)
class UserGroupAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'default_profile', 'is_active', 'member_count']
    list_filter = ['is_active', 'default_profile']
    search_fields = ['name', 'code', 'description']
    filter_horizontal = ['permission_sets', 'members']

    fieldsets = (
        ('Basic Information', {
            'fields': ('code', 'name', 'description', 'is_active')
        }),
        ('Permissions', {
            'fields': ('default_profile', 'permission_sets')
        }),
        ('Members', {
            'fields': ('members',)
        }),
    )

    def member_count(self, obj):
        return obj.members.count()
    member_count.short_description = 'Members'
```

---

## 🎯 Phase 2: Testing Setup (Day 2 Morning)

### **Step 2.1: Create Test Data** ⏱️ 30 mins

**Commands to run**:

```bash
# 1. Populate sales objects
python manage.py populate_sales_objects

# 2. Setup sales permissions
python manage.py setup_sales_permissions

# 3. Create sales groups
python manage.py create_sales_groups

# 4. Verify in admin
# Visit: http://ekk.localhost:8000/admin/
# Check:
# - Base > Objects (should see 5 sales objects)
# - Permissions > Permission Sets (should see 3 sales sets)
# - Authentication > User Groups (should see 3 sales groups)
```

---

### **Step 2.2: Add Test Users to Groups** ⏱️ 20 mins

**Via Django Admin**:

1. Go to **User Groups**
2. Open "Sales - Cashiers"
3. Add test users to Members
4. Save

**Or via Django shell**:

```python
from authentication.models import CustomUser, UserGroup

# Get test user
sarah = CustomUser.objects.get(email='sarah@company.com')

# Add to Sales Cashiers group
cashiers_group = UserGroup.objects.get(code='SALES_CASHIERS')
cashiers_group.members.add(sarah)

# Check what Sarah got
print(f"User Groups: {sarah.user_groups.all()}")
print(f"Roles: {sarah.roles.all()}")  # Should have Cashier role
```

---

### **Step 2.3: Test Permission Checking** ⏱️ 30 mins

**Via Django shell**:

```python
from authentication.models import CustomUser

sarah = CustomUser.objects.get(email='sarah@company.com')

# Test permissions
print("Testing Sarah's permissions:")
print("="*50)

# Can read customers?
can_read, source = sarah.check_object_permission(2600, 'read')
print(f"Read Customer: {can_read} ({source})")

# Can delete customers?
can_delete, source = sarah.check_object_permission(2600, 'delete')
print(f"Delete Customer: {can_delete} ({source})")

# Can create invoices?
can_insert, source = sarah.check_object_permission(2700, 'insert')
print(f"Create Invoice: {can_insert} ({source})")

# Can modify invoices?
can_modify, source = sarah.check_object_permission(2700, 'modify')
print(f"Modify Invoice: {can_modify} ({source})")

# Expected results for Cashier:
# Read Customer: True
# Delete Customer: False
# Create Invoice: True
# Modify Invoice: False
```

---

## 🎯 Phase 3: Backend API Integration (Day 2 Afternoon)

### **Step 3.1: Update JWT Token** ⏱️ 30 mins

**File**: `authentication/serializers.py`

Update `CustomTokenObtainPairSerializer`:

```python
@classmethod
def get_token(cls, user):
    token = super().get_token(user)

    # Existing
    token['authority'] = user.get_authority()
    token['roles'] = [role.name for role in user.roles.all()]

    # NEW: User groups
    token['user_groups'] = user.get_user_groups_info()

    # NEW: Permission sets summary
    permission_sets = []
    for group in user.user_groups.filter(is_active=True):
        permission_sets.extend(group.permission_sets.all())
    token['permission_sets'] = [ps.code for ps in set(permission_sets)]

    return token
```

---

### **Step 3.2: Add Permission Check Decorator** ⏱️ 30 mins

**File**: `authentication/decorators.py`

Add new decorator for granular permissions:

```python
from functools import wraps
from rest_framework.response import Response
from rest_framework import status

def require_object_permission(object_id, permission_type):
    """
    Decorator to check granular object permissions.

    Usage:
        @require_object_permission(2600, 'read')
        def list_customers(request):
            ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            user = request.user

            if not user.is_authenticated:
                return Response(
                    {'error': 'Authentication required'},
                    status=status.HTTP_401_UNAUTHORIZED
                )

            # Check permission
            has_permission, source = user.check_object_permission(
                object_id, permission_type
            )

            if not has_permission:
                return Response(
                    {
                        'error': 'Insufficient permissions',
                        'detail': f'You need {permission_type} permission for object {object_id}',
                        'reason': source
                    },
                    status=status.HTTP_403_FORBIDDEN
                )

            return view_func(request, *args, **kwargs)

        return wrapper
    return decorator
```

---

### **Step 3.3: Apply to Sales Views** ⏱️ 45 mins

**File**: `sales/views.py`

Add permission checks to existing views:

```python
from authentication.decorators import require_object_permission
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

# Customer views
@api_view(['GET'])
@permission_classes([IsAuthenticated])
@require_object_permission(2600, 'read')  # Customer Table
def list_customers(request):
    """List customers - requires read permission"""
    customers = Customer.objects.all()
    # ... existing code

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@require_object_permission(2600, 'insert')  # Customer Table
def create_customer(request):
    """Create customer - requires insert permission"""
    # ... existing code

@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
@require_object_permission(2600, 'modify')  # Customer Table
def update_customer(request, customer_id):
    """Update customer - requires modify permission"""
    # ... existing code

@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
@require_object_permission(2600, 'delete')  # Customer Table
def delete_customer(request, customer_id):
    """Delete customer - requires delete permission"""
    # ... existing code

# Sales Invoice views
@api_view(['GET'])
@permission_classes([IsAuthenticated])
@require_object_permission(2700, 'read')  # Sales Invoice Table
def list_invoices(request):
    """List invoices - requires read permission"""
    # ... existing code

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@require_object_permission(2700, 'insert')  # Sales Invoice Table
def create_invoice(request):
    """Create invoice - requires insert permission"""
    # ... existing code
```

---

### **Step 3.4: Test API Endpoints** ⏱️ 30 mins

**Using Postman or curl**:

```bash
# 1. Login as Sarah (Cashier)
curl -X POST http://ekk.localhost:8000/api/auth/token/ \
  -H "Content-Type: application/json" \
  -d '{"email": "sarah@company.com", "password": "password"}'

# Save the token

# 2. Test: List customers (should work ✅)
curl -X GET http://ekk.localhost:8000/api/sales/customers/ \
  -H "Authorization: Bearer YOUR_TOKEN"

# 3. Test: Create customer (should work ✅)
curl -X POST http://ekk.localhost:8000/api/sales/customers/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "Test Customer", "email": "test@example.com"}'

# 4. Test: Delete customer (should fail ❌)
curl -X DELETE http://ekk.localhost:8000/api/sales/customers/1/ \
  -H "Authorization: Bearer YOUR_TOKEN"
# Expected: 403 Forbidden - "Insufficient permissions"
```

---

## 🎯 Phase 4: Frontend Integration (Day 3)

### **Step 4.1: Update Auth Types** ⏱️ 20 mins

**File**: `zentro-frontend/src/@types/auth.ts`

```typescript
export interface UserGroup {
  code: string;
  name: string;
  default_role: string | null;
  permission_sets: string[];
}

export interface User {
  id: string;
  email: string;
  username: string;
  full_name: string;
  authority: string[]; // Existing
  roles: string[]; // Existing
  user_groups: UserGroup[]; // NEW
  permission_sets: string[]; // NEW
}
```

---

### **Step 4.2: Add Permission Hook** ⏱️ 30 mins

**File**: `zentro-frontend/src/hooks/usePermissions.ts` (NEW)

```typescript
import { useAppSelector } from "@/store";

export const usePermissions = () => {
  const user = useAppSelector((state) => state.auth.user);

  const hasPermission = (objectId: number, action: string): boolean => {
    // For now, check if user is in a group with permissions
    // Later, we'll add actual permission checking from token
    if (!user || !user.user_groups) return false;

    // Admin always has permission
    if (user.roles.includes("Admin")) return true;

    // For pilot: Check if user is in relevant groups
    const salesGroups = ["SALES_CASHIERS", "SALES_TEAM", "SALES_VIEWERS"];
    const isInSalesGroup = user.user_groups.some((group) =>
      salesGroups.includes(group.code)
    );

    return isInSalesGroup;
  };

  const isInGroup = (groupCode: string): boolean => {
    if (!user || !user.user_groups) return false;
    return user.user_groups.some((group) => group.code === groupCode);
  };

  const canCreate = (objectId: number): boolean => {
    return hasPermission(objectId, "insert");
  };

  const canEdit = (objectId: number): boolean => {
    return hasPermission(objectId, "modify");
  };

  const canDelete = (objectId: number): boolean => {
    return hasPermission(objectId, "delete");
  };

  return {
    hasPermission,
    isInGroup,
    canCreate,
    canEdit,
    canDelete,
  };
};
```

---

### **Step 4.3: Update Customer Page** ⏱️ 30 mins

**File**: `zentro-frontend/src/views/customers/Customers.tsx`

```typescript
import { usePermissions } from "@/hooks/usePermissions";

const Customers = () => {
  const { canCreate, canEdit, canDelete } = usePermissions();

  // Customer Table object ID
  const CUSTOMER_TABLE = 2600;

  const showCreateButton = canCreate(CUSTOMER_TABLE);
  const showEditButton = canEdit(CUSTOMER_TABLE);
  const showDeleteButton = canDelete(CUSTOMER_TABLE);

  return (
    <div>
      {/* Only show Create button if user has permission */}
      {showCreateButton && (
        <Button onClick={handleCreate}>Create Customer</Button>
      )}

      <Table>
        {/* ... customer list */}

        <ActionColumn>
          {showEditButton && <EditButton />}
          {showDeleteButton && <DeleteButton />}
        </ActionColumn>
      </Table>
    </div>
  );
};
```

---

### **Step 4.4: Update Sales Invoice Page** ⏱️ 30 mins

Similar updates to Sales Invoice page using object ID `2700`.

---

## 🎯 Phase 5: Testing & Validation (Day 3 Afternoon)

### **Step 5.1: User Acceptance Testing** ⏱️ 2 hours

**Test Scenarios**:

1. **Cashier User**:

   - ✅ Can view customers
   - ✅ Can add customers
   - ✅ Can edit customers
   - ❌ Cannot delete customers
   - ✅ Can view invoices
   - ✅ Can create invoices
   - ❌ Cannot edit invoices
   - ❌ Cannot delete invoices

2. **Sales User**:

   - ✅ Can do everything with customers
   - ✅ Can do everything with invoices

3. **Viewer User**:
   - ✅ Can view customers
   - ✅ Can view invoices
   - ❌ Cannot modify anything

---

### **Step 5.2: Performance Testing** ⏱️ 30 mins

```python
# Test permission check performance
import time

user = CustomUser.objects.get(email='sarah@company.com')

start = time.time()
for i in range(100):
    user.check_object_permission(2600, 'read')
end = time.time()

print(f"100 permission checks: {(end - start) * 1000:.2f}ms")
# Should be < 100ms total (< 1ms per check)
```

---

### **Step 5.3: Documentation** ⏱️ 1 hour

Create `SALES_PILOT_RESULTS.md` with:

- ✅ What worked
- ❌ What didn't work
- 📊 Performance metrics
- 💡 Lessons learned
- 🚀 Next steps

---

## 📋 Rollout Checklist

### **Before Starting**:

- [ ] Backup database
- [ ] Notify test users
- [ ] Prepare rollback plan

### **Day 1 - Backend**:

- [ ] Create UserGroup model
- [ ] Run migrations
- [ ] Register sales objects
- [ ] Create permission sets
- [ ] Create user groups
- [ ] Update CustomUser methods
- [ ] Setup admin interface

### **Day 2 - API Integration**:

- [ ] Update JWT token
- [ ] Create permission decorator
- [ ] Apply to sales views
- [ ] Test API endpoints
- [ ] Verify permissions work

### **Day 3 - Frontend**:

- [ ] Update auth types
- [ ] Create permission hook
- [ ] Update customer page
- [ ] Update invoice page
- [ ] Test UI changes
- [ ] User acceptance testing

### **After Pilot**:

- [ ] Gather feedback
- [ ] Document results
- [ ] Decide on rollout to other modules
- [ ] Create rollout timeline

---

## 🚀 Success Criteria

The pilot is successful if:

1. ✅ All permission checks work correctly
2. ✅ Performance is acceptable (< 100ms per check)
3. ✅ Users understand the system
4. ✅ No data security issues
5. ✅ Easy to manage in admin

---

## 🔄 Next Modules (After Sales Pilot)

If successful, roll out to:

1. **Items Module** (similar to sales)
2. **Purchases Module**
3. **Financials Module**
4. **Hotel Module** (if applicable)

---

## 📞 Support Plan

**During Pilot**:

- Daily check-ins with test users
- Monitor error logs
- Quick bug fixes
- Gather feedback

**Key Contacts**:

- Technical: [Your name]
- Business: Sales team lead
- Users: Test user group

---

## 🎯 Summary

**Timeline**: 3 days  
**Scope**: Sales module only  
**Users**: 5-10 test users  
**Risk**: Low (can rollback easily)  
**Benefit**: Validate entire system before full rollout

**Go/No-Go Decision After Pilot**:

- ✅ GO: Roll out to all modules
- ❌ NO-GO: Refine and re-pilot

Let's start! 🚀
