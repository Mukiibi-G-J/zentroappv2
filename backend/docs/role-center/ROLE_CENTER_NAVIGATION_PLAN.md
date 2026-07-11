# 🧭 Role Center Navigation Integration - Complete Plan

## 🎯 The Challenge

**Current Situation**:
Your navigation uses `authority` (hardcoded strings like "admin", "view_sales") to show/hide menu items.

**Your Goal**:
Use **role center modules** from JWT token to dynamically show/hide entire module sections.

**Example**:

- Cashier → Role Center Modules: `["sales", "customers", "profile"]`
- Navigation should show: Sales section, Customers (within Sales), Profile
- Navigation should hide: Items, Financials, Purchases, Payments, Expenses

---

## 💡 Solution: Module-Based Navigation Filtering

### **Approach**: Map navigation sections to role center modules

**Current Navigation Structure**:

```typescript
// apps.navigation.config.ts
{
  key: "apps.sales",         // Navigation item
  authority: [ADMIN, VIEW_SALES],  // Current (hardcoded)
  // ...
}
```

**New Navigation Structure**:

```typescript
// apps.navigation.config.ts
{
  key: "apps.sales",
  authority: [ADMIN, VIEW_SALES],  // Keep for backward compatibility
  moduleCode: "sales",  // NEW - maps to role center module
  // ...
}
```

---

## 🔧 Implementation Plan

### **Step 1: Add Module Codes to Navigation Config**

**File**: `zentro-frontend/src/configs/navigation.config/apps.navigation.config.ts`

Add `moduleCode` to each navigation section:

```typescript
const appsNavigationConfig: NavigationTree[] = [
  {
    key: "apps",
    title: "APPS",
    type: NAV_ITEM_TYPE_TITLE,
    authority: [],
    subMenu: [
      {
        key: "apps.sales",
        title: "Sales",
        icon: "sales",
        type: NAV_ITEM_TYPE_COLLAPSE,
        authority: [ADMIN, VIEW_SALES],
        moduleCode: "sales",  // NEW - maps to role center
        subMenu: [
          {
            key: "appsSales.dashboard",
            path: `${APP_PREFIX_PATH}/sales/dashboard`,
            title: "Dashboard",
            authority: [ADMIN],
            moduleCode: "sales",  // NEW
            subMenu: [],
          },
          {
            key: "appsSales.customers",
            path: `${APP_PREFIX_PATH}/sales/customers`,
            title: "Customers",
            authority: [ADMIN, VIEW_SALES],
            moduleCode: "customers",  // NEW - can have different module
            subMenu: [],
          },
        ],
      },
      {
        key: "apps.items",
        title: "Items",
        icon: "items",
        type: NAV_ITEM_TYPE_COLLAPSE,
        authority: [ADMIN, VIEW_ITEMS],
        moduleCode: "items",  // NEW
        subMenu: [...],
      },
      {
        key: "apps.financials",
        title: "Financials",
        icon: "financials",
        type: NAV_ITEM_TYPE_COLLAPSE,
        authority: [ADMIN, VIEW_FINANCIALS],
        moduleCode: "financials",  // NEW
        subMenu: [...],
      },
      {
        key: "apps.purchases",
        title: "Purchases",
        icon: "purchases",
        type: NAV_ITEM_TYPE_COLLAPSE,
        authority: [ADMIN, VIEW_PURCHASES],
        moduleCode: "purchases",  // NEW
        subMenu: [...],
      },
      {
        key: "apps.payments",
        title: "Payments",
        icon: "payments",
        type: NAV_ITEM_TYPE_COLLAPSE,
        authority: [ADMIN, VIEW_FINANCIALS],
        moduleCode: "payments",  // NEW
        subMenu: [...],
      },
      {
        key: "apps.expenses",
        title: "Expenses",
        icon: "expenses",
        type: NAV_ITEM_TYPE_COLLAPSE,
        authority: [],
        moduleCode: "expenses",  // NEW
        subMenu: [...],
      },
    ],
  },
];
```

---

### **Step 2: Update NavigationTree Type**

**File**: `zentro-frontend/src/@types/navigation.ts`

```typescript
export interface NavigationTree {
  key: string;
  path: string;
  title: string;
  translateKey: string;
  icon: string;
  type: string;
  authority: string[];
  moduleCode?: string; // NEW - maps to role center module
  subMenu: NavigationTree[];
}
```

---

### **Step 3: Create Module Visibility Hook**

