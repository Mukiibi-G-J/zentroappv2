# 🏠 Role Center Design - Module Visibility

## 🎯 The Problem

**Current Situation**:
You have a Role Center (dashboard/home page) that should show different modules based on user role/permissions.

**Example**:

- **Sales Role Center** → Should show: Sales, Customers, Items
- **Accountant Role Center** → Should show: Financials, Reports, Payments
- **Manager Role Center** → Should show: Everything

**Question**: How do we determine which modules to show?

---

## 💡 Solution: Module Access via User Groups + Roles

### **Approach 1: Use Existing Authority (Simple)**

**How it works**:

```typescript
// Frontend
const user = useAppSelector((state) => state.auth.user);
const authority = user.authority; // ["sales", "customers", "items"]

// Show modules based on authority
if (authority.includes("sales")) {
  showSalesModule(); // ✅
}

if (authority.includes("financials")) {
  showFinancialsModule(); // ❌ (not in authority)
}
```

**Pros**:

- ✅ Already implemented
- ✅ Works right now
- ✅ Simple to use

**Cons**:

- ❌ Not granular enough
- ❌ Can't say "show module but hide certain features"

---

### **Approach 2: Role Center Configuration (Recommended)**

**How it works**:
Create a Role Center model that defines which modules appear for which role.

#### **Backend Model**:

```python
# authentication/models.py or new role_center/models.py

class RoleCenter(BaseModel):
    """
    Role Center - Defines which modules and features are visible for a role
    """

    code = models.CharField(
        max_length=50,
        unique=True,
        help_text="Unique code (e.g., SALES_CENTER, ACCOUNTING_CENTER)"
    )

    name = models.CharField(
        max_length=100,
        help_text="Display name (e.g., 'Sales Role Center')"
    )

    description = models.TextField(blank=True)

    linked_role = models.ForeignKey(
        'Role',
        on_delete=models.CASCADE,
        related_name='role_centers',
        help_text="Role that uses this role center"
    )

    # Modules to show
    modules = models.JSONField(
        default=list,
        help_text="List of module codes to show, e.g., ['sales', 'customers', 'items']"
    )

    # Pages/features to show within modules
    features = models.JSONField(
        default=dict,
        help_text="""
        Features per module, e.g.:
        {
          "sales": ["dashboard", "invoices", "history"],
          "customers": ["list", "create", "reports"]
        }
        """
    )

    # Dashboard widgets
    dashboard_widgets = models.JSONField(
        default=list,
        help_text="Widget IDs to show on dashboard, e.g., ['sales_chart', 'top_customers']"
    )

    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'authentication_rolecenter'
        verbose_name = 'Role Center'
        verbose_name_plural = 'Role Centers'
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.code})"
```

#### **Example Configuration**:

```python
# Sales Role Center
RoleCenter.objects.create(
    code='SALES_CENTER',
    name='Sales Role Center',
    linked_role=Role.objects.get(name='Cashier'),
    modules=['sales', 'customers', 'items'],
    features={
        'sales': ['dashboard', 'invoices', 'create_invoice', 'sales_history'],
        'customers': ['list', 'create', 'edit'],
        'items': ['list', 'view_only']  # Can see items but not manage
    },
    dashboard_widgets=['sales_today', 'top_customers', 'recent_invoices']
)

# Accountant Role Center
RoleCenter.objects.create(
    code='ACCOUNTING_CENTER',
    name='Accountant Role Center',
    linked_role=Role.objects.get(name='Accountant'),
    modules=['financials', 'reports', 'payments', 'expenses'],
    features={
        'financials': ['chart_of_accounts', 'gl_entries', 'reports'],
        'reports': ['profit_loss', 'balance_sheet', 'trial_balance'],
        'payments': ['list', 'view_only'],
        'expenses': ['list', 'view_only']
    },
    dashboard_widgets=['financial_summary', 'account_balances', 'monthly_pl']
)
```

---

### **Approach 3: Combined - Authority + Permissions (Best)**

**Use both systems together**:

```python
# User gets modules from:
# 1. Role → Authority (existing) → Modules shown
# 2. User Groups → Permission Sets → Features shown within modules

Example:
User: Sarah (Cashier)
├─ Role: Cashier
│  └─ Authority: ['sales', 'customers', 'items']
│     → Shows: Sales, Customers, Items modules ✅
│
└─ User Group: SALES_CASHIERS
   └─ Permission Set: SALES_CASHIER
      ├─ Customer: Read, Insert, Modify (no Delete)
      │  → Shows: Create button ✅, Edit button ✅
      │  → Hides: Delete button ❌
      │
      └─ Invoice: Read, Insert (no Modify/Delete)
         → Shows: Create button ✅
         → Hides: Edit button ❌, Delete button ❌
```

