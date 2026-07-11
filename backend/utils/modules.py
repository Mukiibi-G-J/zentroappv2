"""
Module Registry System for ZentroApp

This module defines available feature modules and their configurations.
Each module can be enabled/disabled per tenant for multi-industry support.
"""

from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class ModuleConfig:
    """Configuration for a feature module"""

    identifier: str
    display_name: str
    description: str
    app_name: str
    url_prefix: str
    required_permissions: List[str]
    dependencies: List[str]  # Other modules this module depends on
    icon: str = "cube"


# Define all available modules
MODULE_REGISTRY: Dict[str, ModuleConfig] = {
    # --- Core modules (included in all plans) ---
    "sales": ModuleConfig(
        identifier="sales",
        display_name="Sales & POS",
        description="Point of sale, sales orders, invoices, and sales history",
        app_name="sales",
        url_prefix="/api/sales/",
        required_permissions=[],
        dependencies=[],
        icon="shopping-cart",
    ),
    "inventory": ModuleConfig(
        identifier="inventory",
        display_name="Inventory Management",
        description="Item management, categories, and inventory adjustments",
        app_name="items",
        url_prefix="/api/items/",
        required_permissions=[],
        dependencies=[],
        icon="cube",
    ),
    "purchases": ModuleConfig(
        identifier="purchases",
        display_name="Purchases & Suppliers",
        description="Purchase orders, supplier management, and purchase history",
        app_name="purchases",
        url_prefix="/api/purchases/",
        required_permissions=[],
        dependencies=[],
        icon="truck",
    ),
    "customers": ModuleConfig(
        identifier="customers",
        display_name="Customer Management",
        description="Customer records, contact information, and transaction history",
        app_name="customers",
        url_prefix="/api/customers/",
        required_permissions=[],
        dependencies=[],
        icon="users",
    ),
    "expenses": ModuleConfig(
        identifier="expenses",
        display_name="Expense Tracking",
        description="Expense recording, categorisation, and history",
        app_name="expenses",
        url_prefix="/api/expenses/",
        required_permissions=[],
        dependencies=[],
        icon="credit-card",
    ),
    "reports": ModuleConfig(
        identifier="reports",
        display_name="Reports & Analytics",
        description="Daily profit, weekly/monthly summaries, product profitability, expense breakdown",
        app_name="reports",
        url_prefix="/api/reports/",
        required_permissions=[],
        dependencies=[],
        icon="chart-bar",
    ),
    "financials": ModuleConfig(
        identifier="financials",
        display_name="Financial Statements",
        description="Chart of Accounts, Profit & Loss, Balance Sheet",
        app_name="accounting",
        url_prefix="/api/accounting/",
        required_permissions=[],
        dependencies=[],
        icon="file-text",
    ),
    "payments": ModuleConfig(
        identifier="payments",
        display_name="Payments & Settlements",
        description="Payment processing, methods, and settlement history",
        app_name="payments",
        url_prefix="/api/payments/",
        required_permissions=[],
        dependencies=[],
        icon="dollar-sign",
    ),
    "prepayments": ModuleConfig(
        identifier="prepayments",
        display_name="Prepayments & Deposits",
        description="Customer prepayments and deposit tracking",
        app_name="prepayment",
        url_prefix="/api/prepayments/",
        required_permissions=[],
        dependencies=[],
        icon="layers",
    ),
    "bank_accounts": ModuleConfig(
        identifier="bank_accounts",
        display_name="Bank Account Management",
        description="Bank account tracking, reconciliation, and transactions",
        app_name="bank_account",
        url_prefix="/api/bank-accounts/",
        required_permissions=[],
        dependencies=[],
        icon="landmark",
    ),
    "user_management": ModuleConfig(
        identifier="user_management",
        display_name="User Roles & Permissions",
        description="User management, role centres, permission sets, and user groups",
        app_name="authentication",
        url_prefix="/api/auth/",
        required_permissions=[],
        dependencies=[],
        icon="shield",
    ),
    # --- Business+ modules (differentiating) ---
    "item_tracking": ModuleConfig(
        identifier="item_tracking",
        display_name="Item Tracking",
        description="Lot, serial, and expiry tracking for inventory items",
        app_name="items",
        url_prefix="/api/items/tracking/",
        required_permissions=[],
        dependencies=["inventory"],
        icon="tag",
    ),
    "stock_taking": ModuleConfig(
        identifier="stock_taking",
        display_name="Stock Taking",
        description="Physical inventory counts and stock reconciliation",
        app_name="items",
        url_prefix="/api/items/stock-taking/",
        required_permissions=[],
        dependencies=["inventory"],
        icon="clipboard-check",
    ),
    "manufacturing": ModuleConfig(
        identifier="manufacturing",
        display_name="Manufacturing & Production",
        description="Production BOMs, production orders, and manufacturing workflows",
        app_name="production",
        url_prefix="/api/production/",
        required_permissions=[],
        dependencies=["inventory"],
        icon="cog",
    ),
    "loans": ModuleConfig(
        identifier="loans",
        display_name="Loan Management",
        description="Loan registration, repayments, and loan history",
        app_name="loans",
        url_prefix="/api/loans/",
        required_permissions=[],
        dependencies=[],
        icon="currency-dollar",
    ),
    "resources": ModuleConfig(
        identifier="resources",
        display_name="Resources",
        description="People, equipment, and resource allocation management",
        app_name="resources",
        url_prefix="/api/resources/",
        required_permissions=[],
        dependencies=[],
        icon="briefcase",
    ),
    "multi_branch": ModuleConfig(
        identifier="multi_branch",
        display_name="Multi-Branch (Up to 3)",
        description="Up to 3 branch locations; enable Branch Management, branch switching, and per-branch workflows such as Stock Taking",
        app_name="company",
        url_prefix="",
        required_permissions=[],
        dependencies=["sales"],
        icon="map-pin",
    ),
    # --- Pro modules ---
    "efris": ModuleConfig(
        identifier="efris",
        display_name="EFRIS Integration",
        description="Uganda Revenue Authority EFRIS tax compliance integration",
        app_name="efris",
        url_prefix="/api/efris/",
        required_permissions=[],
        dependencies=["sales"],
        icon="shield-check",
    ),
    # --- Add-on modules ---
    "hotel": ModuleConfig(
        identifier="hotel",
        display_name="Hotel Management",
        description="Rooms, bookings, guests, frontdesk, and channel manager",
        app_name="hotel_management",
        url_prefix="/api/hotel/",
        required_permissions=[],
        dependencies=["sales"],
        icon="building",
    ),
    "restaurant": ModuleConfig(
        identifier="restaurant",
        display_name="Restaurant Management",
        description="Table management, reservations, menu items, and kitchen display",
        app_name="restaurant_management",
        url_prefix="/api/restaurant/",
        required_permissions=[],
        dependencies=["sales"],
        icon="utensils",
    ),
    # Legacy alias
    "pos": ModuleConfig(
        identifier="pos",
        display_name="Point of Sale",
        description="Legacy alias for sales module",
        app_name="sales",
        url_prefix="/api/",
        required_permissions=[],
        dependencies=[],
        icon="shopping-cart",
    ),
}

