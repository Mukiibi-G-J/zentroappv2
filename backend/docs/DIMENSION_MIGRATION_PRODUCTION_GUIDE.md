# Dimension Migration – Production Guide

Step-by-step guide for running dimension-related migrations in production.  
Follow this order to avoid the issues encountered during development.

---

## Overview

Dimension migrations affect multiple apps:

- `dimension` – Dimension, DimensionValue, DimensionSet, DefaultDimension
- `authentication` – CustomUser (global_dimension_1)
- `financials` – GeneralLedgerEntry, GeneralLedgerSetup
- `sales` – CustomerLedgerEntry, PostedSalesInvoiceLine, SalesInvoice, etc.
- `purchases` – PurchaseInvoice, VendorLedger, etc.
- `items` – ItemLedgerEntries, ValueEntry
- `bank_account` – BankAccountLedgerEntry
- `prepayment` – Preayment, PreaymentLine

Fields are renamed from `dimension_1` to `global_dimension_1`, and `dimension_set` / `dimension_set_id` are introduced.

---

## Prerequisites (Before Running Migrations)

### 1. Database Backup

```bash
# PostgreSQL - backup before any migration
pg_dump -U <user> -d <database> -F c -f backup_$(date +%Y%m%d_%H%M).dump
```

### 2. Virtual Environment Active

```bash
# Linux/Mac
source env/bin/activate

# Windows
.\env\Scripts\Activate.ps1
```

### 3. Environment Variables

Ensure `.env` or environment has correct:

- `DATABASE_URL` (or `DB_*` settings)
- Any tenant-related config

---

## Step 1: Run Schema Migrations

Runs migrations on **public schema first**, then **all tenant schemas**.

```bash
python manage.py migrate_schemas
```

**Expected output:**

- `Migrating schema public`
- Then `Migrating schema <tenant1>`, `<tenant2>`, etc.
- Each app’s migrations should complete without errors.

**If it fails:**

- Check the traceback for the failing app and schema
- Typical causes:
  - FK constraints (e.g. dimension tables)
  - Missing columns in dependent tables
  - Partial or out-of-order migrations
- Resolve in dev/staging first; do not force migrations in production without understanding the error

---

## Step 2: Per-Tenant Post-Migration Commands

Run these **per tenant** (replace `<tenant_schema>` with the actual schema, e.g. `demo`, `ekk`, `hardwareworld`).

### 2a. Page Objects & Permissions (Required)

```bash
python manage.py tenant_command populate_page_objects --schema=<tenant_schema>
python manage.py tenant_command setup_page_permissions --schema=<tenant_schema>
```

### 2b. Populate Objects Table (Required for `seed_item_branch_dimensions`)

```bash
python manage.py tenant_command populate_objects_table --schema=<tenant_schema>
```

### 2c. Ensure First Branch Exists (Required for `backfill_entry_dimensions`)

The backfill command needs a "first branch" dimension value. One of these must be true:

**Option A: General Ledger Setup**

- In Django Admin: **Financials → General Ledger Setup**
- Set **Global Dimension 1** to a Dimension (e.g. BRANCH)
- That Dimension must have at least one DimensionValue

**Option B: Create BRANCH Dimension (if not present)**

- In Django Admin: **Dimension → Dimensions**
- Create a Dimension with code `BRANCH` (case-insensitive)
- In **Dimension Values**, add at least one value (e.g. code `MAIN`, name `Main Branch`)

**Option C: Run GL seeds** (if they create setup)

```bash
python manage.py tenant_command seed_gl_accounts_from_json --schema=<tenant_schema>
# Then verify General Ledger Setup has global_dimension_1 set
```

### 2d. Dimension Backfill (First-Branch)

Populates `global_dimension_1` and `dimension_set_id` on existing ledger entries that are null.

```bash
python manage.py tenant_command backfill_entry_dimensions --schema=<tenant_schema> --first-branch
```

**Expected output:**

