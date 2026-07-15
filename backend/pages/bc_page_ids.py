"""
Business Central–aligned page object IDs for Zentro permissions.

BC permission sets reference pages by type + ID (see AL ``permissionset`` blocks).
Zentro uses the **same numeric IDs as BC** (e.g. page 31 Item List → object_id 31).

Zentro-only pages (no BC counterpart) use IDs from ``ZENTRO_CUSTOM_PAGE_ID_START`` (50 000+),
matching BC partner-extension ranges.
"""

from __future__ import annotations

ZENTRO_CUSTOM_PAGE_ID_START = 50_000

# page_engine Page.name → (bc_page_id, module_code)
BC_PAGE_REGISTRY: dict[str, tuple[int, str]] = {
    # ── Financials / G/L ─────────────────────────────────────────────────────
    'GLAccountCard': (15, 'financials'),
    'GLAccountList': (16, 'financials'),
    'GeneralLedgerEntryList': (20, 'financials'),
    'GeneralLedgerSetupCard': (118, 'financials'),
    'GeneralPostingSetupList': (252, 'financials'),
    'GeneralBusinessPostingGroupList': (253, 'financials'),
    'GeneralProductPostingGroupList': (254, 'financials'),
    'FinancialReportList': (108, 'financials'),
    'FinancialReportOverview': (490, 'financials'),
    'FinancialReportRowGroupList': (103, 'financials'),
    'FinancialReportRowDefinition': (104, 'financials'),
    'FinancialReportRowGroupCard': (50001, 'financials'),
    'FinancialReportColumnGroupList': (488, 'financials'),
    'FinancialReportColumnGroupCard': (489, 'financials'),
    # ── Sales — Customer ───────────────────────────────────────────────────────
    'CustomerCard': (21, 'customers'),
    'CustomerList': (22, 'customers'),
    'CustomerLedgerEntryList': (25, 'customers'),
    'CustomerAppliedEntriesList': (232, 'sales'),
    # ── Purchases — Vendor ─────────────────────────────────────────────────────
    'VendorCard': (26, 'purchases'),
    'VendorList': (27, 'purchases'),
    'VendorLedgerEntryList': (29, 'purchases'),
    'VendorAppliedEntriesList': (233, 'purchases'),
    # ── Inventory — Item ───────────────────────────────────────────────────────
    'ItemCard': (30, 'inventory'),
    'ItemList': (31, 'inventory'),
    'ItemLedgerEntryList': (38, 'inventory'),
    'ItemUnitOfMeasureList': (5404, 'inventory'),
    'InventorySetupCard': (1407, 'inventory'),
    'UnitOfMeasureList': (209, 'inventory'),
    # ── Journals ───────────────────────────────────────────────────────────────
    'GeneralJournal': (39, 'financials'),
    'GeneralJournalBatchList': (251, 'financials'),
    'CashReceiptJournal': (255, 'payments'),
    'PaymentJournalCard': (256, 'payments'),
    'PaymentJournalList': (257, 'payments'),
    # ── Sales documents ────────────────────────────────────────────────────────
    'SalesOrder': (42, 'sales'),
    'SalesOrderSubform': (46, 'sales'),
    'SalesOrderList': (9305, 'sales'),
    'SalesInvoice': (43, 'sales'),
    'SalesInvoiceSubform': (47, 'sales'),
    'SalesInvoiceList': (9301, 'sales'),
    'PostedSalesInvoiceList': (9302, 'sales'),
    # ── Purchase documents ─────────────────────────────────────────────────────
    'PurchaseInvoice': (51, 'purchases'),
    'PurchaseInvoiceSubform': (52, 'purchases'),
    'PurchaseInvoiceList': (9308, 'purchases'),
    'PostedPurchaseInvoiceList': (146, 'purchases'),
    'PostedPurchaseInvoice': (138, 'purchases'),
    'PostedPurchaseInvoiceSubform': (139, 'purchases'),
    'PostedItemTrackingLines': (6511, 'inventory'),
    # ── Bank ───────────────────────────────────────────────────────────────────
    'BankAccountCard': (371, 'bankAccount'),
    'BankAccountList': (372, 'bankAccount'),
    'BankAccountLedgerEntryList': (374, 'bankAccount'),
    # ── Payments setup ─────────────────────────────────────────────────────────
    'PaymentMethodList': (427, 'payments'),
    # ── Dimensions ─────────────────────────────────────────────────────────────
    'DimensionList': (536, 'financials'),
    'DimensionCard': (537, 'financials'),
    'DimensionValueList': (539, 'financials'),
    'DimensionValueCard': (540, 'financials'),
    # ── Expenses ───────────────────────────────────────────────────────────────
    'ExpenseList': (5802, 'expenses'),
    'ExpenseCard': (5803, 'expenses'),
    # ── Item journals ──────────────────────────────────────────────────────────
    'ItemJournalCard': (40, 'inventory'),
    'InventoryAdjustmentJournalList': (262, 'inventory'),
    'UserSetupList': (119, 'user_management'),
    'UsersCard': (9800, 'user_management'),
    'UsersList': (9801, 'user_management'),
    'UserSettingsList': (9176, 'user_management'),
    'UserSettingsCard': (9175, 'user_management'),
    'PermissionSetsList': (9042, 'user_management'),
    'PermissionSetsCard': (9043, 'user_management'),
    'UserGroupsList': (9830, 'user_management'),
    'UserGroupsCard': (9831, 'user_management'),
    # ── Setup ──────────────────────────────────────────────────────────────────
    'NoSeriesList': (456, 'setup'),
    'NoSeriesCard': (457, 'setup'),
    'CompanyCard': (79, 'company'),
    'ManufacturingSetupCard': (99000858, 'manufacturing'),
}