# Valid module identifiers for quick validation
VALID_MODULES = set(MODULE_REGISTRY.keys())

# Legacy ``pos`` is the same product module as ``sales`` (plans use ``sales``).
SALES_MODULE_ALIASES = frozenset({"pos", "sales"})


def canonical_module_id(module_id: str) -> str:
    """Map legacy identifiers to the canonical plan module id."""
    if module_id in SALES_MODULE_ALIASES:
        return "sales"
    return module_id


def plan_includes_module(plan_modules: list[str] | None, module_id: str) -> bool:
    """True when the subscription plan already covers this module (incl. pos/sales alias)."""
    plan_set = set(plan_modules or [])
    if module_id in plan_set:
        return True
    if module_id in SALES_MODULE_ALIASES:
        return bool(plan_set & SALES_MODULE_ALIASES)
    return False


def dedupe_enabled_modules(modules: list[str] | None) -> list[str]:
    """Drop redundant legacy ``pos`` when ``sales`` is already enabled."""
    items = list(modules or [])
    if "sales" in items and "pos" in items:
        items = [m for m in items if m != "pos"]
    return items


def get_available_modules() -> List[ModuleConfig]:
    """
    Get list of all available modules

    Returns:
        List[ModuleConfig]: List of all module configurations
    """
    return list(MODULE_REGISTRY.values())


def get_module_config(module_identifier: str) -> Optional[ModuleConfig]:
    """
    Get configuration for a specific module

    Args:
        module_identifier: The module identifier (e.g., 'pos', 'hotel')

    Returns:
        ModuleConfig: Module configuration if found, None otherwise
    """
    return MODULE_REGISTRY.get(module_identifier)


