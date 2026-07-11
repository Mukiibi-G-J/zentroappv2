---
description: How Sales Prepayment accounts are provisioned and maintained
globs: docs/prepayment/prepayment-accounts.md
alwaysApply: false
---

- **New Chart of Accounts Entries**
  - 5350 `Sales Prepayments` (Begin-Total, Balance Sheet → Liabilities → Current Liabilities)
  - 5360 `Customer Prepayments VAT 0%` (Posting, nested under 5350 and totals into 5390)
  - 5390 `Sales Prepayments, Total` (End-Total spanning the Sales Prepayments block)
- **General Posting Setup**
  - Each posting setup can now point to a dedicated `prepayment_account`
  - During company creation we automatically link all setups to account `5360`
- **Automatic Provisioning**
  - Company creation triggers `python manage.py seed_prepayment_accounts` inside the tenant bootstrap task so the accounts are inserted/updated with the correct hierarchy metadata
  - The same command links any General Posting Setup missing a `prepayment_account`, defaulting to `5360` unless you pass `--account-no=<no>`
- **Production Seeding**
  - Run `python manage.py seed_prepayment_accounts` in any environment to (re)apply the defaults
  - Use `--account-no=<no>` if a tenant needs a different posting account for prepayments
  - Run `python manage.py seed_prepayment_no_series` if an older tenant is missing the POSTPREPINV/POSTPREPCM number series
- **Usage Notes**

  - The new accounts follow the Balance Sheet → Liabilities → Current Liabilities structure so financial statements continue to roll up correctly
  - Existing tenants should execute the seed command once so historical posting setups gain the new account reference

- **Posted Prepayment Number Series**

  - Added `POSTPREPINV` (Posted Prepayment Invoice) and `POSTPREPCM` (Posted Prepayment Credit Memo) to `data/default_no_series.json`
  - `company.tasks.setup_default_no_series()` plus the tenant bootstrap task now create the Sales & Receivables setup with both posted prepayment series linked
  - New nullable fields on `sales.SalesReceivable` hold these references so prepayment invoices/credit memos stay in their own sequences
  - Existing tenants should run `python manage.py seed_prepayment_no_series` (for the base No Series records) followed by `python manage.py tenant_command seed_sales_prepayment_numbers --schema=<schema>` to backfill the Sales & Receivables configuration
  - The same seed command ensures each No Series line has a `start_number`/`increment_by` before linking, making it safe to rerun in live environments

- **Preayment Tracking (Simplified BC parity)**
  - `PreaymentLine` now stores:
    - `Prepmt. Line Amount` (user input) and auto `Prepmt. Line Amount %`
    - `Prepmt. Amt. Inv.`, `Prepmt Amt to Deduct`, `Prepmt Amt Deducted` for lifecycle tracking
    - `New Installment` input lets users type the latest deposit collected; when saved, it automatically increases `Prepmt. Line Amount` so partial postings don’t require manual math
  - Validation mirrors BC rules: deposit can’t exceed line total, deductions can’t exceed invoiced remainder, negative values blocked
  - `Preayment` header aggregates total collected/invoiced/deducted so dashboards and posting checks have a single source
- **Preview Posting Workflow**
  - The prepayment preview builds a simulated invoice that debits Accounts Receivable and credits the configured prepayment account per `GeneralPostingSetup`
  - Quantity is fixed at 1 and the amount equals the deposit received so stakeholders can see what will post without creating entries
  - Cash payment methods automatically preview cash receipt entries so finance can see how the payment and invoice will apply before posting
  - Sales invoice lines (and posted sales invoice lines) now include an optional `G/L Account` column so future postings can reference explicit accounts when needed
- **Posting Workflow**

  - The new **Post Prepayment Invoice** admin action generates real `PostedSalesInvoice` + lines (one line per deposit, tied to the prepayment account) and persists the GL / customer ledger / detailed customer ledger entries that were shown in the preview
  - Customer ledger entries follow the same four‑step pattern as BC (invoice initial, payment initial, application to invoice, application to payment) so cash prepayments reconcile automatically
  - Each `PostedSalesInvoice` keeps a back-reference to the originating prepayment, allowing the **View Posted Prepayment Invoices** action/factbox to list every invoice created for the document
  - Header fields `posted_at`, `posted_by`, and `posted_transaction_no` track who posted the prepayment and link out to the GL batch if auditing is required

- **Frontend Workspace (Phase 1)**
  - Added `/app/prepayments` dashboard so branch operators can create/edit documents without Django admin access
  - Detail view mirrors admin lifecycle fields, supports new installments, posting preview, and partial posting actions
  - Navigation + route protection use module code `prepayments` and page name `Prepayments` (Page ID 11001). Update Role Centers and permission sets accordingly so the workspace is visible to the right personas.
