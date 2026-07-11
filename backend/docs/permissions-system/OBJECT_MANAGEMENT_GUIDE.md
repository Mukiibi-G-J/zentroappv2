# Object Management Quick Reference

## 🎯 Quick Answer: How to Handle New Objects

When you add **anything new** to your project, follow this simple process:

---

## 📊 Object ID Ranges (Reserved)

```
1000-1099   = System tables (Django, Auth, etc.)
2000-2099   = Base & Common
2100-2199   = Authentication
2200-2299   = Company
2300-2399   = Setup
2400-2499   = Config Packages
2500-2599   = Items
2600-2699   = Customers
2700-2799   = Sales
2800-2899   = Financials
2900-2999   = Postings
3000-3099   = (Reserved)
3100-3199   = Purchases
3200-3299   = Payments
3300-3399   = Dimension
3400-3499   = Hotel Management ⭐ (your new module)
3500-3599   = Production ⭐ (your new module)
3600-3699   = Resources ⭐ (your new module)
3700-3799   = Future Module 1
3800-3899   = Future Module 2
...
5000+       = Auto-assigned (if not in dictionary)

10000-19999 = Pages/Views
20000-29999 = Reports
30000-39999 = API Endpoints
40000-49999 = Codeunits/Business Logic
```

---

## 🆕 Scenario 1: Adding a New Database Table

### Example: You create a new `Booking` model in `hotel_management` app

**Step 1**: Add to object registry

**File**: `base/management/commands/populate_objects_table.py`

```python
TABLE_OBJECT_IDS = {
    # ... existing entries ...

    # Hotel Management (3400-3499) - NEW RANGE
    "hotel_management_room": 3400,
    "hotel_management_roomtype": 3401,
    "hotel_management_booking": 3402,  # ← ADD THIS
    "hotel_management_guest": 3403,
    "hotel_management_reservation": 3404,
}
```

**Step 2**: Run the command

```bash
python manage.py populate_objects_table
```

**Step 3**: Done! ✅

The object is now:

- ✅ Tracked in the system
- ✅ Available for permission assignment
- ✅ Has unique ID 3402
- ✅ Can be used in permission checks

---

## 📄 Scenario 2: Adding a New Page/View

### Example: You create a booking management page

**Step 1**: Add to page registry

**File**: `base/management/commands/register_pages.py`

```python
PAGES = {
    # ... existing entries ...

    # Hotel Pages (10400-10499)
    "booking_list": {
        "id": 10401,
        "name": "Booking List",
        "caption": "Hotel Bookings",
        "app_label": "hotel_management",
        "route": "/hotel/bookings",
    },
    "booking_detail": {
        "id": 10402,
        "name": "Booking Detail",
        "caption": "Booking Details",
        "app_label": "hotel_management",
        "route": "/hotel/bookings/:id",
    },
}
```

**Step 2**: Run the command

```bash
python manage.py register_pages
```

**Step 3**: Use in frontend

```typescript
// In your component
import { useObjectPermission, OBJECTS } from "@/hooks/useObjectPermission";

// Add to OBJECTS constant
export const OBJECTS = {
  // ... existing ...
  BOOKING_LIST_PAGE: 10401,
  BOOKING_DETAIL_PAGE: 10402,
};

// Use in component
const BookingList = () => {
  const { canRead } = useObjectPermission(OBJECTS.BOOKING_LIST_PAGE);

  if (!canRead) {
    return <div>Access Denied</div>;
  }

  // ... rest of component
};
```

---

## 📈 Scenario 3: Adding a New Report

### Example: You create a hotel occupancy report

**Step 1**: Add to page registry (with type REPORT)

**File**: `base/management/commands/register_pages.py`

```python
PAGES = {
    # ... existing entries ...

    # Hotel Reports (20400-20499)
    "hotel_occupancy_report": {
        "id": 20401,
        "name": "Hotel Occupancy Report",
        "caption": "Room Occupancy Analysis",
        "app_label": "hotel_management",
        "type": "REPORT",  # ← Mark as REPORT
    },
}
```

**Step 2**: Run the command

```bash
python manage.py register_pages
```

---

## 🔌 Scenario 4: Adding a New API Endpoint

### Example: Special booking API

**Option A: Manual Registration**

```python
# In Django shell or a command
from base.models import Objects, ObjectType

api_type = ObjectType.objects.get(code='API')

Objects.objects.create(
    object_id=30401,
    object_name="Booking API",
    object_caption="Hotel Booking API Endpoint",
    object_type='API',
    object_type_ref=api_type,
    app_label='hotel_management',
    object_subtype='Custom',
    requires_permission=True
)
```

**Option B: Add to register_pages.py**

```python
PAGES = {
    # ... existing ...

    "booking_api": {
        "id": 30401,
        "name": "Booking API",
        "caption": "Hotel Booking API",
        "app_label": "hotel_management",
        "type": "API",
    },
}
```

---

## 🎯 Scenario 5: Entire New Module

