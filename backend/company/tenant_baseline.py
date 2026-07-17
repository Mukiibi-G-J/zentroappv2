"""
Tenant-generic baseline data for golden template + slow-path signup.

Baked into ``_zentro_template`` during ``rebuild_template_schema`` so new companies
that clone the template skip re-running roles, pages engine, BC permission objects,
JSON import, and seed commands.
"""

from __future__ import annotations

import json
import logging
import os
from io import StringIO
from typing import Callable, Optional

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import OutputWrapper
from django.core.management.color import color_style
from django_tenants.utils import schema_context

from authentication.models import CustomUser as User, Role
from company.tenant_import import run_tenant_data_import
from helpers.helpers import setup_default_no_series
from items.models import Location
from purchases.models import PurchasePayable, Vendor, VendorPostingGroup
from sales.enums import CustomerType
from sales.models import Customer, CustomerPostingGroup, SalesReceivable
from financials.models import PaymentMethod
from postings.models import (
    GeneralBusinessPostingGroup,
    InventoryPostingSetup,
)
from setup.models import NoSeries, NoSeriesLines

logger = logging.getLogger(__name__)

ProgressCb = Optional[Callable[[float, str, str], None]]

TENANT_JSON_EXPORT = "tenant_semuna_export_20250227_062346.json"


def _progress(cb: ProgressCb, pct: float, message: str, status: str) -> None:
    if cb:
        cb(pct, message, status)


def _quiet_call_command(name: str, **kwargs) -> None:
    buf = StringIO()
    wrapper = OutputWrapper(buf, ending="")
    call_command(name, stdout=wrapper, stderr=wrapper, verbosity=0, **kwargs)
    buf.close()


def tenant_has_baseline_data() -> bool:
    """
    Return True when the active tenant schema already has gold-template baseline rows.

    Call inside ``schema_context(tenant)``.
    """
    from financials.models import FinancialReport
    from pages.models import Page
    from permissions.models import PermissionSet

    return (
        Role.objects.filter(name="Admin").exists()
        and PermissionSet.objects.filter(code="SALES_FULL").exists()
        and Page.objects.exists()
        and NoSeries.objects.filter(code="VENDOR").exists()
        and PurchasePayable.objects.exists()
        and SalesReceivable.objects.exists()
        and FinancialReport.objects.filter(name="INCOME").exists()
    )