---

## 🎨 Implementation: Module Visibility

### **Option A: Simple Authority Check (Use Now)**

**Frontend - appsRoute.ts**:

```typescript
// Already working!
const appsRoute: Routes = [
  {
    key: "appsSales.customers",
    path: `${APP_PREFIX_PATH}/sales/customers`,
    component: lazy(() => import("@/views/customers/Customers")),
    authority: [], // Empty = show to everyone with module access
    // OR
    authority: ["sales", "customers"], // Only show to users with these in authority
  },
];
```

**Current Behavior**:

```typescript
// In ProtectedRoute or similar
if (route.authority.length > 0) {
  // Check if user has ANY of the required authorities
  const hasAccess = route.authority.some((auth) =>
    user.authority.includes(auth)
  );

  if (!hasAccess) {
    return <AccessDenied />; // Don't show route
  }
}
```

---

### **Option B: Enhanced with User Groups (Recommended)**

**Add group-based module visibility**:

```typescript
// types/routes.ts
export interface RouteConfig {
  key: string;
  path: string;
  component: React.LazyExoticComponent<any>;
  authority: string[]; // Existing - module level
  requiredGroups?: string[]; // NEW - group level
  requiredPermissionSets?: string[]; // NEW - permission set level
  meta?: {
    header?: string;
    layout?: string;
  };
}
```

**Example Routes**:

```typescript
// appsRoute.ts
const appsRoute: Routes = [
  // Sales Dashboard - Only for Sales Team or Managers
  {
    key: "appsSales.dashboard",
    path: `${APP_PREFIX_PATH}/sales/dashboard`,
    component: lazy(() => import("@/views/sales/SalesDashboard")),
    authority: ["sales"], // Module access
    requiredGroups: ["SALES_TEAM", "SALES_CASHIERS", "MANAGER_GROUP"], // NEW
  },

  // Customers - Available to all sales roles
  {
    key: "appsSales.customers",
    path: `${APP_PREFIX_PATH}/sales/customers`,
    component: lazy(() => import("@/views/customers/Customers")),
    authority: ["sales", "customers"],
    requiredGroups: ["SALES_CASHIERS", "SALES_TEAM", "SALES_VIEWERS"], // NEW
  },

  // Advanced Sales Reports - Only for Sales Team
  {
    key: "appsSales.advancedReports",
    path: `${APP_PREFIX_PATH}/sales/advanced-reports`,
    component: lazy(() => import("@/views/sales/AdvancedReports")),
    authority: ["sales"],
    requiredGroups: ["SALES_TEAM"], // Only sales team, not cashiers
  },
];
```

**Updated Route Protection**:

```typescript
// components/route/ProtectedRoute.tsx or similar

const hasRouteAccess = (route: RouteConfig, user: UserState): boolean => {
  // Check 1: Module authority (existing)
  if (route.authority.length > 0) {
    const hasModuleAccess = route.authority.some((auth) =>
      user.authority?.includes(auth)
    );
    if (!hasModuleAccess) return false;
  }

  // Check 2: User groups (NEW)
  if (route.requiredGroups && route.requiredGroups.length > 0) {
    const isInRequiredGroup = route.requiredGroups.some((groupCode) =>
      user.user_groups?.some((group) => group.code === groupCode)
    );
    if (!isInRequiredGroup) return false;
  }

  // Check 3: Permission sets (NEW)
  if (route.requiredPermissionSets && route.requiredPermissionSets.length > 0) {
    const hasRequiredPermissionSet = route.requiredPermissionSets.some(
      (setCode) => user.permission_sets?.includes(setCode)
    );
    if (!hasRequiredPermissionSet) return false;
  }

  return true; // All checks passed
};
```

---

## 🏠 Role Center Dashboard Design

### **Dynamic Module Grid**:

