# Permission System - Quick Visual Guide

## 🎯 The Big Picture

```
┌─────────────────────────────────────────────────────────────┐
│                     YOUR APPLICATION                         │
│  ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐           │
│  │Customer│  │ Sales  │  │Reports │  │Settings│  (Objects) │
│  └────────┘  └────────┘  └────────┘  └────────┘           │
└─────────────────────────────────────────────────────────────┘
                            ↑
                            │ Controls access to
                            │
┌─────────────────────────────────────────────────────────────┐
│              PERMISSION SYSTEM (Middleware)                  │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Permission Set: "CASHIER"                            │  │
│  │  ┌────────────────────────────────────────────────┐  │  │
│  │  │ Customer: Read✓ Insert✓ Modify✓ Delete✗       │  │  │
│  │  │ Sales:    Read✓ Insert✓ Modify✓ Delete✗       │  │  │
│  │  │ Reports:  Read✓ Insert✗ Modify✗ Delete✗       │  │  │
│  │  │ Settings: Read✗ Insert✗ Modify✗ Delete✗       │  │  │
│  │  └────────────────────────────────────────────────┘  │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                            ↑
                            │ Assigned to
                            │
┌─────────────────────────────────────────────────────────────┐
│                    USER GROUPS & USERS                       │
│  ┌──────────────┐       ┌──────────────┐                   │
│  │Group:Cashiers│  ←──  │ User: John   │                   │
│  └──────────────┘       └──────────────┘                   │
└─────────────────────────────────────────────────────────────┘
```

---

## 🧩 The 4 Building Blocks

### 1️⃣ ObjectType (Categories)

```
┌─────────────┐
│  ObjectType │
├─────────────┤
│ • Table     │ ← Database tables
│ • Page      │ ← UI pages/views
│ • Report    │ ← Reports
│ • Codeunit  │ ← Business logic
└─────────────┘
```

**Think of it as**: File folders in a filing cabinet

---

### 2️⃣ ApplicationObject (Specific Items)

```
ObjectType: TABLE
┌──────────────────────┐
│ ApplicationObject    │
├──────────────────────┤
│ ID: 18               │
│ Name: Customer       │
│ Type: TABLE          │
└──────────────────────┘

ObjectType: PAGE
┌──────────────────────┐
│ ApplicationObject    │
├──────────────────────┤
│ ID: 42               │
│ Name: Sales Order    │
│ Type: PAGE           │
└──────────────────────┘
```

**Think of it as**: Individual files in those folders

---

### 3️⃣ PermissionSet (Role Templates)

```
┌────────────────────────┐
│ PermissionSet: CASHIER │
├────────────────────────┤
│ • Can ring up sales    │
│ • Can add customers    │
│ • Cannot delete data   │
│ • Cannot access reports│
└────────────────────────┘
```

**Think of it as**: Job description with access levels

---

### 4️⃣ PermissionSetLine (Actual Rules)

```
┌─────────────────────────────────────────┐
│ PermissionSetLine                       │
├─────────────────────────────────────────┤
│ Permission Set: CASHIER                 │
│ Object: Customer (Table ID: 18)         │
│ ┌─────────────────────────────────────┐ │
│ │ Read:   ✓ Yes   (Can view)          │ │
│ │ Insert: ✓ Yes   (Can create new)    │ │
│ │ Modify: ✓ Yes   (Can edit existing) │ │
│ │ Delete: ✗ None  (Cannot delete)     │ │
│ │ Execute:✗ None  (N/A for tables)    │ │
│ └─────────────────────────────────────┘ │
└─────────────────────────────────────────┘
```

**Think of it as**: Specific rules written on the job description

---

## 🔄 How Permission Check Works

```
Step 1: User John tries to delete a customer
        ↓
Step 2: System asks: "Does John have delete permission on Customer?"
        ↓
Step 3: System checks John's groups → "Cashiers" group
        ↓
Step 4: System checks "Cashiers" permission sets → "CASHIER" set
        ↓
Step 5: System finds permission line:
        Object: Customer (Table 18)
        Delete: None ✗
        ↓
Step 6: Access DENIED ❌
```

---

## 📊 Permission Matrix Example

### CASHIER Permission Set:

| Object          | Type   | ID  | Read | Insert | Modify | Delete | Execute |
| --------------- | ------ | --- | ---- | ------ | ------ | ------ | ------- |
| Customer        | Table  | 18  | ✓    | ✓      | ✓      | ✗      | -       |
| Item            | Table  | 27  | ✓    | ✗      | ✗      | ✗      | -       |
| Sales Order     | Page   | 42  | ✓    | ✓      | ✓      | ✗      | -       |
| Financial Setup | Page   | 50  | ✗    | ✗      | ✗      | ✗      | -       |
| Sales Report    | Report | 206 | ✓    | -      | -      | -      | ✓       |

Legend:

- ✓ = Yes (Has permission)
- ✗ = None (No permission)
- - = Not applicable

---

## 🎭 Different Roles, Different Access

### CASHIER vs MANAGER vs ACCOUNTANT

```
Customer Table (ID: 18)
┌─────────────────────────────────────────────────────────┐
│              Read  Insert  Modify  Delete               │
│ CASHIER       ✓      ✓       ✓       ✗                 │
│ MANAGER       ✓      ✓       ✓       ✓                 │
│ ACCOUNTANT    ✓      ✗       ✗       ✗                 │
└─────────────────────────────────────────────────────────┘

Financial Reports (ID: 301)
┌─────────────────────────────────────────────────────────┐
│              Read  Execute                              │
│ CASHIER       ✗      ✗                                  │
│ MANAGER       ✓      ✓                                  │
│ ACCOUNTANT    ✓      ✓                                  │
└─────────────────────────────────────────────────────────┘
```

