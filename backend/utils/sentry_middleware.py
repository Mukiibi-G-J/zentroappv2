"""Attach tenant and user context to Sentry events."""

from django.db import connection

import sentry_sdk


class SentryTenantMiddleware:
    """Set tenant schema and authenticated user on the current Sentry scope."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        scope = sentry_sdk.get_current_scope()

        tenant = getattr(request, "tenant", None) or getattr(connection, "tenant", None)
        if tenant is not None:
            schema_name = getattr(tenant, "schema_name", None)
            if schema_name:
                scope.set_tag("tenant_schema", schema_name)
            tenant_name = getattr(tenant, "name", None)
            if tenant_name:
                scope.set_context(
                    "tenant",
                    {
                        "schema_name": schema_name,
                        "name": tenant_name,
                    },
                )

        user = getattr(request, "user", None)
        if user is not None and getattr(user, "is_authenticated", False):
            scope.set_user(
                {
                    "id": str(user.pk),
                    "username": getattr(user, "username", None) or None,
                }
            )

        return self.get_response(request)