```typescript
// views/home/RoleCenterDashboard.tsx

const RoleCenterDashboard = () => {
  const user = useAppSelector((state) => state.auth.user);
  const { isInGroup, hasPermissionSet } = usePermissions();

  // Define all possible modules
  const allModules = [
    {
      id: "sales",
      name: "Sales",
      icon: "ShoppingCart",
      path: "/app/sales",
      showIf: () => user.authority?.includes("sales"),
    },
    {
      id: "customers",
      name: "Customers",
      icon: "Users",
      path: "/app/sales/customers",
      showIf: () =>
        user.authority?.includes("customers") ||
        isInGroup("SALES_CASHIERS") ||
        isInGroup("SALES_TEAM"),
    },
    {
      id: "items",
      name: "Items",
      icon: "Package",
      path: "/app/items",
      showIf: () => user.authority?.includes("items"),
    },
    {
      id: "financials",
      name: "Financials",
      icon: "DollarSign",
      path: "/app/financials",
      showIf: () => user.authority?.includes("financials"),
    },
    {
      id: "reports",
      name: "Reports",
      icon: "BarChart",
      path: "/app/reports",
      showIf: () =>
        hasPermissionSet("SALES_FULL") ||
        hasPermissionSet("MANAGER") ||
        user.is_superuser,
    },
  ];

  // Filter modules based on user permissions
  const visibleModules = allModules.filter((module) => module.showIf());

  return (
    <div className="role-center">
      <h1>Welcome, {user.fullName}!</h1>
      <p>Role: {user.roles?.join(", ") || "User"}</p>

      <div className="module-grid">
        {visibleModules.map((module) => (
          <ModuleCard key={module.id} {...module} />
        ))}
      </div>
    </div>
  );
};
```

---

## 🎯 Recommended Approach for ZentroApp

### **Phase 1: Use Existing Authority (Now)**

```typescript
// Simple and already working
const showSalesModule = user.authority.includes("sales");
const showFinancialsModule = user.authority.includes("financials");

// Render modules based on authority
{
  showSalesModule && <SalesModule />;
}
{
  showFinancialsModule && <FinancialsModule />;
}
```

**This gives you**:

- ✅ Module-level visibility (Sales, Items, etc.)
- ✅ Already implemented
- ✅ Works with existing roles

---

### **Phase 2: Add User Group Checks (Granular)**

```typescript
// Add user group checks for finer control
const { isInGroup, isInAnyGroup } = usePermissions();

// Show different content based on groups
const showSalesModule =
  user.authority.includes("sales") ||
  isInAnyGroup(["SALES_CASHIERS", "SALES_TEAM", "SALES_VIEWERS"]);

const showAdvancedFeatures =
  isInGroup("SALES_TEAM") || isInGroup("MANAGER_GROUP");

// Render
{
  showSalesModule && <SalesModule showAdvanced={showAdvancedFeatures} />;
}
```

---

## 🎨 Practical Example: Sales Role Center

### **What Cashier Sees**:

```
┌─────────────────────────────────────┐
│   SALES ROLE CENTER                 │
│                                     │
│   Welcome, Sarah! (Cashier)         │
│                                     │
│   📊 Quick Actions:                 │
│   ┌──────────┐ ┌──────────┐       │
│   │  Create  │ │  View    │       │
│   │ Invoice  │ │Customers │       │
│   └──────────┘ └──────────┘       │
│                                     │
│   📋 Available Modules:             │
│   • Sales              ✅           │
│   • Customers          ✅           │
│   • Items (view only)  ✅           │
│   • Reports            ❌ (hidden)  │
│   • Settings           ❌ (hidden)  │
│                                     │
│   📈 Today's Summary:               │
│   • Sales: 10 invoices              │
│   • Customers served: 15            │
└─────────────────────────────────────┘
```

### **What Sales Manager Sees**:

```
┌─────────────────────────────────────┐
│   SALES ROLE CENTER                 │
│                                     │
│   Welcome, John! (Sales Manager)    │
│                                     │
│   📊 Quick Actions:                 │
│   ┌──────────┐ ┌──────────┐ ┌────┐│
│   │  Create  │ │ Advanced │ │Edit││
│   │ Invoice  │ │ Reports  │ │Setup││
│   └──────────┘ └──────────┘ └────┘│
│                                     │
│   📋 Available Modules:             │
│   • Sales              ✅           │
│   • Customers          ✅           │
│   • Items              ✅           │
│   • Reports            ✅ (visible!)│
│   • Settings           ✅ (visible!)│
│   • Analytics          ✅           │
│                                     │
│   📈 Team Performance:              │
│   • Total Sales: $50,000            │
│   • Team Members: 5                 │
│   • Top Performer: Sarah            │
└─────────────────────────────────────┘
```

---

## 🔧 Implementation

### **Step 1: Create Module Config**

