# ZentroApp Module System Guide

## Overview

ZentroApp uses a **3-layer access control architecture**. Each layer operates independently, and **all layers must pass** for a user to access a feature.

| Layer | Scope | Controls | Source |
|---|---|---|---|
| **1. Modules** | Company-level | What features the company has paid for | Subscription plan + admin overrides |
| **2. Role Center** | User-level | Which sidebar sections a user sees | Role Center `modules` array |
| **3. Permission Sets** | User-level | Which pages and CRUD actions a user has | Permission Sets via User Groups |

### How Layers Interact

```
Can user X access "Item Tracking"?

Layer 1: Does the COMPANY have "item_tracking" in enabled_modules?
  YES -> continue
  NO  -> BLOCKED (feature not available for this company)

Layer 2: Does the USER's role center include the "items" moduleCode?
  YES -> continue
  NO  -> HIDDEN from sidebar (but company has the feature)

Layer 3: Does the USER have page permission for "Item Tracking"?
  YES -> ACCESS GRANTED with specific CRUD permissions
  NO  -> HIDDEN from navigation (but company and role allow it)
```

**Key distinction:**
- **Modules** = Company license. "Does this company pay for this feature?" Same for all users in the company.
- **Permissions** = Employee access. "Does this specific user's job role allow them to use this feature?" Different per user.

---

## Module Registry

All modules are defined in `zentro-backend/utils/modules.py` in the `MODULE_REGISTRY` dictionary.

### Core Modules (Starter plan and above)

| # | Identifier | Display Name | App | URL Prefix | Dependencies |
|---|---|---|---|---|---|
| 1 | `sales` | Sales & POS | sales | /api/sales/ | -- |
| 2 | `inventory` | Inventory Management | items | /api/items/ | -- |
| 3 | `purchases` | Purchases & Suppliers | purchases | /api/purchases/ | -- |
| 4 | `customers` | Customer Management | customers | /api/customers/ | -- |
| 5 | `expenses` | Expense Tracking | expenses | /api/expenses/ | -- |
| 6 | `reports` | Reports & Analytics | reports | /api/reports/ | -- |
| 7 | `financials` | Financial Statements | accounting | /api/accounting/ | -- |
| 8 | `payments` | Payments & Settlements | payments | /api/payments/ | -- |
| 9 | `prepayments` | Prepayments & Deposits | prepayment | /api/prepayments/ | -- |
| 10 | `bank_accounts` | Bank Account Management | bank_account | /api/bank-accounts/ | -- |
| 11 | `user_management` | User Roles & Permissions | authentication | /api/auth/ | -- |

### Business+ Modules (Business plan and above)

| # | Identifier | Display Name | App | URL Prefix | Dependencies |
|---|---|---|---|---|---|
| 12 | `item_tracking` | Item Tracking | items | /api/items/tracking/ | `inventory` |
| 13 | `stock_taking` | Stock Taking | items | /api/items/stock-taking/ | `inventory` |
| 14 | `manufacturing` | Manufacturing & Production | production | /api/production/ | `inventory` |
| 15 | `loans` | Loan Management | loans | /api/loans/ | -- |
| 16 | `resources` | Resources | resources | /api/resources/ | -- |

### Pro Modules (Pro plan only)

| # | Identifier | Display Name | App | URL Prefix | Dependencies |
|---|---|---|---|---|---|
| 17 | `efris` | EFRIS Integration | efris | /api/efris/ | `sales` |

### Add-on Modules (purchased separately)

| # | Identifier | Display Name | App | URL Prefix | Dependencies |
|---|---|---|---|---|---|
| 18 | `hotel` | Hotel Management | hotel_management | /api/hotel/ | `sales` |
| 19 | `restaurant` | Restaurant Management | restaurant_management | /api/restaurant/ | `sales` |

### Legacy

| Identifier | Notes |
|---|---|
| `pos` | Legacy alias for `sales`. Default module for backwards compatibility. |

---

## Subscription Plans and Module Mapping

### Plans (from `data/pricing_plans.json`)

| Plan | Monthly Price (UGX) | Modules |
|---|---|---|
| **Starter** | 50,000 | 11 core modules |
| **Business** | 100,000 | Core + item_tracking, stock_taking, manufacturing, loans, resources |
| **Pro** | 150,000 | Business + efris |

### Plan Name Mapping

Historical subscription plan names are mapped to pricing plan names via `Company.PLAN_NAME_TO_PRICING`:

