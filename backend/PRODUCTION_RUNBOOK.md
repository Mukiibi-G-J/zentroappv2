# ZentroApp Production Runbook

Complete checklist of migrations, seeds, and management commands to run in production.  
Replace `<tenant_schema>` with your actual tenant (e.g. `kleen1`, `kisaasi`, `ekk`, `hardwareworld`).

---

## 1. Database Migrations

Always run first:

```powershell
python manage.py migrate_schemas
```

---

## 2. Page Objects & Permissions

Required for every tenant (User Management, Purchase/Payment History, etc.):

```powershell
python manage.py tenant_command populate_page_objects --schema=<tenant_schema>
python manage.py tenant_command setup_page_permissions --schema=<tenant_schema>
```

---

## 3. Dimension Backfill (First-Branch)

**Required for multi-branch:** Backfills ledger entries with null `global_dimension_1` / `dimension_set_id` using the first branch dimension value.

Run **per tenant**:

```powershell
python manage.py tenant_command backfill_entry_dimensions --schema=<tenant_schema> --first-branch
```

**Example output:**
```
General Ledger Entries: 32/32 updated
Customer Ledger Entries: 6/6 updated
Detailed Customer Ledger Entries: 12/12 updated
...
```

---

## 4. Seed Commands (Per Tenant)

Run via `tenant_command` for tenant-specific data. Order matters for some seeds.

### Base / Setup

```powershell
python manage.py tenant_command populate_objects_table --schema=<tenant_schema>
```

### Authentication & Roles

```powershell
# Some seeds use --tenant; pass same value when using tenant_command
python manage.py tenant_command seed_roles --schema=<tenant_schema> --tenant=<tenant_schema>
python manage.py tenant_command setup_admin_permissions --schema=<tenant_schema>
python manage.py tenant_command setup_role_centers_all_tenants --schema=<tenant_schema>
```

### Dimension & Branch Filtering

```powershell
python manage.py tenant_command seed_item_branch_dimensions --schema=<tenant_schema>
```

### Financials

```powershell
python manage.py tenant_command seed_gl_accounts_from_json --schema=<tenant_schema>
python manage.py tenant_command seed_prepayment_accounts --schema=<tenant_schema>
python manage.py tenant_command seed_mobile_money_account --schema=<tenant_schema>
```

### No Series (Document Numbering)

```powershell
python manage.py tenant_command seed_no_series_from_json --schema=<tenant_schema>
python manage.py tenant_command seed_sales_order_numbers --schema=<tenant_schema>
python manage.py tenant_command seed_credit_memo_numbers --schema=<tenant_schema>
python manage.py tenant_command seed_sales_prepayment_numbers --schema=<tenant_schema>
python manage.py tenant_command seed_prepayment_no_series --schema=<tenant_schema>
python manage.py tenant_command seed_purchase_credit_memo_series --schema=<tenant_schema>
python manage.py tenant_command seed_prodorde_no_series --schema=<tenant_schema>
```

### Items & Inventory

```powershell
python manage.py tenant_command seed_item_ledger_entry_types --schema=<tenant_schema>
python manage.py tenant_command seed_physical_inventory_setup --schema=<tenant_schema>
python manage.py tenant_command seed_inventory_posting_setup --schema=<tenant_schema>
```

### Manufacturing / Production

```powershell
python manage.py tenant_command seed_manufacturing_setup --schema=<tenant_schema>
python manage.py tenant_command seed_production_bom_numbers --schema=<tenant_schema>
```

### Sales & Purchases

```powershell
python manage.py tenant_command create_payment_methods --schema=<tenant_schema>
```

### Expenses

```powershell
python manage.py tenant_command seed_expense_types --schema=<tenant_schema>
python manage.py tenant_command seed_expense_categories --schema=<tenant_schema>
```

### Loans (if enabled)

```powershell
python manage.py tenant_command seed_loan_no_series --schema=<tenant_schema>
python manage.py tenant_command seed_loan_accounts --schema=<tenant_schema>
```

### Company / Add-ons

```powershell
python manage.py tenant_command seed_add_ons --schema=<tenant_schema>
```

---

## 5. Run All Seeds for a Tenant (Seed Manager)

If using the Django Admin Seed Manager:

1. Go to **Setup → Seed Manager**
2. Select the Seed Manager instance
3. **Actions** → **Run All Seed Commands**
4. Click **Go**

> Note: Seed Manager runs in the current request context. For multi-tenant, ensure you are logged into the correct tenant or run seeds via `tenant_command` per schema.

---

## 6. Run for All Tenants

For commands that support it:

```powershell
python manage.py migrate_schemas --command=seed_add_ons
```

Or run the tenant_command in a loop for each schema.

---

## 7. Verification

```powershell
python manage.py tenant_command check_admin_permissions --schema=<tenant_schema>
python manage.py tenant_command debug_branch_filter --schema=<tenant_schema>
```

---

## 8. Post-restore (ZentroApp → V2 todos)

Payment ledger cleanup and other post-restore tasks: **[zentroapp-to-v2-todos/README.md](zentroapp-to-v2-todos/README.md)**

---

## Quick Reference: Minimal Production Deploy (One Tenant)

```powershell
python manage.py migrate_schemas
python manage.py tenant_command populate_page_objects --schema=<tenant_schema>
python manage.py tenant_command setup_page_permissions --schema=<tenant_schema>
python manage.py tenant_command backfill_entry_dimensions --schema=<tenant_schema> --first-branch
```

---

## Related Docs

- [zentroapp-to-v2-todos/README.md](zentroapp-to-v2-todos/README.md) – **ZentroApp → V2 migration todos** (all post-restore checklists)
- [docs/DIMENSION_MIGRATION_PRODUCTION_GUIDE.md](docs/DIMENSION_MIGRATION_PRODUCTION_GUIDE.md) – **Dimension migrations** (step-by-step, production)
- [PRODUCTION_SETUP_COMMANDS.txt](PRODUCTION_SETUP_COMMANDS.txt) – User Management deployment
- [.cursor/rules/seed_commands.mdc](../.cursor/rules/seed_commands.mdc) – Seed command conventions