**File**: `zentro-frontend/src/hooks/useModuleVisibility.ts` (NEW)

```typescript
import { useAppSelector } from "@/store";

export const useModuleVisibility = () => {
  const user = useAppSelector((state) => state.auth.user);
  const roleCenterModules = user.role_center_modules || [];

  /**
   * Check if a module should be visible based on role center configuration
   */
  const isModuleVisible = (moduleCode: string): boolean => {
    // Superuser sees everything
    if (user.is_superuser) return true;

    // If user has role center modules, use them (primary)
    if (roleCenterModules.length > 0) {
      return roleCenterModules.includes(moduleCode);
    }

    // Fallback to authority for backward compatibility
    // This handles users who don't have role centers yet
    return user.authority?.includes(moduleCode) || false;
  };

  /**
   * Check if navigation item should be visible
   */
  const isNavItemVisible = (navItem: {
    moduleCode?: string;
    authority?: string[];
  }): boolean => {
    // Superuser sees everything
    if (user.is_superuser) return true;

    // Check module code first (if provided)
    if (navItem.moduleCode) {
      return isModuleVisible(navItem.moduleCode);
    }

    // Fallback to authority check
    if (navItem.authority && navItem.authority.length > 0) {
      return navItem.authority.some((auth) => user.authority?.includes(auth));
    }

    // No restrictions = visible to all
    return true;
  };

  return {
    isModuleVisible,
    isNavItemVisible,
    roleCenterModules,
  };
};
```

---

### **Step 4: Update VerticalMenuContent to Filter by Module**

**File**: `zentro-frontend/src/components/template/VerticalMenuContent/VerticalMenuContent.tsx`

**Current filtering** (line ~50):

```typescript
const filteredNavigationTree = useMemo(
  () =>
    navigationTree.filter((nav) => {
      if (nav.authority.length > 0) {
        return nav.authority.some((auth) => userAuthority?.includes(auth));
      }
      return true;
    }),
  [navigationTree, userAuthority]
);
```

**New filtering** (with role center modules):

```typescript
import { useModuleVisibility } from "@/hooks/useModuleVisibility";

const VerticalMenuContent = (props: VerticalMenuContentProps) => {
  const { isNavItemVisible } = useModuleVisibility();

  // Filter navigation tree by role center modules
  const filteredNavigationTree = useMemo(() => {
    const filterNav = (navItems: NavigationTree[]): NavigationTree[] => {
      return navItems
        .filter((nav) => isNavItemVisible(nav))
        .map((nav) => ({
          ...nav,
          subMenu: nav.subMenu ? filterNav(nav.subMenu) : [],
        }));
    };

    return filterNav(navigationTree);
  }, [navigationTree, isNavItemVisible]);

  // ... rest of component
};
```

---

### **Step 5: Update Frontend Auth Types**

**File**: `zentro-frontend/src/@types/auth.ts`

```typescript
export interface DecodedToken {
  username: string;
  email: string;
  full_name: string;
  // ... existing fields
  role_center_modules?: string[]; // NEW
}

export interface UserState {
  id: number;
  username: string;
  email: string;
  // ... existing fields
  role_center_modules?: string[]; // NEW
}
```

---

### **Step 6: Update Redux Store**

**File**: `zentro-frontend/src/store/slices/auth/userSlice.ts`

```typescript
const initialState: UserState = {
  // ... existing fields
  role_center_modules: [],  // NEW
};

// In setUser reducer
setUser: (state, action: PayloadAction<Partial<UserState>>) => {
  // ... existing assignments
  state.role_center_modules = action.payload.role_center_modules || [];
},
```

---

### **Step 7: Update Auth Hook**

**File**: `zentro-frontend/src/utils/hooks/useAuth.ts`

In the `signIn` function:

```typescript
dispatch(
  setUser({
    // ... existing fields
    role_center_modules: decoded.role_center_modules || [],
  })
);
```

---

## 📊 Navigation Mapping Strategy

### **Map Each Navigation Section to Module Code**:

