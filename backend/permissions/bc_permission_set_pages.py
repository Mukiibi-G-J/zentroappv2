"""
BC-style permission set page lines.

Each entry is (permission_set_code, name, description, [(page_engine_name, 'RIMD'), ...]).
Page engine names must exist in ``pages.bc_page_ids`` and be synced to ``base.Objects``
via ``seed_pages`` / ``sync_page_permission_objects``.

Mirrors AL permissionset blocks that grant ``page "X" = X`` (execute) — Zentro uses
R/I/M/D on Page objects; list + card are separate lines like BC.
"""

from __future__ import annotations

# Format: (code, name, description, [(Page.name, permissions)])
BC_PERMISSION_SET_PAGES: list[tuple[str, str, str, list[tuple[str, str]]]] = [
    (
        'SALES_FULL',
        'Sales - Full Access',
        'Complete access to all sales features',
        [
            ('SalesPOS', 'RIMD'),
            ('SalesOrder', 'RIMD'),
            ('SalesOrderList', 'RIMD'),
            ('SalesInvoice', 'RIMD'),
            ('SalesInvoiceList', 'RIMD'),
            ('PostedSalesInvoiceList', 'R'),
            ('PaymentMethodList', 'R'),
        ],
    ),
    (
        'SALES_BASIC',
        'Sales - Basic Access',
        'Create sales and orders; view invoices',
        [
            ('SalesPOS', 'RI'),
            ('SalesOrder', 'RIM'),
            ('SalesOrderList', 'RIM'),
            ('SalesInvoice', 'R'),
            ('SalesInvoiceList', 'R'),
            ('PaymentMethodList', 'R'),
        ],
    ),
    (
        'SALES_HISTORY_ONLY',
        'Sales - History View Only',
        'Posted sales invoices only',
        [
            ('PostedSalesInvoiceList', 'R'),
        ],
    ),
    (
        'CUSTOMER_FULL',
        'Customers - Full Access',
        'Complete CRUD on customers',
        [
            ('CustomerList', 'RIMD'),
            ('CustomerCard', 'RIMD'),
            ('CustomerLedgerEntryList', 'R'),
        ],
    ),
    (
        'CUSTOMER_BASIC',
        'Customers - Basic Access',
        'View and create customers',
        [
            ('CustomerList', 'RI'),
            ('CustomerCard', 'RI'),
        ],
    ),
    (
        'CUSTOMER_VIEW_ONLY',
        'Customers - View Only',
        'Read-only customer access',
        [
            ('CustomerList', 'R'),
            ('CustomerCard', 'R'),
        ],
    ),
    (
        'ITEMS_FULL',
        'Items - Full Access',
        'Items, categories, inventory adjustment',
        [
            ('ItemList', 'RIMD'),
            ('ItemCard', 'RIMD'),
            ('ItemUnitOfMeasureList', 'RIMD'),
            ('InventoryAdjustmentJournalList', 'RIMD'),
            ('ItemLedgerEntryList', 'R'),
            ('UnitOfMeasureList', 'RIMD'),
        ],
    ),
    (
        'ITEMS_VIEW_ONLY',
        'Items - View Only',
        'Read-only items and ledger',
        [
            ('ItemList', 'R'),
            ('ItemCard', 'R'),
            ('ItemLedgerEntryList', 'R'),
        ],
    ),
    (
        'PURCHASES_FULL',
        'Purchases - Full Access',
        'Purchase invoices',
        [
            ('PurchaseInvoice', 'RIMD'),
            ('PurchaseInvoiceList', 'RIMD'),
            ('PostedPurchaseInvoice', 'R'),
            ('PostedPurchaseInvoiceList', 'R'),
            ('PostedItemTrackingLines', 'R'),
        ],
    ),
    (
        'PURCHASES_CREATE',
        'Purchases - Create Only',
        'Create purchase invoices',
        [
            ('PurchaseInvoice', 'RI'),
            ('PurchaseInvoiceList', 'R'),
            ('PostedPurchaseInvoice', 'R'),
            ('PostedPurchaseInvoiceList', 'R'),
        ],
    ),
    (
        'SUPPLIERS_FULL',
        'Suppliers - Full Access',
        'Vendors / suppliers',
        [
            ('VendorList', 'RIMD'),
            ('VendorCard', 'RIMD'),
            ('VendorLedgerEntryList', 'R'),
        ],
    ),
    (
        'SUPPLIERS_BASIC',
        'Suppliers - Basic Access',
        'View and create suppliers',
        [
            ('VendorList', 'RI'),
            ('VendorCard', 'RI'),
        ],
    ),
    (
        'SUPPLIERS_VIEW_ONLY',
        'Suppliers - View Only',
        'Read-only suppliers',
        [
            ('VendorList', 'R'),
            ('VendorCard', 'R'),
        ],
    ),
    (
        'PAYMENTS_FULL',
        'Payments - Full Access',
        'Payment journals and methods',
        [
            ('PaymentJournalList', 'RIMD'),
            ('PaymentJournalCard', 'RIMD'),
            ('CashReceiptJournal', 'RIMD'),
            ('PaymentMethodList', 'RIMD'),
            ('BankAccountLedgerEntryList', 'R'),
        ],
    ),
    (
        'PAYMENTS_VIEW_ONLY',
        'Payments - View Only',
        'Read payment journals and methods',
        [
            ('PaymentJournalList', 'R'),
            ('PaymentMethodList', 'R'),
        ],
    ),
    (
        'FINANCIALS_FULL',
        'Financials - Full Access',
        'Chart of accounts, dimensions, G/L setup',
        [
            ('GLAccountList', 'RIMD'),
            ('GLAccountCard', 'RIMD'),
            ('DimensionList', 'RIMD'),
            ('DimensionValueList', 'RIMD'),
            ('GeneralLedgerSetupCard', 'RIMD'),
            ('GeneralPostingSetupList', 'RIMD'),
            ('GeneralBusinessPostingGroupList', 'RIMD'),
            ('GeneralProductPostingGroupList', 'RIMD'),
            ('GeneralLedgerEntryList', 'R'),
            ('FinancialReportList', 'RIMD'),
            ('FinancialReportOverview', 'RIMD'),
            ('FinancialReportCard', 'RIMD'),
            ('FinancialReportRowGroupList', 'RIMD'),
            ('FinancialReportRowDefinition', 'RIMD'),
            ('FinancialReportRowGroupCard', 'RIMD'),
            ('FinancialReportColumnGroupList', 'RIMD'),
            ('FinancialReportColumnGroupCard', 'RIMD'),
        ],
    ),
    (
        'FINANCIALS_VIEW_ONLY',
        'Financials - View Only',
        'Read financial setup and COA',
        [
            ('GLAccountList', 'R'),
            ('GLAccountCard', 'R'),
            ('DimensionList', 'R'),
            ('DimensionValueList', 'R'),
            ('GeneralLedgerEntryList', 'R'),
            ('FinancialReportList', 'R'),
            ('FinancialReportOverview', 'R'),
            ('FinancialReportCard', 'R'),
            ('FinancialReportRowGroupList', 'R'),
            ('FinancialReportRowDefinition', 'R'),
            ('FinancialReportRowGroupCard', 'R'),
            ('FinancialReportColumnGroupList', 'R'),
            ('FinancialReportColumnGroupCard', 'R'),
        ],
    ),
    (
        'EXPENSES_FULL',
        'Expenses - Full Access',
        'Expense entries',
        [
            ('ExpenseList', 'RIMD'),
            ('ExpenseCard', 'RIMD'),
        ],
    ),
    (
        'EXPENSES_CREATE',
        'Expenses - Create Only',
        'Create expenses',
        [
            ('ExpenseList', 'RI'),
            ('ExpenseCard', 'RI'),
        ],
    ),
    (
        'BANK_ACCOUNT_FULL',
        'Bank Account - Full Access',
        'Bank accounts and ledger',
        [
            ('BankAccountList', 'RIMD'),
            ('BankAccountCard', 'RIMD'),
            ('BankAccountLedgerEntryList', 'RIMD'),
        ],
    ),
    (
        'BANK_ACCOUNT_BASIC',
        'Bank Account - Basic Access',
        'View and create bank accounts',
        [
            ('BankAccountList', 'RI'),
            ('BankAccountCard', 'RI'),
            ('BankAccountLedgerEntryList', 'R'),
        ],
    ),
    (
        'BANK_ACCOUNT_VIEW_ONLY',
        'Bank Account - View Only',
        'Read-only bank accounts',
        [
            ('BankAccountList', 'R'),
            ('BankAccountCard', 'R'),
            ('BankAccountLedgerEntryList', 'R'),
        ],
    ),
    (
        'USER_MGMT_FULL',
        'User Management - Full Access',
        'Users, groups, permission sets (BC admin)',
        [
            ('UsersList', 'RIMD'),
            ('UsersCard', 'RIMD'),
            ('UserSetupList', 'RIMD'),
            ('UserSettingsList', 'RIMD'),
            ('UserSettingsCard', 'RIMD'),
            ('UserGroupsList', 'RIMD'),
            ('UserGroupsCard', 'RIMD'),
            ('PermissionSetsList', 'RIMD'),
            ('PermissionSetsCard', 'RIMD'),
        ],
    ),
    (
        'USER_MGMT_BASIC',
        'User Management - Basic',
        'Manage users; view security setup',
        [
            ('UsersList', 'RIM'),
            ('UsersCard', 'RIM'),
            ('UserGroupsList', 'R'),
            ('PermissionSetsList', 'R'),
        ],
    ),
    (
        'USER_MGMT_VIEW_ONLY',
        'User Management - View Only',
        'Read-only user administration',
        [
            ('UsersList', 'R'),
            ('UsersCard', 'R'),
            ('UserGroupsList', 'R'),
            ('PermissionSetsList', 'R'),
        ],
    ),
    (
        'USER_GROUP_FULL',
        'User Groups - Full Access',
        'User groups',
        [
            ('UserGroupsList', 'RIMD'),
            ('UserGroupsCard', 'RIMD'),
        ],
    ),
    (
        'PERMISSION_SET_FULL',
        'Permission Sets - Full Access',
        'Permission sets and lines',
        [
            ('PermissionSetsList', 'RIMD'),
            ('PermissionSetsCard', 'RIMD'),
        ],
    ),
    (
        'COMPANY_FULL',
        'Company - Full Access',
        'Company information',
        [
            ('CompanyCard', 'RIMD'),
            ('CompanySubscriptionCard', 'RIMD'),
            ('CompanyBillingHistoryList', 'R'),
        ],
    ),
    (
        'COMPANY_VIEW_ONLY',
        'Company - View Only',
        'Read company information',
        [
            ('CompanyCard', 'R'),
            ('CompanyBillingHistoryList', 'R'),
        ],
    ),
    (
        'PROFILE_FULL',
        'Profile - Full Access',
        'User profile / personal settings',
        [
            ('UserSettingsList', 'RIMD'),
            ('UserSettingsCard', 'RIMD'),
        ],
    ),
    (
        'RESTAURANT_FULL',
        'Restaurant - Full Access',
        'Restaurant operations and POS',
        [
            ('RestaurantOrderList', 'RIMD'),
            ('RestaurantOrder', 'RIMD'),
            ('RestaurantPOS', 'RIMD'),
            ('KitchenDisplay', 'RIMD'),
            ('TableList', 'RIMD'),
            ('ReservationList', 'RIMD'),
            ('MenuItemList', 'RIMD'),
            ('MenuList', 'RIMD'),
            ('MenuBuilder', 'RIMD'),
        ],
    ),
    (
        'RESTAURANT_KITCHEN',
        'Restaurant - Kitchen / KDS',
        'Kitchen display',
        [
            ('KitchenDisplay', 'RIMD'),
            ('RestaurantOrderList', 'RIM'),
        ],
    ),
    (
        'RESTAURANT_FOH',
        'Restaurant - Front of house',
        'POS, tables, reservations, orders',
        [
            ('RestaurantPOS', 'RIMD'),
            ('RestaurantOrderList', 'RIMD'),
            ('TableList', 'RIMD'),
            ('ReservationList', 'RIMD'),
        ],
    ),
]
