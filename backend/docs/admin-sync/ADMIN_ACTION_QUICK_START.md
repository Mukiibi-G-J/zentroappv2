# 🏨 Hotel Module Admin Action - Quick Start

## ✨ One-Click Hotel Setup

The easiest way to enable and set up the hotel module for any tenant!

---

## 🚀 Quick Steps (2 Minutes)

### Step 1: Enable Hotel Module

1. Go to Django Admin: `http://localhost:8000/admin/`
2. Navigate to **Companies**
3. Click on your company
4. Find `enabled_modules` field
5. Change from `["pos"]` to `["pos", "hotel"]`
6. **Save**

### Step 2: Run Setup Action

1. Go back to **Company list**
2. **Select your company** (checkbox on the left)
3. **Actions dropdown** → Choose:
   ```
   🏨 Setup Hotel Module (creates number series, GL accounts, etc.)
   ```
4. Click **Go**
5. Done! ✅

---

## ✅ Success Message

You'll see:

```
Successfully set up hotel module for 1 company(ies):
✅ demo: Setup successful!
   - Number Series: 6/6
   - GL Accounts: 12/12
   - Amenities: 11/11
   - Payment Methods: 4/4
```

---

## 📋 What Gets Created

### 1. Number Series (6)
- **ROOM-TYPE** → RT-001, RT-002, ...
- **ROOM** → ROOM-101, ROOM-102, ...
- **GUEST** → GUEST-000001, ...
- **BOOKING** → BKG-2025-00001 (resets yearly)
- **FOLIO** → FOL-000001, ...
- **HOUSEKEEPING** → HK-0001, ...

### 2. GL Accounts (12)
**Revenue:**
- 4100 - Room Revenue - Hotel
- 4110 - Food & Beverage Revenue - Hotel
- 4120 - Laundry Revenue - Hotel
- 4130 - Minibar Revenue - Hotel
- 4140 - Spa & Wellness Revenue
- 4150 - Conference Room Revenue
- 4199 - Other Hotel Revenue

**Expense:**
- 5100 - Housekeeping Expenses
- 5110 - Room Maintenance & Repairs

**Liability:**
- 2100 - Guest Deposits - Hotel
- 2110 - Unearned Room Revenue

**Asset:**
- 1300 - Guest Accounts Receivable

### 3. Room Amenities (11)
- WiFi
- Air Conditioning
- Television
- Minibar
- Room Safe
- Work Desk
- Coffee Maker
- Hairdryer
- Iron & Board
- Telephone
- Balcony/Terrace

### 4. Payment Methods (4)
- POST-ROOM - Post to Room
- HOTEL-DEPOSIT - Advance Deposit - Hotel
- HOTEL-CC - Credit Card - Hotel
- HOTEL-CASH - Cash - Hotel

---

## ✓ Verify Setup Worked

### Frontend Check
1. Login to `http://demo.localhost:5173` (or your subdomain)
2. **Check sidebar** - You should see **"Hotel Management"** section
3. Navigate to Hotel → Dashboard

### Backend Check
1. Django Admin → Navigate to:
   - **Number Series** - Verify 6 hotel series exist
   - **Payment Methods** - Verify 4 hotel methods exist
   - **G/L Accounts** - Verify 12 hotel accounts exist
   - **Room Amenities** (under Hotel Management) - Verify 11 amenities

---

## 🔄 Batch Operations

You can run the setup action on **multiple companies at once**:

1. Select multiple companies (checkboxes)
2. Choose the setup action
3. Click Go
4. Each company gets set up individually with feedback

---

## ⚠️ Common Issues

### "Hotel module not enabled"
**Solution:** Make sure `enabled_modules` includes `"hotel"` before running the action.

### "Hotel setup already exists"
**Solution:** Setup is idempotent - if already run, it skips. Safe to ignore.

### "Cannot import PaymentMethodType"
**Solution:** Fixed! Make sure you have the latest code.

---

## 💡 Pro Tips

- The action is **idempotent** - safe to run multiple times
- It **won't overwrite** existing data
- You can see **"Hotel Module"** column in the company list (✅/❌)
- The action works in **tenant context** - no cross-tenant pollution

---

## 📞 Need Help?

See full documentation:
- `HOTEL_MODULE_SETUP.md` - Complete setup guide
- `ADMIN_ACTIONS_GUIDE.md` - Admin actions documentation

---

**Created by:** Hotel Module Admin Action System  
**Version:** 1.0  
**Last Updated:** October 2025