# Zentro-only pages: (object_id, module) — 50 000+ partner-extension range
ZENTRO_CUSTOM_PAGE_REGISTRY: dict[str, tuple[int, str]] = {
    'SalesPOS': (50_003, 'sales'),
    'CashReceiptJournalBatchList': (50_004, 'payments'),
    'ApplyVendorEntries': (50_010, 'purchases'),
    'ApplyCustomerEntries': (50_011, 'sales'),
    'ItemTrackingLinesWorksheet': (50_012, 'inventory'),
    'FinancialReportCard': (50_013, 'financials'),
    'CompanySubscriptionCard': (50_020, 'company'),
    'CompanyBillingHistoryList': (50_021, 'company'),
    'CompanyPaymentMethodList': (50_022, 'company'),
    'OpeningBalanceJournalList': (50_030, 'inventory'),
    'RestaurantOrder': (50_100, 'restaurant'),
    'RestaurantOrderList': (50_101, 'restaurant'),
    'KitchenDisplay': (50_102, 'restaurant'),
    'KitchenDisplayList': (50_103, 'restaurant'),
    'RestaurantPOS': (50_104, 'restaurant'),
    'MenuBuilder': (50_105, 'restaurant'),
    'TableList': (50_106, 'restaurant'),
    'FloorList': (50_107, 'restaurant'),
    'ReservationList': (50_108, 'restaurant'),
    'MenuItemList': (50_109, 'restaurant'),
    'MenuCategoryList': (50_110, 'restaurant'),
    'MenuList': (50_111, 'restaurant'),
    'ExpiryReport': (50_200, 'reports'),
    'InventoryTransactionDetailReport': (50_201, 'reports'),
    'BusinessManagerRC': (50_300, 'general'),
    'SalesManagerRC': (50_301, 'sales'),
    'AccountingRC': (50_302, 'financials'),
    'WarehouseRC': (50_303, 'inventory'),
    'CashierRC': (50_304, 'sales'),
    'RestaurantManagerRC': (50_305, 'restaurant'),
    'OperationsManagerRC': (50_306, 'general'),
    'PharmacistRC': (50_307, 'inventory'),
}


def bc_page_object_id(bc_page_id: int) -> int:
    """Return the BC page ID unchanged (same as Business Central)."""
    if bc_page_id <= 0:
        raise ValueError(f'BC page ID must be positive, got {bc_page_id}')
    return bc_page_id


# Backward-compatible alias
zentro_page_object_id = bc_page_object_id


def module_for_page_name(page_name: str) -> str | None:
    if page_name in BC_PAGE_REGISTRY:
        return BC_PAGE_REGISTRY[page_name][1]
    if page_name in ZENTRO_CUSTOM_PAGE_REGISTRY:
        return ZENTRO_CUSTOM_PAGE_REGISTRY[page_name][1]
    return None


def resolve_page_object_id(page_name: str) -> int | None:
    """Stable permission object ID for a page-engine name (BC ID or 50 000+ custom)."""
    if page_name in BC_PAGE_REGISTRY:
        return BC_PAGE_REGISTRY[page_name][0]
    if page_name in ZENTRO_CUSTOM_PAGE_REGISTRY:
        return ZENTRO_CUSTOM_PAGE_REGISTRY[page_name][0]
    return None


def all_registered_page_names() -> list[str]:
    return sorted(set(BC_PAGE_REGISTRY) | set(ZENTRO_CUSTOM_PAGE_REGISTRY))
