# 🎨 Business Central Style Role Centers - Visual Guide

## 🏗️ Architecture Overview

```
┌──────────────────────────────────────────────────────────────┐
│                     BUSINESS CENTRAL STYLE                    │
│                    Role → Role Center ID                      │
└──────────────────────────────────────────────────────────────┘

         ┌─────────────┐
         │    User     │
         │   (John)    │
         └──────┬──────┘
                │ has
                ↓
         ┌─────────────┐
         │    Role     │
         │ (Dispenser) │◄────────────┐
         └──────┬──────┘             │
                │ specifies          │
                ↓                    │
         ┌─────────────┐             │
         │ Role Center │             │
         │  (Disp.     │             │
         │   Center)   │             │
         └──────┬──────┘             │
                │ defines            │
                ↓                    │
         ┌─────────────┐             │
         │   Modules   │             │
         │   [sales,   │             │
         │  customers, │             │
         │    items]   │             │
         └──────┬──────┘             │
                │ controls           │
                ↓                    │
         ┌─────────────┐             │
         │ Navigation  │             │
         │  (Frontend) │             │
         └─────────────┘             │
                                     │
         Multiple roles can share ──┘
         the same role center!
```

---

## 🔄 Before vs After Diagram

### **❌ BEFORE (Wrong Direction)**:

```
┌────────────────┐
│  Role Center   │
│  (Admin Ctr)   │
│                │
│ linked_role ───┼────→ ┌──────────┐
│                │      │   Role   │
└────────────────┘      │  (Admin) │
                        └──────────┘

Problem: Role Center points to Role
Result: Each role needs its own center
```

### **✅ AFTER (Business Central Style!)**:

```
┌────────────────┐      ┌────────────────┐
│     Role       │      │  Role Center   │
│   (Admin)      │      │  (Admin Ctr)   │
│                │      │                │
│ role_center ───┼─────→│  modules       │
│                │      │  [sales, ...]  │
└────────────────┘      └────────────────┘
        │                        ↑
        │                        │
┌────────────────┐               │
│     Role       │               │
│  (SuperAdmin)  │               │
│                │───────────────┘
│ role_center    │    Multiple roles
│                │    can use same center!
└────────────────┘
```

---

## 👥 Real-World User Flow

### **Scenario: Pharmacy with 3 Users**

```
┌────────────────────────────────────────────────────────────────┐
│                    PHARMACY SETUP                              │
└────────────────────────────────────────────────────────────────┘

Step 1: Create Role Centers
┌───────────────────┐  ┌───────────────────┐  ┌───────────────────┐
│ Admin Center      │  │ Dispenser Center  │  │ Accountant Center │
│                   │  │                   │  │                   │
│ Modules:          │  │ Modules:          │  │ Modules:          │
│ • sales           │  │ • sales           │  │ • financials      │
│ • customers       │  │ • customers       │  │ • reports         │
│ • items           │  │ • items           │  │ • payments        │
│ • purchases       │  │ • profile         │  │ • expenses        │
│ • financials      │  │                   │  │ • profile         │
│ • payments        │  └───────────────────┘  └───────────────────┘
│ • expenses        │
│ • reports         │
│ • settings        │
│ • company         │
│ • roles           │
│ • profile         │
└───────────────────┘

Step 2: Create Roles (link to role centers)
┌────────────┐           ┌────────────┐           ┌────────────┐
│   Admin    │───────────│ Dispenser  │───────────│ Accountant │
│            │     ↓     │            │     ↓     │            │
│ role_center│  Admin    │ role_center│ Dispenser │ role_center│
│            │  Center   │            │  Center   │            │
└────────────┘           └────────────┘           └────────────┘
                                   ↓ Accountant
                                     Center

Step 3: Assign Roles to Users
┌────────────┐           ┌────────────┐           ┌────────────┐
│ Sarah      │           │    John    │           │    Mary    │
│ (Owner)    │           │ (Dispenser)│           │ (Accountant)│
│            │           │            │           │            │
│ Role:      │           │ Role:      │           │ Role:      │
│ • Admin    │           │ • Dispenser│           │ • Accountant│
└────────────┘           └────────────┘           └────────────┘

Step 4: Users See Different Modules
┌───────────────────┐  ┌───────────────────┐  ┌───────────────────┐
│ Sarah sees:       │  │ John sees:        │  │ Mary sees:        │
│ ✅ Sales          │  │ ✅ Sales          │  │ ❌ Sales          │
│ ✅ Customers      │  │ ✅ Customers      │  │ ❌ Customers      │
│ ✅ Items          │  │ ✅ Items          │  │ ❌ Items          │
│ ✅ Purchases      │  │ ❌ Purchases      │  │ ❌ Purchases      │
│ ✅ Financials     │  │ ❌ Financials     │  │ ✅ Financials     │
│ ✅ Payments       │  │ ❌ Payments       │  │ ✅ Payments       │
│ ✅ Expenses       │  │ ❌ Expenses       │  │ ✅ Expenses       │
│ ✅ Reports        │  │ ❌ Reports        │  │ ✅ Reports        │
│ ✅ Settings       │  │ ❌ Settings       │  │ ❌ Settings       │
│ ✅ Company        │  │ ❌ Company        │  │ ❌ Company        │
│ ✅ Roles          │  │ ❌ Roles          │  │ ❌ Roles          │
│ ✅ Profile        │  │ ✅ Profile        │  │ ✅ Profile        │
└───────────────────┘  └───────────────────┘  └───────────────────┘
```

