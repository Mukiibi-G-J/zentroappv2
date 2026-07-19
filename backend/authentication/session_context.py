"""Resolve login session context: profile, Role Centre page, sidebar nav."""


def serialize_rc_nav_items(role_centre_page) -> list[dict]:
    if role_centre_page is None:
        return []
    from pages.desktop_pages import DESKTOP_ONLY_PAGE_NAMES

    items = []
    for action in role_centre_page.page_actions.filter(
        action_type='NavItem',
        visible=True,
    ).order_by('action_id'):
        target = action.action_relative_url or ''
        ribbon_tab = action.ribbon_tab or 'Navigation'
        items.append({
            'name': action.name,
            'caption': action.caption,
            'imageUrl': action.image_url or '',
            'targetPageName': target,
            'ribbonTab': ribbon_tab,
            # Sync Queue and other Electron-only entries: hide in web UI.
            'desktopOnly': target in DESKTOP_ONLY_PAGE_NAMES or ribbon_tab == 'Desktop',
        })
    return items


def _resolve_company_from_connection():
    """Return the real Company row; schema_context() leaves a FakeTenant on connection."""
    from django.db import connection
    from company.models import Company

    tenant = getattr(connection, 'tenant', None)
    if tenant is None:
        return None

    if hasattr(tenant, 'logo'):
        return tenant

    schema_name = getattr(tenant, 'schema_name', None)
    if not schema_name:
        return None

    try:
        return Company.objects.get(schema_name=schema_name)
    except Company.DoesNotExist:
        return None


def serialize_company(request=None) -> dict | None:
    company = _resolve_company_from_connection()
    if company is None:
        return None

    logo_url = None
    if company.logo:
        try:
            relative = company.logo.url
            logo_url = request.build_absolute_uri(relative) if request else relative
        except (ValueError, AttributeError):
            logo_url = None

    return {
        'name': company.name,
        'displayName': company.display_name or company.name,
        'logoUrl': logo_url,
        'email': company.email or '',
        'phone': company.phone or '',
    }


def _serialize_branch(dimension_value) -> dict | None:
    if not dimension_value:
        return None
    return {
        'id': dimension_value.id,
        'code': dimension_value.code,
        'description': dimension_value.description or '',
    }


def _branch_config_for_user(user) -> dict:
    enable_multiple_branches = False
    try:
        from financials.models import GeneralLedgerSetup

        gl_setup = GeneralLedgerSetup.objects.first()
        enable_multiple_branches = bool(
            gl_setup and getattr(gl_setup, 'enable_multiple_branches', False)
        )
    except Exception:
        pass

    return {
        'assignedBranch': _serialize_branch(getattr(user, 'global_dimension_1', None)),
        'enableMultipleBranches': enable_multiple_branches,
        'canSwitchBranch': getattr(user, 'can_switch_branch', True),
    }


def _company_module_context(company) -> dict:
    enabled_modules: list[str] = []
    plan_name = None
    plan_branches = None
    if company is None:
        return {
            "enabledModules": enabled_modules,
            "planName": plan_name,
            "planBranches": plan_branches,
        }

    enabled_modules = list(company.enabled_modules or [])
    try:
        sub = company.subscription
        plan_name = sub.plan
        plan_key = sub.plan or ""
        pricing_name = company.PLAN_NAME_TO_PRICING.get(plan_key, plan_key)
        if not pricing_name and sub.status in ("trial", "active"):
            pricing_name = "Starter"
        from django_tenants.utils import schema_context
        from company.models import Pricing

        with schema_context("public"):
            pricing = Pricing.objects.filter(name=pricing_name, is_active=True).first()
            if pricing:
                feats = pricing.features or {}
                if isinstance(feats, dict):
                    plan_branches = feats.get("branches")
    except Exception:
        pass

    return {
        "enabledModules": enabled_modules,
        "planName": plan_name,
        "planBranches": plan_branches,
    }


def build_auth_session_payload(user, request=None) -> dict:
    from authentication.impersonation import impersonation_from_request
    from authentication.models import UserPersonalization
    from utils.page_access import filter_nav_items_by_user_permissions

    company = _resolve_company_from_connection()
    module_ctx = _company_module_context(company)

    personalization = UserPersonalization.get_or_create_for_user(user)
    profile = personalization.role
    rc_page = personalization.resolve_role_centre_page()
    role_name = profile.description if profile else ''
    if not role_name:
        first_role = user.roles.filter(is_active=True).first()
        if first_role:
            role_name = first_role.name

    avatar_url = None
    if user.avatar:
        try:
            relative = user.avatar.url
            avatar_url = request.build_absolute_uri(relative) if request else relative
        except (ValueError, AttributeError):
            avatar_url = None

    payload = {
        'user': {
            'id': user.id,
            'email': user.email,
            'fullName': user.full_name or user.username,
            'username': user.username,
            'role': role_name,
            'avatarUrl': avatar_url,
        },
        'profile': (
            {
                'code': profile.code,
                'description': profile.description,
            }
            if profile
            else None
        ),
        'company': serialize_company(request),
        'roleCentrePageId': rc_page.page_id if rc_page else None,
        'navItems': filter_nav_items_by_user_permissions(
            _filter_nav_by_modules(
                serialize_rc_nav_items(rc_page),
                module_ctx["enabledModules"],
            ),
            user,
        ),
        'branch': _branch_config_for_user(user),
        **module_ctx,
    }

    impersonation = impersonation_from_request(request, user)
    if impersonation:
        payload['impersonation'] = impersonation

    return payload


def _filter_nav_by_modules(nav_items, enabled_modules):
    from utils.page_modules import filter_nav_items_by_enabled_modules

    return filter_nav_items_by_enabled_modules(nav_items, enabled_modules)
