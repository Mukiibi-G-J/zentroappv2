"""
Zentro page IDs for the page engine and permissions.

Rule: PageId == ObjectId == stable Zentro page ID (same number everywhere).

Bands align with classic ZentroApp ``populate_page_objects`` ranges so old
permission sets / mental model stay familiar:

  10000–10099  Sales
  10100–10199  Customers
  10200–10299  Items / inventory
  10300–10399  Purchases / vendors
  10400–10499  Payments
  10500–10599  Financials / G/L
  10600–10699  Bank / dimensions / setup extras
  10700–10799  Restaurant
  10800–10899  User management
  10900–10999  Company / manufacturing / reports
  12000–12999  Role Centres & other V2-only shells

Tables / ledger permissions stay in the low table-object ranges (separate system).
"""

from __future__ import annotations

# Lowest ID used for page-engine pages (keeps clear of table object IDs).
ZENTRO_PAGE_ID_START = 10_000

# page_engine Page.name → (zentro_page_id, module_code)
ZENTRO_PAGE_REGISTRY: dict[str, tuple[int, str]] = {
    # ── Sales (10000) ──────────────────────────────────────────────────────────
    'SalesPOS': (10002, 'sales'),
    'SalesInvoiceList': (10003, 'sales'),
    'PostedSalesInvoiceList': (10004, 'sales'),
    'PostedSalesInvoice': (10014, 'sales'),
    'PostedSalesInvoiceSubform': (10015, 'sales'),
    'SalesOrderList': (10005, 'sales'),
    'SalesOrder': (10006, 'sales'),
    'SalesOrderSubform': (10007, 'sales'),
    'SalesInvoice': (10008, 'sales'),
    'SalesInvoiceSubform': (10009, 'sales'),
    'SalesCreditMemoList': (10016, 'sales'),
    'SalesCreditMemo': (10017, 'sales'),
    'SalesCreditMemoSubform': (10018, 'sales'),
    'PostedSalesCreditMemoList': (10019, 'sales'),
    'CustomerAppliedEntriesList': (10010, 'sales'),
    'ApplyCustomerEntries': (10011, 'sales'),
    'SalesManagerRC': (10012, 'sales'),
    'CashierRC': (10013, 'sales'),
    # ── Customers (10100) ──────────────────────────────────────────────────────
    'CustomerList': (10101, 'customers'),
    'CustomerCard': (10102, 'customers'),
    'CustomerLedgerEntryList': (10103, 'customers'),
    # ── Items / inventory (10200) ──────────────────────────────────────────────
    'ItemList': (10201, 'inventory'),
    'ItemCard': (10202, 'inventory'),
    'InventoryAdjustmentJournalList': (10203, 'inventory'),
    'OpeningBalanceJournalList': (10204, 'inventory'),
    'ItemLedgerEntryList': (10205, 'inventory'),
    'ItemUnitOfMeasureList': (10206, 'inventory'),
    'ItemUnitOfMeasureSubform': (10207, 'inventory'),
    'UnitOfMeasureList': (10208, 'inventory'),
    'InventorySetupCard': (10209, 'inventory'),
    'ItemJournalCard': (10210, 'inventory'),
    'ItemTrackingLinesWorksheet': (10211, 'inventory'),
    'PostedItemTrackingLines': (10212, 'inventory'),
    'WarehouseRC': (10213, 'inventory'),
    'PharmacistRC': (10214, 'inventory'),
    'PostedInventoryAdjustmentList': (10215, 'inventory'),
    # ── Purchases / vendors (10300) ────────────────────────────────────────────
    'PurchaseInvoiceList': (10301, 'purchases'),
    'PostedPurchaseInvoiceList': (10302, 'purchases'),
    'VendorList': (10303, 'purchases'),
    'VendorCard': (10304, 'purchases'),
    'PurchaseInvoice': (10305, 'purchases'),
    'PurchaseInvoiceSubform': (10306, 'purchases'),
    'PostedPurchaseInvoice': (10307, 'purchases'),
    'PostedPurchaseInvoiceSubform': (10308, 'purchases'),
    'VendorLedgerEntryList': (10309, 'purchases'),
    'VendorAppliedEntriesList': (10310, 'purchases'),
    'ApplyVendorEntries': (10311, 'purchases'),
    # ── Payments (10400) ───────────────────────────────────────────────────────
    'PaymentJournalList': (10401, 'payments'),
    'PaymentJournalCard': (10402, 'payments'),
    'CashReceiptJournal': (10403, 'payments'),
    'CashReceiptJournalBatchList': (10404, 'payments'),
    'PaymentMethodList': (10405, 'payments'),
    # ── Financials (10500) ─────────────────────────────────────────────────────
    'GLAccountList': (10501, 'financials'),
    'GLAccountCard': (10502, 'financials'),
    'GeneralLedgerEntryList': (10503, 'financials'),
    'GeneralLedgerSetupCard': (10504, 'financials'),
    'GeneralJournal': (10505, 'financials'),
    'GeneralJournalBatchList': (10506, 'financials'),
    'GeneralPostingSetupList': (10507, 'financials'),
    'GeneralBusinessPostingGroupList': (10508, 'financials'),
    'GeneralProductPostingGroupList': (10509, 'financials'),
    'FinancialReportList': (10510, 'financials'),
    'FinancialReportOverview': (10511, 'financials'),
    'FinancialReportRowGroupList': (10512, 'financials'),
    'FinancialReportRowDefinition': (10513, 'financials'),
    'FinancialReportRowGroupCard': (10514, 'financials'),
    'FinancialReportColumnGroupList': (10515, 'financials'),
    'FinancialReportColumnGroupCard': (10516, 'financials'),
    'FinancialReportCard': (10517, 'financials'),
    'AccountingRC': (10518, 'financials'),
    'ExpenseList': (10520, 'expenses'),
    'ExpenseCard': (10521, 'expenses'),
    # ── Bank / dimensions / no. series (10600) ────────────────────────────────
    'BankAccountList': (10601, 'bankAccount'),
    'BankAccountCard': (10602, 'bankAccount'),
    'BankAccountLedgerEntryList': (10603, 'bankAccount'),
    'DimensionList': (10610, 'financials'),
    'DimensionCard': (10611, 'financials'),
    'DimensionValueList': (10612, 'financials'),
    'DimensionValueCard': (10613, 'financials'),
    'NoSeriesList': (10620, 'setup'),
    'NoSeriesCard': (10621, 'setup'),
    # ── Restaurant (10700) ─────────────────────────────────────────────────────
    'RestaurantOrder': (10710, 'restaurant'),
    'RestaurantOrderList': (10711, 'restaurant'),
    'KitchenDisplay': (10712, 'restaurant'),
    'KitchenDisplayList': (10713, 'restaurant'),
    'RestaurantPOS': (10714, 'restaurant'),
    'MenuBuilder': (10715, 'restaurant'),
    'TableList': (10716, 'restaurant'),
    'FloorList': (10717, 'restaurant'),
    'ReservationList': (10718, 'restaurant'),
    'MenuItemList': (10719, 'restaurant'),
    'MenuCategoryList': (10720, 'restaurant'),
    'MenuList': (10721, 'restaurant'),
    'RestaurantManagerRC': (10722, 'restaurant'),
    # ── User management (10800) ────────────────────────────────────────────────
    'UserSetupList': (10801, 'user_management'),
    'UsersList': (10802, 'user_management'),
    'UsersCard': (10803, 'user_management'),
    'UserSettingsList': (10804, 'user_management'),
    'UserSettingsCard': (10805, 'user_management'),
    'PermissionSetsList': (10806, 'user_management'),
    'PermissionSetsCard': (10807, 'user_management'),
    'UserGroupsList': (10808, 'user_management'),
    'UserGroupsCard': (10809, 'user_management'),
    # ── Company / manufacturing / reports (10900) ──────────────────────────────
    'CompanyCard': (10901, 'company'),
    'CompanySubscriptionCard': (10902, 'company'),
    'CompanyBillingHistoryList': (10903, 'company'),
    'CompanyPaymentMethodList': (10904, 'company'),
    'ManufacturingSetupCard': (10910, 'manufacturing'),
    'ExpiryReport': (10920, 'reports'),
    'InventoryTransactionDetailReport': (10921, 'reports'),
    # ── Role Centres / general shells (12000) ──────────────────────────────────
    'BusinessManagerRC': (12001, 'general'),
    'OperationsManagerRC': (12002, 'general'),
}

