# 🧪 Role Center - Testing & Usage Guide

## ✅ Current Status

**Backend**: 100% Complete ✅  
**Default Role Centers**: Created for all 8 tenants ✅  
**JWT Integration**: Working ✅  
**Admin Interface**: Ready to use ✅

---

## 🎯 Quick Test: Verify It Works

### **Test 1: Check Role Centers Exist**

1. **Go to Admin Panel**:

   ```
   http://ekk.localhost:8000/admin/authentication/rolecenter/
   ```

2. **You should see 7 role centers**:

   - ✅ Accountant Center
   - ✅ Admin Center
   - ✅ Cashier Center
   - ✅ Inventory Center
   - ✅ Manager Center
   - ✅ Sales Center
   - ✅ User Center

3. **Click on any role center**:
   - See the linked role
   - See the modules array
   - See colored module badges

---

### **Test 2: Verify JWT Token**

1. **Login to the app** (any user)

2. **Open browser console** (F12)

3. **Run this**:

   ```javascript
   const token = localStorage.getItem("accessToken");
   const decoded = JSON.parse(atob(token.split(".")[1]));
   console.log("Roles:", decoded.roles);
   console.log("Authority:", decoded.authority);
   console.log("Role Center Modules:", decoded.role_center_modules);
   ```

4. **You should see**:
   ```javascript
   Roles: ["Admin"]
   Authority: ["all"]
   Role Center Modules: ["sales", "customers", "items", "purchases",
                         "financials", "payments", "expenses", "reports",
                         "settings", "company", "roles", "profile"]
   ```

---

### **Test 3: Create Custom Role Center**

**Scenario**: Create "Dispenser" role center

1. **Go to Role Centers**:

   ```
   http://ekk.localhost:8000/admin/authentication/rolecenter/
   ```

2. **Click "Add Role Center"**

3. **Fill in**:

   ```
   Code: DISPENSER_CENTER
   Name: Dispenser Role Center
   Description: For pharmacy dispensers
   Linked Role: Select or create "Dispenser" role
   Modules: ["sales", "customers", "items"]
   Is Active: ✅ Checked
   ```

4. **Save**

5. **Verify**:
   - Go back to list
   - See "Dispenser Role Center"
   - See modules: sales, customers, items

---

### **Test 4: Assign Role to User**

1. **Create/Get Dispenser Role**:

   ```
   Admin Panel → Roles → Add/Edit "Dispenser" role
   Permissions: ["sales", "customers", "items"]
   ```

2. **Assign to User**:

   ```
   Admin Panel → Users → Select user → Roles → Add "Dispenser"
   Save
   ```

3. **Login as that user**

4. **Check JWT token**:
   ```javascript
   const decoded = JSON.parse(atob(token.split(".")[1]));
   console.log(decoded.role_center_modules);
   // Should show: ["sales", "customers", "items"]
   ```

---

### **Test 5: Multiple Roles**

**Scenario**: User has multiple roles

1. **Assign multiple roles to user**:

   ```
   User → Roles:
   - Cashier
   - Sales
   ```

2. **Login as that user**

3. **Check JWT**:
   ```javascript
   console.log(decoded.role_center_modules);
   // Should combine modules from both role centers:
   // ["sales", "customers", "profile", "items", "reports"]
   // (unique, no duplicates)
   ```

---

## 🎨 Frontend Integration Testing

### **Step 1: Update TypeScript Types**

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

### **Step 2: Update Redux Store**

**File**: `zentro-frontend/src/store/slices/auth/userSlice.ts`

```typescript
const initialState: UserState = {
  // ... existing fields
  role_center_modules: [], // NEW
};

// In setUser reducer
setUser: (state, action: PayloadAction<Partial<UserState>>) => {
  // ... existing assignments
  state.role_center_modules = action.payload.role_center_modules || [];
},
```

---

### **Step 3: Update Auth Hook**

