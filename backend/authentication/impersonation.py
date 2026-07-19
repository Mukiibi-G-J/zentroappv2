"""Helpers for debug_admin Login-as-user impersonation."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response

IMPERSONATION_ACCESS_LIFETIME = timedelta(hours=2)


def is_impersonating(request) -> bool:
    auth = getattr(request, "auth", None)
    if auth is None:
        return False
    try:
        return bool(auth.get("impersonation"))
    except (AttributeError, TypeError):
        return False


def impersonation_forbidden_response() -> Response:
    return Response(
        {
            "error": "Action not allowed while impersonating",
            "detail": "Exit impersonation before performing this admin action.",
        },
        status=status.HTTP_403_FORBIDDEN,
    )


def client_ip(request) -> str | None:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip() or None
    return request.META.get("REMOTE_ADDR") or None


def client_user_agent(request) -> str:
    return (request.META.get("HTTP_USER_AGENT") or "")[:512]


def impersonation_meta_for_tokens(
    *,
    target,
    impersonator,
) -> dict[str, Any]:
    return {
        "active": True,
        "target": {
            "id": target.id,
            "fullName": target.full_name or target.username,
            "username": target.username,
            "email": target.email,
        },
        "impersonator": {
            "id": impersonator.id,
            "username": impersonator.username,
        },
    }


def impersonation_from_request(request, user=None) -> dict[str, Any] | None:
    """Build session impersonation block from JWT claims when present."""
    if not is_impersonating(request):
        return None

    auth = request.auth
    target_user = user or getattr(request, "user", None)
    target = {
        "id": getattr(target_user, "id", None),
        "fullName": getattr(target_user, "full_name", None)
        or getattr(target_user, "username", "")
        or "",
        "username": getattr(target_user, "username", "") or "",
        "email": getattr(target_user, "email", "") or "",
    }
    try:
        impersonator = {
            "id": auth.get("impersonator_id"),
            "username": auth.get("impersonator_username") or "",
        }
    except (AttributeError, TypeError):
        impersonator = {"id": None, "username": ""}

    return {
        "active": True,
        "target": target,
        "impersonator": impersonator,
    }


def mint_impersonation_tokens(*, target, impersonator):
    """Return (refresh, access) JWT pair with impersonation claims."""
    from authentication.serializers import AuthTokenViewSerializer

    refresh = AuthTokenViewSerializer.get_token(target)
    refresh["impersonation"] = True
    refresh["impersonator_id"] = impersonator.id
    refresh["impersonator_username"] = impersonator.username

    access = refresh.access_token
    access["impersonation"] = True
    access["impersonator_id"] = impersonator.id
    access["impersonator_username"] = impersonator.username
    access.set_exp(from_time=timezone.now(), lifetime=IMPERSONATION_ACCESS_LIFETIME)

    return refresh, access


def create_impersonation_audit(*, actor, target, request):
    from django.db import connection
    from django_tenants.utils import schema_context
    from authentication.models import ImpersonationAuditLog

    schema_name = getattr(connection, "schema_name", None) or "public"
    with schema_context("public"):
        return ImpersonationAuditLog.objects.create(
            schema_name=schema_name,
            actor_id=actor.id,
            actor_username=actor.username,
            target_id=target.id,
            target_username=target.username,
            ip_address=client_ip(request),
            user_agent=client_user_agent(request),
        )


def close_open_impersonation_audits(*, actor_id: int, target_id: int) -> int:
    """Mark open audit rows as ended for this actor→target pair in the current tenant."""
    from django.db import connection
    from django_tenants.utils import schema_context
    from authentication.models import ImpersonationAuditLog

    schema_name = getattr(connection, "schema_name", None) or "public"
    with schema_context("public"):
        return ImpersonationAuditLog.objects.filter(
            schema_name=schema_name,
            actor_id=actor_id,
            target_id=target_id,
            ended_at__isnull=True,
        ).update(ended_at=timezone.now())
