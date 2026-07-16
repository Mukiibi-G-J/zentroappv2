"""
Map Page engine page names to subscription module identifiers for nav filtering.
"""

from __future__ import annotations

from functools import lru_cache

# Pages that are always visible regardless of enabled_modules.
_ALWAYS_VISIBLE_PAGE_NAMES = frozenset(
    {
        "",
        "UserSettingsCard",
        "UserSettingsList",
        "CompanyCard",
        "CompanySubscriptionCard",
        "CompanyBillingHistoryList",
        "CompanyPaymentMethodList",
    }
)

# Explicit overrides where prefix matching would be wrong.
_PAGE_NAME_MODULE_OVERRIDES: dict[str, str | None] = {
    "UserSettingsCard": None,
    "UserSettingsList": "user_management",
    "UserSetupList": "user_management",
    "UsersList": "user_management",
    "UsersCard": "user_management",
    "CompanyCard": None,
    "CompanySubscriptionCard": None,
    "CompanyBillingHistoryList": None,
    "CompanyPaymentMethodList": None,
    "NoSeriesList": "user_management",
    "DimensionList": "financials",
    "UnitOfMeasureList": "inventory",
    "InventorySetupCard": "inventory",
    "ManufacturingSetupCard": "manufacturing",
    "GeneralLedgerSetupCard": "financials",
    "PaymentMethodList": "payments",
    "CashReceiptJournal": "payments",
    "PaymentJournalList": "payments",
    "PaymentCard": "payments",
    "ExpenseList": "expenses",
    "ExpenseCard": "expenses",
    "BankAccountList": "bank_accounts",
    "BankAccountCard": "bank_accounts",
    "GLAccountList": "financials",
    "GLAccountCard": "financials",
    "GeneralJournal": "financials",
    "CustomerList": "customers",
    "CustomerCard": "customers",
    "VendorList": "purchases",
    "VendorCard": "purchases",
    "ItemList": "inventory",
    "ItemCard": "inventory",
    "InventoryAdjustmentJournalList": "inventory",
    "OpeningBalanceJournalList": "inventory",
    "SalesPOS": "sales",
    "SalesOrderList": "sales",
    "SalesInvoiceList": "sales",
    "PostedSalesInvoiceList": "sales",
    "PostedSalesInvoice": "sales",
    "PurchaseInvoiceList": "purchases",
    "PostedPurchaseInvoiceList": "purchases",
    "PostedPurchaseInvoice": "purchases",
    "FloorList": "restaurant",
    "TableList": "restaurant",
    "ReservationList": "restaurant",
    "MenuCategoryList": "restaurant",
    "MenuItemList": "restaurant",
    "MenuList": "restaurant",
    "MenuBuilder": "restaurant",
    "KitchenDisplay": "restaurant",
    "KitchenDisplayList": "restaurant",
    "RestaurantPOS": "restaurant",
    "RestaurantOrderList": "restaurant",
    "RestaurantManagerRC": "restaurant",
    "RestaurantFOHRC": "restaurant",
    "RestaurantKitchenRC": "restaurant",
}

_PREFIX_MODULE_HINTS: tuple[tuple[str, str], ...] = (
    ("Restaurant", "restaurant"),
    ("Hotel", "hotel"),
    ("Manufacturing", "manufacturing"),
    ("Production", "manufacturing"),
    ("Loan", "loans"),
    ("Resource", "resources"),
    ("StockTaking", "stock_taking"),
    ("ItemTracking", "item_tracking"),
    ("Efris", "efris"),
    ("Sales", "sales"),
    ("Customer", "customers"),
    ("Vendor", "purchases"),
    ("Purchase", "purchases"),
    ("Item", "inventory"),
    ("Inventory", "inventory"),
    ("Expense", "expenses"),
    ("Payment", "payments"),
    ("Bank", "bank_accounts"),
    ("GL", "financials"),
    ("GeneralJournal", "financials"),
    ("Report", "reports"),
    ("User", "user_management"),
)


def _module_enabled(module_id: str | None, enabled_modules: set[str]) -> bool:
    if not module_id:
        return True
    if module_id in enabled_modules:
        return True
    if module_id == "sales" and "pos" in enabled_modules:
        return True
    return False


def resolve_module_for_page_name(page_name: str) -> str | None:
    """Return module identifier required for a page, or None if always visible."""
    name = (page_name or "").strip()
    if not name:
        return None
    if name in _ALWAYS_VISIBLE_PAGE_NAMES:
        return None
    if name in _PAGE_NAME_MODULE_OVERRIDES:
        return _PAGE_NAME_MODULE_OVERRIDES[name]

    for prefix, module_id in _PREFIX_MODULE_HINTS:
        if name.startswith(prefix):
            return module_id
    return None


@lru_cache(maxsize=512)
def _page_source_table(page_name: str) -> str:
    if not page_name:
        return ""
    try:
        from pages.models import Page

        return (
            Page.objects.filter(name=page_name)
            .values_list("source_table", flat=True)
            .first()
            or ""
        )
    except Exception:
        return ""


_SOURCE_TABLE_MODULE: dict[str, str] = {
    "Expense": "expenses",
    "PaymentJournal": "payments",
    "Payment": "payments",
    "BankAccount": "bank_accounts",
    "GLAccount": "financials",
    "Customer": "customers",
    "Vendor": "purchases",
    "Item": "inventory",
    "SalesOrder": "sales",
    "SalesInvoice": "sales",
    "PurchaseInvoice": "purchases",
    "Loan": "loans",
    "Resource": "resources",
    "Restaurant": "restaurant",
    "Hotel": "hotel",
    "Floor": "restaurant",
    "Table": "restaurant",
    "Reservation": "restaurant",
    "MenuCategory": "restaurant",
    "MenuItem": "restaurant",
    "Menu": "restaurant",
    "RestaurantOrder": "restaurant",
    "RestaurantOrderItem": "restaurant",
}


def resolve_module_for_nav_target(page_name: str) -> str | None:
    """Resolve module for a nav item target page name."""
    explicit = resolve_module_for_page_name(page_name)
    if explicit is not None or not (page_name or "").strip():
        return explicit

    source_table = _page_source_table(page_name)
    if source_table in _SOURCE_TABLE_MODULE:
        return _SOURCE_TABLE_MODULE[source_table]
    return None


def filter_nav_items_by_enabled_modules(
    nav_items: list[dict],
    enabled_modules: list[str] | None,
) -> list[dict]:
    """Drop nav items whose target page belongs to a disabled module."""
    enabled = set(enabled_modules or [])
    if not enabled:
        return nav_items

    filtered: list[dict] = []
    for item in nav_items:
        target = (item.get("targetPageName") or "").strip()
        module_id = resolve_module_for_nav_target(target)
        if _module_enabled(module_id, enabled):
            filtered.append(item)
    return filtered


def filter_application_profiles_by_enabled_modules(qs, enabled_modules: list[str] | None):
    """
    Restrict ApplicationProfile choices to profiles whose Role Centre page
    belongs to an enabled subscription module (e.g. hide REST-* when restaurant
    is disabled).
    """
    enabled = set(enabled_modules or [])
    if not enabled:
        return qs

    allowed_ids: list[int] = []
    for profile in qs.select_related("role_centre_page"):
        rc_name = getattr(profile.role_centre_page, "name", "") or ""
        module_id = resolve_module_for_page_name(rc_name)
        if _module_enabled(module_id, enabled):
            allowed_ids.append(profile.pk)

    if not allowed_ids:
        return qs.none()
    return qs.filter(pk__in=allowed_ids)