def create_default_roles(schema_name: str) -> list[str]:
    """Create default user roles for a tenant schema."""
    try:
        with schema_context(schema_name):
            default_roles = [
                {
                    "name": "Admin",
                    "description": (
                        "Full system administrator with complete access to all "
                        "features and settings"
                    ),
                    "permissions": ["all"],
                    "is_active": True,
                },
                {
                    "name": "Manager",
                    "description": (
                        "Business manager with comprehensive access to reports, "
                        "user management, and business settings"
                    ),
                    "permissions": [
                        "view_dashboard",
                        "view_profile",
                        "edit_profile",
                        "view_sales",
                        "create_sales",
                        "edit_sales",
                        "view_sales_history",
                        "create_sales_invoice",
                        "view_purchases",
                        "create_purchases",
                        "edit_purchases",
                        "view_purchase_history",
                        "view_items",
                        "create_items",
                        "edit_items",
                        "manage_item_categories",
                        "view_inventory",
                        "adjust_inventory",
                        "view_inventory_history",
                        "view_customers",
                        "create_customers",
                        "edit_customers",
                        "view_vendors",
                        "create_vendors",
                        "edit_vendors",
                        "view_expenses",
                        "create_expenses",
                        "edit_expenses",
                        "view_expense_history",
                        "view_payments",
                        "create_payments",
                        "edit_payments",
                        "view_payment_history",
                        "view_financials",
                        "create_financials",
                        "edit_financials",
                        "view_chart_of_accounts",
                        "view_profit_loss",
                        "view_balance_sheet",
                        "view_reports",
                        "export_reports",
                        "create_custom_reports",
                        "manage_users",
                        "manage_roles",
                        "view_user_activity",
                        "view_company",
                        "edit_company",
                        "manage_company_settings",
                        "view_settings",
                        "edit_settings",
                        "view_subscription",
                        "manage_subscription",
                    ],
                    "is_active": True,
                },
                {
                    "name": "Sales",
                    "description": (
                        "Sales staff with access to sales, customers, and basic reporting"
                    ),
                    "permissions": [
                        "view_dashboard",
                        "view_profile",
                        "edit_profile",
                        "view_sales",
                        "create_sales",
                        "edit_sales",
                        "view_sales_history",
                        "create_sales_invoice",
                        "view_customers",
                        "create_customers",
                        "edit_customers",
                        "view_items",
                        "view_inventory",
                        "view_reports",
                        "export_reports",
                    ],
                    "is_active": True,
                },
                {
                    "name": "Cashier",
                    "description": (
                        "Cashier with access to sales transactions and basic "
                        "customer management"
                    ),
                    "permissions": [
                        "view_dashboard",
                        "view_profile",
                        "edit_profile",
                        "view_sales",
                        "create_sales",
                        "view_sales_history",
                        "view_customers",
                        "create_customers",
                        "view_items",
                        "view_inventory",
                        "view_reports",
                    ],
                    "is_active": True,
                },
                {
                    "name": "Inventory",
                    "description": (
                        "Inventory manager with access to stock management and purchasing"
                    ),
                    "permissions": [
                        "view_dashboard",
                        "view_profile",
                        "edit_profile",
                        "view_items",
                        "create_items",
                        "edit_items",
                        "manage_item_categories",
                        "manage_item_units",
                        "view_inventory",
                        "adjust_inventory",
                        "view_inventory_history",
                        "manage_inventory_tracking",
                        "view_purchases",
                        "create_purchases",
                        "edit_purchases",
                        "view_purchase_history",
                        "view_vendors",
                        "create_vendors",
                        "edit_vendors",
                        "view_reports",
                        "export_reports",
                    ],
                    "is_active": True,
                },
                {
                    "name": "Accountant",
                    "description": (
                        "Accountant with access to financial records, reports, "
                        "and accounting features"
                    ),
                    "permissions": [
                        "view_dashboard",
                        "view_profile",
                        "edit_profile",
                        "view_financials",
                        "create_financials",
                        "edit_financials",
                        "view_chart_of_accounts",
                        "manage_chart_of_accounts",
                        "view_profit_loss",
                        "view_balance_sheet",
                        "view_sales",
                        "view_sales_history",
                        "view_purchases",
                        "view_purchase_history",
                        "view_items",
                        "view_inventory",
                        "view_inventory_history",
                        "view_expenses",
                        "create_expenses",
                        "edit_expenses",
                        "view_expense_history",
                        "view_payments",
                        "create_payments",
                        "edit_payments",
                        "view_payment_history",
                        "manage_payment_methods",
                        "view_reports",
                        "export_reports",
                        "create_custom_reports",
                    ],
                    "is_active": True,
                },
                {
                    "name": "User",
                    "description": "Basic user with limited access to view-only features",
                    "permissions": [
                        "view_dashboard",
                        "view_profile",
                        "edit_profile",
                        "view_sales",
                        "view_customers",
                        "view_items",
                        "view_inventory",
                        "view_reports",
                    ],
                    "is_active": True,
                },
            ]

            created_roles: list[str] = []
            for role_data in default_roles:
                role, created = Role.objects.get_or_create(
                    name=role_data["name"],
                    defaults={
                        "description": role_data["description"],
                        "permissions": role_data["permissions"],
                        "is_active": role_data["is_active"],
                    },
                )
                if created:
                    created_roles.append(role.name)
                    logger.info("Created role: %s", role.name)

            logger.info(
                "Successfully created %s roles: %s",
                len(created_roles),
                ", ".join(created_roles),
            )
            return created_roles
    except Exception as exc:
        logger.error("Error creating default roles: %s", exc)
        raise


