"""
BC-style page access helpers for nav and Application Profile filtering.
"""

from __future__ import annotations

from typing import Any

from permissions.table_permissions import SOURCE_TABLE_PAGE_ALIASES

# Nav targets that should show when the user can access a related page (BC-style).
NAV_PAGE_ALIASES: dict[str, list[str]] = {
    'PostedPurchaseInvoiceList': ['PurchaseInvoiceList', 'PostedPurchaseInvoice'],
    'PostedSalesInvoiceList': ['SalesInvoiceList', 'PostedSalesInvoice'],
    'PaymentHistoryList': ['ExpenseList', 'ExpenseCard'],
}


def _user_bypasses_page_checks(user: Any) -> bool:
    if getattr(user, 'is_superuser', False):
        return True
    from permissions.services.super_permission_set import user_has_super_permission

    return user_has_super_permission(user)


def page_permissions_for_user(user: Any) -> dict[str, dict[str, bool]]:
    from authentication.permission_claims import page_permissions_from_user_groups

    return page_permissions_from_user_groups(user)


def _perms_grant_access(perms: dict | None) -> bool:
    if not isinstance(perms, dict):
        return False
    return any(perms.get(k) for k in ('read', 'insert', 'modify', 'delete'))


def user_has_any_page_access(
    user: Any,
    page_name: str,
    page_permissions: dict[str, dict[str, bool]] | None = None,
) -> bool:
    """True when the user may open a page (any CRUD flag or object permission)."""
    if _user_bypasses_page_checks(user):
        return True

    page_name = (page_name or '').strip()
    if not page_name:
        return True

    if page_permissions is None:
        page_permissions = page_permissions_for_user(user)

    if _perms_grant_access(page_permissions.get(page_name)):
        return True

    for alias in NAV_PAGE_ALIASES.get(page_name, []):
        if _perms_grant_access(page_permissions.get(alias)):
            return True

    for aliases in SOURCE_TABLE_PAGE_ALIASES.values():
        if page_name not in aliases:
            continue
        for alias in aliases:
            if _perms_grant_access(page_permissions.get(alias)):
                return True

    from pages.bc_page_ids import resolve_page_object_id

    oid = resolve_page_object_id(page_name)
    if oid is not None:
        allowed, _ = user.check_object_permission(oid, 'read')
        if allowed:
            return True

    return False


def filter_nav_items_by_user_permissions(
    nav_items: list[dict],
    user: Any,
    page_permissions: dict[str, dict[str, bool]] | None = None,
) -> list[dict]:
    """Drop sidebar nav entries the user cannot read (Layer 2 — BC-style hide)."""
    if _user_bypasses_page_checks(user):
        return nav_items

    if page_permissions is None:
        page_permissions = page_permissions_for_user(user)

    filtered: list[dict] = []
    for item in nav_items:
        target = (item.get('targetPageName') or '').strip()
        if user_has_any_page_access(user, target, page_permissions):
            filtered.append(item)
    return filtered


def _profile_nav_targets(role_centre_page) -> list[str]:
    if role_centre_page is None:
        return []
    from pages.models import PageAction

    return list(
        PageAction.objects.filter(
            page=role_centre_page,
            action_type='NavItem',
            visible=True,
        )
        .order_by('action_id')
        .values_list('action_relative_url', flat=True)
    )


def _user_may_select_profile(
    user: Any,
    profile,
    page_permissions: dict[str, dict[str, bool]] | None = None,
) -> bool:
    """Profile is selectable when the user can open Home or any nav page on that RC."""
    if _user_bypasses_page_checks(user):
        return True

    targets = _profile_nav_targets(getattr(profile, 'role_centre_page', None))
    if not targets:
        return False

    for target in targets:
        if user_has_any_page_access(user, (target or '').strip(), page_permissions):
            return True
    return False


def filter_application_profiles_for_user(
    qs,
    user: Any,
    *,
    current_profile_id: int | None = None,
):
    """
    Restrict Role Centre choices on User Settings to profiles the user may use.
    Always retains the current profile so users are never stuck on an invalid value.
    """
    if _user_bypasses_page_checks(user):
        return qs

    page_permissions = page_permissions_for_user(user)
    allowed_ids: set[int] = set()
    if current_profile_id:
        allowed_ids.add(current_profile_id)

    for profile in qs.select_related('role_centre_page'):
        if _user_may_select_profile(user, profile, page_permissions):
            allowed_ids.add(profile.pk)

    if not allowed_ids:
        return qs.none()
    return qs.filter(pk__in=list(allowed_ids))