# Backward-compatible aliases (older imports)
BC_PAGE_REGISTRY = ZENTRO_PAGE_REGISTRY
ZENTRO_CUSTOM_PAGE_REGISTRY: dict[str, tuple[int, str]] = {}
ZENTRO_CUSTOM_PAGE_ID_START = 12_000


def zentro_page_id(page_id: int) -> int:
    if page_id < ZENTRO_PAGE_ID_START:
        raise ValueError(f'Zentro page ID must be >= {ZENTRO_PAGE_ID_START}, got {page_id}')
    return page_id


# Legacy aliases kept so existing imports do not break
bc_page_object_id = zentro_page_id


def module_for_page_name(page_name: str) -> str | None:
    if page_name in ZENTRO_PAGE_REGISTRY:
        return ZENTRO_PAGE_REGISTRY[page_name][1]
    return None


def resolve_page_object_id(page_name: str) -> int | None:
    """Stable Zentro page ID (used as both PageId and ObjectId)."""
    if page_name in ZENTRO_PAGE_REGISTRY:
        return ZENTRO_PAGE_REGISTRY[page_name][0]
    return None


def resolve_zentro_page_id(page_name: str) -> int | None:
    return resolve_page_object_id(page_name)


def all_registered_page_names() -> list[str]:
    return sorted(ZENTRO_PAGE_REGISTRY)