def ensure_default_user_groups() -> None:
    """
    Create default user groups and attach permission sets.

    Call with tenant schema active. Does not assign any user.
    """
    from authentication.models import UserGroup
    from permissions.models import PermissionSet

    admin_role = Role.objects.filter(name="Admin").first()
    manager_role = Role.objects.filter(name="Manager").first()
    sales_role = Role.objects.filter(name="Sales").first()
    cashier_role = Role.objects.filter(name="Cashier").first()
    inventory_role = Role.objects.filter(name="Inventory").first()
    accountant_role = Role.objects.filter(name="Accountant").first()
    user_role = Role.objects.filter(name="User").first()

    if admin_role:
        admin_group, created = UserGroup.objects.get_or_create(
            code="Admin",
            defaults={
                "name": "Admin",
                "description": "Administrator user group with full access",
                "default_profile": admin_role,
                "is_active": True,
            },
        )
        all_permission_sets = PermissionSet.objects.filter(is_active=True)
        admin_group.permission_sets.set(all_permission_sets)
        logger.info(
            "%s Admin user group with %s permission sets",
            "Created" if created else "Updated",
            all_permission_sets.count(),
        )

    group_specs = [
        (
            manager_role,
            "Manager",
            "Manager user group with comprehensive access",
            [
                "SALES_FULL",
                "CUSTOMER_FULL",
                "ITEMS_FULL",
                "PURCHASES_FULL",
                "PAYMENTS_FULL",
                "EXPENSES_FULL",
                "FINANCIALS_FULL",
            ],
        ),
        (
            sales_role,
            "Sales",
            "Sales user group with sales and customer access",
            ["SALES_FULL", "CUSTOMER_FULL", "ITEMS_VIEW_ONLY"],
        ),
        (
            cashier_role,
            "Cashier",
            "Cashier user group with POS access",
            ["SALES_CASHIER", "CUSTOMER_BASIC", "ITEMS_VIEW_ONLY"],
        ),
        (
            inventory_role,
            "Inventory",
            "Inventory user group with stock management access",
            ["ITEMS_FULL", "PURCHASES_FULL"],
        ),
        (
            accountant_role,
            "Accountant",
            "Accountant user group with financial access",
            [
                "FINANCIALS_FULL",
                "PAYMENTS_FULL",
                "EXPENSES_FULL",
                "SALES_VIEW_ONLY",
                "PURCHASES_VIEW_ONLY",
            ],
        ),
        (
            user_role,
            "User",
            "Basic user group with view-only access",
            [
                "SALES_VIEW_ONLY",
                "CUSTOMER_VIEW_ONLY",
                "ITEMS_VIEW_ONLY",
                "FINANCIALS_VIEW_ONLY",
            ],
        ),
    ]

    for role, code, description, perm_codes in group_specs:
        if not role:
            continue
        group, created = UserGroup.objects.get_or_create(
            code=code,
            defaults={
                "name": code,
                "description": description,
                "default_profile": role,
                "is_active": True,
            },
        )
        if created:
            perms = PermissionSet.objects.filter(code__in=perm_codes)
            group.permission_sets.add(*perms)
            logger.info("Created %s user group", code)


def assign_user_to_admin_group(user: User) -> None:
    """Attach ``user`` to the Admin user group and Business Manager Role Centre."""
    from authentication.models import ApplicationProfile, UserGroup, UserPersonalization
    from authentication.profile_assignment import _is_debug_admin_user

    admin_group = UserGroup.objects.filter(code="Admin").first()
    if admin_group and user:
        user.user_groups.add(admin_group)
        logger.info("Assigned user %s to Admin user group", user.username)

    if not user or _is_debug_admin_user(user):
        return

    profile = ApplicationProfile.objects.filter(code="BUSINESS-MGR").first()
    if not profile:
        logger.warning(
            "BUSINESS-MGR ApplicationProfile missing; cannot assign Role Centre to %s",
            getattr(user, "username", user),
        )
        return

    personalization = UserPersonalization.get_or_create_for_user(user)
    if personalization.role_id != profile.pk:
        personalization.role = profile
        personalization.modified_by = "assign_user_to_admin_group"
        personalization.save(update_fields=["role", "modified_by"])
        logger.info(
            "Assigned user %s to Business Manager Role Centre",
            user.username,
        )


