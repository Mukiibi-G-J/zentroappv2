"""
Helpers for SPA permission claims on JWT (page permissions + visible modules).

When a group's default Role only exposes "profile" (e.g. base "User") but the group
still has Permission Sets granting Page access (e.g. RESTAURANT_FOH), the sidebar uses
role_center_modules before page checks — so we merge in module codes derived from Page
objects' app_label for any Page the user can access.
"""

from __future__ import annotations

from typing import Any


def page_permissions_from_user_groups(user: Any) -> dict[str, dict[str, bool]]:
    """Aggregate CRUD flags for Pages from permission sets assigned via user groups."""
    from permissions.models import PermissionSetLine
    from permissions.services.super_permission_set import (
        full_page_permissions_for_user,
        user_has_super_permission,
    )

    if user_has_super_permission(user):
        return full_page_permissions_for_user(user)

    page_permissions: dict[str, dict[str, bool]] = {}

    for group in user.user_groups.filter(is_active=True):
        for perm_set in group.permission_sets.filter(is_active=True):
            page_lines = perm_set.permissionsetline_set.filter(
                application_object__object_type="Page",
            ).select_related("application_object")

            for line in page_lines:
                page_name = line.application_object.object_name

                if page_name not in page_permissions:
                    page_permissions[page_name] = {
                        "read": False,
                        "insert": False,
                        "modify": False,
                        "delete": False,
                    }

                page_permissions[page_name]["read"] = (
                    page_permissions[page_name]["read"] or line.read_permission
                )
                page_permissions[page_name]["insert"] = (
                    page_permissions[page_name]["insert"] or line.insert_permission
                )
                page_permissions[page_name]["modify"] = (
                    page_permissions[page_name]["modify"] or line.modify_permission
                )
                page_permissions[page_name]["delete"] = (
                    page_permissions[page_name]["delete"] or line.delete_permission
                )

    return page_permissions


def infer_module_codes_from_page_permissions(
    page_permissions: dict[str, dict[str, bool]] | None,
) -> set[str]:
    """Return distinct Objects.app_label for Pages where the user has any CRUD flag."""
    if not page_permissions:
        return set()

    eligible: list[str] = []
    for page_name, perms in page_permissions.items():
        if not isinstance(perms, dict):
            continue
        if any(perms.get(k) for k in ("read", "insert", "modify", "delete")):
            eligible.append(page_name)

    if not eligible:
        return set()

    from base.models import Objects

    labels = Objects.objects.filter(
        object_type="Page",
        object_name__in=eligible,
    ).values_list("app_label", flat=True)

    return {label for label in labels if label and str(label).strip()}


def merge_role_center_modules_with_page_derived_visible_modules(
    role_center_modules: list[str],
    page_permissions: dict[str, dict[str, bool]],
) -> list[str]:
    """Union role-center modules with module codes implied by granted page permissions."""
    inferred = infer_module_codes_from_page_permissions(page_permissions)
    return list(set(role_center_modules) | inferred)
