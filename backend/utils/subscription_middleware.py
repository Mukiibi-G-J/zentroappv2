"""
Subscription Check Middleware

Blocks API requests when the tenant's subscription/trial has expired.
Returns 402 Payment Required (not 403) so the frontend redirects to the subscription page
without triggering logout or permission modal. User stays logged in.
"""

import logging
import re

from django.http import JsonResponse
from django.db import connection
from django.utils import timezone
from django_tenants.utils import schema_context, get_public_schema_name

logger = logging.getLogger(__name__)

# Paths that bypass subscription checks (auth, subscription page, admin, static)
BYPASS_PATTERNS = [
    re.compile(r"^/api/app/"),
    re.compile(r"^/api/auth/"),
    re.compile(r"^/api/company/subscription"),
    re.compile(r"^/api/company/subscriptions"),
    re.compile(r"^/api/company/pricing-plans"),  # subscription page needs plans
    re.compile(r"^/api/company/add-ons"),
    re.compile(r"^/api/company/starter-"),  # starter pack flow
    re.compile(r"^/api/restaurant/public-menu"),  # guest QR digital menu
    re.compile(r"^/admin/"),
    re.compile(r"^/static/"),
    re.compile(r"^/media/"),
]


def _should_bypass(path: str) -> bool:
    """Return True if the path should bypass subscription checks."""
    for pattern in BYPASS_PATTERNS:
        if pattern.search(path):
            return True
    return False


class SubscriptionCheckMiddleware:
    """
    Middleware to block requests when the tenant's subscription has expired.
    Must run after TenantMainMiddleware (tenant must be set).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Skip OPTIONS (CORS preflight)
        if request.method == "OPTIONS":
            return self.get_response(request)

        # Skip bypass paths
        if _should_bypass(request.path):
            return self.get_response(request)

        # Skip if no tenant (public schema - e.g. main domain admin)
        if not hasattr(connection, "tenant") or not connection.tenant:
            return self.get_response(request)

        tenant = connection.tenant
        public_schema = get_public_schema_name()
        if tenant.schema_name == public_schema:
            return self.get_response(request)

        # Block when no subscription or past grace (today >= access lock date)
        try:
            with schema_context(public_schema):
                from company.models import Subscription
                from company.subscription_grace import (
                    expiry_detail_for_kind,
                    expiry_kind_for_subscription,
                )

                subscription = (
                    Subscription.objects.select_related("company")
                    .filter(company_id=tenant.pk)
                    .first()
                )

                if subscription is None:
                    return JsonResponse(
                        {
                            "code": "subscription_expired",
                            "expiry_kind": "trial",
                            "detail": "No active subscription. Please proceed to the subscription page to continue.",
                            "lock_date": None,
                        },
                        status=402,
                    )

                # Fresh company row so subscription_grace_days edits in admin apply immediately
                # (avoids stale FK cache on long-lived tenant instances).
                subscription.company.refresh_from_db(fields=["subscription_grace_days", "grace_reminder_offsets"])

                if not subscription.is_active():
                    kind = expiry_kind_for_subscription(subscription)
                    lock_d = subscription.access_lock_date()
                    return JsonResponse(
                        {
                            "code": "subscription_expired",
                            "expiry_kind": kind,
                            "detail": expiry_detail_for_kind(kind),
                            "lock_date": lock_d.isoformat() if lock_d else None,
                        },
                        status=402,
                    )
        except Exception:
            logger.exception(
                "SubscriptionCheckMiddleware: error checking subscription for tenant pk=%s; "
                "request allowed (fail-open). Fix the underlying error or APIs stay open.",
                getattr(tenant, "pk", None),
            )

        return self.get_response(request)