def ensure_branch_location(
    *,
    address: str = "",
    city: str = "",
    phone: str = "",
    email: str = "",
) -> object:
    """
    Ensure BRANCH dimension + matching Location exist; update location contact fields.

    Returns the default branch DimensionValue. Tenant schema must be active.
    """
    from dimension.setup import (
        DEFAULT_FIRST_BRANCH_CODE,
        DEFAULT_FIRST_BRANCH_DESCRIPTION,
        ensure_default_branch_dimension_and_gl_setup,
    )

    branch_setup = ensure_default_branch_dimension_and_gl_setup(
        default_branch_value_code=DEFAULT_FIRST_BRANCH_CODE,
        default_branch_value_description=DEFAULT_FIRST_BRANCH_DESCRIPTION,
    )
    branch_value = branch_setup["default_branch_value"]
    Location.objects.update_or_create(
        code=branch_value.code,
        defaults={
            "description": branch_value.description,
            "address": (address or "").strip(),
            "city": city or "",
            "phone": phone or "",
            "email": email or "",
        },
    )
    return branch_value


def ensure_inventory_posting_for_branch(branch_code: str) -> None:
    """Copy NULL-location InventoryPostingSetup rows onto the branch location."""
    from postings.setup import ensure_inventory_posting_setups_for_location

    location = Location.objects.filter(code=branch_code).first()
    if not location:
        logger.warning(
            "No Location for branch %s; skipping inventory posting setup sync",
            branch_code,
        )
        return
    created_setups = ensure_inventory_posting_setups_for_location(location)
    if created_setups:
        logger.info(
            "Created %s InventoryPostingSetup(s) for location %s",
            created_setups,
            location.code,
        )
    elif not InventoryPostingSetup.objects.filter(location=location).exists():
        logger.warning(
            "No InventoryPostingSetup templates (location=NULL) to copy for %s",
            location.code,
        )


def ensure_default_vendor_and_customer(
    *,
    address: str = "",
    city: str = "",
) -> None:
    """Create or update the default General vendor/customer (company-specific fields)."""
    cash = PaymentMethod.objects.get(code="CASH")
    domestic_gbp = GeneralBusinessPostingGroup.objects.get(code="DOMESTIC")
    vendor_pg = VendorPostingGroup.objects.get(code="DOMESTIC")
    customer_pg = CustomerPostingGroup.objects.get(code="DOMESTIC")

    vendor, _ = Vendor.objects.get_or_create(
        name="General",
        defaults={
            "address": address,
            "address_2": address,
            "city": city,
            "payment_method": cash,
            "vendor_posting_group": vendor_pg,
            "business_posting_group": domestic_gbp,
        },
    )
    if vendor.address != address or vendor.city != city:
        vendor.address = address
        vendor.address_2 = address
        vendor.city = city
        vendor.save(update_fields=["address", "address_2", "city"])

    customer, _ = Customer.objects.get_or_create(
        name="General",
        defaults={
            "address": address,
            "address_2": address,
            "city": city,
            "payment_method": cash,
            "general_business_posting_group": domestic_gbp,
            "customer_posting_group": customer_pg,
            "customer_type": CustomerType.General.name,
        },
    )
    if customer.address != address or customer.city != city:
        customer.address = address
        customer.address_2 = address
        customer.city = city
        customer.save(update_fields=["address", "address_2", "city"])