def validate_module(module_identifier: str) -> bool:
    """
    Validate if a module identifier is valid

    Args:
        module_identifier: The module identifier to validate

    Returns:
        bool: True if valid, False otherwise
    """
    return module_identifier in VALID_MODULES


def validate_modules(module_identifiers: List[str]) -> tuple[bool, List[str]]:
    """
    Validate a list of module identifiers

    Args:
        module_identifiers: List of module identifiers to validate

    Returns:
        tuple: (is_valid, invalid_modules)
            is_valid: True if all modules are valid
            invalid_modules: List of invalid module identifiers
    """
    invalid_modules = [m for m in module_identifiers if not validate_module(m)]
    return (len(invalid_modules) == 0, invalid_modules)


def check_module_dependencies(
    module_identifier: str, enabled_modules: List[str]
) -> tuple[bool, List[str]]:
    """
    Check if all dependencies for a module are satisfied

    Args:
        module_identifier: The module to check dependencies for
        enabled_modules: List of currently enabled modules

    Returns:
        tuple: (dependencies_met, missing_dependencies)
            dependencies_met: True if all dependencies are enabled
            missing_dependencies: List of missing dependency identifiers
    """
    config = get_module_config(module_identifier)
    if not config:
        return (False, [])

    missing_deps = [dep for dep in config.dependencies if dep not in enabled_modules]
    return (len(missing_deps) == 0, missing_deps)


def validate_module_list(module_identifiers: List[str]) -> tuple[bool, str]:
    """
    Comprehensive validation of a module list including dependencies

    Args:
        module_identifiers: List of module identifiers to validate

    Returns:
        tuple: (is_valid, error_message)
            is_valid: True if validation passes
            error_message: Description of validation error if any
    """
    # Check for valid modules
    is_valid, invalid_modules = validate_modules(module_identifiers)
    if not is_valid:
        return (
            False,
            f"Invalid modules: {', '.join(invalid_modules)}. Valid modules are: {', '.join(VALID_MODULES)}",
        )

    # Check dependencies
    for module in module_identifiers:
        deps_met, missing_deps = check_module_dependencies(module, module_identifiers)
        if not deps_met:
            config = get_module_config(module)
            return (
                False,
                f"Module '{config.display_name}' requires the following modules to be enabled: {', '.join(missing_deps)}",
            )

    return (True, "")


def get_module_display_name(module_identifier: str) -> str:
    """
    Get the display name for a module

    Args:
        module_identifier: The module identifier

    Returns:
        str: Display name or identifier if not found
    """
    config = get_module_config(module_identifier)
    return config.display_name if config else module_identifier


def get_modules_requiring_module(module_identifier: str) -> List[str]:
    """
    Get list of modules that depend on the specified module

    Args:
        module_identifier: The module to check dependents for

    Returns:
        List[str]: List of module identifiers that depend on this module
    """
    dependent_modules = []
    for identifier, config in MODULE_REGISTRY.items():
        if module_identifier in config.dependencies:
            dependent_modules.append(identifier)
    return dependent_modules


def get_base_modules() -> List[str]:
    """
    Get list of base modules (modules with no dependencies)
    These are core modules that should always be enabled

    Returns:
        List[str]: List of base module identifiers
    """
    base_modules = []
    for identifier, config in MODULE_REGISTRY.items():
        if not config.dependencies:
            base_modules.append(identifier)
    return base_modules


def ensure_base_modules(module_list: List[str]) -> List[str]:
    """
    Ensure all base modules are included in the module list

    Args:
        module_list: List of module identifiers

    Returns:
        List[str]: Module list with base modules prepended if missing
    """
    base_modules = get_base_modules()
    result = list(module_list) if module_list else []

    # Add base modules that are missing, ensuring they come first
    for base_module in base_modules:
        if base_module not in result:
            result.insert(0, base_module)
        else:
            # Move base module to the front if it exists
            result.remove(base_module)
            result.insert(0, base_module)

    return result


def validate_pos_required(module_list: List[str]) -> tuple[bool, str]:
    """
    Validate that POS module is always included in the module list

    Args:
        module_list: List of module identifiers

    Returns:
        tuple: (is_valid, error_message)
            is_valid: True if POS is included
            error_message: Error message if POS is missing
    """
    if "pos" not in (module_list or []):
        return (
            False,
            "POS module is required and cannot be disabled. It is the base module for the system.",
        )
    return (True, "")