---

## 🔄 Reusability Example

### **Multiple Roles → Same Center**

```
┌──────────────────────────────────────────────────────────────┐
│             ONE ROLE CENTER, MULTIPLE ROLES                   │
└──────────────────────────────────────────────────────────────┘

                    ┌──────────────────┐
                    │  Sales Center    │
                    │                  │
                    │  Modules:        │
                    │  • sales         │
                    │  • customers     │
                    │  • items         │
                    │  • reports       │
                    │  • profile       │
                    └────────┬─────────┘
                             │
        ┌────────────────────┼────────────────────┐
        ↓                    ↓                    ↓
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│ Sales Person │    │ Senior Sales │    │Sales Manager │
│              │    │              │    │              │
│ role_center ─┼────┤ role_center ─┼────┤ role_center ─┤
│              │    │              │    │              │
└──────────────┘    └──────────────┘    └──────────────┘

Result:
• All 3 roles get the same modules
• Change Sales Center → All 3 roles updated instantly!
• No need to update each role individually
• Perfect reusability! ✨
```

---

## 📊 Data Flow Diagram

### **From Database to User Screen**

```
┌──────────────────────────────────────────────────────────────┐
│                      DATA FLOW                                │
└──────────────────────────────────────────────────────────────┘

1. DATABASE
┌────────────────────────────────────────────────────────────┐
│ Role Table                 RoleCenter Table                │
│ ┌───────────────┐         ┌────────────────┐             │
│ │ id: 1         │         │ id: 1          │             │
│ │ name: Cashier │         │ code: CASHIER_ │             │
│ │ role_center_id│────────→│      CENTER    │             │
│ │         = 1   │         │ modules: [     │             │
│ └───────────────┘         │   "sales",     │             │
│                           │   "customers", │             │
│                           │   "profile"    │             │
│                           │ ]              │             │
│                           └────────────────┘             │
└────────────────────────────────────────────────────────────┘
                              ↓
2. BACKEND (JWT Token Creation)
┌────────────────────────────────────────────────────────────┐
│ authentication/serializers.py                              │
│                                                            │
│ for role in user.roles.all():                             │
│     if role.role_center:                                  │
│         modules.extend(role.role_center.modules)          │
│                                                            │
│ token["role_center_modules"] = ["sales", "customers", ... ]│
└────────────────────────────────────────────────────────────┘
                              ↓
3. JWT TOKEN (Sent to Frontend)
┌────────────────────────────────────────────────────────────┐
│ {                                                          │
│   "user_id": 123,                                         │
│   "email": "john@pharmacy.com",                           │
│   "roles": ["Cashier"],                                   │
│   "role_center_modules": [                                │
│     "sales",                                              │
│     "customers",                                          │
│     "profile"                                             │
│   ]                                                       │
│ }                                                         │
└────────────────────────────────────────────────────────────┘
                              ↓
4. FRONTEND (Redux Store)
┌────────────────────────────────────────────────────────────┐
│ userSlice.ts                                               │
│                                                            │
│ state = {                                                  │
│   user: {                                                  │
│     ...                                                    │
│     role_center_modules: ["sales", "customers", "profile"]│
│   }                                                       │
│ }                                                         │
└────────────────────────────────────────────────────────────┘
                              ↓
5. NAVIGATION COMPONENT
┌────────────────────────────────────────────────────────────┐
│ VerticalMenuContent.tsx                                    │
│                                                            │
│ const { isModuleVisible } = usePermissions();             │
│                                                            │
│ // Filter navigation                                      │
│ const filteredNav = navigation.filter(item => {           │
│   return isModuleVisible(item.moduleCode);               │
│ });                                                       │
│                                                            │
│ // isModuleVisible checks if moduleCode is in            │
│ // role_center_modules array                             │
└────────────────────────────────────────────────────────────┘
                              ↓
6. USER SCREEN
┌────────────────────────────────────────────────────────────┐
│ Navigation Menu                                            │
│                                                            │
│ APPS                                                       │
│ ├─ 📊 Sales ✅ (moduleCode: "sales" → visible!)          │
│ │  ├─ Dashboard                                           │
│ │  ├─ New Sale                                            │
│ │  └─ Sales History                                       │
│ ├─ 👥 Customers ✅ (moduleCode: "customers" → visible!)  │
│ │  ├─ All Customers                                       │
│ │  └─ Add Customer                                        │
│ └─ 👤 Profile ✅ (moduleCode: "profile" → visible!)      │
│                                                            │
│ Hidden: Items ❌, Financials ❌, Purchases ❌, etc.       │
└────────────────────────────────────────────────────────────┘
```