```
================================================================================
FIRST-BRANCH DIMENSION BACKFILL SUMMARY
================================================================================
General Ledger Entries: 32/32 updated
Customer Ledger Entries: 6/6 updated
Detailed Customer Ledger Entries: 12/12 updated
Item Ledger Entries: 10/10 updated
Value Entries: 15/15 updated
Vendor Ledger Entries: 4/4 updated
Detailed Vendor Ledger Entries: 8/8 updated
Bank Account Ledger Entries: 2/2 updated (if applicable)
Sales Invoices: 5/5 updated
...
--------------------------------------------------------------------------------
```

**If it fails with “No first branch dimension value found”:**

- Ensure Step 2c is complete (GL Setup or BRANCH dimension with values)
- Run:

  ```bash
  python manage.py tenant_command debug_branch_filter --schema=<tenant_schema>
  ```

  to inspect dimension configuration

### 2e. Seed Item Branch Dimensions (Optional – Multi-Branch)

Assigns a default BRANCH dimension to all items:

```bash
python manage.py tenant_command seed_item_branch_dimensions --schema=<tenant_schema>
```

**Requires:** `populate_objects_table` and BRANCH dimension with values (from 2b and 2c).

---

## Step 3: Verification

```bash
python manage.py tenant_command check_admin_permissions --schema=<tenant_schema>
python manage.py tenant_command debug_branch_filter --schema=<tenant_schema>
```

---

## Production Checklist (Single Run)

Use this for one tenant at a time:

```bash
# 1. Migrations
python manage.py migrate_schemas

# 2. Per tenant (repeat for each tenant)
TENANT=demo   # or ekk, hardwareworld, etc.

python manage.py tenant_command populate_page_objects --schema=$TENANT
python manage.py tenant_command setup_page_permissions --schema=$TENANT
python manage.py tenant_command populate_objects_table --schema=$TENANT

# 3. Ensure BRANCH dimension / GL Setup exists (Django Admin if needed)

# 4. Dimension backfill
python manage.py tenant_command backfill_entry_dimensions --schema=$TENANT --first-branch

# 5. Optional: item branch dimensions
python manage.py tenant_command seed_item_branch_dimensions --schema=$TENANT
```

---

## PowerShell (Windows)

```powershell
$TENANT = "demo"

python manage.py migrate_schemas
python manage.py tenant_command populate_page_objects --schema=$TENANT
python manage.py tenant_command setup_page_permissions --schema=$TENANT
python manage.py tenant_command populate_objects_table --schema=$TENANT
python manage.py tenant_command backfill_entry_dimensions --schema=$TENANT --first-branch
python manage.py tenant_command seed_item_branch_dimensions --schema=$TENANT
```

---

## Using the Deploy Script (Optional)

```bash
# Linux/Mac
./deploy_user_management.sh <tenant_schema>

# Windows
.\deploy_user_management.ps1 -Schema <tenant_schema>
```

The script runs migrations, page objects, permissions, and prompts for dimension backfill.

---

## Common Issues

| Issue | Cause | Fix |
|-------|-------|-----|
| `No first branch dimension value found` | No BRANCH dimension or GL Setup `global_dimension_1` | Create BRANCH dimension + value, or configure GL Setup (Step 2c) |
| `Items table not found in Objects` | `populate_objects_table` not run | Run `tenant_command populate_objects_table --schema=<schema>` |
| `Relation "dimension_dimension" does not exist` | Migrations not applied to that schema | Run `migrate_schemas` and verify it finishes for that schema |
| FK constraint errors during migrate | Dependency order or partial migration | Investigate failing migration; fix in staging first |

---

## Related Docs

- [PRODUCTION_RUNBOOK.md](../PRODUCTION_RUNBOOK.md) – Full production checklist
- [PRODUCTION_SETUP_COMMANDS.txt](../PRODUCTION_SETUP_COMMANDS.txt) – User management deployment
- [docs/dimension/DIMENSION_FLOW_IMPLEMENTATION.md](dimension/DIMENSION_FLOW_IMPLEMENTATION.md) – Dimension design