### Example: You add a `restaurant` module

**Step 1**: Reserve an ID range

```python
# In your planning doc or comments
# Restaurant Module: 3900-3999 (tables)
#                   10900-10999 (pages)
#                   20900-20999 (reports)
```

**Step 2**: Add tables to populate_objects_table.py

```python
TABLE_OBJECT_IDS = {
    # ... existing ...

    # Restaurant Module (3900-3999)
    "restaurant_menu": 3900,
    "restaurant_menuitem": 3901,
    "restaurant_order": 3902,
    "restaurant_table": 3903,
}
```

**Step 3**: Add pages to register_pages.py

```python
PAGES = {
    # ... existing ...

    # Restaurant Pages (10900-10999)
    "menu_management": {
        "id": 10901,
        "name": "Menu Management",
        "caption": "Restaurant Menu",
        "app_label": "restaurant",
        "route": "/restaurant/menu",
    },
}
```

**Step 4**: Run both commands

```bash
python manage.py populate_objects_table
python manage.py register_pages
```

---

## 🔄 Automatic vs Manual Registration

### Automatic (Recommended for Tables):

```python
# Just add to TABLE_OBJECT_IDS and run command
python manage.py populate_objects_table
```

**Pros**:

- ✅ Automatic discovery of all models
- ✅ Syncs with database automatically
- ✅ Updates existing entries

**When to use**: Always for database tables

### Manual (For Non-Tables):

```python
# Add to register_pages.py and run command
python manage.py register_pages
```

**Pros**:

- ✅ Full control over what's registered
- ✅ Can add pages that don't have models
- ✅ Can add reports, APIs, etc.

**When to use**: Pages, Reports, APIs, Codeunits

---

## 🎨 Best Practices

### 1. **Always Reserve Ranges**

When starting a new module, reserve 100 IDs:

```python
# Bad ❌
"hotel_room": 5234,  # Random number
"hotel_booking": 2891,  # In wrong range

# Good ✅
"hotel_room": 3400,  # Start of hotel range
"hotel_booking": 3401,  # Next in sequence
```

### 2. **Use Consistent Naming**

```python
# Bad ❌
"hotel_management_Room": 3400,  # Inconsistent case
"HotelBooking": 3401,  # No app prefix

# Good ✅
"hotel_management_room": 3400,
"hotel_management_booking": 3401,
```

### 3. **Document Your Ranges**

Add comments in the code:

```python
TABLE_OBJECT_IDS = {
    # Hotel Management (3400-3499)
    # - 3400-3419: Core entities (Room, RoomType, etc.)
    # - 3420-3439: Booking related
    # - 3440-3459: Guest management
    # - 3460-3499: Reserved for future

    "hotel_management_room": 3400,
    "hotel_management_roomtype": 3401,
    # ...
}
```

### 4. **Keep Related Objects Together**

```python
# Bad ❌
"hotel_management_room": 3400,
"sales_invoice": 2703,
"hotel_management_booking": 3401,  # Separated from room

# Good ✅
"hotel_management_room": 3400,
"hotel_management_booking": 3401,  # Together
"hotel_management_guest": 3402,  # Together
```

---

## 🔍 How to Find Available IDs

### Method 1: Check Your Dictionary

```python
# In populate_objects_table.py
TABLE_OBJECT_IDS = {
    # Find the highest ID in your range
    "hotel_management_reservation": 3404,  # Last one
    # Next available: 3405
}
```

### Method 2: Query Database

```python
# In Django shell
from base.models import Objects

# Find highest ID in hotel range
Objects.objects.filter(
    object_id__gte=3400,
    object_id__lt=3500
).order_by('-object_id').first()
```

### Method 3: Check Your Planning Doc

Maintain a file like `OBJECT_ID_REGISTRY.md`:

```markdown
## Object ID Registry

### Hotel Management (3400-3499)

- 3400: Room ✅ Used
- 3401: RoomType ✅ Used
- 3402: Booking ✅ Used
- 3403: Guest ✅ Used
- 3404: Reservation ✅ Used
- 3405-3499: Available 🟢
```

---

## ⚡ Quick Commands Reference

```bash
# Discover all database tables
python manage.py populate_objects_table

# Register pages/reports/APIs
python manage.py register_pages

# Setup object types (run once)
python manage.py setup_object_types

# Create default permissions (run once)
python manage.py setup_default_permissions

# Check what objects exist
python manage.py shell
>>> from base.models import Objects
>>> Objects.objects.filter(app_label='hotel_management')
```

---

## 🚨 Common Mistakes to Avoid

### ❌ Mistake 1: Reusing IDs

```python
# Never reuse an ID!
"old_feature": 3400,  # Deleted this
"new_feature": 3400,  # ❌ Don't reuse!
```

**Why?**: Old permission references will break

### ❌ Mistake 2: Using Random IDs

```python
"my_model": 9876,  # ❌ Random number
```

**Why?**: No organization, hard to manage

### ❌ Mistake 3: Not Running Commands

