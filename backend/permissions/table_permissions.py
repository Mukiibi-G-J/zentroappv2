"""
BC-style table data permissions for the page engine.

Maps page-engine ``source_table`` names to ``base.Objects`` (type Table) and
enforces R/I/M/D on data APIs. Page permissions remain the fallback when no
table object is registered or the table is not in the enforced set.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from django.apps import apps

if TYPE_CHECKING:
    from authentication.models import CustomUser

# Page-engine source_table values that enforce table-data permissions (opt-in rollout).
ENFORCED_SOURCE_TABLES = frozenset({
    'RestaurantOrder',
    'RestaurantOrderItem',
    'Table',
    'Reservation',
    'MenuItem',
    'MenuCategory',
    'Menu',
    'Floor',
    'Customer',
    'Item',
    'Vendor',
    'SalesOrder',
    'SalesOrderLine',
    'SalesInvoice',
    'SalesInvoiceLine',
    'PurchaseInvoice',
    'PurchaseInvoiceLine',
    'Expense',
    'PaymentJournal',
    'PaymentLine',
    'BankAccount',
    'G_LAccount',
})

# Fallback: if table check fails, allow when user has page permission on any alias.
SOURCE_TABLE_PAGE_ALIASES: dict[str, list[str]] = {
    'RestaurantOrder': ['Orders', 'RestaurantOrderList', 'Restaurant POS', 'RestaurantPOS'],
    'RestaurantOrderItem': ['Orders', 'RestaurantOrderList', 'Kitchen Display', 'KitchenDisplayList'],
    'Table': ['Table Management', 'TableList'],
    'Reservation': ['Reservations', 'ReservationList'],
    'MenuItem': ['Menu Management', 'MenuItemList', 'Restaurant Menus'],
    'MenuCategory': ['Menu Management', 'MenuCategoryList'],
    'Menu': ['Restaurant Menus', 'MenuList', 'MenuBuilder'],
    'Floor': ['Table Management', 'FloorList'],
    'Customer': ['Customer Management', 'CustomerList'],
    'Item': ['Items', 'ItemList'],
    'Vendor': ['Suppliers', 'VendorList'],
    'SalesOrder': ['Sales Order Page', 'SalesOrderList'],
    'SalesOrderLine': ['Sales Order Page', 'SalesOrderList'],
    'SalesInvoice': ['Sales Invoice Page', 'SalesInvoiceList'],
    'SalesInvoiceLine': ['Sales Invoice Page', 'SalesInvoiceList'],
    'PostedSalesInvoice': ['Posted Sales Invoices', 'PostedSalesInvoiceList'],
    'PostedSalesInvoiceLine': ['Posted Sales Invoices', 'PostedSalesInvoiceList'],
    'PurchaseInvoice': ['Purchase Invoices', 'PurchaseInvoiceList'],
    'PurchaseInvoiceLine': ['Purchase Invoices', 'PurchaseInvoiceList'],
    'PostedPurchaseInvoice': ['Posted Purchase Invoices', 'PostedPurchaseInvoiceList'],
    'PostedPurchaseInvoiceLine': ['Posted Purchase Invoices', 'PostedPurchaseInvoiceList'],
    'Expense': ['Expenses', 'ExpenseList'],
    'PaymentJournal': ['Payments', 'PaymentJournalList'],
    'PaymentLine': ['Payments', 'PaymentJournalList'],
    'BankAccount': ['Bank Account Management', 'BankAccountList'],
    'G_LAccount': ['Chart of Accounts', 'GLAccountList'],  # permission object 1016 (BC page 16)
}

# Mirrors pages.views.MODEL_REGISTRY (avoid circular import).
SOURCE_TABLE_MODEL: dict[str, tuple[str, str]] = {
    'RestaurantOrder': ('restaurant_management', 'RestaurantOrder'),
    'RestaurantOrderItem': ('restaurant_management', 'RestaurantOrderItem'),
    'Table': ('restaurant_management', 'Table'),
    'Reservation': ('restaurant_management', 'Reservation'),
    'MenuItem': ('restaurant_management', 'MenuItem'),
    'MenuCategory': ('restaurant_management', 'MenuCategory'),
    'Menu': ('restaurant_management', 'Menu'),
    'Floor': ('restaurant_management', 'Floor'),
    'Customer': ('sales', 'Customer'),
    'Item': ('items', 'Item'),
    'Vendor': ('purchases', 'Vendor'),
    'SalesOrder': ('sales', 'SalesOrder'),
    'SalesOrderLine': ('sales', 'SalesOrderLine'),
    'SalesInvoice': ('sales', 'SalesInvoice'),
    'SalesInvoiceLine': ('sales', 'SalesInvoiceLine'),
    'PurchaseInvoice': ('purchases', 'PurchaseInvoice'),
    'PurchaseInvoiceLine': ('purchases', 'PurchaseInvoiceLine'),
    'Expense': ('expenses', 'Expense'),
    'PaymentJournal': ('payments', 'PaymentJournal'),
    'PaymentLine': ('payments', 'PaymentLine'),
    'BankAccount': ('bank_account', 'BankAccount'),
    'G_LAccount': ('financials', 'G_LAccount'),
}


def get_table_object_for_source_table(source_table: str):
    """Resolve a page-engine source_table to a Table ``Objects`` row."""
    from base.models import Objects

    if not source_table:
        return None

    entry = SOURCE_TABLE_MODEL.get(source_table)
    if entry:
        app_label, model_name = entry
        for related in (f'{app_label}.{model_name}', f'{app_label}.{source_table}'):
            obj = Objects.objects.filter(
                object_type='Table',
                related_model=related,
            ).first()
            if obj:
                return obj
        obj = Objects.objects.filter(
            object_type='Table',
            object_name=model_name,
        ).first()
        if obj:
            return obj

    return Objects.objects.filter(
        object_type='Table',
        object_name=source_table,
    ).first()


def _user_has_page_fallback(user: 'CustomUser', source_table: str, permission_type: str) -> bool:
    from base.models import Objects

    aliases = SOURCE_TABLE_PAGE_ALIASES.get(source_table, [])
    for page_name in aliases:
        page_obj = Objects.objects.filter(
            object_type='Page',
            object_name=page_name,
        ).first()
        if not page_obj:
            continue
        allowed, _ = user.check_object_permission(page_obj.object_id, permission_type)
        if allowed:
            return True
    return False


def check_source_table_permission(
    user: 'CustomUser',
    source_table: str,
    permission_type: str,
) -> tuple[bool, str]:
    """
    BC-style table data check for page-engine CRUD.

    Returns (allowed, reason).
    """
    if not source_table:
        return True, 'No source table'

    if getattr(user, 'is_superuser', False):
        return True, 'Superuser'

    from permissions.services.super_permission_set import user_has_super_permission

    if user_has_super_permission(user):
        return True, 'SUPER permission set'

    if source_table not in ENFORCED_SOURCE_TABLES:
        return True, 'Table not in enforced set'

    table_obj = get_table_object_for_source_table(source_table)
    if table_obj is None:
        return True, 'Table object not registered'

    if not table_obj.requires_permission:
        return True, 'Table does not require permission'

    allowed, source = user.check_object_permission(table_obj.object_id, permission_type)
    if allowed:
        return True, source

    if _user_has_page_fallback(user, source_table, permission_type):
        return True, 'Page permission fallback'

    return False, source or 'No table permission'


def permission_denied_message(source_table: str, permission_type: str, reason: str) -> str:
    table_obj = get_table_object_for_source_table(source_table)
    label = table_obj.object_name if table_obj else source_table
    return (
        f'Insufficient permission to {permission_type} {label} data. {reason}'
    )


def _resolve_application_object(object_type: str, identifier: str):
    """Resolve by BC object_id (page engine name) or legacy object_name."""
    from base.models import Objects

    if object_type == 'Page':
        from pages.bc_page_ids import resolve_page_object_id

        oid = resolve_page_object_id(identifier)
        if oid is not None:
            obj = Objects.objects.filter(object_type='Page', object_id=oid).first()
            if obj:
                return obj

    obj = Objects.objects.filter(
        object_type=object_type,
        object_name=identifier,
    ).first()
    if obj:
        return obj

    return Objects.objects.filter(
        object_type=object_type,
        object_id=identifier if str(identifier).isdigit() else -1,
    ).first() if str(identifier).isdigit() else None


def create_permission_lines(
    perm_set,
    entries: list[tuple[str, str]],
    *,
    object_type: str = 'Page',
    stdout=None,
    style=None,
) -> int:
    """
    Create PermissionSetLine rows.

    entries: [(object_name, 'RIMD'), ...]
    object_type: 'Page' or 'Table'
    """
    from permissions.models import PermissionSetLine

    created = 0
    for object_name, permissions in entries:
        if not permissions:
            continue
        app_object = _resolve_application_object(object_type, object_name)
        if app_object is None:
            if stdout and style:
                stdout.write(
                    style.WARNING(
                        f'  {object_type} object not found: "{object_name}" (skipping)'
                    )
                )
            continue

        PermissionSetLine.objects.create(
            permissionset=perm_set,
            application_object=app_object,
            read_permission='R' in permissions,
            insert_permission='I' in permissions,
            modify_permission='M' in permissions,
            delete_permission='D' in permissions,
            execute_permission='X' in permissions and object_type == 'Page',
        )
        created += 1
    return created


def resolve_model_class(source_table: str):
    entry = SOURCE_TABLE_MODEL.get(source_table)
    if not entry:
        return None
    try:
        return apps.get_model(*entry)
    except LookupError:
        return None