---

## 🎯 Admin Panel Flow

### **Creating a Custom Role Center**

```
Step 1: Admin Panel → Role Centers
┌─────────────────────────────────────────────────────────────┐
│ Role Centers                                                 │
│                                                              │
│ [+ Add Role Center]                                         │
│                                                              │
│ ┌──────────────────────────────────────────────────────┐   │
│ │ Admin Center    | ADMIN_CENTER    | Admin | ...      │   │
│ │ Cashier Center  | CASHIER_CENTER  | Cashier | ...    │   │
│ │ Sales Center    | SALES_CENTER    | Sales | ...      │   │
│ └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                              ↓
Step 2: Fill Form
┌─────────────────────────────────────────────────────────────┐
│ Add Role Center                                              │
│                                                              │
│ Code: [DISPENSER_CENTER___________________]                 │
│ Name: [Dispenser Center___________________]                 │
│ Description: [For pharmacy dispensers_____]                 │
│                                                              │
│ Modules (JSON array):                                       │
│ ┌─────────────────────────────────────────┐                │
│ │ [                                       │                │
│ │   "sales",                              │                │
│ │   "customers",                          │                │
│ │   "items",                              │                │
│ │   "profile"                             │                │
│ │ ]                                       │                │
│ └─────────────────────────────────────────┘                │
│                                                              │
│ Is Active: ☑                                                │
│                                                              │
│ [Save] [Cancel]                                             │
└─────────────────────────────────────────────────────────────┘
                              ↓
Step 3: Admin Panel → Roles
┌─────────────────────────────────────────────────────────────┐
│ Edit Role: Dispenser                                         │
│                                                              │
│ Name: [Dispenser___________________________]                 │
│ Description: [Pharmacy dispenser role_____]                 │
│                                                              │
│ Role Center: [Dispenser Center ▼]  ← SELECT HERE!          │
│              ┌──────────────────┐                           │
│              │ Admin Center     │                           │
│              │ Cashier Center   │                           │
│              │ Dispenser Center │ ← Choose this!            │
│              │ Sales Center     │                           │
│              └──────────────────┘                           │
│                                                              │
│ [Save] [Cancel]                                             │
└─────────────────────────────────────────────────────────────┘
                              ↓
Step 4: Admin Panel → Users
┌─────────────────────────────────────────────────────────────┐
│ Edit User: John                                              │
│                                                              │
│ Email: [john@pharmacy.com_________________]                  │
│ Name: [John Doe_________________________]                    │
│                                                              │
│ Roles: ☑ Dispenser  ← ASSIGN HERE!                         │
│        ☐ Admin                                              │
│        ☐ Cashier                                            │
│        ☐ Sales                                              │
│                                                              │
│ [Save] [Cancel]                                             │
└─────────────────────────────────────────────────────────────┘
                              ↓
Result: John logs in → Sees only Sales, Customers, Items, Profile!
```

---

## 🎨 Visual Summary

```
┌─────────────────────────────────────────────────────────────┐
│              BUSINESS CENTRAL STYLE FLOW                     │
└─────────────────────────────────────────────────────────────┘

Create         Assign         Assign         Get
Role Center → to Role     → to User      → Modules
    ↓             ↓             ↓             ↓
┌────────┐   ┌────────┐   ┌────────┐   ┌────────┐
│ Disp.  │   │Dispenser│   │  John  │   │ [sales,│
│ Center │───│  Role  │───│  User  │───│customers│
│        │   │        │   │        │   │ items] │
└────────┘   └────────┘   └────────┘   └────────┘

✅ Clean      ✅ Simple    ✅ Easy     ✅ Auto
✅ Reusable   ✅ Flexible  ✅ Fast     ✅ Dynamic
```

---

**Perfect Business Central implementation with clear visuals!** 🚀✨