```python
# After adding to dictionary...
# ❌ Forgot to run: python manage.py populate_objects_table
```

**Why?**: Object won't exist in database

### ❌ Mistake 4: Forgetting to Reserve Range

```python
# Started without planning
"module_thing1": 5000,  # Auto-assigned
"module_thing2": 5001,  # Auto-assigned
# ❌ Now they're scattered
```

**Why?**: Hard to find related objects later

---

## 📝 Checklist: Adding New Feature

- [ ] Decide which range to use (tables, pages, reports)
- [ ] Reserve next available ID in that range
- [ ] Add to appropriate registry file
- [ ] Run the registration command
- [ ] Verify object appears in database
- [ ] Update frontend constants (OBJECTS)
- [ ] Add permission checks in code
- [ ] Test with different user roles
- [ ] Document in your ID registry

---

## 🎯 Real Example: Complete Flow

**Task**: Add a "Room Service" feature to hotel module

### Step 1: Plan IDs

```
Tables: 3400-3499 (hotel range)
  - Last used: 3404 (Reservation)
  - Next: 3405 (RoomService)
  - Next: 3406 (RoomServiceItem)

Pages: 10400-10499 (hotel pages)
  - Last used: 10402
  - Next: 10403 (RoomServiceList)
  - Next: 10404 (RoomServiceDetail)
```

### Step 2: Add to populate_objects_table.py

```python
TABLE_OBJECT_IDS = {
    # ... existing hotel entries ...
    "hotel_management_reservation": 3404,
    "hotel_management_roomservice": 3405,  # NEW
    "hotel_management_roomserviceitem": 3406,  # NEW
}
```

### Step 3: Add to register_pages.py

```python
PAGES = {
    # ... existing hotel entries ...
    "room_service_list": {
        "id": 10403,
        "name": "Room Service List",
        "caption": "Room Service Orders",
        "app_label": "hotel_management",
        "route": "/hotel/room-service",
    },
    "room_service_detail": {
        "id": 10404,
        "name": "Room Service Detail",
        "caption": "Room Service Order Detail",
        "app_label": "hotel_management",
        "route": "/hotel/room-service/:id",
    },
}
```

### Step 4: Run commands

```bash
python manage.py populate_objects_table
python manage.py register_pages
```

### Step 5: Update frontend constants

```typescript
// zentro-frontend/src/hooks/useObjectPermission.ts
export const OBJECTS = {
  // ... existing ...

  // Hotel Management - Tables
  ROOM_SERVICE: 3405,
  ROOM_SERVICE_ITEM: 3406,

  // Hotel Management - Pages
  ROOM_SERVICE_LIST_PAGE: 10403,
  ROOM_SERVICE_DETAIL_PAGE: 10404,
} as const;
```

### Step 6: Use in component

```typescript
const RoomServiceList = () => {
  const { canRead, canInsert, canModify, canDelete } = useObjectPermission(
    OBJECTS.ROOM_SERVICE
  );

  if (!canRead) {
    return <AccessDenied />;
  }

  return (
    <div>
      <h1>Room Service Orders</h1>
      {canInsert && <button>New Order</button>}
      {/* ... */}
    </div>
  );
};
```

### Step 7: Add to permission sets (admin)

Go to Django admin → Permission Sets → Select a permission set → Add these permission lines:

- Room Service (3405): Read ✓, Insert ✓, Modify ✓, Delete ✗
- Room Service List Page (10403): Read ✓, Execute ✓

**Done!** ✅

---

## 💡 Pro Tips

### Tip 1: Use Constants

```python
# In your app
HOTEL_OBJECT_IDS = {
    'ROOM': 3400,
    'BOOKING': 3401,
    'GUEST': 3402,
}

# Easy to reference
from .constants import HOTEL_OBJECT_IDS
user.check_object_permission(HOTEL_OBJECT_IDS['ROOM'], 'read')
```

### Tip 2: Batch Register

```python
# Create a script to register all your module's objects at once
# base/management/commands/setup_hotel_objects.py

def handle(self, *args, **options):
    call_command('populate_objects_table')
    call_command('register_pages')
    call_command('setup_hotel_permissions')  # Your custom command
```

### Tip 3: Document as You Go

Keep a `HOTEL_OBJECTS.md` file in your module:

```markdown
## Hotel Module Objects

### Tables (3400-3499)

- 3400: Room - Hotel room entity
- 3401: RoomType - Room categories
- 3402: Booking - Booking records

### Pages (10400-10499)

- 10401: Booking List - Main booking view
- 10402: Booking Detail - Single booking view
```

---

## 🎉 Summary

**For Tables**: Add to `TABLE_OBJECT_IDS` → Run `populate_objects_table`

**For Pages**: Add to `PAGES` → Run `register_pages`

**For Everything**: Use ID ranges, document your choices, run the commands!

---

**Questions? Check the main implementation plan: `PERMISSION_IMPLEMENTATION_PLAN.md`**



