# Django Admin Actions Guide

## Hotel Module Setup Action

### Quick Access

**Path:** `Django Admin → Companies → Select Company → Actions → "🏨 Setup Hotel Module"`

### What It Does

The **Setup Hotel Module** admin action provides one-click initialization of all hotel module requirements for selected companies. No more running management commands manually!

### How to Use

1. **Enable Hotel Module First:**

   - Edit the company
   - Set `enabled_modules` to `["pos", "hotel"]`
   - Save

2. **Run the Setup Action:**
   - Select one or more companies (checkbox)
   - Choose "🏨 Setup Hotel Module" from Actions dropdown
   - Click Go
   - See instant feedback!

### What Gets Created

The action automatically creates:

✅ **6 Number Series:**

- Room Type (RT-001, RT-002, ...)
- Room (ROOM-101, ROOM-102, ...)
- Guest (GUEST-000001, ...)
- Booking (BKG-2025-00001, resets yearly)
- Folio (FOL-000001, ...)
- Housekeeping (HK-0001, ...)

✅ **13 GL Accounts:**

- Revenue: Room, F&B, Laundry, Minibar, Spa, Conference, Other
- Expense: Housekeeping, Maintenance
- Liability: Guest Deposits, Advance Bookings
- Asset: Advance Deposits Paid, Guest Receivables

✅ **11 Default Room Amenities:**

- WiFi, Air Conditioning, Television, Minibar
- Room Safe, Work Desk, Coffee Maker, Hairdryer
- Iron & Board, Telephone, Balcony/Terrace

✅ **4 Payment Methods:**

- Post to Room
- Advance Deposit
- Credit Card - Hotel
- Cash - Hotel

### Features

- **Batch Operations:** Select multiple companies, run setup on all at once
- **Duplicate Prevention:** Won't create duplicates if already set up
- **Detailed Feedback:** Shows exact counts of created items
- **Validation:** Checks if hotel module is enabled before running
- **Error Handling:** Clear error messages if something goes wrong

### Success Message Example

```
Successfully set up hotel module for 1 company(ies):
✅ YourCompany: Setup successful!
   - Number Series: 6/6
   - GL Accounts: 13/13
   - Amenities: 11/11
   - Payment Methods: 4/4
```

### Error Messages

**If hotel module not enabled:**

```
⚠️ YourCompany: Hotel module not enabled.
Please add 'hotel' to enabled_modules first.
```

**If already set up:**

```
❌ YourCompany: Hotel setup already exists for this company
```

### Behind the Scenes

The action uses `HotelSetupService` from `hotel_management/services.py`, which is also used by the management command. This ensures consistency between admin actions and CLI commands.

### Code Location

- **Admin Action:** `company/admin.py` → `CompanyAdmin.setup_hotel_module_action`
- **Service Layer:** `hotel_management/services.py` → `HotelSetupService`
- **Management Command:** `hotel_management/management/commands/setup_hotel_module.py`

### Troubleshooting

**Action doesn't appear?**

- Make sure you're in the Company admin section
- Check that you have admin permissions

**Action fails?**

- Verify `enabled_modules` includes `"hotel"`
- Check Django logs for detailed error messages
- Ensure database migrations are up to date

**Want to undo?**

- Currently no rollback action in admin
- Use management command: `python manage.py setup_hotel_module --company=<id> --rollback`

### Future Enhancements

Potential additions:

- Rollback action in admin
- Preview mode (show what would be created)
- Custom configuration options
- Setup status indicator in Company list
- Bulk enable + setup in one action

---

## Adding More Admin Actions

To add similar actions for other modules:

1. Create a service class in `<module>/services.py`
2. Add action method to the appropriate admin class
3. Add to `actions = [...]` list
4. Provide detailed feedback with counts
5. Handle errors gracefully
6. Document in this guide

See `CompanyAdmin.setup_hotel_module_action` as a reference implementation.