def ensure_purchase_and_sales_setup() -> None:
    """Create PurchasePayable / SalesReceivable setup rows if missing."""
    if not PurchasePayable.objects.exists():
        PurchasePayable.objects.create(
            vendor_no=NoSeriesLines.objects.get(
                no_series=NoSeries.objects.get(code="VENDOR"),
            ),
            invoice_no=NoSeriesLines.objects.get(
                no_series=NoSeries.objects.get(code="INV"),
            ),
            posted_invoice_no=NoSeriesLines.objects.get(
                no_series=NoSeries.objects.get(code="POSTINV"),
            ),
            credit_memo_no=NoSeriesLines.objects.get(
                no_series=NoSeries.objects.get(code="PURCR"),
            ),
            posted_credit_memo_no=NoSeriesLines.objects.get(
                no_series=NoSeries.objects.get(code="POSTPURCR"),
            ),
        )

    if not SalesReceivable.objects.exists():
        SalesReceivable.objects.create(
            customer_no=NoSeriesLines.objects.get(
                no_series=NoSeries.objects.get(code="CUSTOMER"),
            ),
            sales_no=NoSeriesLines.objects.get(
                no_series=NoSeries.objects.get(code="SALES"),
            ),
            invoice_no=NoSeriesLines.objects.get(
                no_series=NoSeries.objects.get(code="SALESINV"),
            ),
            posted_invoice_no=NoSeriesLines.objects.get(
                no_series=NoSeries.objects.get(code="PSIN"),
            ),
            credit_memo_no=NoSeriesLines.objects.get(
                no_series=NoSeries.objects.get(code="CM"),
            ),
            posted_credit_memo_no=NoSeriesLines.objects.get(
                no_series=NoSeries.objects.get(code="POSTCM"),
            ),
            posted_prepayment_invoice_no=NoSeriesLines.objects.get(
                no_series=NoSeries.objects.get(code="POSTPREPINV"),
            ),
            posted_prepayment_credit_memo_no=NoSeriesLines.objects.get(
                no_series=NoSeries.objects.get(code="POSTPREPCM"),
            ),
            sales_order_no=NoSeriesLines.objects.get(
                no_series=NoSeries.objects.get(code="SO"),
            ),
            sales_price_list_no=NoSeriesLines.objects.get(
                no_series=NoSeries.objects.get(code="SPL"),
            ),
        )

    try:
        call_command("seed_credit_memo_numbers", verbosity=0)
    except Exception as cm_error:
        logger.warning(
            "seed_credit_memo_numbers after SalesReceivable create: %s",
            cm_error,
        )


