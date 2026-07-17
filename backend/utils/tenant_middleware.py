"""
Tenant JWT Middleware

Resolves the tenant when the Host header has no tenant subdomain (apex API).

Sources (in order):
1. X-Tenant header (mobile / explicit)
2. Frontend Origin/Referer workspace slug (e.g. primewise.zentroapp.uncodedsolutions.com)
3. JWT schema_name claim

This runs BEFORE TenantMainMiddleware and rewrites Host to the tenant API domain
so Django Tenants routes into the correct schema.
"""

from __future__ import annotations

import logging
from urllib.parse import urlparse

import jwt
from django.conf import settings
from django_tenants.utils import get_public_schema_name, get_tenant_model
from rest_framework_simplejwt.settings import api_settings

logger = logging.getLogger(__name__)

MAIN_DOMAIN_ROUTES = [
    "/api/company/check-company-exists/",
    "/api/company/create-company-account/",
    "/api/company/validate-company-name/",
    "/api/company/task-status/",
    "/api/company/payment-methods/create_payment_intent/",
    "/api/company/payment-methods/verify_payment/",
    "/api/home/on-boarding",
    "/api/home/on-boarding/",
    "/api/company/pricing-plans-v2/",
    "/api/auth/restaurant-app/company-lookup/",
]


def _is_main_domain_route(path: str) -> bool:
    return any(route in path for route in MAIN_DOMAIN_ROUTES)


def _request_has_tenant_subdomain(host: str) -> bool:
    parsed_host = urlparse(f"//{host}")
    domain_parts = parsed_host.netloc.split(".")

    if settings.ENVIRONMENT == "development":
        if len(domain_parts) > 1:
            if (
                "localhost" in domain_parts[1]
                and len(domain_parts[0].split(":")) == 1
            ):
                return True
        return False

    main_domain = getattr(settings, "DOMAIN", "zentroapp.app")
    backend_domain = getattr(settings, "BACKEND_DOMAIN", "zentroapp-backend.com")
    host_suffix = ".".join(domain_parts[1:])
    return (
        len(domain_parts) > 2
        and domain_parts[0] != "www"
        and host_suffix in (main_domain, backend_domain)
    )


def _schema_from_frontend_origin(request) -> str | None:
    """
    Map browser Origin/Referer to a tenant schema.

    Frontend calls the apex API (zentroapp-api...) from
    {slug}.zentroapp.uncodedsolutions.com — without this, login hits the
    public schema and authenticates the wrong user.

    Local Next rewrites also hit Django via LAN IP (Host has no tenant);
    Origin {slug}.localhost must map to schema {slug}.
    """
    main_domain = getattr(settings, "DOMAIN", "zentroapp.uncodedsolutions.com")
    for header in ("HTTP_ORIGIN", "HTTP_REFERER"):
        raw = (request.META.get(header) or "").strip()
        if not raw:
            continue
        try:
            hostname = urlparse(raw).hostname or ""
        except Exception:
            continue
        hostname = hostname.lower().strip(".")
        if not hostname or hostname == main_domain or hostname == f"www.{main_domain}":
            continue

        # Dev: primewise.localhost → primewise
        if settings.ENVIRONMENT == "development":
            parts = hostname.split(".")
            if (
                len(parts) == 2
                and parts[1] == "localhost"
                and parts[0] not in ("www", "api", "localhost")
            ):
                return parts[0]

        suffix = f".{main_domain}"
        if hostname.endswith(suffix):
            slug = hostname[: -len(suffix)]
            if slug and "." not in slug and slug not in ("www", "api"):
                return slug
    return None


def _apply_tenant_schema(request, schema_name: str, source: str) -> bool:
    """Set connection tenant + Host from schema_name. Returns True if applied."""
    public_schema = get_public_schema_name()
    if not schema_name or schema_name == public_schema:
        return False
    if _is_main_domain_route(request.path_info):
        return False

    TenantModel = get_tenant_model()
    from django.db import connection as db_connection
    from django_tenants.utils import schema_context
    from company.models import Domain

    try:
        with schema_context(public_schema):
            tenant = TenantModel.objects.get(schema_name=schema_name)

        db_connection.set_tenant(tenant)
        request.tenant = tenant

        with schema_context(public_schema):
            domain = Domain.objects.filter(tenant=tenant).first()

        if domain:
            if settings.ENVIRONMENT == "development":
                port = f":{request.get_port()}" if request.get_port() else ""
                new_host = f"{domain.domain}{port}"
            else:
                new_host = domain.domain
            request.META["HTTP_HOST"] = new_host
            request.META["SERVER_NAME"] = domain.domain.split(":")[0]

        logger.info(
            "TenantJWTMiddleware: set tenant=%s from %s", schema_name, source
        )
        return True
    except TenantModel.DoesNotExist:
        logger.warning(
            "TenantJWTMiddleware: tenant '%s' not found (%s)", schema_name, source
        )
    except Exception as e:
        logger.warning(
            "TenantJWTMiddleware: error setting tenant from %s: %s", source, e
        )
    return False


class TenantJWTMiddleware:
    """
    Middleware to set tenant from X-Tenant, frontend Origin, or JWT when Host
    has no tenant subdomain (apex API / mobile).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        host = request.get_host()
        if _request_has_tenant_subdomain(host):
            return self.get_response(request)

        # 1) Explicit X-Tenant (mobile)
        x_tenant = (request.META.get("HTTP_X_TENANT") or "").strip()
        if x_tenant and _apply_tenant_schema(request, x_tenant, "X-Tenant"):
            return self.get_response(request)

        # 2) Frontend Origin/Referer — required for login on apex API
        #    (no JWT yet). Prefer this over a public-schema JWT so a stale
        #    public token cannot keep the request on the wrong tenant when
        #    the user is clearly on a workspace frontend host.
        origin_schema = _schema_from_frontend_origin(request)
        if origin_schema and _apply_tenant_schema(
            request, origin_schema, "Origin/Referer"
        ):
            return self.get_response(request)

        # 3) JWT schema_name (authenticated API calls without Origin)
        auth_header = request.META.get("HTTP_AUTHORIZATION", "")
        if auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1]
            try:
                decoded = jwt.decode(
                    token,
                    api_settings.SIGNING_KEY,
                    algorithms=[api_settings.ALGORITHM],
                    options={"verify_signature": False, "verify_exp": False},
                )
                schema_name = decoded.get("schema_name")
                if schema_name:
                    _apply_tenant_schema(request, schema_name, "JWT")
            except (jwt.DecodeError, jwt.InvalidTokenError, KeyError) as e:
                logger.debug("TenantJWTMiddleware: token decode error: %s", e)
            except Exception as e:
                logger.warning(
                    "TenantJWTMiddleware: unexpected JWT error: %s", e, exc_info=True
                )

        return self.get_response(request)
