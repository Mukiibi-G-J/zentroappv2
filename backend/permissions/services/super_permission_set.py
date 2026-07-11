"""
Business Central-style SUPER permission set.

SUPER grants unrestricted access to all application objects that require
permission, and acts as a runtime bypass for any object check (including
objects registered after the set was last synced).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from base.models import Objects
from permissions.constants import FULL_OBJECT_PERMISSIONS, SUPER_PERMISSION_SET_CODE
from permissions.models import PermissionSet, PermissionSetLine

if TYPE_CHECKING:
    from authentication.models import CustomUser

SUPER_DEFAULTS = {
    "name": "Super",
    "description": (
        "Provides full unrestricted access to all business data and all "
        "application functionality, just like Business Central SUPER."
    ),
    "is_active": True,
}


def user_has_super_permission(user: "CustomUser | None") -> bool:
    """True when the user belongs to a group with the active SUPER permission set."""
    if user is None:
        return False
    if getattr(user, "is_superuser", False):
        return True

    return user.user_groups.filter(is_active=True).filter(
        permission_sets__code=SUPER_PERMISSION_SET_CODE,
        permission_sets__is_active=True,
    ).exists()


def permission_objects_queryset():
    """Objects that should receive explicit permission lines."""
    return Objects.objects.filter(requires_permission=True, is_active=True)


def ensure_super_permission_set(*, update: bool = False) -> tuple[PermissionSet, dict[str, int]]:
    """
    Create or refresh the SUPER permission set with RIMDX on all secured objects.

    Returns (permission_set, stats dict).
    """
    permission_set, created = PermissionSet.objects.get_or_create(
        code=SUPER_PERMISSION_SET_CODE,
        defaults=SUPER_DEFAULTS,
    )

    stats = {"created_set": int(created), "lines_created": 0, "lines_updated": 0}

    if not created and not update:
        return permission_set, stats

    if not created:
        permission_set.name = SUPER_DEFAULTS["name"]
        permission_set.description = SUPER_DEFAULTS["description"]
        permission_set.is_active = True
        permission_set.save(
            update_fields=["name", "description", "is_active", "updated_at"]
        )

    objects = list(permission_objects_queryset().only("pk"))
    if update or created:
        PermissionSetLine.objects.filter(permissionset=permission_set).delete()
        lines = [
            PermissionSetLine(
                permissionset=permission_set,
                application_object_id=obj.pk,
                **FULL_OBJECT_PERMISSIONS,
            )
            for obj in objects
        ]
        PermissionSetLine.objects.bulk_create(lines, batch_size=500)
        stats["lines_created"] = len(lines)
        return permission_set, stats

    existing_object_ids = set(
        PermissionSetLine.objects.filter(permissionset=permission_set).values_list(
            "application_object_id", flat=True
        )
    )
    missing = [obj for obj in objects if obj.pk not in existing_object_ids]
    if missing:
        PermissionSetLine.objects.bulk_create(
            [
                PermissionSetLine(
                    permissionset=permission_set,
                    application_object_id=obj.pk,
                    **FULL_OBJECT_PERMISSIONS,
                )
                for obj in missing
            ],
            batch_size=500,
        )
        stats["lines_created"] = len(missing)

    return permission_set, stats


def assign_super_to_admin_group() -> tuple[Any | None, bool]:
    """
    Assign SUPER to the Admin user group (creates assignment if missing).

    Returns (admin_group, assigned_now).
    """
    from authentication.models import UserGroup

    admin_group = UserGroup.objects.filter(code="Admin", is_active=True).first()
    if admin_group is None:
        return None, False

    permission_set = PermissionSet.objects.filter(
        code=SUPER_PERMISSION_SET_CODE, is_active=True
    ).first()
    if permission_set is None:
        return admin_group, False

    if admin_group.permission_sets.filter(pk=permission_set.pk).exists():
        return admin_group, False

    admin_group.permission_sets.add(permission_set)
    return admin_group, True


def full_page_permissions_for_user(user: "CustomUser") -> dict[str, dict[str, bool]]:
    """All page CRUD flags granted — used for JWT when user has SUPER."""
    page_permissions: dict[str, dict[str, bool]] = {}
    for page_name in Objects.objects.filter(
        object_type="Page",
        requires_permission=True,
        is_active=True,
    ).values_list("object_name", flat=True):
        page_permissions[page_name] = {
            "read": True,
            "insert": True,
            "modify": True,
            "delete": True,
        }
    return page_permissions