**File**: `zentro-frontend/src/utils/hooks/useAuth.ts`

Find the `signIn` function and update:

```typescript
dispatch(
  setUser({
    // ... existing fields
    role_center_modules: decoded.role_center_modules || [],
  })
);
```

---

### **Step 4: Use in Navigation**

**File**: Your sidebar/navigation component

```typescript
import { useAppSelector } from "@/store";

const Navigation = () => {
  const user = useAppSelector((state) => state.auth.user);
  const roleCenterModules = user.role_center_modules || [];

  // Check module visibility
  const isModuleVisible = (moduleCode: string): boolean => {
    // Superuser sees everything
    if (user.is_superuser) return true;

    // Check role center modules (primary)
    if (roleCenterModules.length > 0) {
      return roleCenterModules.includes(moduleCode);
    }

    // Fallback to authority
    return user.authority?.includes(moduleCode) || false;
  };

  // Module visibility
  const showSales = isModuleVisible("sales");
  const showCustomers = isModuleVisible("customers");
  const showItems = isModuleVisible("items");
  const showFinancials = isModuleVisible("financials");

  return (
    <nav>
      {showSales && <NavItem label="Sales" path="/app/sales" />}
      {showCustomers && (
        <NavItem label="Customers" path="/app/sales/customers" />
      )}
      {showItems && <NavItem label="Items" path="/app/items" />}
      {showFinancials && <NavItem label="Financials" path="/app/financials" />}
    </nav>
  );
};
```

---

## 🧪 Complete Testing Checklist

### **Backend Testing**:

- [x] ✅ RoleCenter model created
- [x] ✅ Migration applied to all tenants
- [x] ✅ Admin interface accessible
- [x] ✅ Default role centers created (7 per tenant)
- [x] ✅ JWT token includes `role_center_modules`
- [x] ✅ All 8 existing companies updated

### **Admin Panel Testing**:

- [ ] Can view role centers list
- [ ] Can create new role center
- [ ] Can edit existing role center
- [ ] Can see colored module badges
- [ ] Can link role center to role
- [ ] Can activate/deactivate role center

### **JWT Token Testing**:

- [ ] Token includes `role_center_modules`
- [ ] Modules match role center configuration
- [ ] Multiple roles combine modules correctly
- [ ] Superuser gets all modules
- [ ] User without role center falls back to authority

### **Frontend Testing** (After Integration):

- [ ] Types updated
- [ ] Redux store updated
- [ ] Auth hook updated
- [ ] Navigation shows correct modules
- [ ] Cashier sees only sales, customers
- [ ] Admin sees all modules
- [ ] Module visibility changes on role change

---

## 🎯 Manual Test Scenarios

### **Scenario 1: Cashier User**

```
1. Create user "sarah_cashier"
2. Assign role: "Cashier"
3. Login as sarah_cashier
4. Expected JWT:
   {
     "roles": ["Cashier"],
     "authority": ["sales", "customers"],
     "role_center_modules": ["sales", "customers", "profile"]
   }
5. Expected UI:
   ✅ Shows: Sales, Customers, Profile
   ❌ Hides: Items, Financials, Reports, Settings
```

---

### **Scenario 2: Accountant User**

```
1. Create user "john_accountant"
2. Assign role: "Accountant"
3. Login as john_accountant
4. Expected JWT:
   {
     "roles": ["Accountant"],
     "authority": ["financials", "reports", "payments", "expenses"],
     "role_center_modules": ["financials", "reports", "payments", "expenses", "profile"]
   }
5. Expected UI:
   ✅ Shows: Financials, Reports, Payments, Expenses, Profile
   ❌ Hides: Sales, Customers, Items
```

---

### **Scenario 3: Multi-Role User**

