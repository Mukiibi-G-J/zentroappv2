# 🏠 Role Center - Quick Start Guide

## ✅ STATUS: READY TO USE!

**No hardcoding needed! Create role centers dynamically through Django Admin!**

---

## 🎯 What is a Role Center?

A **Role Center** defines which modules a specific role can see in the navigation/sidebar.

**Example**:

- **Dispenser Role** → Can see: Sales, Customers, Items
- **Accountant Role** → Can see: Financials, Reports, Payments
- **Cashier Role** → Can see: Sales, Customers (limited features)

---

## 🚀 Quick Start: Create Your First Role Center

### **Step 1: Access Django Admin**

```
http://ekk.localhost:8000/admin/authentication/rolecenter/
```

### **Step 2: Click "Add Role Center"**

### **Step 3: Fill in the Form**

**Basic Information**:

- **Code**: `DISPENSER_CENTER` (unique identifier)
- **Name**: `Dispenser Role Center` (display name)
- **Description**: `Role center for dispenser users`
- **Linked Role**: Select **"Dispenser"** (or any role you want)
- **Is Active**: ✅ Checked

**Module Configuration**:

```json
["sales", "customers", "items"]
```

### **Step 4: Save**

✅ Done! Users with the "Dispenser" role will now only see Sales, Customers, and Items modules!

---

## 📋 Available Modules

You can include any of these modules in the `modules` field:

```json
[
  "sales", // Sales module
  "customers", // Customer management
  "items", // Item/inventory management
  "purchases", // Purchase orders
  "financials", // Chart of accounts, GL
  "payments", // Payment processing
  "expenses", // Expense tracking
  "reports", // Reports and analytics
  "settings", // System settings
  "profile", // User profile
  "company", // Company settings
  "roles" // Role management
]
```

---

## 🎨 Real-World Examples

### **Example 1: Dispenser Center**

```json
Code: DISPENSER_CENTER
Name: Dispenser Role Center
Linked Role: Dispenser
Modules: ["sales", "customers", "items"]
```

**What users see**:

- ✅ Sales (create invoices)
- ✅ Customers (view, create)
- ✅ Items (view only)
- ❌ Financials (hidden)
- ❌ Settings (hidden)

---

### **Example 2: Accountant Center**

```json
Code: ACCOUNTANT_CENTER
Name: Accountant Role Center
Linked Role: Accountant
Modules: ["financials", "reports", "payments", "expenses"]
```

**What users see**:

- ✅ Financials
- ✅ Reports
- ✅ Payments
- ✅ Expenses
- ❌ Sales (hidden)
- ❌ Items (hidden)

---

### **Example 3: Manager Center (Full Access)**

```json
Code: MANAGER_CENTER
Name: Manager Role Center
Linked Role: Manager
Modules: ["sales", "customers", "items", "purchases", "financials", "payments", "expenses", "reports", "settings", "company", "roles"]
```

**What users see**:

- ✅ Everything!

---

### **Example 4: Cashier Center (Limited)**

```json
Code: CASHIER_CENTER
Name: Cashier Role Center
Linked Role: Cashier
Modules: ["sales", "customers"]
Features: {
  "sales": ["create_invoice", "view_history"],
  "customers": ["view", "create"]
}
```

**What users see**:

- ✅ Sales (create invoices, view history)
- ✅ Customers (view, create)
- ❌ Items (hidden)
- ❌ Reports (hidden)

---

## 🔧 How It Works

### **Backend (Already Done!)**

1. **Model**: `RoleCenter` model created in `authentication/models.py`
2. **Migration**: Table created via migration
3. **Admin**: Configured in `authentication/admin.py`
4. **JWT Token**: Modules added to `role_center_modules` in JWT token

### **JWT Token Structure**:

```json
{
  "username": "john_dispenser",
  "roles": ["Dispenser"],
  "authority": ["sales", "customers", "items"],
  "role_center_modules": ["sales", "customers", "items"],  // ← NEW!
  "permission_sets": ["SALES_CASHIER"],
  "user_groups": [...]
}
```

---

## 🎯 Frontend Integration (Next Step)

### **Update Frontend Types**:

```typescript
// zentro-frontend/src/@types/auth.ts

export interface DecodedToken {
  // ... existing fields
  role_center_modules?: string[]; // NEW
}

export interface UserState {
  // ... existing fields
  role_center_modules?: string[]; // NEW
}
```

### **Update Redux Store**:

```typescript
// zentro-frontend/src/store/slices/auth/userSlice.ts

const initialState: UserState = {
  // ... existing fields
  role_center_modules: [], // NEW
};

setUser: (state, action) => {
  // ... existing assignments
  state.role_center_modules = action.payload.role_center_modules || [];
},
```

### **Update Auth Hook**:

```typescript
// zentro-frontend/src/utils/hooks/useAuth.ts

dispatch(
  setUser({
    // ... existing fields
    role_center_modules: decoded.role_center_modules || [],
  })
);
```

