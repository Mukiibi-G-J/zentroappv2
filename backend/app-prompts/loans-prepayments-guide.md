# Loans & Prepayments Guide

## Overview

This guide covers two finance workspaces:
- **Loans**: register loans, post them to GL, and capture repayments.
- **Prepayments**: customer deposits with card + lines flow, posting to sales and final invoices.

Use it when working in `zentro-frontend/src/views/loans/Loans.tsx` and `zentro-frontend/src/views/prepayments/Prepayments.tsx` or when adding backend support in `zentro-backend/loans` and `zentro-backend/prepayment`.

## Permissions & Navigation

- **Page Object IDs**
  - Loans: `10806` Loan Registration, `10807` Loan Repayment (history pages 10808/10809).
  - Prepayments: `11001` Prepayments.
- **Permission sets** (see `permissions/management/commands/setup_page_permissions.py`)
  - Loans: `LOANS_FULL` (RIMD), `LOANS_BASIC` (RI), `LOANS_VIEW_ONLY` (R).
  - Prepayments: `PREPAYMENTS_FULL` (RIMD), `PREPAYMENTS_VIEW_ONLY` (R).
- **Routes**
  - Loans: `/app/loans`, `/app/loans/repayments`.
  - Prepayments: `/app/prepayments`.
- Frontend checks `usePermissions` + `pageName` to hide create/edit/delete/post buttons.

## Loans Module (Loan Registration + Repayments)

### Backend API

- Base URLs (prefixed with `/api/` by backend; omit `/api/` on frontend services):
  - Loans CRUD: `GET/POST /loans/loans/`, `GET/PATCH/DELETE /loans/loans/<id>/`.
  - Loan posting: `GET /loans/loans/<id>/preview_posting/`, `POST /loans/loans/<id>/post_loan/`.
  - Repayments CRUD: `GET/POST /loans/loan-repayments/`, `GET/PATCH/DELETE /loans/loan-repayments/<id>/`.
  - Repayment posting: `GET /loans/loan-repayments/<id>/preview_posting/`, `POST /loans/loan-repayments/<id>/post_repayment/`.
- Permissions enforced per action using `PAGE_OBJECT_ID` (`10806` loans, `10807` repayments).
- Number series:
  - Loans: uses `JournalSetup` with `JournalType.LOAN`; fallback `LOAN-YYYYMMDDHHMMSS`.
  - Repayments: uses `NoSeries` code `LOANREP`; fallback `LOANREP-YYYYMMDDHHMMSS`.
  - Seed helpers: `python manage.py tenant_command seed_loan_no_series --schema=<tenant>` and `seed_loan_accounts` for GL accounts (`5110`, `5320`).
- Validation highlights:
  - Positive `loan_amount`, `repayment_period` > 0, `interest_rate` 0–100.
  - `repayment_account="Bank/Mobile Money"` requires `bank_account` when posting; with `Cash`, `bank_account` must be empty.
  - Repayments: `amount_paid` > 0, `payment_date` cannot precede `loan.disbursement_date`; same bank rule as above.
- Posting:
  - Preview builds journal lines via `LoanPostingProcessor` / `LoanRepaymentPostingProcessor`.
  - Posting wraps in transaction and finalizes via `LoanPostingFinalPoster` / `LoanRepaymentPostingFinalPoster`.
  - Sets `posted=true`, `posted_date`, `posted_by`, `status="Posted"`.

### Frontend (Loans.tsx)

- **Listing**
  - `BaseTable` with pagination, search debounce (500ms), ordering, filters (loan type, status, posted, date range, lender, repayment account).
  - Defaults to status `Open`.
  - Data source: `LoanServices.getLoans`.
- **Create/Edit modal**
  - `Formik` form with `AutoSaveField` per input; allows partial PATCH while typing.
  - Initial minimal create allowed with just `lenderName`; backend fills safe defaults.
  - Fields: loanType, lenderName, loanAmount, disbursementDate, interestRate, repaymentPeriod, repaymentAccount, bankAccount (required for Bank/Mobile), purpose, status.
  - Bank accounts fetched via `BankAccountServices.getBankAccounts` (page_size=1000).
- **Actions**
  - Create button guarded by `canCreate("Loan Registration")`.
  - Edit/delete guarded by `canEdit/canDelete`.
  - Delete uses `LoanServices.deleteLoan` then refreshes table.
  - Posting: confirm dialog → `LoanServices.previewPosting` (optional) → `postLoan`. Requires modify permission; once posted, buttons disabled.