```typescript
// configs/moduleConfig.ts

export interface ModuleConfig {
  id: string;
  name: string;
  icon: string;
  path: string;
  visibleForAuthority?: string[]; // Module authority
  visibleForGroups?: string[]; // User groups
  visibleForRoles?: string[]; // Role names
  requiredPermissions?: {
    objectId: number;
    action: string;
  }[];
}

export const MODULE_CONFIGS: ModuleConfig[] = [
  {
    id: "sales",
    name: "Sales",
    icon: "ShoppingCart",
    path: "/app/sales",
    visibleForAuthority: ["sales"],
    visibleForGroups: ["SALES_CASHIERS", "SALES_TEAM", "SALES_VIEWERS"],
  },
  {
    id: "customers",
    name: "Customers",
    icon: "Users",
    path: "/app/sales/customers",
    visibleForAuthority: ["customers", "sales"],
    visibleForGroups: ["SALES_CASHIERS", "SALES_TEAM", "SALES_VIEWERS"],
  },
  {
    id: "items",
    name: "Items",
    icon: "Package",
    path: "/app/items",
    visibleForAuthority: ["items", "inventory"],
  },
  {
    id: "sales_reports",
    name: "Sales Reports",
    icon: "BarChart",
    path: "/app/sales/reports",
    visibleForAuthority: ["sales"],
    visibleForGroups: ["SALES_TEAM"], // Only sales team, NOT cashiers
    requiredPermissions: [
      { objectId: 5001, action: "execute" }, // Sales Report object
    ],
  },
  {
    id: "financials",
    name: "Financials",
    icon: "DollarSign",
    path: "/app/financials",
    visibleForAuthority: ["financials"],
    visibleForRoles: ["Accountant", "Manager"],
  },
];
```

---

### **Step 2: Create Module Visibility Hook**

```typescript
// hooks/useModuleVisibility.ts

import { useAppSelector } from "@/store";
import { usePermissions } from "@/hooks/usePermissions";
import { ModuleConfig, MODULE_CONFIGS } from "@/configs/moduleConfig";

export const useModuleVisibility = () => {
  const user = useAppSelector((state) => state.auth.user);
  const { isInGroup, hasRole, canView } = usePermissions();

  const isModuleVisible = (module: ModuleConfig): boolean => {
    // Superuser sees everything
    if (user.is_superuser) return true;

    // Check authority (module access)
    if (module.visibleForAuthority && module.visibleForAuthority.length > 0) {
      const hasAuthority = module.visibleForAuthority.some((auth) =>
        user.authority?.includes(auth)
      );
      if (!hasAuthority) return false;
    }

    // Check user groups
    if (module.visibleForGroups && module.visibleForGroups.length > 0) {
      const isInRequiredGroup = module.visibleForGroups.some((groupCode) =>
        isInGroup(groupCode)
      );
      if (!isInRequiredGroup) return false;
    }

    // Check roles
    if (module.visibleForRoles && module.visibleForRoles.length > 0) {
      const hasRequiredRole = module.visibleForRoles.some((roleName) =>
        hasRole(roleName)
      );
      if (!hasRequiredRole) return false;
    }

    // Check permissions
    if (module.requiredPermissions && module.requiredPermissions.length > 0) {
      const hasAllPermissions = module.requiredPermissions.every((perm) =>
        canView(perm.objectId)
      );
      if (!hasAllPermissions) return false;
    }

    return true; // All checks passed
  };

  const getVisibleModules = (): ModuleConfig[] => {
    return MODULE_CONFIGS.filter(isModuleVisible);
  };

  return {
    isModuleVisible,
    getVisibleModules,
  };
};
```

---

### **Step 3: Use in Navigation/Role Center**

```typescript
// views/RoleCenterDashboard.tsx

import { useModuleVisibility } from "@/hooks/useModuleVisibility";

const RoleCenterDashboard = () => {
  const user = useAppSelector((state) => state.auth.user);
  const { getVisibleModules } = useModuleVisibility();

  const visibleModules = getVisibleModules();

  return (
    <div className="role-center">
      <h1>Welcome, {user.fullName}!</h1>
      <p>Role: {user.roles?.join(", ") || "User"}</p>

      <div className="modules-grid">
        {visibleModules.map((module) => (
          <ModuleCard
            key={module.id}
            name={module.name}
            icon={module.icon}
            onClick={() => navigate(module.path)}
          />
        ))}
      </div>

      {visibleModules.length === 0 && (
        <EmptyState message="No modules available for your role" />
      )}
    </div>
  );
};
```

---

## 📊 Module Visibility Matrix

### **What Each User Sees**:

