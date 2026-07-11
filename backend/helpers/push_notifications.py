"""
Firebase Cloud Messaging helpers for backend-triggered push notifications.
"""

from __future__ import annotations

import json
import logging
from typing import Iterable

from django.conf import settings

logger = logging.getLogger(__name__)

_firebase_app = None


def _get_firebase_app():
    global _firebase_app
    if _firebase_app is not None:
        return _firebase_app

    import firebase_admin
    from firebase_admin import credentials

    cred_path = getattr(settings, "FIREBASE_CREDENTIALS_PATH", "") or ""
    cred_json = getattr(settings, "FIREBASE_CREDENTIALS_JSON", "") or ""

    if cred_json:
        cred = credentials.Certificate(json.loads(cred_json))
    elif cred_path:
        cred = credentials.Certificate(cred_path)
    else:
        raise RuntimeError(
            "Firebase credentials not configured. Set FIREBASE_CREDENTIALS_PATH "
            "or FIREBASE_CREDENTIALS_JSON in environment."
        )

    try:
        _firebase_app = firebase_admin.get_app()
    except ValueError:
        _firebase_app = firebase_admin.initialize_app(cred)
    return _firebase_app


def send_push_to_tokens(
    tokens: Iterable[str],
    *,
    title: str,
    body: str,
    data: dict | None = None,
) -> dict:
    """
    Send the same notification to one or more FCM device tokens.
    Returns counts: {success, failure, invalid_tokens}.
    """
    token_list = [t.strip() for t in tokens if t and str(t).strip()]
    if not token_list:
        return {"success": 0, "failure": 0, "invalid_tokens": []}

    from firebase_admin import messaging

    _get_firebase_app()

    notification = messaging.Notification(title=title, body=body)
    payload_data = {str(k): str(v) for k, v in (data or {}).items()}

    message = messaging.MulticastMessage(
        notification=notification,
        data=payload_data,
        tokens=token_list,
        android=messaging.AndroidConfig(
            priority="high",
            notification=messaging.AndroidNotification(
                channel_id="zentro-default",
            ),
        ),
    )

    response = messaging.send_each_for_multicast(message)
    invalid_tokens: list[str] = []
    for idx, send_response in enumerate(response.responses):
        if send_response.success:
            continue
        exc = send_response.exception
        code = getattr(exc, "code", "") or str(exc)
        if "registration-token-not-registered" in str(code).lower():
            invalid_tokens.append(token_list[idx])
        logger.warning("FCM send failed for token index %s: %s", idx, exc)

    return {
        "success": response.success_count,
        "failure": response.failure_count,
        "invalid_tokens": invalid_tokens,
    }


def deactivate_invalid_tokens(invalid_tokens: list[str]) -> int:
    if not invalid_tokens:
        return 0
    from authentication.models import DevicePushToken

    updated = DevicePushToken.objects.filter(fcm_token__in=invalid_tokens).update(
        is_active=False
    )
    return updated


def send_push_to_users(
    user_ids: Iterable[int],
    *,
    title: str,
    body: str,
    data: dict | None = None,
) -> dict:
    """Send push to all active tokens for the given user IDs (current tenant schema)."""
    from authentication.models import DevicePushToken

    tokens = list(
        DevicePushToken.objects.filter(
            user_id__in=list(user_ids),
            is_active=True,
        ).values_list("fcm_token", flat=True)
    )
    result = send_push_to_tokens(tokens, title=title, body=body, data=data)
    if result["invalid_tokens"]:
        result["deactivated"] = deactivate_invalid_tokens(result["invalid_tokens"])
    return result