### **Use in Navigation**:

```typescript
// In your Sidebar/Navigation component

const user = useAppSelector((state) => state.auth.user);
const roleCenterModules = user.role_center_modules || [];

// Simple check
const showSalesModule = roleCenterModules.includes("sales");
const showFinancialsModule = roleCenterModules.includes("financials");

// Render
{
  showSalesModule && <NavItem label="Sales" path="/app/sales" />;
}
{
  showFinancialsModule && <NavItem label="Financials" path="/app/financials" />;
}
```

---

## 📊 Module Visibility Logic

### **Priority Order**:

```
1. Superuser → Sees everything (bypass all checks)
2. Role Center Modules → Defines which modules appear
3. Authority (from Role) → Backup if no role center defined
4. User Groups + Permissions → Controls features within modules
```

### **Example Logic**:

```typescript
const isModuleVisible = (moduleCode: string): boolean => {
  // Superuser sees everything
  if (user.is_superuser) return true;

  // Check role center modules (primary)
  if (user.role_center_modules && user.role_center_modules.length > 0) {
    return user.role_center_modules.includes(moduleCode);
  }

  // Fallback to authority
  return user.authority?.includes(moduleCode) || false;
};
```

---

## 🎨 Advanced: Features Within Modules (Optional)

You can also control **features within modules**:

```json
{
  "modules": ["sales", "customers", "items"],
  "features": {
    "sales": ["create_invoice", "view_history"],
    "customers": ["view", "create"],
    "items": ["view_only"]
  }
}
```

**This allows**:

- Show Sales module, but hide "Edit Invoice" feature
- Show Customers module, but hide "Delete Customer" feature
- Show Items module, but only in view-only mode

---

## 🔍 Testing Your Role Center

### **Step 1: Create a Role Center**

```
Admin Panel → Role Centers → Add New
Code: TEST_CENTER
Name: Test Role Center
Linked Role: Cashier
Modules: ["sales", "customers"]
```

### **Step 2: Assign Role to User**

```
Admin Panel → Users → Select User → Add "Cashier" role
```

### **Step 3: Login as That User**

```
Login → Check JWT token (browser console)
Verify: token.role_center_modules = ["sales", "customers"]
```

### **Step 4: Verify Navigation**

```
Should see: Sales, Customers
Should NOT see: Items, Financials, Reports, etc.
```

---

## 🎯 Benefits

### **✅ No Hardcoding**:

- Create role centers through admin panel
- No need to modify code

### **✅ Flexible**:

- Change modules anytime
- Enable/disable role centers on the fly

### **✅ Multi-Role Support**:

- Users can have multiple roles
- Modules from all role centers are combined

### **✅ Secure**:

- Backend enforces permissions
- Frontend just hides UI elements

---

## 📝 Common Use Cases

### **1. Department-Based Access**:

```
Sales Department → SALES_CENTER → [sales, customers, items]
Finance Department → FINANCE_CENTER → [financials, reports, payments]
Warehouse → WAREHOUSE_CENTER → [items, purchases]
```

### **2. Experience-Based Access**:

```
Junior Staff → BASIC_CENTER → [sales, customers]
Senior Staff → ADVANCED_CENTER → [sales, customers, items, reports]
Management → MANAGER_CENTER → [all modules]
```

### **3. Location-Based Access**:

```
Retail Counter → COUNTER_CENTER → [sales, customers]
Back Office → OFFICE_CENTER → [financials, reports, expenses]
Warehouse → WAREHOUSE_CENTER → [items, purchases]
```

---

## 🚀 Next Steps

### **Option 1: Start Using It!**

1. Create your first role center
2. Assign it to a role
3. Test with a user

### **Option 2: Integrate with Frontend**

1. Update TypeScript types
2. Update Redux store
3. Update navigation component
4. Test module visibility

### **Option 3: Add More Features**

1. Dashboard widgets configuration
2. Feature-level controls
3. Custom module descriptions
4. Module icons

---

## 🎉 Summary

**With Role Centers, you can**:

- ✅ Wake up → Create "Dispenser" role center → Select modules → Done!
- ✅ No hardcoding needed
- ✅ Fully dynamic and configurable
- ✅ Works with existing permission system

**Perfect for your use case!** 🚀

---

## 📞 Quick Reference

### **Admin URL**:

```
http://ekk.localhost:8000/admin/authentication/rolecenter/
```

### **Create Role Center**:

```
1. Click "Add Role Center"
2. Fill in Code, Name, Linked Role
3. Add modules as JSON array: ["sales", "customers", "items"]
4. Save
```

### **Check JWT Token**:

```javascript
// In browser console after login
const token = localStorage.getItem("accessToken");
const decoded = JSON.parse(atob(token.split(".")[1]));
console.log(decoded.role_center_modules);
```

---

**That's it! You now have a flexible, no-hardcoding role center system!** ✅