| Navigation Section | moduleCode     | Default Roles                     |
| ------------------ | -------------- | --------------------------------- |
| Sales              | `"sales"`      | Admin, Manager, Sales, Cashier    |
| Customers          | `"customers"`  | Admin, Manager, Sales, Cashier    |
| Items              | `"items"`      | Admin, Manager, Sales, Inventory  |
| Financials         | `"financials"` | Admin, Manager, Accountant        |
| Purchases          | `"purchases"`  | Admin, Manager, Inventory         |
| Payments           | `"payments"`   | Admin, Manager, Accountant        |
| Expenses           | `"expenses"`   | Admin, Manager, Accountant        |
| Reports            | `"reports"`    | Admin, Manager, Accountant, Sales |
| Settings           | `"settings"`   | Admin                             |
| Company            | `"company"`    | Admin                             |
| Roles              | `"roles"`      | Admin                             |
| Profile            | `"profile"`    | Everyone                          |

---

## 🎨 Visual Example: What Users Will See

### **Cashier User**:

**Role**: Cashier  
**Role Center Modules**: `["sales", "customers", "profile"]`

**Navigation Shows**:

```
APPS
├─ 📊 Sales ✅
│  ├─ New Sale ✅
│  ├─ Sales Invoice ✅
│  ├─ Sales History ✅
│  └─ Customers ✅
└─ 👤 Profile ✅

Hidden: Items ❌, Financials ❌, Purchases ❌, Payments ❌, Expenses ❌
```

---

### **Accountant User**:

**Role**: Accountant  
**Role Center Modules**: `["financials", "reports", "payments", "expenses", "profile"]`

**Navigation Shows**:

```
APPS
├─ 💰 Financials ✅
│  ├─ Chart of Accounts ✅
│  ├─ Financial Reports ✅
│  └─ P&L Statement ✅
├─ 💳 Payments ✅
│  ├─ Payments ✅
│  └─ Payment History ✅
├─ 💵 Expenses ✅
│  ├─ Expenses ✅
│  └─ Expense History ✅
└─ 👤 Profile ✅

Hidden: Sales ❌, Customers ❌, Items ❌, Purchases ❌
```

---

### **Manager User**:

**Role**: Manager  
**Role Center Modules**: `["sales", "customers", "items", "purchases", "financials", "payments", "expenses", "reports", "profile"]`

**Navigation Shows**:

```
APPS
├─ 📊 Sales ✅
├─ 📦 Items ✅
├─ 💰 Financials ✅
├─ 🛒 Purchases ✅
├─ 💳 Payments ✅
├─ 💵 Expenses ✅
└─ 👤 Profile ✅

Hidden: Settings ❌, Company ❌, Roles ❌ (admin only)
```

---

## 🚀 Quick Implementation

### **Option A: Simple Mapping (Recommended)**

Just add `moduleCode` to each section and use the hook:

```typescript
// apps.navigation.config.ts
{
  key: "apps.sales",
  title: "Sales",
  moduleCode: "sales",  // Add this
  authority: [ADMIN, VIEW_SALES],  // Keep for fallback
  subMenu: [...],
}
```

---

### **Option B: Advanced - Group + Module Visibility**

Combine role center modules with user groups for even finer control:

```typescript
const isNavItemVisible = (navItem): boolean => {
  // Check 1: Module code (from role center)
  if (navItem.moduleCode && !isModuleVisible(navItem.moduleCode)) {
    return false;
  }

  // Check 2: User groups (optional, for finer control)
  if (navItem.requiredGroups) {
    const isInGroup = navItem.requiredGroups.some((g) =>
      user.user_groups?.some((ug) => ug.code === g)
    );
    if (!isInGroup) return false;
  }

  // Check 3: Authority (fallback)
  if (navItem.authority?.length > 0) {
    return navItem.authority.some((auth) => user.authority?.includes(auth));
  }

  return true;
};
```

---

## 📋 Step-by-Step Implementation Guide

### **Phase 1: Backend Integration** ✅ (DONE!)

- [x] RoleCenter model created
- [x] JWT token includes `role_center_modules`
- [x] Default role centers created for all tenants
- [x] Admin interface ready

---

### **Phase 2: Frontend Types** (15 minutes)

**File 1**: `src/@types/navigation.ts`

```typescript
export interface NavigationTree {
  // ... existing fields
  moduleCode?: string; // NEW
}
```

**File 2**: `src/@types/auth.ts`

```typescript
export interface DecodedToken {
  // ... existing fields
  role_center_modules?: string[]; // NEW
}

export interface UserState {
  // ... existing fields
  role_center_modules?: string[]; // NEW
}
```

---

### **Phase 3: Redux & Auth** (10 minutes)

**File 1**: `src/store/slices/auth/userSlice.ts`

```typescript
const initialState: UserState = {
  // ... existing
  role_center_modules: [],
};

setUser: (state, action) => {
  // ... existing
  state.role_center_modules = action.payload.role_center_modules || [];
},
```