| Subscription Plan Name | Maps To |
|---|---|
| `"Free Trial"` | Starter |
| `"Starter Pack"` | Starter |
| `"Standard Plan"` | Starter |
| `""` (empty) | Starter |
| `"Starter"` | Starter |
| `"Multi-Branch Plan"` | Business |
| `"Business"` | Business |
| `"Premium Plan with EFRIS"` | Pro |
| `"Pro"` | Pro |

---

## How Modules Are Computed

### Data Flow

```
Pricing.included_modules  ─────┐
(from subscription plan)       │
                               ├──> Company.compute_enabled_modules()
Company.module_overrides  ─────┘         │
(admin waivers/deals)                    │
                                         v
                              Company.enabled_modules = union(plan_modules, overrides)
                                         │
                    ┌────────────────────┼────────────────────┐
                    v                    v                    v
              JWT Token            Middleware            Backend Views
           (at login time)    ModulePermission       request.has_module()
                 │            ModuleContext
                 v
           Frontend Redux
           (userSlice.enabledModules)
                 │
                 v
           useModuleEnabled hook ──> nav.module check (subscription tier)
           usePermissions hook ────> nav.moduleCode check (role center)
                                   > nav.pageName check (page permissions)
```

### Key Models

**`Company`** (`company/models.py`):
- `enabled_modules` (JSONField): Computed list. The authoritative source of what modules the company can access.
- `module_overrides` (JSONField): Manually-granted modules beyond the subscription plan (waivers/deals).
- `compute_enabled_modules()`: Method that recomputes `enabled_modules` from the subscription plan + overrides.

**`Subscription`** (`company/models.py`):
- `plan` (CharField): The subscription plan name (e.g., "Free Trial", "Starter Pack").
- `status` (CharField): Current status ("trial", "active", "pending").
- A `post_save` signal on `Subscription` automatically calls `company.compute_enabled_modules()` when saved.

**`Pricing`** (`company/models.py`, shared/public schema):
- `name` (CharField): The canonical plan name ("Starter", "Business", "Pro").
- `included_modules` (JSONField): List of module identifiers included in this plan.
- Seeded from `data/pricing_plans.json`.

### Auto-Recompute Triggers

1. **Subscription saved**: `post_save` signal on `Subscription` calls `company.compute_enabled_modules()`.
2. **Login**: JWT serializer auto-heals if `enabled_modules` is empty.
3. **Company Settings API**: `/api/company/modules/` endpoint auto-heals if `enabled_modules` is empty.

---

## Module Overrides (Waivers / Deals)

The super admin can grant modules beyond a company's subscription plan via the Django Admin:

1. Navigate to **Django Admin > Company > Companies > [Company Name]**
2. Find the `module_overrides` field
3. Add module identifiers as a JSON array, e.g., `["item_tracking", "manufacturing"]`
4. Save. The `post_save` signal on `Company` (or manual `compute_enabled_modules()`) merges these with the plan's modules.

The result: `enabled_modules = union(plan_modules, module_overrides)`

The Company Settings page in the frontend (Company Management > Company Settings) displays:
- **Enabled Modules**: All currently enabled modules
- **Module Overrides**: Which modules were manually added beyond the plan
- **All Available Modules**: Full list with source (Subscription Plan / Manual Override) and status

---

## Frontend Integration

### Navigation Config

Every navigation item in `zentro-frontend/src/configs/navigation.config/apps.navigation.config.ts` uses three properties for access control:

| Property | Layer | Purpose | Example |
|---|---|---|---|
| `module` | Layer 1 (Modules) | Subscription-level gating | `module: "inventory"` |
| `moduleCode` | Layer 2 (Role Center) | Sidebar section visibility per user role | `moduleCode: "items"` |
| `pageName` | Layer 3 (Permissions) | Page-level CRUD access per user | `pageName: "Items"` |

### Navigation Filtering

In `VerticalMenuContent.tsx`, every nav item is filtered through all three checks:

```typescript
// Layer 1: Does the company have this module?
if (nav.module && !hasModule(nav.module)) return false;

// Layer 2: Does the user's role center include this section?
if (nav.moduleCode && !isModuleVisible(nav.moduleCode)) return false;

// Layer 3: Does the user have page access?
if (nav.pageName && !hasAnyPageAccess(nav.pageName)) return false;
```

### Hooks

- `useModuleEnabled()` (from `utils/hooks/useModuleEnabled.ts`): Provides `hasModule()`, `hasAllModules()`, `hasAnyModule()`, and raw `enabledModules` from Redux.
- `usePermissions()`: Provides `isModuleVisible()`, `hasAnyPageAccess()`, `getPagePermissions()` from JWT claims.

