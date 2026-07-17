"""
Assign ApplicationProfile (Role Centre) from legacy Role / UserGroup access.

Used after restore so we do not give every user BUSINESS-MGR.
"""

from __future__ import annotations

from typing import Any

# Legacy RoleCenter.code (V1) → V2 ApplicationProfile.code
LEGACY_ROLE_CENTER_TO_PROFILE: dict[str, str] = {
    'ADMIN_CENTER': 'BUSINESS-MGR',
    'MANAGER_CENTER': 'OPERATIONS-MGR',
    'CASHIER_CENTER': 'CASHIER',
    'INVENTORY_CENTER': 'PHARMACIST',
    'USER_CENTER': 'CASHIER',
}

# UserGroup.code → ApplicationProfile.code (when no Role.role_center)
USER_GROUP_TO_PROFILE: dict[str, str] = {
    'ADMIN': 'BUSINESS-MGR',
    'MANAGER': 'OPERATIONS-MGR',
    'OPERATIONS_MANAGER': 'OPERATIONS-MGR',
    'DISPENSER': 'CASHIER',
    'CASHIER': 'CASHIER',
    'INVENTORY_MANAGER': 'WAREHOUSE',
    'WAREHOUSE': 'WAREHOUSE',
    'PHARCIST': 'PHARMACIST',  # historical typo in primewise data
    'PHARMACIST': 'PHARMACIST',
    'SALES': 'SALES-MGR',
    'SALES_MANAGER': 'SALES-MGR',
    'ACCOUNTANT': 'ACCOUNTANT',
    'REST_MGR': 'REST-MGR',
    'REST_FOH': 'REST-FOH',
    'REST_KITCHEN': 'REST-KITCHEN',
}

# When a user is in several groups, prefer the more specific group first.
_GROUP_CODE_PRIORITY: tuple[str, ...] = (
    'ADMIN',
    'PHARCIST',
    'PHARMACIST',
    'INVENTORY_MANAGER',
    'WAREHOUSE',
    'DISPENSER',
    'CASHIER',
    'SALES',
    'SALES_MANAGER',
    'ACCOUNTANT',
    'REST_MGR',
    'REST_FOH',
    'REST_KITCHEN',
    'MANAGER',
    'OPERATIONS_MANAGER',
)

# When choosing among profile codes (from Role Centres), prefer broader admin profiles.
_PROFILE_PRIORITY: tuple[str, ...] = (
    'DEBUG-ADMIN',
    'BUSINESS-MGR',
    'OPERATIONS-MGR',
    'ACCOUNTANT',
    'SALES-MGR',
    'WAREHOUSE',
    'PHARMACIST',
    'REST-MGR',
    'CASHIER',
    'REST-FOH',
    'REST-KITCHEN',
)


def _priority_key(profile_code: str) -> tuple[int, str]:
    try:
        return (_PROFILE_PRIORITY.index(profile_code), profile_code)
    except ValueError:
        return (len(_PROFILE_PRIORITY), profile_code)


def _group_priority_key(group_code: str) -> tuple[int, str]:
    try:
        return (_GROUP_CODE_PRIORITY.index(group_code), group_code)
    except ValueError:
        return (len(_GROUP_CODE_PRIORITY), group_code)


def _is_debug_admin_user(user: Any) -> bool:
    from django.conf import settings

    debug_username = getattr(settings, 'DEBUG_ADMIN_USERNAME', 'debug_admin')
    debug_email = getattr(settings, 'DEBUG_ADMIN_EMAIL', '')
    username = (getattr(user, 'username', None) or '').strip()
    email = (getattr(user, 'email', None) or '').strip().lower()
    if username and username == debug_username:
        return True
    if debug_email and email and email == debug_email.strip().lower():
        return True
    return False


def resolve_application_profile_code_for_user(user: Any) -> str | None:
    """
    Pick the best ApplicationProfile.code for a user from old Role Centres / groups.

    debug_admin → DEBUG-ADMIN (full Setup nav).
    Other superusers → BUSINESS-MGR.
    Prefer Role.role_center when present; otherwise UserGroup codes.
    Returns None when nothing maps (do not invent BUSINESS-MGR).
    """
    if _is_debug_admin_user(user):
        return 'DEBUG-ADMIN'
    if getattr(user, 'is_superuser', False):
        return 'BUSINESS-MGR'

    role_candidates: list[str] = []
    roles = getattr(user, 'roles', None)
    if roles is not None:
        for role in roles.select_related('role_center').all():
            rc = getattr(role, 'role_center', None)
            code = getattr(rc, 'code', None) if rc is not None else None
            if code and code in LEGACY_ROLE_CENTER_TO_PROFILE:
                role_candidates.append(LEGACY_ROLE_CENTER_TO_PROFILE[code])

    if role_candidates:
        return sorted(set(role_candidates), key=_priority_key)[0]

    group_codes: list[str] = []
    groups = getattr(user, 'user_groups', None)
    if groups is not None:
        for group in groups.filter(is_active=True):
            gcode = (getattr(group, 'code', None) or '').strip().upper()
            if gcode in USER_GROUP_TO_PROFILE:
                group_codes.append(gcode)

    if not group_codes:
        return None

    best_group = sorted(set(group_codes), key=_group_priority_key)[0]
    return USER_GROUP_TO_PROFILE[best_group]


def resolve_application_profile_for_user(user: Any):
    from authentication.models import ApplicationProfile

    code = resolve_application_profile_code_for_user(user)
    if not code:
        return None
    return ApplicationProfile.objects.filter(code=code).first()


def assign_application_profiles(
    *,
    only_missing: bool = False,
    force: bool = False,
) -> dict[str, int]:
    """
    Write UserPersonalization.role from legacy access.

    only_missing: only set when role is null
    force: overwrite every user's profile (including existing)
    """
    from authentication.models import ApplicationProfile, CustomUser, UserPersonalization

    stats = {
        'users': 0,
        'updated': 0,
        'skipped': 0,
        'unmapped': 0,
        'missing_profile': 0,
    }
    profiles = {p.code: p for p in ApplicationProfile.objects.all()}

    for user in CustomUser.objects.all().prefetch_related('roles__role_center', 'user_groups'):
        stats['users'] += 1
        code = resolve_application_profile_code_for_user(user)
        personalization, _ = UserPersonalization.objects.get_or_create(
            user=user,
            defaults={
                'created_by': user.email or user.username,
                'modified_by': user.email or user.username,
            },
        )

        if not code:
            stats['unmapped'] += 1
            if force and personalization.role_id:
                personalization.role = None
                personalization.modified_by = 'assign_application_profiles'
                personalization.save(update_fields=['role', 'modified_by'])
                stats['updated'] += 1
            else:
                stats['skipped'] += 1
            continue

        profile = profiles.get(code)
        if profile is None:
            stats['missing_profile'] += 1
            stats['skipped'] += 1
            continue

        if only_missing and personalization.role_id:
            stats['skipped'] += 1
            continue
        if not force and not only_missing and personalization.role_id == profile.pk:
            stats['skipped'] += 1
            continue
        if not force and personalization.role_id and not only_missing:
            # overwrite wrong blanket BUSINESS-MGR when force not set? caller uses force=True after restore
            pass

        if personalization.role_id == profile.pk:
            stats['skipped'] += 1
            continue

        personalization.role = profile
        personalization.modified_by = 'assign_application_profiles'
        personalization.save(update_fields=['role', 'modified_by'])
        stats['updated'] += 1

    return stats