| Module          | Cashier   | Sales Team | Viewer    | Accountant | Manager |
| --------------- | --------- | ---------- | --------- | ---------- | ------- |
| Sales Dashboard | ✅        | ✅         | ✅        | ❌         | ✅      |
| Customers       | ✅        | ✅         | ✅        | ❌         | ✅      |
| Create Invoice  | ✅        | ✅         | ❌        | ❌         | ✅      |
| Edit Invoice    | ❌        | ✅         | ❌        | ❌         | ✅      |
| Delete Customer | ❌        | ✅         | ❌        | ❌         | ✅      |
| Sales Reports   | ❌        | ✅         | ✅        | ❌         | ✅      |
| Items           | ✅ (view) | ✅         | ✅ (view) | ❌         | ✅      |
| Financials      | ❌        | ❌         | ❌        | ✅         | ✅      |
| Settings        | ❌        | ❌         | ❌        | ❌         | ✅      |

---

## 🎯 Simple Solution for Now

### **Use Authority + User Groups**:

```typescript
// In your navigation/sidebar component

import { usePermissions } from "@/hooks/usePermissions";

const Sidebar = () => {
  const user = useAppSelector((state) => state.auth.user);
  const { isInAnyGroup } = usePermissions();

  // Module visibility logic
  const showSalesModule =
    user.authority?.includes("sales") ||
    isInAnyGroup(["SALES_CASHIERS", "SALES_TEAM", "SALES_VIEWERS"]);

  const showCustomersModule =
    user.authority?.includes("customers") ||
    isInAnyGroup(["SALES_CASHIERS", "SALES_TEAM", "SALES_VIEWERS"]);

  const showItemsModule =
    user.authority?.includes("items") || user.authority?.includes("inventory");

  const showFinancialsModule =
    user.authority?.includes("financials") || hasRole("Accountant");

  return (
    <nav>
      {showSalesModule && <NavItem label="Sales" path="/app/sales" />}
      {showCustomersModule && (
        <NavItem label="Customers" path="/app/sales/customers" />
      )}
      {showItemsModule && <NavItem label="Items" path="/app/items" />}
      {showFinancialsModule && (
        <NavItem label="Financials" path="/app/financials" />
      )}
    </nav>
  );
};
```

---

## 🚀 Quick Implementation for Your Current System

### **Step 1: Use What You Have (Authority)**

Your Role model already has a `permissions` field (JSON array):

```python
# authentication/models.py
class Role(BaseModel):
    name = models.CharField(max_length=100, unique=True)
    permissions = models.JSONField(default=list, blank=True)  # ← This!
```

**Example Role Configuration**:

```python
# Cashier role
Role.objects.create(
    name='Cashier',
    permissions=['sales', 'customers', 'items']  # These become authority
)

# Sales role
Role.objects.create(
    name='Sales',
    permissions=['sales', 'customers', 'items', 'reports']
)

# Accountant role
Role.objects.create(
    name='Accountant',
    permissions=['financials', 'reports', 'payments', 'expenses']
)
```

**This already populates `authority` in your JWT token!**

---

### **Step 2: Add Group-Based Visibility (Optional)**

If you need finer control:

```typescript
// Show module to specific groups regardless of authority
const showAdvancedReports =
  user.authority.includes("reports") ||
  isInGroup("SALES_TEAM") || // Sales team gets reports
  hasRole("Manager"); // Managers get reports
```

---

## 📝 Summary

### **For Module Visibility (Role Center)**:

**Simple (Use Now)**:

```typescript
// Check authority (existing)
const showModule = user.authority.includes("sales");
```

**Medium (Add Soon)**:

```typescript
// Check authority + groups
const showModule =
  user.authority.includes("sales") ||
  isInAnyGroup(["SALES_CASHIERS", "SALES_TEAM"]);
```

**Advanced (Later)**:

```typescript
// Create RoleCenter model with full configuration
const roleCenter = RoleCenter.objects.get((linked_role = user.roles.first()));
const visibleModules = roleCenter.modules; // ["sales", "customers", "items"]
```

---

## 🎯 Recommendation

### **For Your Sales Pilot**:

**Use this simple approach**:

```typescript
// In your sidebar/navigation
const { isInAnyGroup, hasRole } = usePermissions();

// Sales module - visible to sales groups
const showSales =
  user.authority.includes("sales") ||
  isInAnyGroup(["SALES_CASHIERS", "SALES_TEAM", "SALES_VIEWERS"]);

// Sales reports - only for sales team and managers
const showSalesReports =
  isInAnyGroup(["SALES_TEAM"]) || hasRole("Manager") || user.is_superuser;
```

**This gives you**:

- ✅ Module visibility based on authority
- ✅ Feature visibility based on groups
- ✅ Simple to implement
- ✅ Works with existing code

---

**Would you like me to implement the module visibility hook and update your navigation/sidebar?** 🚀
