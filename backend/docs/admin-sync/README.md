# Admin Sync Action Guide

This guide explains how to use the JSON sync actions in Django Admin to synchronize data from JSON export files.

## Overview

The sync actions allow you to:

- **Update existing records** in the database from JSON data
- **Create new records** if they don't exist
- **Sync individual models** or **all models at once**
- **Always available** - no need to select items first

## Features

✅ Update or Create (upsert) functionality
✅ Handles foreign key relationships automatically
✅ Works with any model that has a unique field (code, no, name, etc.)
✅ Provides detailed feedback on created/updated/error counts
✅ Two sync modes: single model or all models

## How to Add Sync Actions to Your Admin

### Step 1: Import the Sync Functions

Add this import to your admin.py file:

```python
from utils.admin_sync import sync_from_json_file, sync_all_models_from_json
```

### Step 2: Add Actions to Your ModelAdmin

Simply add the actions to your ModelAdmin's `actions` list:

```python
@admin.register(YourModel)
class YourModelAdmin(admin.ModelAdmin):
    list_display = ['field1', 'field2']
    actions = [sync_from_json_file, sync_all_models_from_json]
```

### Example: Multiple Models

```python
# financials/admin.py
from utils.admin_sync import sync_from_json_file, sync_all_models_from_json

@admin.register(G_LAccount)
class G_LAccountAdmin(admin.ModelAdmin):
    actions = [indent_chart_of_accounts, sync_from_json_file, sync_all_models_from_json]

@admin.register(PaymentMethod)
class PaymentMethodAdmin(admin.ModelAdmin):
    actions = [sync_from_json_file, sync_all_models_from_json]
```

## Using the Sync Actions

### Method 1: Sync Single Model

1. Go to the model's admin page (e.g., `/admin/financials/g_laccount/`)
2. **Don't select any items** (or select any items - it doesn't matter)
3. From the action dropdown, select **"🔄 Sync from JSON file (this model only)"**
4. Click **"Go"**

This will:

- Read data for ONLY this model from the JSON file
- Update existing records or create new ones
- Show a success message with counts

### Method 2: Sync All Models

1. Go to ANY model's admin page
2. From the action dropdown, select **"🔄 Sync ALL models from JSON file"**
3. Click **"Go"**

This will:

- Read data for ALL models in the JSON file
- Process each model sequentially
- Show a comprehensive summary with details for each model

## JSON File Configuration

By default, the sync actions look for:

```
zentro-backend/tenant_semuna_export_20250227_062346.json
```

### JSON File Structure

The JSON file should have this structure:

```json
{
  "metadata": {
    "schema_name": "semuna",
    "export_date": "2025-02-27T06:23:45.945196"
  },
  "data": {
    "financials.G_LAccount": [
      {
        "no": "5400",
        "name": "Accounts Payable",
        "accounttype": "Begin-Total"
      }
    ],
    "financials.PaymentMethod": [
      {
        "code": "CASH",
        "description": "Cash",
        "bal_account_no": "Cash"
      }
    ]
  }
}
```

## How It Works

### Lookup Fields

The sync action automatically determines which field to use for lookups:

1. First tries `code` field
2. Then tries `no` field
3. Finally tries `name` field

### Foreign Key Resolution

For fields that reference other models (like `bal_account_no`), the system:

1. Detects it's a foreign key
2. Tries to find the related record by `name`, `code`, or `no`
3. Links the objects automatically

### Update or Create Logic

For each record in the JSON:

```python
obj, created = Model.objects.update_or_create(
    code=record['code'],  # or 'no', or 'name'
    defaults=record_data   # All other fields
)
```

## Success Messages

### Single Model Sync

```
Sync completed: 5 created, 10 updated
```

### All Models Sync

```
Global sync completed:
Total: 25 created, 50 updated

Processed models:
financials.G_LAccount: 5 created, 20 updated
financials.PaymentMethod: 3 created, 0 updated
postings.GeneralPostingSetup: 2 created, 5 updated
...
```

## Error Handling

If errors occur, you'll see:

- **File not found**: "JSON file not found: [path]"
- **Model not in JSON**: "No data found for [model] in JSON file"
- **Processing errors**: "Error processing record: [details]"
- **Summary with errors**: "Sync completed: 5 created, 10 updated, 2 errors"

## Models Supported in Current JSON

Based on your JSON export, these models can be synced:

### Financials

- ✅ `financials.G_LAccount` - Chart of Accounts
- ✅ `financials.PaymentMethod` - Payment Methods

### Postings

- ✅ `postings.GeneralBusinessPostingGroup`
- ✅ `postings.GeneralProductPostingGroup`
- ✅ `postings.GeneralPostingSetup`
- ✅ `postings.InventoryPostingGroup`
- ✅ `postings.InventoryPostingSetup`

### Sales

- ✅ `sales.CustomerPostingGroup`

### Purchases

- ✅ `purchases.VendorPostingGroup`

### Items

- ✅ `items.UnitOfMeasure`

## Advanced: Custom JSON File Path

If you want to use a different JSON file, you can customize the action:

```python
from utils.admin_sync import sync_from_json_file

def sync_from_custom_file(modeladmin, request, queryset):
    import os
    from django.conf import settings

    custom_path = os.path.join(settings.BASE_DIR, 'my_custom_export.json')
    return sync_from_json_file(modeladmin, request, queryset, custom_path)

sync_from_custom_file.short_description = "🔄 Sync from custom file"

class MyModelAdmin(admin.ModelAdmin):
    actions = [sync_from_custom_file]
```

## Best Practices

1. **Test First**: Try syncing on a development/staging environment first
2. **Backup Data**: Always backup your database before running a global sync
3. **Check Counts**: Review the created/updated counts to ensure they make sense
4. **Monitor Errors**: If you see errors, investigate and fix the data before retrying
5. **Use Single Model**: For targeted updates, use single model sync
6. **Use All Models**: For complete system restore/sync, use all models sync

## Troubleshooting

### Action doesn't appear in dropdown

- Make sure you imported the sync functions
- Verify the actions list includes the sync functions
- Restart the Django development server

### "Model not found" error

- Check that the model path in JSON matches your app structure
- Example: `financials.G_LAccount` means app="financials", model="G_LAccount"

### Foreign key not resolving

- Ensure the related record exists in the database first
- Check that the related record has the expected name/code/no field
- Consider syncing models in dependency order

### No records created/updated

- Verify the JSON file path is correct
- Check that the model has data in the JSON file
- Ensure the lookup field (code/no/name) exists in your model

## Example Workflow

Here's a typical workflow for syncing your tenant export:

1. **Export data** from source tenant to JSON
2. **Place JSON file** in `zentro-backend/` directory
3. **Go to G/L Account admin** page
4. **Select "🔄 Sync ALL models from JSON file"**
5. **Click "Go"**
6. **Review the summary** message
7. **Verify data** in each model's admin page

## Summary

The sync actions provide a powerful way to:

- Keep your database in sync with JSON exports
- Quickly restore/update data from configuration files
- Automate data migration between environments
- Handle bulk updates without custom scripts

The actions are **always available** - you don't need to select any items first. Just use the action dropdown and go!