```
1. Create user "jane_manager"
2. Assign roles: "Manager" + "Accountant"
3. Login as jane_manager
4. Expected JWT:
   {
     "roles": ["Manager", "Accountant"],
     "role_center_modules": [
       // From Manager Center
       "sales", "customers", "items", "purchases",
       "financials", "payments", "expenses", "reports", "profile"
       // Accountant modules already included above
     ]
   }
5. Expected UI:
   ✅ Shows: All modules from both role centers (combined)
```

---

### **Scenario 4: Custom "Dispenser" Role**

```
1. Create role center in admin:
   Code: DISPENSER_CENTER
   Name: Dispenser Center
   Role: Dispenser
   Modules: ["sales", "customers", "items"]

2. Create user "pharmacy_dispenser"
3. Assign role: "Dispenser"
4. Login
5. Expected JWT:
   {
     "roles": ["Dispenser"],
     "role_center_modules": ["sales", "customers", "items"]
   }
6. Expected UI:
   ✅ Shows: Sales, Customers, Items
   ❌ Hides: Everything else
```

---

## 🔍 Troubleshooting

### **Issue**: Role center not appearing in admin

**Solution**:

- Check migration ran: `python manage.py showmigrations authentication`
- Should see `[X] 0013_rolecenter`

---

### **Issue**: JWT token missing `role_center_modules`

**Solution**:

- Check user has a role assigned
- Check role has a linked role center
- Check role center is active (`is_active=True`)
- Try logging in again (fresh token)

---

### **Issue**: User sees wrong modules

**Solution**:

- Check role center configuration in admin
- Verify `modules` array is correct JSON
- Check user's role assignment
- Check JWT token in browser console

---

### **Issue**: Want to change modules for existing role center

**Solution**:

- Go to admin → Role Centers → Click role center
- Edit `modules` array
- Save
- Users get new config on next login

---

## 📊 Default Role Center Matrix

| Role       | Sales | Customers | Items | Purchases | Financials | Payments | Expenses | Reports | Settings | Company | Roles | Profile |
| ---------- | ----- | --------- | ----- | --------- | ---------- | -------- | -------- | ------- | -------- | ------- | ----- | ------- |
| Admin      | ✅    | ✅        | ✅    | ✅        | ✅         | ✅       | ✅       | ✅      | ✅       | ✅      | ✅    | ✅      |
| Manager    | ✅    | ✅        | ✅    | ✅        | ✅         | ✅       | ✅       | ✅      | ❌       | ❌      | ❌    | ✅      |
| Accountant | ❌    | ❌        | ❌    | ❌        | ✅         | ✅       | ✅       | ✅      | ❌       | ❌      | ❌    | ✅      |
| Sales      | ✅    | ✅        | ✅    | ❌        | ❌         | ❌       | ❌       | ✅      | ❌       | ❌      | ❌    | ✅      |
| Cashier    | ✅    | ✅        | ❌    | ❌        | ❌         | ❌       | ❌       | ❌      | ❌       | ❌      | ❌    | ✅      |
| Inventory  | ❌    | ❌        | ✅    | ✅        | ❌         | ❌       | ❌       | ❌      | ❌       | ❌      | ❌    | ✅      |
| User       | ❌    | ❌        | ❌    | ❌        | ❌         | ❌       | ❌       | ❌      | ❌       | ❌      | ❌    | ✅      |

---

## 🚀 Ready to Use!

**Everything is set up and working!**

**Next**: Integrate with frontend (3 simple file updates) to show/hide navigation based on `role_center_modules`.

---

## 📞 Quick Commands

### **View role centers for current tenant**:

```bash
python manage.py shell
>>> from authentication.models import RoleCenter
>>> for rc in RoleCenter.objects.all():
...     print(f"{rc.name}: {rc.modules}")
```

### **Setup for new tenant** (automatic now!):

```bash
# Already runs during company creation!
# No manual action needed
```

### **Setup for existing tenants** (already done!):

```bash
# All 8 companies already have role centers!
python manage.py setup_role_centers_all_tenants  # If needed again
```

---

**Perfect! You can now create role centers without any hardcoding!** 🎉
