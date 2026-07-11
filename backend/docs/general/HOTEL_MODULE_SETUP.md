# Hotel Module Setup Guide

## Enable Hotel Module for a Tenant

The Hotel Management System is now available as an optional module. Follow these steps to enable it for a tenant:

### Option 1: Using Django Admin Action (Recommended - One-Click Setup!)

1. Run the Django server:

   ```bash
   cd zentro-backend
   python manage.py runserver
   ```

2. Access Django admin at `http://localhost:8000/admin/`

3. Navigate to **Companies** (Company model)

4. **First, enable the hotel module:**

   - Click on your company
   - Find `enabled_modules` field
   - Set it to: `["pos", "hotel"]`
   - Save

5. **Then, run the setup action:**

   - Go back to Company list
   - Select your company (checkbox)
   - From the **Actions** dropdown, choose:
     **"🏨 Setup Hotel Module (creates number series, GL accounts, etc.)"**
   - Click **Go**

6. Done! ✅ You'll see a success message with counts of created items.

**Benefits of Admin Action:**

- ✨ One-click setup
- 📊 Shows detailed counts (number series, GL accounts, amenities, etc.)
- 🔄 Works on multiple companies at once
- ✅ Prevents duplicate setups
- 💬 Clear success/error feedback

### Option 2: Using Django Shell

```bash
cd zentro-backend
python manage.py shell
```

Then run:

```python
from company.models import Company
from django_tenants.utils import schema_context

# Get your company (replace 'yourcompany' with actual subdomain)
company = Company.objects.get(schema_name='yourcompany')

# Enable hotel module
company.enabled_modules = ['pos', 'hotel']
company.save()

print(f"Hotel module enabled for {company.schema_name}")
```

Then run the setup command:

```bash
python manage.py setup_hotel_module yourcompany
```

### What the Setup Command Does

The `setup_hotel_module` command automatically creates:

1. **Number Series** (6 series):

   - ROOM-TYPE (RT-001, RT-002, ...)
   - ROOM (ROOM-101, ROOM-102, ...)
   - GUEST (GUEST-000001, ...)
   - BOOKING (BKG-2025-00001, resets yearly)
   - FOLIO (FOL-000001, ...)
   - HOUSEKEEPING (HK-0001, ...)

2. **GL Accounts** (13 accounts):

   - Revenue: Room Revenue, F&B Revenue, Laundry, Minibar, etc.
   - Expense: Housekeeping, Maintenance
   - Liability: Guest Deposits
   - Asset: Advance Deposits

3. **Default Room Amenities** (11 items):

   - WiFi, Air Conditioning, TV, Minibar, Safe, etc.

4. **Housekeeping Task Types**:

   - Deep Clean, Standard Clean, Turndown Service, etc.

5. **Payment Methods**:
   - Post to Room
   - Advance Deposit
   - Credit Card - Hotel
   - Cash - Hotel

### Verify Setup

After enabling and running setup:

1. **Frontend**: Login and check the sidebar - you should see "HOTEL MANAGEMENT" section
2. **Backend**: Check Django admin for hotel models (Rooms, Guests, Bookings, etc.)
3. **Number Series**: Verify in Setup → Number Series that all 6 hotel series exist
4. **GL Accounts**: Check Chart of Accounts for hotel-specific accounts

### Rollback (if needed)

To undo the setup:

```bash
python manage.py setup_hotel_module <tenant_subdomain> --rollback
```

This will remove all created number series, GL accounts, amenities, etc.

### Disable Hotel Module

To disable the hotel module:

```python
from company.models import Company

company = Company.objects.get(schema_name='yourcompany')
company.enabled_modules = ['pos']  # Remove 'hotel'
company.save()
```

**Note**: Disabling the module hides it from the frontend but does NOT delete any hotel data. Re-enabling it will restore access to all existing data.

## Troubleshooting

### Hotel menu not showing in sidebar

1. Check if module is enabled:

   ```python
   company = Company.objects.get(schema_name='yourcompany')
   print(company.enabled_modules)  # Should include 'hotel'
   ```

2. Check JWT token includes enabled_modules:

   - Login and copy your access token
   - Decode it at jwt.io
   - Verify `enabled_modules` contains `"hotel"`

3. Clear browser cache and re-login

### Setup command fails

1. Ensure company exists and has hotel module enabled
2. Check if setup was already run (it's idempotent, safe to re-run)
3. Check Django logs for detailed error messages

### Permission errors

1. Ensure user has `admin` authority
2. Check `ADMIN` role is assigned to user
3. Verify navigation items have correct `authority: [ADMIN]`
