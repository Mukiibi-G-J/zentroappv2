# ✅ Production BOM - Line Item Filters

## 🎯 **Filtering Logic**

### **ProductionBOM Header (Main Form)**

- **Service Item** field: Shows only Service and Non-Inventory items
- This is the service you're creating a recipe for

### **BOM Lines (Inline)**

- **Resource** field: Shows all active resources (people, equipment, spaces)
- **Inventory Item** field: Shows only **Inventory** type items (physical products)

---

## 📋 **Item Type Filtering**

| Location             | Field Name     | Shows Item Types           | Purpose                   |
| -------------------- | -------------- | -------------------------- | ------------------------- |
| **Header**           | Service Item   | Service, Non-Inventory     | The service being defined |
| **Line (Resource)**  | Resource       | N/A (Resources, not Items) | People, equipment, spaces |
| **Line (Inventory)** | Inventory Item | **Inventory only**         | Physical products used    |

---

## 🔧 **Implementation**

### **ProductionBOM Header Filter:**

```python
def formfield_for_foreignkey(self, db_field, request, **kwargs):
    if db_field.name == "service_item":
        # Only Service and Non-Inventory items for the BOM
        kwargs["queryset"] = Item.objects.filter(
            blocked=False,
            type__in=["Service", "Non-Inventory"]
        ).order_by("item_name")
```

**Shows:**

- ✅ Service items (e.g., "Men's Haircut", "Spa Treatment")
- ✅ Non-Inventory items (e.g., "Consulting Hour")
- ❌ Inventory items (physical products can't be BOM headers)

---

### **BOM Line Inventory Filter:**

```python
def formfield_for_foreignkey(self, db_field, request, **kwargs):
    if db_field.name == "inventory_item":
        # Only Inventory type items for BOM lines
        kwargs["queryset"] = Item.objects.filter(
            blocked=False,
            type="Inventory"
        ).order_by("item_name")
```

**Shows:**

- ✅ Inventory items only (e.g., "Shampoo", "Towels", "Coffee")
- ❌ Service items (can't use services as ingredients)
- ❌ Non-Inventory items (can't use non-inventory as ingredients)

---

## 🎯 **Example: Haircut Service BOM**

### **Header:**

```
Service Item: "Men's Haircut" (type: Service)
```

### **Lines:**

```
Line 1:
  Line Type: Resource
  Resource: "Senior Stylist" (person)
  Quantity: 0.5 hours

Line 2:
  Line Type: Resource
  Resource: "Styling Chair" (equipment)
  Quantity: 0.5 hours

Line 3:
  Line Type: Inventory
  Inventory Item: "Shampoo" (type: Inventory)
  Quantity: 50 ml

Line 4:
  Line Type: Inventory
  Inventory Item: "Towel" (type: Inventory)
  Quantity: 1 unit
```

---

## ✅ **Why This Logic?**

### **Service Item (Header) - Service or Non-Inventory:**

- These represent **services** that customers purchase
- They don't have physical stock
- They need BOMs to calculate cost

### **Inventory Item (Lines) - Inventory Only:**

- These are **physical products** consumed during service
- They have stock quantities
- They're tracked in inventory

### **Resource (Lines) - Resources Only:**

- These are **people, equipment, or spaces**
- They have hourly/usage rates
- They're not inventory items

---

## 📊 **Item Type Summary**

| Item Type         | Can Be BOM Header? | Can Be BOM Line? | Why?                                     |
| ----------------- | ------------------ | ---------------- | ---------------------------------------- |
| **Service**       | ✅ Yes             | ❌ No            | Services are what we create recipes for  |
| **Non-Inventory** | ✅ Yes             | ❌ No            | Non-inventory services also need recipes |
| **Inventory**     | ❌ No              | ✅ Yes           | Physical products are used in services   |

---

## 🧪 **Testing**

### **Test 1: Create BOM for Service**

1. Go to: http://localhost:8000/admin/production/productionbom/add/
2. **Service Item dropdown**: Should show Service and Non-Inventory items only
3. Add BOM line with type "inventory"
4. **Inventory Item dropdown**: Should show Inventory items only ✅

### **Test 2: Verify Filtering**

```python
# Service Item dropdown shows:
✅ "Men's Haircut" (Service)
✅ "Consulting Hour" (Non-Inventory)
❌ "Shampoo" (Inventory) - Not shown

# Inventory Item dropdown shows:
✅ "Shampoo" (Inventory)
✅ "Towel" (Inventory)
❌ "Men's Haircut" (Service) - Not shown
❌ "Consulting Hour" (Non-Inventory) - Not shown
```

---

## ✅ **System Status**

```
✅ Service Item Filter:     Service + Non-Inventory only
✅ Inventory Item Filter:   Inventory only
✅ Resource Filter:         All non-blocked resources
✅ Linting:                 Passed
✅ Logic:                   Consistent and clear
```

**Server Status:** ✅ Running at http://localhost:8000/  
**Admin Panel:** ✅ http://localhost:8000/admin/production/productionbom/  
**Errors:** ✅ None

---

## 📝 **Summary**

**Change:** Restricted BOM line inventory items to only show Inventory type items.

**Reason:**

- BOM lines represent physical materials consumed during service
- Only Inventory type items have stock tracking
- Service and Non-Inventory items can't be used as ingredients

**Impact:**

- ✅ Clearer dropdown options
- ✅ Prevents incorrect item selection
- ✅ Consistent business logic

**Date:** October 18, 2025  
**Status:** ✅ Complete  
**Version:** Production BOM v1.2


