"""Who may use restaurant PIN / device registration (aligned with JWT role_center_modules)."""

from __future__ import annotations

from datetime import timedelta

from django.utils import timezone

RESTAURANT_PIN_VALIDITY_DAYS = 90


def _role_center_modules_for_user(user) -> set:
    """Effective SPA module codes including Page-derived visibility (JWT-aligned)."""
    modules: list = []
    all_roles = []

    for group in user.user_groups.filter(is_active=True):
        if group.default_profile and group.default_profile.is_active:
            all_roles.append(group.default_profile)

    for role in user.roles.filter(is_active=True):
        if role not in all_roles:
            all_roles.append(role)

    role_names = [role.name for role in all_roles]
    for role in all_roles:
        if role.role_center and role.role_center.is_active and role.role_center.modules:
            modules.extend(role.role_center.modules)

    if user.is_superuser or "Administrator" in role_names:
        try:
            from django.db import connection

            tenant = getattr(connection, "tenant", None)
            if tenant is not None:
                enabled = getattr(tenant, "enabled_modules", None) or []
                modules = list(set(modules) | set(enabled))
        except Exception:
            pass

    base = list(set(modules))
    try:
        from authentication.permission_claims import (
            merge_role_center_modules_with_page_derived_visible_modules,
            page_permissions_from_user_groups,
        )

        page_perm = page_permissions_from_user_groups(user)
        merged = merge_role_center_modules_with_page_derived_visible_modules(base, page_perm)
        return set(merged)
    except Exception:
        return set(base)


def user_can_use_restaurant_pin(user, tenant) -> bool:
    """
    True if company has restaurant module and user has restaurant in role-center visibility.
    `tenant` is the django-tenants company model (connection.tenant).
    """
    if not tenant:
        return False
    if not getattr(tenant, "has_module", lambda _: False)("restaurant"):
        return False
    if user.is_superuser:
        return True
    mods = _role_center_modules_for_user(user)
    return "restaurant" in mods


def restaurant_pin_is_expired(user) -> bool:
    """True if PIN must be renewed (90 days since restaurant_pin_set_at)."""
    if not user.restaurant_pin_hash:
        return False
    if not user.restaurant_pin_set_at:
        return True
    cutoff = user.restaurant_pin_set_at + timedelta(days=RESTAURANT_PIN_VALIDITY_DAYS)
    return timezone.now() >= cutoff