def run_tenant_baseline_bootstrap(
    schema_name: str,
    *,
    progress: ProgressCb = None,
    ensure_branch: bool = True,
) -> dict:
    """
    Populate tenant-generic baseline into ``schema_name``.

    Includes roles, role centres, pages engine + BC permission objects, permission
    sets, user groups, JSON chart/posting import, number series, and related seeds.

    Does **not** create an admin user, domain, subscription, or company-addressed
    General vendor/customer.
    """
    created_roles: list[str] = []
    import_output = ""

    with schema_context(schema_name):
        if ensure_branch:
            ensure_branch_location()

        _progress(progress, 68, "Creating default roles...", "creating_roles")
        created_roles = create_default_roles(schema_name)

        _progress(
            progress, 69, "Creating default role centers...", "creating_role_centers"
        )
        try:
            _quiet_call_command("setup_default_role_centers")
            logger.info("Created default role centers for %s", schema_name)
        except Exception as rc_error:
            logger.error("Error creating role centers: %s", rc_error)

        _progress(progress, 70, "Seeding page engine...", "seeding_pages")
        try:
            _quiet_call_command("seed_pages", schema=schema_name)
            logger.info("Seeded page engine for %s", schema_name)
        except Exception as pages_error:
            logger.error("Error seeding pages: %s", pages_error)
            raise

        _progress(
            progress, 70.5, "Setting up legacy page objects...", "creating_page_objects"
        )
        try:
            _quiet_call_command("populate_page_objects")
            logger.info("Created legacy page objects for %s", schema_name)
        except Exception as po_error:
            logger.error("Error creating page objects: %s", po_error)

        _progress(
            progress, 71, "Setting up permission sets...", "creating_permission_sets"
        )
        try:
            _quiet_call_command("setup_page_permissions")
            logger.info("Created permission sets for %s", schema_name)
        except Exception as ps_error:
            logger.error("Error creating permission sets: %s", ps_error)
            raise

        _progress(
            progress,
            71.75,
            "Seeding mobile money account...",
            "seeding_mobile_money_account",
        )
        try:
            call_command("seed_mobile_money_account", schema=schema_name)
        except Exception as mm_error:
            logger.error("Error seeding mobile money account: %s", mm_error)

        _progress(
            progress,
            71.77,
            "Seeding mobile money bank accounts...",
            "seeding_mobile_money_bank_accounts",
        )
        try:
            call_command("seed_mobile_money_bank_accounts")
        except Exception as mmba_error:
            logger.error("Error seeding mobile money bank accounts: %s", mmba_error)

        _progress(
            progress, 71.8, "Setting up bank account configuration...", "setting_up_bank_account"
        )
        try:
            call_command("setup_bank_account")
        except Exception as ba_error:
            logger.error("Error setting up bank account: %s", ba_error)

        _progress(
            progress,
            71.85,
            "Seeding prepayment number series...",
            "seeding_prepayment_no_series",
        )
        try:
            call_command("seed_prepayment_no_series")
        except Exception as pns_error:
            logger.error("Error seeding prepayment number series: %s", pns_error)

        _progress(progress, 72, "Creating user groups...", "creating_user_groups")
        try:
            ensure_default_user_groups()
        except Exception as ug_error:
            logger.error("Error creating user groups: %s", ug_error)
            raise

        _progress(progress, 73, "Starting data import...", "importing_data")
        file_path = os.path.join(settings.BASE_DIR, TENANT_JSON_EXPORT)
        with open(file_path, "r", encoding="utf-8") as json_file:
            import_data = json.load(json_file)

        _progress(progress, 80, "Importing initial data...", "importing_data")
        output_buffer = StringIO()
        output_wrapper = OutputWrapper(output_buffer, ending="")
        style = color_style()
        run_tenant_data_import(
            schema_name,
            import_data,
            output_wrapper,
            output_wrapper,
            style,
        )
        import_output = output_buffer.getvalue()
        output_buffer.close()

        call_command("seed_prepayment_accounts")

        _progress(
            progress,
            82.5,
            "Seeding financial reports...",
            "seeding_financial_reports",
        )
        try:
            # After CoA import so row totaling can resolve Income Statement posting accounts.
            call_command("seed_income_statement_row_definition", schema=schema_name)
            logger.info("Seeded financial reports (INCOME) for %s", schema_name)
        except Exception as fr_error:
            logger.error("Error seeding financial reports: %s", fr_error)
            # Template rebuild must not silently ship without reports; signup slow-path
            # can continue and still create the company.
            if schema_name == "_zentro_template":
                raise

        _progress(
            progress, 83, "Seeding expense categories...", "seeding_expense_categories"
        )
        try:
            call_command("seed_expense_categories", tenant=schema_name)
        except Exception as ec_error:
            logger.error("Error seeding expense categories: %s", ec_error)

        _progress(progress, 84, "Seeding expense types...", "seeding_expense_types")
        try:
            call_command("seed_expense_types", tenant=schema_name)
        except Exception as et_error:
            logger.error("Error seeding expense types: %s", et_error)

        _progress(
            progress,
            84.5,
            "Seeding item tracking codes...",
            "seeding_item_tracking_codes",
        )
        try:
            call_command("seed_item_tracking_codes", tenant=schema_name)
        except Exception as itc_error:
            logger.error("Error seeding item tracking codes: %s", itc_error)

        _progress(progress, 85, "Updating inventory setup...", "importing_data")
        from dimension.setup import (
            DEFAULT_FIRST_BRANCH_CODE,
            DEFAULT_FIRST_BRANCH_DESCRIPTION,
            ensure_default_branch_dimension_and_gl_setup,
        )

        branch_setup = ensure_default_branch_dimension_and_gl_setup(
            default_branch_value_code=DEFAULT_FIRST_BRANCH_CODE,
            default_branch_value_description=DEFAULT_FIRST_BRANCH_DESCRIPTION,
        )
        ensure_inventory_posting_for_branch(
            branch_setup["default_branch_value"].code
        )

        if "Error" in import_output or "error" in import_output:
            raise Exception(f"Import errors occurred: {import_output}")

        _progress(progress, 90, "Setting up number series...", "setting_up_series")
        series_result = setup_default_no_series()
        logger.info("Number series setup result: %s", series_result)

        _progress(progress, 92, "Creating default records...", "setting_up_series")
        ensure_purchase_and_sales_setup()

        ensure_default_branch_dimension_and_gl_setup(
            default_branch_value_code=DEFAULT_FIRST_BRANCH_CODE,
            default_branch_value_description=DEFAULT_FIRST_BRANCH_DESCRIPTION,
        )

        if not tenant_has_baseline_data():
            raise RuntimeError(
                f"Baseline bootstrap finished but tenant_has_baseline_data() is False "
                f"for schema {schema_name!r}"
            )

        logger.info("Tenant baseline bootstrap complete for schema %s", schema_name)
        return {
            "created_roles": created_roles,
            "import_output": import_output,
        }
