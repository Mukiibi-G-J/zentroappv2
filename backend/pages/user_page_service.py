"""Page-engine hooks for CustomUser (Users list/card pages)."""

from __future__ import annotations

import uuid

from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils import timezone

from authentication.models import UserSetup

User = get_user_model()

DEBUG_USER_EMAILS = {"mukiibijoseph19@gmail.com"}
DEBUG_USER_USERNAMES = {"debug_admin"}

PASSWORD_MASK = "••••••••"


def normalize_full_name(value: str) -> str:
    return (value or "").strip().upper()


def normalize_email(value: str) -> str:
    return (value or "").strip().lower()


def users_queryset():
    return (
        User.objects.filter(terminated=False)
        .exclude(Q(email__in=DEBUG_USER_EMAILS) | Q(username__in=DEBUG_USER_USERNAMES))
        .order_by("username", "email")
    )


def get_user_by_page_id(system_id: str):
    if not system_id:
        return None
    user = User.objects.filter(system_id=system_id).first()
    if user:
        return user
    if str(system_id).isdigit():
        return User.objects.filter(pk=int(system_id)).first()
    return None


def serialize_user_field(user, field_name: str):
    if field_name == "password":
        return PASSWORD_MASK if user.password else ""
    if field_name == "assigned_user_groups":
        return format_user_groups_display(user)
    return getattr(user, field_name, None)


def format_user_groups_display(user) -> str:
    groups = user.user_groups.filter(is_active=True).order_by("code")
    if not groups.exists():
        return ""
    return ", ".join(f"{group.code} ({group.name})" for group in groups)


def user_effective_permission_sets(user):
    """
    Permission sets inherited from the user's active groups.

    Returns list of (PermissionSet, group_codes) sorted by permission set code.
    """
    if user is None:
        return []

    from permissions.models import PermissionSet

    grouped: dict[int, tuple[PermissionSet, list[str]]] = {}
    for group in user.user_groups.filter(is_active=True).prefetch_related(
        "permission_sets",
    ):
        for perm_set in group.permission_sets.filter(is_active=True):
            entry = grouped.get(perm_set.pk)
            if entry is None:
                grouped[perm_set.pk] = (perm_set, [group.code])
            elif group.code not in entry[1]:
                entry[1].append(group.code)

    rows = list(grouped.values())
    rows.sort(key=lambda item: item[0].code)
    for perm_set, codes in rows:
        codes.sort()
    return rows


def patch_user_field(user, field_name: str, value, *, creating: bool = False):
    if field_name == "password":
        if value and value != PASSWORD_MASK:
            user.set_password(str(value))
            user.save(update_fields=["password"])
        return user

    if field_name == "full_name":
        value = normalize_full_name(str(value))
    elif field_name == "email":
        value = normalize_email(str(value))
    elif field_name == "username" and value:
        value = str(value).strip()

    setattr(user, field_name, value)

    if creating and field_name == "email" and value and not user.username:
        base = value.split("@")[0] or "user"
        candidate = base
        n = 1
        while User.objects.filter(username=candidate).exclude(pk=user.pk).exists():
            candidate = f"{base}{n}"
            n += 1
        user.username = candidate

    if creating and not user.phone_number:
        user.phone_number = f"PENDING_{uuid.uuid4().hex[:10]}"

    user.save()
    return user


def create_user_for_page(system_id: str, field_name: str, value):
    from django.db import connection

    company = getattr(connection, "tenant", None)
    if company:
        effective_max = company.get_effective_max_users()
        current_count = (
            User.objects.filter(is_active=True, terminated=False)
            .exclude(username__in=DEBUG_USER_USERNAMES)
            .count()
        )
        if current_count >= effective_max:
            raise ValueError(
                f"User limit reached ({current_count}/{effective_max}). "
                "Upgrade your plan or deactivate another user."
            )

    user = User(
        system_id=system_id,
        is_active=True,
        must_change_password=True,
        email=f"pending_{system_id[:12]}@zentro.pending",
        username=f"user_{uuid.uuid4().hex[:8]}",
        full_name="NEW USER",
        phone_number=f"PENDING_{uuid.uuid4().hex[:10]}",
    )
    user = patch_user_field(user, field_name, value, creating=True)
    UserSetup.get_or_create_for_user(user)
    return user, True


def update_user_for_page(user, field_name: str, value):
    if field_name == "email" and user.pk:
        raise ValueError("Email cannot be changed after the user is created.")
    patch_user_field(user, field_name, value, creating=False)
    return user, False


def soft_delete_user(user):
    user.is_active = False
    user.terminated = True
    user.token_valid_after = timezone.now()
    user.save(update_fields=["is_active", "terminated", "token_valid_after"])
