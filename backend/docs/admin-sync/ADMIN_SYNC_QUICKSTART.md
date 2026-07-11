# Admin Sync Actions - Quick Start

## ✅ What Was Created

A **centralized** Django admin interface for syncing data from JSON export files to your database.

## 📁 Files Created/Modified

### New Files:

1. **`utils/admin_sync.py`** - Core sync utility functions
2. **`settings/models.py`** - DataSyncConfig and SystemSettings models
3. **`settings/admin.py`** - Dedicated admin interface for JSON syncs
4. **`ADMIN_SYNC_GUIDE.md`** - Complete documentation
5. **`ADMIN_SYNC_QUICKSTART.md`** - This file

### Modified Admin Files:

The sync actions are also available in these admins (optional):

- `financials/admin.py` - G_LAccount and PaymentMethod
- `postings/admin.py` - All posting groups
- `sales/admin.py` - CustomerPostingGroup
- `purchases/admin.py` - VendorPostingGroup

## 🚀 How to Use (3 Simple Steps)

### Step 1: Create Migration and Migrate

```bash
python manage.py makemigrations settings
python manage.py migrate settings
```

### Step 2: Go to Data Sync Admin

Navigate to: `/admin/settings/datasyncconfig/`

You'll see a default configuration automatically created for you.

### Step 3: Run the Sync Action

1. **Select the config** (or don't select anything)
2. From the "Action" dropdown, choose:
   - **🔄 Sync from JSON file (this model only)** - Syncs based on current admin model
   - **🔄 Sync ALL models from JSON file** - Syncs all models at once ✅ **RECOMMENDED**
3. Click **"Go"**

That's it! You'll see a success message with the results.

## 🎯 Why This Approach is Better

### ✅ Centralized Management

- **One place** to manage all JSON syncs
- No clutter in individual model admins
- Easy to find and use

### ✅ Configuration Storage

- Track when syncs were run
- See sync status and results
- Configure different JSON file paths
- Store sync history

### ✅ Clean Separation

- Settings app handles system management
- Model admins focus on their data
- Better organization

## 📊 What Models Can Be Synced?

The **ALL models sync** will process these from your JSON file:

### ✅ Financials (2 models)

- `G_LAccount` (Chart of Accounts)
- `PaymentMethod`

### ✅ Postings (5 models)

- `GeneralBusinessPostingGroup`
- `GeneralProductPostingGroup`
- `GeneralPostingSetup`
- `InventoryPostingGroup`
- `InventoryPostingSetup`

### ✅ Sales (1 model)

- `CustomerPostingGroup`

### ✅ Purchases (1 model)

- `VendorPostingGroup`

### ✅ Items (1 model)

- `UnitOfMeasure`

**Total: 10 models** can be synced from your JSON export!

## 💡 Tips

### Use the Settings Admin

Go to `/admin/settings/datasyncconfig/` for:

- ✅ Centralized sync management
- ✅ Sync history tracking
- ✅ Easy configuration

### Sync All Models at Once

The **"🔄 Sync ALL models from JSON file"** action is recommended because:

- ✅ Syncs everything in one go
- ✅ Handles dependencies automatically
- ✅ Provides comprehensive summary
- ✅ Saves time

## 🔧 Example Workflow

### Scenario: Complete System Sync (Recommended)

1. **Run migrations:**

   ```bash
   python manage.py makemigrations settings
   python manage.py migrate
   ```

2. **Place your JSON file:**

   ```
   zentro-backend/tenant_semuna_export_20250227_062346.json
   ```

3. **Go to Data Sync Config:**

   - Navigate to `/admin/settings/datasyncconfig/`
   - You'll see a default config already created

4. **Run Sync All Models:**

   - From action dropdown: **"🔄 Sync ALL models from JSON file"**
   - Click "Go"

5. **Review Results:**

   ```
   Global sync completed:
   Total: 25 created, 150 updated

   Processed models:
   financials.G_LAccount: 5 created, 78 updated
   financials.PaymentMethod: 3 created, 0 updated
   postings.GeneralPostingSetup: 2 created, 5 updated
   ...
   ```

6. **Verify:**
   - Check the DataSyncConfig record
   - It will show last sync date and status
   - Review individual model admins to verify data

## ⚙️ How It Works

```python
# For each record in JSON:
1. Find existing record by: code, no, or name
2. If exists → UPDATE with new data
3. If not exists → CREATE new record
4. Handle foreign keys automatically
5. Return counts: created, updated, errors
6. Update sync status in DataSyncConfig
```

## 🎯 Key Features

- ✅ **Centralized Interface** - One place for all syncs
- ✅ **Auto-Created Config** - Default config created automatically
- ✅ **Sync History** - Track when and what was synced
- ✅ **Update or Create** - Handles both scenarios automatically
- ✅ **Foreign Keys** - Resolves relationships automatically
- ✅ **Detailed Feedback** - Shows exactly what happened
- ✅ **Error Handling** - Continues even if some records fail

## 📖 Model Structure

### DataSyncConfig Fields:

- **name** - Configuration name
- **description** - What this config is for
- **json_file_path** - Path to JSON file (relative to BASE_DIR)
- **last_sync_date** - When last sync was run
- **last_sync_status** - Success/Error status
- **last_sync_summary** - Detailed sync results
- **is_active** - Enable/disable this config

## 🆘 Troubleshooting

### No settings app?

Make sure `settings` is in INSTALLED_APPS:

```python
INSTALLED_APPS = [
    ...
    'settings',
]
```

### Migration errors?

Run these commands:

```bash
python manage.py makemigrations settings
python manage.py migrate settings
```

### Action not showing?

- Restart Django development server
- Check that you're on the DataSyncConfig admin page

### No records updated?

- Verify JSON file path in the config
- Check that JSON contains data
- Ensure lookup field (code/no/name) exists

## 🎉 Success!

You now have a **professional, centralized sync system**!

### Quick Access:

- **Data Sync Admin**: `/admin/settings/datasyncconfig/`
- **System Settings**: `/admin/settings/systemsettings/`

### Remember:

**Settings App → Data Sync Config → Sync ALL Models → Done** 🚀

It's that simple and organized!
