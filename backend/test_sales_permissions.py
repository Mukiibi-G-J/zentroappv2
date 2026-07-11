"""
Quick test script for Sales Permission Pilot
Run in Django shell: python manage.py shell < test_sales_permissions.py
Or copy-paste into Django shell
"""

from authentication.models import CustomUser, UserGroup
from company.models import Company
from django.db import connection

print("\n" + "=" * 70)
print("SALES PERMISSION PILOT - QUICK TEST")
print("=" * 70)

# Switch to EKK tenant
try:
    tenant = Company.objects.filter(schema_name="ekk").first()
    if not tenant:
        print("❌ EKK tenant not found!")
        exit()

    connection.set_tenant(tenant)
    print(f"✅ Connected to tenant: {tenant.name} ({tenant.schema_name})\n")
except Exception as e:
    print(f"❌ Error connecting to tenant: {e}")
    exit()

# Test 1: Check User Groups exist
print("📋 Test 1: User Groups")
print("-" * 70)
groups = UserGroup.objects.all()
if groups.exists():
    for group in groups:
        member_count = group.members.count()
        perm_count = group.permission_sets.count()
        print(f"  ✅ {group.name} ({group.code})")
        print(f"     Role: {group.default_profile}")
        print(f"     Members: {member_count}")
        print(f"     Permission Sets: {perm_count}")
else:
    print("  ❌ No user groups found! Run setup command first.")

# Test 2: Check Permission Sets
print("\n📋 Test 2: Permission Sets")
print("-" * 70)
from permissions.models import PermissionSet

perm_sets = PermissionSet.objects.all()
if perm_sets.exists():
    for ps in perm_sets:
        line_count = ps.permission_lines.count()
        print(f"  ✅ {ps.name} ({ps.code})")
        print(f"     Linked Role: {ps.linked_role}")
        print(f"     Permission Lines: {line_count}")
else:
    print("  ❌ No permission sets found!")

# Test 3: Check Sales Objects
print("\n📋 Test 3: Sales Objects")
print("-" * 70)
from base.models import Objects

sales_objects = Objects.objects.filter(object_id__gte=2600, object_id__lte=2720)
if sales_objects.exists():
    for obj in sales_objects:
        print(f"  ✅ {obj.object_name} (ID: {obj.object_id})")
else:
    print("  ❌ No sales objects found!")

# Test 4: Test User Permissions (if we have users in groups)
print("\n📋 Test 4: User Permissions")
print("-" * 70)
cashier_users = CustomUser.objects.filter(user_groups__code="SALES_CASHIERS")
if cashier_users.exists():
    user = cashier_users.first()
    print(f"Testing user: {user.email}")
    print(f"Groups: {list(user.user_groups.values_list('name', flat=True))}")
    print(f"Roles: {list(user.roles.values_list('name', flat=True))}")

    print("\nPermission Tests:")
    tests = [
        (2600, "read", "View customers"),
        (2600, "insert", "Create customers"),
        (2600, "modify", "Edit customers"),
        (2600, "delete", "Delete customers"),
        (2700, "read", "View invoices"),
        (2700, "insert", "Create invoices"),
        (2700, "modify", "Edit invoices"),
        (2700, "delete", "Delete invoices"),
    ]

    for obj_id, perm, desc in tests:
        can_do, source = user.check_object_permission(obj_id, perm)
        icon = "✅" if can_do else "❌"
        print(f"  {icon} {desc}: {can_do}")
        if can_do:
            print(f"      Source: {source}")
else:
    print("  ⚠️  No users in SALES_CASHIERS group yet")
    print("     Add users via Django admin to test permissions")

# Summary
print("\n" + "=" * 70)
print("✅ TEST COMPLETE")
print("=" * 70)
print("\n💡 Next Steps:")
print("  1. Add users to groups via admin: http://ekk.localhost:8000/admin/")
print("  2. Test API endpoints with curl or Postman")
print("  3. Proceed to Day 3 (Frontend integration)")
print("")
