"""
Tenant JWT Middleware

This middleware extracts the tenant schema_name from JWT tokens for mobile app requests
that don't include subdomain information in the Host header.

This middleware runs BEFORE TenantMainMiddleware and modifies the Host header
to include the tenant subdomain, allowing Django Tenants to properly route the request.
"""

import jwt
from django.conf import settings
from django_tenants.utils import get_tenant_model, get_public_schema_name
from rest_framework_simplejwt.settings import api_settings
from urllib.parse import urlparse


class TenantJWTMiddleware:
    """
    Middleware to set tenant from JWT token for mobile app requests.

    This runs BEFORE TenantMainMiddleware. If the request doesn't have a subdomain
    in the Host header but has a JWT token with schema_name, we modify the Host
    header to include the tenant subdomain so Django Tenants can properly route it.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Check if request already has a subdomain (web requests)
        host = request.get_host()
        parsed_host = urlparse(f"//{host}")
        domain_parts = parsed_host.netloc.split(".")

        # Check if we're on a subdomain
        has_subdomain = False
        if settings.ENVIRONMENT == "development":
            # Development: company.localhost:8000 or IP address (mobile testing)
            # Check if we have a subdomain before localhost
            if len(domain_parts) > 1:
                # Check if it's a subdomain pattern (e.g., "ekk.localhost:8000")
                if (
                    "localhost" in domain_parts[1]
                    and len(domain_parts[0].split(":")) == 1
                ):
                    # Has subdomain (e.g., "ekk" before "localhost")
                    has_subdomain = True
                # If it's just "localhost" or an IP address, no subdomain
        else:
            # Production: company.zentroapp.app or company.zentroapp-backend.com
            main_domain = getattr(settings, "DOMAIN", "zentroapp.app")
            backend_domain = getattr(
                settings, "BACKEND_DOMAIN", "zentroapp-backend.com"
            )
            host_suffix = ".".join(domain_parts[1:])
            has_subdomain = (
                len(domain_parts) > 2
                and domain_parts[0] != "www"
                and host_suffix in (main_domain, backend_domain)
            )

        # If no subdomain detected, try to get tenant from X-Tenant header or JWT token
        if not has_subdomain:
            # First, check for X-Tenant header (mobile apps)
            x_tenant_header = request.META.get("HTTP_X_TENANT", "")

            if x_tenant_header:
                # Mobile app is providing tenant via X-Tenant header
                import logging

                logger = logging.getLogger(__name__)
                logger.info(
                    f"TenantJWTMiddleware: Processing request to {request.path_info} with X-Tenant header: {x_tenant_header}"
                )

                schema_name = x_tenant_header

                try:
                    public_schema = get_public_schema_name()

                    # Don't modify Host for public schema or main domain routes
                    if schema_name != public_schema:
                        # Check if this is a main domain route
                        path = request.path_info
                        main_domain_routes = [
                            "/api/company/check-company-exists/",
                            "/api/company/create-company-account/",
                            "/api/company/validate-company-name/",
                            "/api/company/task-status/",
                            "/api/company/payment-methods/create_payment_intent/",
                            "/api/company/payment-methods/verify_payment/",
                            "/api/home/on-boarding",
                            "/api/company/pricing-plans-v2/",
                            "/api/auth/restaurant-app/company-lookup/",
                        ]

                        is_main_domain_route = any(
                            route in path for route in main_domain_routes
                        )

                        if not is_main_domain_route:
                            # Set tenant from X-Tenant header
                            TenantModel = get_tenant_model()
                            from django_tenants.utils import schema_context
                            from django.db import connection as db_connection

                            try:
                                # Query tenant from public schema
                                with schema_context(public_schema):
                                    tenant = TenantModel.objects.get(
                                        schema_name=schema_name
                                    )

                                # Set tenant on connection
                                db_connection.set_tenant(tenant)

                                # Also set on request for consistency
                                request.tenant = tenant

                                # Modify Host header to match tenant domain
                                from company.models import Domain

                                with schema_context(public_schema):
                                    domain = Domain.objects.filter(
                                        tenant=tenant
                                    ).first()

                                if domain:
                                    if settings.ENVIRONMENT == "development":
                                        port = (
                                            f":{request.get_port()}"
                                            if request.get_port()
                                            else ""
                                        )
                                        new_host = f"{domain.domain}{port}"
                                    else:
                                        new_host = domain.domain

                                    request.META["HTTP_HOST"] = new_host
                                    request.META["SERVER_NAME"] = domain.domain.split(
                                        ":"
                                    )[0]

                                    logger.info(
                                        f"TenantJWTMiddleware: Set tenant to {schema_name} from X-Tenant header"
                                    )

                            except TenantModel.DoesNotExist:
                                logger.warning(
                                    f"TenantJWTMiddleware: Tenant with schema_name '{schema_name}' not found from X-Tenant header"
                                )
                            except Exception as e:
                                logger.warning(
                                    f"TenantJWTMiddleware: Error setting tenant from X-Tenant header: {e}"
                                )

                except Exception as e:
                    import logging

                    logger = logging.getLogger(__name__)
                    logger.warning(
                        f"TenantJWTMiddleware: Unexpected error with X-Tenant header: {e}",
                        exc_info=True,
                    )

            # If no X-Tenant header, check for JWT token
            auth_header = request.META.get("HTTP_AUTHORIZATION", "")

            if not x_tenant_header and auth_header.startswith("Bearer "):
                # Debug: Print to verify middleware is running (remove in production)
                import logging

                logger = logging.getLogger(__name__)
                logger.info(
                    f"TenantJWTMiddleware: Processing request to {request.path_info} without subdomain"
                )
                token = auth_header.split(" ")[1]

                try:
                    # Decode token without verification (we'll verify later in authentication)
                    # This is just to extract schema_name for tenant routing
                    decoded_token = jwt.decode(
                        token,
                        api_settings.SIGNING_KEY,
                        algorithms=[api_settings.ALGORITHM],
                        options={"verify_signature": False, "verify_exp": False},
                    )

                    schema_name = decoded_token.get("schema_name")

                    if schema_name:
                        # Get public schema name
                        public_schema = get_public_schema_name()

                        # Don't modify Host for public schema or main domain routes
                        if schema_name != public_schema:
                            # Check if this is a main domain route (should not use tenant)
                            path = request.path_info
                            main_domain_routes = [
                                "/api/company/check-company-exists/",
                                "/api/company/create-company-account/",
                                "/api/company/validate-company-name/",
                                "/api/company/task-status/",
                                "/api/company/payment-methods/create_payment_intent/",
                                "/api/company/payment-methods/verify_payment/",
                                "/api/home/on-boarding",
                                "/api/company/pricing-plans-v2/",
                                "/api/auth/restaurant-app/company-lookup/",
                            ]

                            is_main_domain_route = any(
                                route in path for route in main_domain_routes
                            )

                            if not is_main_domain_route:
                                # Set tenant directly on connection and request
                                # This allows TenantMainMiddleware to use the tenant
                                TenantModel = get_tenant_model()

                                # Query from public schema to get tenant
                                from django_tenants.utils import schema_context
                                from django.db import connection as db_connection

                                try:
                                    public_schema = get_public_schema_name()

                                    # Query tenant from public schema
                                    with schema_context(public_schema):
                                        tenant = TenantModel.objects.get(
                                            schema_name=schema_name
                                        )

                                    # Set tenant on connection - this is what Django Tenants uses
                                    db_connection.set_tenant(tenant)

                                    # Also set on request for consistency
                                    request.tenant = tenant

                                    # Modify Host header to match tenant domain for proper routing
                                    from company.models import Domain

                                    # Query domain from public schema
                                    with schema_context(public_schema):
                                        domain = Domain.objects.filter(
                                            tenant=tenant
                                        ).first()

                                    if domain:
                                        # Update Host header to match tenant domain
                                        if settings.ENVIRONMENT == "development":
                                            # Development: company.localhost:8000
                                            port = (
                                                f":{request.get_port()}"
                                                if request.get_port()
                                                else ""
                                            )
                                            new_host = f"{domain.domain}{port}"
                                        else:
                                            # Production: company.zentroapp.app
                                            new_host = domain.domain

                                        request.META["HTTP_HOST"] = new_host
                                        request.META["SERVER_NAME"] = (
                                            domain.domain.split(":")[0]
                                        )

                                except TenantModel.DoesNotExist:
                                    # Tenant doesn't exist, let TenantMainMiddleware handle it
                                    import logging

                                    logger = logging.getLogger(__name__)
                                    logger.debug(
                                        f"TenantJWTMiddleware: Tenant with schema_name '{schema_name}' not found"
                                    )
                                    pass
                                except Exception as e:
                                    # Domain lookup failed, but tenant is set, continue
                                    import logging

                                    logger = logging.getLogger(__name__)
                                    logger.warning(
                                        f"TenantJWTMiddleware: Error setting tenant: {e}"
                                    )
                                    pass

                except (jwt.DecodeError, jwt.InvalidTokenError, KeyError) as e:
                    # Invalid token format, let TenantMainMiddleware handle it
                    import logging

                    logger = logging.getLogger(__name__)
                    logger.debug(f"TenantJWTMiddleware: Token decode error: {e}")
                    pass
                except Exception as e:
                    # Any other error, log but don't break the request
                    import logging

                    logger = logging.getLogger(__name__)
                    logger.warning(
                        f"TenantJWTMiddleware: Unexpected error: {e}", exc_info=True
                    )

        response = self.get_response(request)
        return response