- **State**
  - Redux slice `loans` for data, filters, tableData, currentRecord; reducer injected in component.
  - Keeps `tableDataRef` to avoid stale pagination on refresh.

### Loan Repayments (if building UI)

- Similar CRUD/post flow with endpoints above.
- Must select `loan` first; payment method/bank account follow same validation rules.
- Posting calculates principal/interest split and writes GL entries.

## Prepayments Module (Card + Lines)

### Backend API

- Endpoints (ModelViewSet in `prepayment/views.py`, `PAGE_OBJECT_ID=11001`):
  - List/create: `GET/POST /prepayments/`
  - Detail/update/delete: `GET/PATCH/DELETE /prepayments/<id>/`
  - Lines upsert/delete: `POST /prepayments/<id>/update_lines/` (mixed create/update/delete; see `prepayment_card_lines` rule).
  - Preview/post document: `POST /prepayments/<id>/preview/`, `POST /prepayments/<id>/post/` (payment method required, excludes NOT_PAID).
  - Installments: `POST /prepayments/<id>/installments/` (adds installment amount → deposit math).
  - Final invoice: `POST /prepayments/<id>/preview-final-invoice/`, `POST /prepayments/<id>/post-final-invoice/` (allows NOT_PAID method).
- Validation:
  - Delete blocked if posted invoices exist.
  - Lines normalize item/UOM (code, id, or object), recompute amounts, aggregate totals after save.
  - Totals recalculated via `Preayment.recalculate_totals`.

### Frontend (Prepayments.tsx)

- **Listing**
  - `BaseTable` with pagination/sort/search/status filter (All, Draft, Posted, Cancelled).
  - Data source: `PrepaymentService.fetchPrepayments`.
- **Card form**
  - `BaseCard` modal for create/edit; uses Redux store (`prepaymentsActions`) and Formik via `formikRef`.
  - Opens in create/edit modes; `handleCloseCard` resets state and refreshes list.
- **Lines**
  - `PrepaymentLinesSection` provides editable table (item & UOM pickers, autosave on blur).
  - Lines persisted with `update_lines` endpoint; camelCase accepted (unitPrice/unitOfMeasure).
  - Delete lines by sending `is_deleted: true`; backend hard-deletes before upsert.
- **Posting flows**
  - Posting prepayment requires selecting a payment method (filters out `NOT_PAID`); modal opens before posting.
  - `postPrepayment` returns posted invoice no + transaction no, closes card, refreshes list.
  - Final invoice path supports `NOT_PAID` and refreshes detail if open.
  - `preview` and `previewFinalInvoice` show ledger preview via `PostingPreviewModal`.
- **Installments**
  - `InstallmentModal` triggered via window event `openInstallmentModal`; posts amount to `/installments/`, updates deposit fields.
- **Payment methods**
  - Uses `PaymentMethodServices.getPaymentMethods`; preselects customer default when available.

### Payload shapes (frontend services)

- `updatePrepaymentLines(id, lines)`:
  ```json
  {
    "id": 10,
    "system_id": "<optional>",
    "lines": [
      { "id": 6807, "quantity": 2, "unit_price": 1000 },
      { "id": 6808, "is_deleted": true },
      { "item": "ITM-000001", "quantity": 1, "unit_price": 500 }
    ]
  }
  ```
- Posting with payment method:
  - Prepayment: `{ "payment_method_id": <id> }` (must not be NOT_PAID).
  - Final invoice: `{ "payment_method_id": <id or null> }` (NOT_PAID allowed).

## Quick references

- Frontend services:
  - `LoanServices` (CRUD, preview/post loan & repayment, bank accounts) in `zentro-frontend/src/services/LoanServices.ts`.
  - `PrepaymentService` (list/detail, update_lines, preview/post, final invoice, installments) in `zentro-frontend/src/services/PrepaymentService.ts`.
- Components:
  - Loans page: `zentro-frontend/src/views/loans/Loans.tsx`.
  - Prepayments page: `zentro-frontend/src/views/prepayments/Prepayments.tsx` plus `components/PrepaymentLinesSection.tsx`, `InstallmentModal`, `PostingPreviewModal`.
- Backend:
  - Loans models/serializers/views in `zentro-backend/loans/`.
  - Prepayments models/serializers/views in `zentro-backend/prepayment/`.





