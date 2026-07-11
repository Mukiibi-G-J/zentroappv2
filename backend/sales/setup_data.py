"""Plain data helpers for sales setup — safe to call from sync views with a DRF Request."""


def fetch_sales_setup_data():
    from dimension.models import Dimension, DimensionValue
    from financials.models import GeneralLedgerSetup
    from sales.models import SalesReceivable

    sales_setup = SalesReceivable.objects.first()
    gl_setup = GeneralLedgerSetup.objects.first()
    enable_line_type = gl_setup.enable_sales_line_type_selection if gl_setup else False
    enable_multiple_branches = gl_setup.enable_multiple_branches if gl_setup else False
    branch_dimension_code = None
    branch_values = []

    if gl_setup and gl_setup.global_dimension_1_id:
        branch_dimension_code = gl_setup.global_dimension_1.code
        branch_values = list(
            DimensionValue.objects.filter(
                dimension_code_id=gl_setup.global_dimension_1_id
            ).values("id", "code", "description")
        )

    if enable_multiple_branches and not branch_values:
        branch_dim = Dimension.objects.filter(code__iexact="BRANCH").first()
        if branch_dim:
            branch_dimension_code = branch_dim.code
            branch_values = list(
                DimensionValue.objects.filter(dimension_code_id=branch_dim.id).values(
                    "id", "code", "description"
                )
            )

    global_dimension_2_code = None
    global_dimension_2_values = []
    if gl_setup and gl_setup.global_dimension_2_id:
        global_dimension_2_code = gl_setup.global_dimension_2.code
        global_dimension_2_values = list(
            DimensionValue.objects.filter(
                dimension_code_id=gl_setup.global_dimension_2_id
            ).values("id", "code", "description")
        )

    vat_enabled = getattr(gl_setup, "vat_enabled", False) if gl_setup else False
    if not sales_setup:
        return {
            "prevent_price_below_original": False,
            "disable_price_editing": False,
            "line_discounts_enabled": False,
            "enable_invoice_discounts": False,
            "enable_sales_line_type_selection": enable_line_type,
            "enable_multiple_branches": enable_multiple_branches,
            "vat_enabled": vat_enabled,
            "branch_dimension_code": branch_dimension_code,
            "branch_values": branch_values,
            "global_dimension_2_code": global_dimension_2_code,
            "global_dimension_2_values": global_dimension_2_values,
        }

    return {
        "prevent_price_below_original": sales_setup.prevent_price_below_original,
        "disable_price_editing": sales_setup.disable_price_editing,
        "line_discounts_enabled": sales_setup.enable_line_discounts,
        "enable_invoice_discounts": sales_setup.enable_invoice_discounts,
        "enable_sales_line_type_selection": enable_line_type,
        "enable_multiple_branches": enable_multiple_branches,
        "vat_enabled": vat_enabled,
        "branch_dimension_code": branch_dimension_code,
        "branch_values": branch_values,
        "global_dimension_2_code": global_dimension_2_code,
        "global_dimension_2_values": global_dimension_2_values,
    }


def fetch_company_info_data(request):
    from django_tenants.utils import get_tenant

    company = get_tenant(request)
    return {
        "company": {
            "name": company.name,
            "displayName": company.display_name or company.name,
            "logo": company.logo.url if company.logo else None,
            "address": company.address,
            "phone": company.phone,
            "email": company.email,
            "website": company.website or "",
            "city": company.city,
            "country": company.country,
            "tin": company.tin,
        }
    }
