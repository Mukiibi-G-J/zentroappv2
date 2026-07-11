# 🔧 Production BOM Admin - Field Name Fix

## ✅ **Issue Fixed**

**Error:**

```
FieldError: Cannot resolve keyword 'is_active' into field.
```

**Cause:** The `Item` model uses `blocked` field, not `is_active` field.

---

## 🔧 **Solution**

Changed all references from `is_active=True` to `blocked=False` in the Production BOM admin filters.

---

## 📋 **Changes Made**

### **File:** `production/admin.py`

#### **1. BOMLineInline - Fixed inventory_item filter**

**Before:** ❌

```python
kwargs["queryset"] = Item.objects.filter(is_active=True).order_by("item_name")
```

**After:** ✅

```python
kwargs["queryset"] = Item.objects.filter(blocked=False).order_by("item_name")
```

---

#### **2. ProductionBOMAdmin - Fixed service_item filter**

**Before:** ❌

```python
kwargs["queryset"] = Item.objects.filter(
    is_active=True, type__in=["Service", "Non-Inventory"]
).order_by("item_name")
```

**After:** ✅

```python
kwargs["queryset"] = Item.objects.filter(
    blocked=False, type__in=["Service", "Non-Inventory"]
).order_by("item_name")
```

---

## 📊 **Item Model Fields**

The `Item` model uses:

- ✅ `blocked` (BooleanField) - Whether item is blocked from use
- ❌ `is_active` - This field does NOT exist on Item model

**Logic:**

- `blocked=False` → Item is available for use ✅
- `blocked=True` → Item is blocked from use ❌

---

## ✅ **System Status**

```
✅ Admin Dropdowns:  Fixed (now filter by blocked=False)
✅ Service Items:    Show only non-blocked Service/Non-Inventory
✅ BOM Line Items:   Show only non-blocked items
✅ Linting:          Passed (no errors)
```

**Server Status:** ✅ Running at http://localhost:8000/  
**Admin Panel:** ✅ http://localhost:8000/admin/production/productionbom/add/  
**Errors:** ✅ None

---

## 📝 **Summary**

**Issue:** Used non-existent `is_active` field on Item model  
**Fix:** Changed to use `blocked` field (which exists)  
**Impact:** Admin forms now load correctly with proper item filtering

**Date:** October 18, 2025  
**Status:** ✅ Fixed