---

## 🔧 Implementation Flow

### 1. Setup Phase (Admin/Developer)

```
1. Create ObjectTypes
   └─> TABLE, PAGE, REPORT, etc.

2. Create ApplicationObjects
   └─> Customer (Table 18), Sales (Page 42), etc.

3. Create PermissionSets
   └─> CASHIER, MANAGER, ACCOUNTANT

4. Add PermissionSetLines
   └─> Define what each role can do with each object

5. Link to Django Groups
   └─> Cashiers group → CASHIER permission set
```

### 2. Assignment Phase (Manager)

```
1. Create User "John"
   ↓
2. Add John to Group "Cashiers"
   ↓
3. John automatically gets all CASHIER permissions
```

### 3. Runtime Phase (Automatic)

```
1. John opens Customer page
   ↓
2. System checks: Can John read Customer?
   ↓
3. Frontend shows/hides buttons based on permissions
   - Show: "View", "Edit", "Add New"
   - Hide: "Delete"
```

---

## 💻 Code Examples

### Backend Check (Python/Django)

```python
# Check if user can delete customers
from .views import PermissionUtility

can_delete = PermissionUtility.check_object_permission(
    user=request.user,
    object_type_code='TABLE',
    object_id=18,  # Customer table
    permission_type='delete'
)

if can_delete:
    customer.delete()
else:
    return HttpResponse("Permission denied", status=403)
```

### Frontend Check (React/TypeScript)

```tsx
import { usePermissions } from "@/contexts/PermissionContext";

function CustomerPage() {
  const { checkPermission } = usePermissions();

  const canRead = checkPermission("TABLE", 18, "read");
  const canDelete = checkPermission("TABLE", 18, "delete");

  if (!canRead) {
    return <div>Access Denied</div>;
  }

  return (
    <div>
      <h1>Customers</h1>
      {canDelete && <button onClick={handleDelete}>Delete</button>}
    </div>
  );
}
```

---

## 🎯 Key Concepts Simplified

### 🔑 ObjectType

**What**: Category of things
**Example**: "Tables", "Pages", "Reports"
**Why**: Organize objects into logical groups

### 🔑 ApplicationObject

**What**: Specific thing in your app
**Example**: Customer table, Sales page
**Why**: Identify what needs permissions

### 🔑 PermissionSet

**What**: Bundle of permissions
**Example**: "CASHIER" role permissions
**Why**: Assign groups of permissions at once

### 🔑 PermissionSetLine

**What**: Individual permission rule
**Example**: "CASHIER can read Customer but not delete"
**Why**: Define exact access for each object

---

## 🚦 Permission Values

### Three Levels (Read, Insert, Modify, Delete):

```
┌──────┐
│ NONE │ ← Cannot do this action
└──────┘

┌──────┐
│ YES  │ ← Can do this action directly
└──────┘

┌──────────┐
│ INDIRECT │ ← Can do through related objects
└──────────┘
```

### Two Levels (Execute):

```
┌──────┐
│ NONE │ ← Cannot execute
└──────┘

┌──────┐
│ YES  │ ← Can execute
└──────┘
```

---

## 🎓 Real-World Analogy

Think of it like a **corporate office building**:

1. **ObjectType** = Floor types (Executive, Sales, Warehouse)
2. **ApplicationObject** = Specific rooms (CEO Office, Conference Room A)
3. **PermissionSet** = Job role (Manager, Employee, Guest)
4. **PermissionSetLine** = Access card rules
   - Manager: Can enter all rooms, can lock/unlock
   - Employee: Can enter common areas, cannot lock
   - Guest: Can only enter lobby, read-only access

---

## 📈 Benefits

### ✅ Granular

Control access to individual features, not just entire modules

### ✅ Flexible

Mix and match permissions however you need

### ✅ Auditable

Know exactly who can do what

### ✅ Scalable

Add new objects and permissions easily

### ✅ Professional

Enterprise-grade access control

---

## 🎯 Quick Start Checklist

- [ ] Create ObjectTypes (TABLE, PAGE, REPORT)
- [ ] Add ApplicationObjects (Customer, Sales, etc.)
- [ ] Design PermissionSets (CASHIER, MANAGER, etc.)
- [ ] Add PermissionSetLines (specific rules)
- [ ] Link PermissionSets to Django Groups
- [ ] Add users to appropriate groups
- [ ] Implement permission checks in code
- [ ] Test with different user roles

---

## 🔍 Debugging Tips

### User has no access:

1. Check: Is user in a group?
2. Check: Does group have permission set?
3. Check: Does permission set have the right permission line?
4. Check: Is permission level set correctly?

### User has too much access:

1. Review all groups user belongs to
2. Check all permission sets linked to those groups
3. Look for overlapping permissions
4. Remove unnecessary permission lines or groups

---

## 📚 Additional Resources

- See `PERMISSION_SYSTEM_EXPLAINED.md` for detailed implementation
- See `permission-idea.txt` for original code examples
- Django Documentation: User Authentication
- Business Central Documentation: Permission Sets

---

**Remember**: This system is powerful but starts simple. Begin with basic permission sets and add complexity as needed!



