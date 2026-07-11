# Setup Admin Sync - Migration Guide

## 🎯 What Changed

The JSON sync actions have been **moved to a centralized location** in the **Settings app** for better organization.

### Before:

- ❌ Sync actions scattered across multiple model admins
- ❌ Hard to find where to sync data
- ❌ Cluttered admin interfaces

### After:

- ✅ **Centralized** in Settings app
- ✅ **One place** to manage all syncs
- ✅ **Clean** model admins
- ✅ **Track** sync history

## 📋 Setup Steps

### Step 1: Make sure Settings app is in INSTALLED_APPS

Check `zentro-backend/core/settings.py`:

```python
INSTALLED_APPS = [
    # ... other apps
    'settings',  # Make sure this is here
    # ... more apps
]
```

### Step 2: Create and Run Migrations

```bash
cd zentro-backend
python manage.py makemigrations settings
python manage.py migrate settings
```

Expected output:

```
Migrations for 'settings':
  settings/migrations/0001_initial.py
    - Create model DataSyncConfig
    - Create model SystemSettings
```

### Step 3: Verify Setup

Start your Django server:

```bash
python manage.py runserver
```

Navigate to:

- `/admin/settings/datasyncconfig/` - Main sync interface
- `/admin/settings/systemsettings/` - System settings

You should see a default "Default Sync Config" automatically created!

### Step 4: Test the Sync

1. Go to `/admin/settings/datasyncconfig/`
2. You'll see the default config
3. From Action dropdown, select: **"🔄 Sync ALL models from JSON file"**
4. Click **"Go"**
5. Review the results!

## 🗂️ File Structure

```
zentro-backend/
├── settings/
│   ├── __init__.py
│   ├── apps.py
│   ├── models.py              ← NEW: DataSyncConfig, SystemSettings
│   ├── admin.py               ← UPDATED: Sync actions here
│   ├── migrations/
│   │   └── 0001_initial.py    ← Created by makemigrations
│   └── ...
├── utils/
│   └── admin_sync.py          ← Sync utility functions
├── ADMIN_SYNC_GUIDE.md        ← Complete documentation
├── ADMIN_SYNC_QUICKSTART.md   ← Quick reference
└── SETUP_ADMIN_SYNC.md        ← This file
```

## 📊 New Models

### 1. DataSyncConfig

Manages JSON sync operations and tracks history.

**Fields:**

- `name` - Configuration name
- `description` - Description
- `json_file_path` - Path to JSON file
- `last_sync_date` - Last sync timestamp
- `last_sync_status` - Success/Error
- `last_sync_summary` - Detailed results
- `is_active` - Enable/disable

### 2. SystemSettings

General system-wide settings (for future use).

**Fields:**

- `setting_key` - Unique setting identifier
- `setting_value` - Setting value
- `description` - What this setting does
- `is_active` - Enable/disable

## 🚀 Usage

### Primary Location (Recommended):

Go to `/admin/settings/datasyncconfig/` and use the actions there.

### Alternative Locations:

Sync actions are also available in these admins (if needed):

- G/L Account Admin
- Payment Method Admin
- Posting Groups Admins
- Customer/Vendor Posting Group Admins

## 💡 Why Centralize?

### Benefits:

1. **Easy to Find** - One place to go for all syncs
2. **Track History** - See when syncs were run
3. **Clean Admins** - Model admins focus on their data
4. **Better UX** - Users know exactly where to go
5. **Scalable** - Easy to add more sync configs

### Use Cases:

- **Different JSON files** - Create multiple configs for different sources
- **Scheduled syncs** - Future: Add scheduling capability
- **Sync auditing** - Track who synced what and when
- **Multiple environments** - Different configs for dev/staging/prod

## 🔧 Configuration Examples

### Example 1: Default Config (Auto-created)

```
Name: Default Sync Config
Description: Default configuration for JSON data sync
JSON File Path: tenant_semuna_export_20250227_062346.json
Is Active: Yes
```

### Example 2: Staging Environment Config

Create a new config:

```
Name: Staging Sync
Description: Sync from staging environment export
JSON File Path: staging_export_2025.json
Is Active: Yes
```

### Example 3: Production Restore

Create a new config:

```
Name: Production Restore
Description: Restore production data from backup
JSON File Path: production_backup_20250301.json
Is Active: Yes
```

## 🆘 Troubleshooting

### Error: "No module named 'utils.utils'"

The settings models imports BaseModel. Make sure you have:

```python
# settings/models.py
from utils.utils import BaseModel
```

### Error: "Settings app not found"

Add to INSTALLED_APPS in settings.py:

```python
INSTALLED_APPS = [
    ...
    'settings',
]
```

### Error: "Table doesn't exist"

Run migrations:

```bash
python manage.py migrate settings
```

### Migration conflicts?

Reset migrations:

```bash
python manage.py migrate settings zero
python manage.py makemigrations settings
python manage.py migrate settings
```

## ✅ Verification Checklist

After setup, verify:

- [ ] Settings app in INSTALLED_APPS
- [ ] Migrations created and applied
- [ ] Can access `/admin/settings/datasyncconfig/`
- [ ] Default config exists
- [ ] Sync actions appear in action dropdown
- [ ] Sync works successfully
- [ ] Last sync date/status updates after sync

## 🎉 Next Steps

1. ✅ **Complete Setup** - Follow steps above
2. ✅ **Test Sync** - Run a test sync
3. ✅ **Create Configs** - Add more configs as needed
4. ✅ **Use Regularly** - Sync data from JSON exports
5. ✅ **Monitor History** - Check last sync details

## 📖 Documentation

- **Quick Start**: `ADMIN_SYNC_QUICKSTART.md`
- **Full Guide**: `ADMIN_SYNC_GUIDE.md`
- **This Setup Guide**: `SETUP_ADMIN_SYNC.md`

## 🎊 You're Done!

Your centralized admin sync system is ready to use!

**Quick Access**: `/admin/settings/datasyncconfig/`

Happy syncing! 🚀