### Route Protection

Routes in `routes.config/appsRoute.ts` also use `pageName` for direct URL protection via `AppRoute.tsx`.

---

## Backend Integration

### Middleware

Two middlewares enforce module access server-side (`utils/middleware.py`):

1. **`ModulePermissionMiddleware`**: Checks URL patterns against `tenant.has_module()`. Currently gates `/api/hotel/`.
2. **`ModuleContextMiddleware`**: Injects `request.enabled_modules` and `request.has_module()` onto every request for views to use.

### View-Level Gating

For views that need module checks, use `request.has_module()`:

```python
class MyViewSet(viewsets.ModelViewSet):
    def create(self, request, *args, **kwargs):
        if not request.has_module("manufacturing"):
            return Response(
                {"error": "Manufacturing module required"},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().create(request, *args, **kwargs)
```

For hard-gating entire viewsets, use the `@require_module` decorator:

```python
from utils.modules import require_module
from django.utils.decorators import method_decorator

@method_decorator(require_module("hotel"), name="dispatch")
class HotelViewSet(viewsets.ModelViewSet):
    ...
```

---

## Adding a New Module

### Step 1: Register in MODULE_REGISTRY

Add to `zentro-backend/utils/modules.py`:

```python
"my_module": ModuleConfig(
    identifier="my_module",
    display_name="My Module",
    description="Description of the module",
    app_name="my_app",
    url_prefix="/api/my-module/",
    required_permissions=[],
    dependencies=["inventory"],  # List dependencies on other modules
    icon="icon-name",
),
```

### Step 2: Add to Pricing Plans

Update `zentro-backend/data/pricing_plans.json` to include the new module identifier in the appropriate plan's `included_modules` array. Then re-run `python manage.py seed_pricing_plans`.

### Step 3: Frontend Navigation

Add `module: "my_module"` to the navigation item in `apps.navigation.config.ts`:

```typescript
{
    key: "apps.myModule",
    moduleCode: "myModule",     // Layer 2: Role Center
    module: "my_module",        // Layer 1: Subscription Module
    subMenu: [{
        pageName: "My Module",  // Layer 3: Page Permission
    }]
}
```

### Step 4: Backend Gating (if needed)

Add URL pattern to `ModulePermissionMiddleware` or use `request.has_module()` in views.

### Step 5: Create Page Objects and Permission Sets

Follow the permission system guide (`PERMISSIONS_SYSTEM_GUIDE.md`) to create page objects and permission sets for the new module's pages.

### Step 6: Backfill Existing Companies

Run `python manage.py backfill_enabled_modules` to recompute `enabled_modules` for all companies.

---

## Management Commands

| Command | Description |
|---|---|
| `python manage.py seed_pricing_plans` | Load pricing plans from `data/pricing_plans.json` |
| `python manage.py seed_add_ons` | Load add-on pricing from `data/add_ons.json` |
| `python manage.py backfill_enabled_modules` | Recompute `enabled_modules` for all companies |
| `python manage.py backfill_enabled_modules --tenant=jom3` | Recompute for a specific company |
| `python manage.py backfill_enabled_modules --dry-run` | Preview changes without saving |

---

## Troubleshooting

### "No modules enabled" on Company Settings

1. Check if `Pricing` records exist in the public schema with `included_modules` populated
2. Check if the company's `Subscription.plan` maps to a valid pricing name via `PLAN_NAME_TO_PRICING`
3. Run `python manage.py backfill_enabled_modules --tenant=<schema_name>` to force recompute
4. User must re-login after module changes for the JWT to pick up new `enabled_modules`

### Module shows in sidebar but gives "Access Denied"

This means Layer 1 (module) passes but Layer 3 (permissions) fails. Check:
1. The user's User Group has the appropriate Permission Set assigned
2. The Permission Set includes the relevant Page Object with the needed CRUD permissions

### Module doesn't show in sidebar despite being enabled

This means Layer 1 (module) passes but Layer 2 (role center) fails. Check:
1. The user's Role Center includes the `moduleCode` in its `modules` array
2. The navigation item has the correct `moduleCode` property matching the role center

### Changes not reflecting after admin override

The user must re-login for JWT token to pick up the new `enabled_modules`. The Company Settings page (`/api/company/modules/`) shows real-time data from the database, but the sidebar relies on the JWT token.
