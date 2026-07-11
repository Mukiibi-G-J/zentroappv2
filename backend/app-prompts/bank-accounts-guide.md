# Bank Accounts Guide

## Overview

How to build and use Bank Account Management and Ledger Entries across frontend (`zentro-frontend/src/views/bankAccounts`) and backend (`zentro-backend/bank_account`). Covers permissions, endpoints, payloads, validation, and UI behaviors.

## Permissions & Navigation

- **Page Object IDs** (Layer 2): `11001` Bank Account Management, `11002` Bank Account Ledger Entries.
- **Permission sets** (`permissions/management/commands/setup_page_permissions.py`):
  - `BANK_ACCOUNT_FULL` (RIMD), `BANK_ACCOUNT_BASIC` (RI for mgmt, R for ledger), `BANK_ACCOUNT_VIEW_ONLY` (R).
- **Routes** (`populate_page_objects.py`):
  - `/app/bank-accounts` (management)
  - `/app/bank-accounts/ledger-entries`
- Frontend: `usePermissions` checks `pageName` to toggle create/edit/delete; ledger is read-only.

## Backend API (omit `/api/` on frontend services)

- Management (ModelViewSet, `PAGE_OBJECT_ID=11001`):
  - `GET /bank-accounts/` list with `search`, `page`, `page_size`, `ordering`.
  - `POST /bank-accounts/` create.
  - `GET /bank-accounts/<no>/` retrieve.
  - `PATCH /bank-accounts/<no>/` update.
  - `DELETE /bank-accounts/<no>/` delete.
- Ledger entries (ReadOnlyModelViewSet, `PAGE_OBJECT_ID=11002`):
  - `GET /bank-account-ledger-entries/` list with filters `bank_account_no`, `search`, `document_type`, `start_date`, `end_date`, `ordering`.
  - `GET /bank-account-ledger-entries/<entry_no>/` detail.
- Posting groups:
  - `GET /bank-account-posting-groups/` list (supports `search`, pagination).
- Permissions enforced per action; `_deny` returns 403 with `reason`.
- Page-size default 10, max 100.

## Validation & Business Rules

- BankAccount (model `bank_account/models.py`):
  - Primary key `no` (required).
  - `bank_account_posting_group` optional but needed for correct posting; stored by code.
  - `min_balance` default 0; balances are computed from ledger entries (`debit_amount`, `credit_amount`, `balance` are read-only FlowFields).
- BankAccountLedgerEntry (read-only):
  - Exposes posting, document, amounts, dimensions, user info, reversal fields; not writable via API.
- Error handling:
  - Create wraps ValidationError into 400 with message dict.
- Seeds:
  - Number series/GL alignment via `seed_mobile_money_bank_accounts` (if applicable) and posting groups; check existing seed commands in `bank_account/management/commands`.

## Frontend (BankAccounts.tsx)

- **Listing**: `BaseTable` driven by Redux slice `bankAccount`; pagination/sort/search. Data from `BankAccountServices.getBankAccounts`.
- **Permissions**: `canCreate/canEdit/canDelete` on `pageName = "Bank Account Management"`.
- **Create/Edit modal**: `BaseCard` + `Formik` (`BankAccountForm`). Initial values empty; edit pre-fills and clears touched.
- **Actions**:
  - Create -> `createBankAccount`.
  - Edit -> `updateBankAccount`.
  - Delete -> `deleteBankAccount` then refetch list.
- **Columns**: `useBankAccountColumns` shows no/name/posting group/balance, etc.
- **Posting groups dropdown**: fetched via `BankAccountServices.getBankAccountPostingGroups()` (page_size=1000).
- **Ledger Entries page**: `BankAccountLedgerEntries.tsx` uses `getBankAccountLedgerEntries` with filters (account, type, date range, search, ordering); read-only table.
- **API URL rule**: services use `/bank-accounts/` and `/bank-account-ledger-entries/` (BaseService prepends `/api/`).

## Quick payload examples

- Create bank account (frontend → backend):
  ```json
  {
    "no": "001",
    "name": "Main Bank UGX",
    "address": "Kampala",
    "contact": "0123-456",
    "bank_account_no": "123456789",
    "bank_branch_no": "001",
    "bank_account_posting_group": "BANK"
  }
  ```
- List ledger entries with filters:
  ```
  GET /bank-account-ledger-entries/?bank_account_no=001&start_date=2025-01-01&end_date=2025-01-31&ordering=-posting_date
  ```

## References

- Backend: `zentro-backend/bank_account/models.py`, `serializers.py`, `views.py`, `urls.py`, seeds in `bank_account/management/commands/`.
- Frontend: `zentro-frontend/src/views/bankAccounts/BankAccounts.tsx`, `BankAccountLedgerEntries.tsx`, components under `components/`, columns `constants/bankAccountColumns.tsx`, services `src/services/BankAccountServices.ts`.