**File 2**: `src/utils/hooks/useAuth.ts`

```typescript
// In signIn function
dispatch(
  setUser({
    // ... existing
    role_center_modules: decoded.role_center_modules || [],
  })
);
```

---

### **Phase 4: Module Visibility Hook** (20 minutes)

**File**: `src/hooks/useModuleVisibility.ts` (NEW)

```typescript
import { useAppSelector } from "@/store";

export const useModuleVisibility = () => {
  const user = useAppSelector((state) => state.auth.user);
  const roleCenterModules = user.role_center_modules || [];

  const isModuleVisible = (moduleCode: string): boolean => {
    if (user.is_superuser) return true;

    if (roleCenterModules.length > 0) {
      return roleCenterModules.includes(moduleCode);
    }

    return user.authority?.includes(moduleCode) || false;
  };

  const isNavItemVisible = (navItem: any): boolean => {
    if (user.is_superuser) return true;

    if (navItem.moduleCode) {
      return isModuleVisible(navItem.moduleCode);
    }

    if (navItem.authority?.length > 0) {
      return navItem.authority.some((auth) => user.authority?.includes(auth));
    }

    return true;
  };

  return { isModuleVisible, isNavItemVisible, roleCenterModules };
};
```

---

### **Phase 5: Update Navigation Config** (30 minutes)

**File**: `src/configs/navigation.config/apps.navigation.config.ts`

Add `moduleCode` to each section:

```typescript
const appsNavigationConfig: NavigationTree[] = [
  {
    key: "apps",
    subMenu: [
      {
        key: "apps.sales",
        moduleCode: "sales", // ← Add
        // ... rest
      },
      {
        key: "apps.items",
        moduleCode: "items", // ← Add
        // ... rest
      },
      {
        key: "apps.financials",
        moduleCode: "financials", // ← Add
        // ... rest
      },
      {
        key: "apps.purchases",
        moduleCode: "purchases", // ← Add
        // ... rest
      },
      {
        key: "apps.payments",
        moduleCode: "payments", // ← Add
        // ... rest
      },
      {
        key: "apps.expenses",
        moduleCode: "expenses", // ← Add
        // ... rest
      },
    ],
  },
];
```

---

### **Phase 6: Update VerticalMenuContent** (15 minutes)

**File**: `src/components/template/VerticalMenuContent/VerticalMenuContent.tsx`

Replace current filtering with module-based filtering:

```typescript
import { useModuleVisibility } from "@/hooks/useModuleVisibility";

const VerticalMenuContent = (props) => {
  const { isNavItemVisible } = useModuleVisibility();

  // New filtering logic
  const filteredNavigationTree = useMemo(() => {
    const filterNav = (navItems: NavigationTree[]): NavigationTree[] => {
      return navItems
        .filter((nav) => isNavItemVisible(nav))
        .map((nav) => ({
          ...nav,
          subMenu: nav.subMenu ? filterNav(nav.subMenu) : [],
        }))
        .filter((nav) => {
          // Remove parent items if all subitems are filtered out
          if (
            nav.type === NAV_ITEM_TYPE_COLLAPSE ||
            nav.type === NAV_ITEM_TYPE_TITLE
          ) {
            return nav.subMenu.length > 0;
          }
          return true;
        });
    };

    return filterNav(navigationTree);
  }, [navigationTree, isNavItemVisible]);

  // ... rest of component
};
```

---

## 🎯 Alternative: Simpler Approach (Recommended for Quick Win)

### **Option: Use Module Code at Top Level Only**

**Only filter the main module sections**, not every submenu item:

```typescript
// In VerticalMenuContent
const { isModuleVisible } = useModuleVisibility();

const filteredNavigationTree = useMemo(() => {
  return navigationTree
    .map((section) => ({
      ...section,
      subMenu: section.subMenu.filter((module) => {
        // Filter main modules (Sales, Items, Financials, etc.)
        if (module.moduleCode) {
          return isModuleVisible(module.moduleCode);
        }
        // Keep items without moduleCode (backward compatibility)
        return (
          module.authority?.length === 0 ||
          module.authority?.some((auth) => userAuthority?.includes(auth))
        );
      }),
    }))
    .filter((section) => section.subMenu.length > 0);
}, [navigationTree, userAuthority, isModuleVisible]);
```

This way:

- ✅ Main modules filtered by role center
- ✅ Subitems still use authority (finer control)
- ✅ Backward compatible
- ✅ Simpler to implement

---

## 📊 Module Mapping Reference

### **Your Current Navigation → Module Codes**:

```typescript
"apps.sales"      → moduleCode: "sales"
"apps.items"      → moduleCode: "items"
"apps.financials" → moduleCode: "financials"
"apps.purchases"  → moduleCode: "purchases"
"apps.payments"   → moduleCode: "payments"
"apps.expenses"   → moduleCode: "expenses"

// Sub-items can have different modules
"appsSales.customers" → moduleCode: "customers"  // Different!
"appsItems.item"      → moduleCode: "items"
```

---

## 🧪 Testing After Implementation

### **Test 1: Cashier User**

1. Assign "Cashier" role to test user
2. Login
3. Expected navigation:
   - ✅ Sales section visible
   - ✅ Customers visible (within Sales)
   - ✅ Profile visible
   - ❌ Items hidden
   - ❌ Financials hidden
   - ❌ All other modules hidden

---

### **Test 2: Accountant User**

1. Assign "Accountant" role
2. Login
3. Expected navigation:
   - ✅ Financials section visible
   - ✅ Payments visible
   - ✅ Expenses visible
   - ✅ Profile visible
   - ❌ Sales hidden
   - ❌ Items hidden
   - ❌ Purchases hidden

---

### **Test 3: Custom Dispenser**

1. Create "Dispenser" role center with modules: `["sales", "customers", "items"]`
2. Assign to user
3. Login
4. Expected navigation:
   - ✅ Sales visible
   - ✅ Items visible
   - ✅ Profile visible
   - ❌ Financials hidden
   - ❌ Everything else hidden

---

## 🎯 Recommended Implementation Order

### **Day 1: Backend Ready** ✅ (DONE!)

- [x] RoleCenter model
- [x] JWT integration
- [x] Default role centers
- [x] All tenants updated

### **Day 2: Frontend Prep** (1 hour)

1. Update types (navigation.ts, auth.ts)
2. Update Redux store
3. Update auth hook
4. Test JWT token includes modules

### **Day 3: Navigation Integration** (2 hours)

1. Create useModuleVisibility hook
2. Add moduleCode to navigation config
3. Update VerticalMenuContent filtering
4. Test with different roles

### **Day 4: Polish & Test** (1 hour)

1. Test all roles
2. Test multi-role users
3. Test custom role centers
4. Fix any edge cases

---

## 💡 Key Insights

### **Priority Logic**:

```
1. Superuser → See everything (bypass all checks)
2. Role Center Modules → Primary filter (if exists)
3. Authority → Fallback (for users without role centers)
4. Empty authority → Show to everyone
```

### **Backward Compatibility**:

```typescript
// Users WITHOUT role centers still work
if (roleCenterModules.length === 0) {
  // Fall back to authority check
  return authority.some((auth) => user.authority.includes(auth));
}
```

### **Multi-Role Users**:

```typescript
// User with Cashier + Sales roles
role_center_modules: [
  "sales",
  "customers",
  "profile", // From Cashier Center
  "items",
  "reports", // From Sales Center
];
// All unique modules combined ✅
```

---

## 🎉 Final Result

**Before**:

```typescript
// Hardcoded authority checks everywhere
authority: [ADMIN, VIEW_SALES, VIEW_FINANCIALS];
```

**After**:

```typescript
// Dynamic module-based visibility
moduleCode: "sales"; // Checked against role_center_modules from JWT
```

**Benefits**:

- ✅ Change modules in admin panel → Navigation updates automatically
- ✅ No frontend code changes for new roles
- ✅ Single source of truth (database)
- ✅ Non-developers can configure

---

## 📞 Summary

### **What to Update**:

1. **Types** (2 files):

   - `navigation.ts` - Add `moduleCode?: string`
   - `auth.ts` - Add `role_center_modules?: string[]`

2. **Redux & Auth** (2 files):

   - `userSlice.ts` - Store role_center_modules
   - `useAuth.ts` - Populate from JWT

3. **Hook** (1 new file):

   - `useModuleVisibility.ts` - Module visibility logic

4. **Navigation** (2 files):
   - `apps.navigation.config.ts` - Add moduleCode to sections
   - `VerticalMenuContent.tsx` - Use module-based filtering

**Total**: 7 files, ~2 hours work, **HUGE IMPACT!** 🚀

---

**Would you like me to implement this now?** 🎯
