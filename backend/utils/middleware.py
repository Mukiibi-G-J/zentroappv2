"""
Module Permission Middleware

Provides middleware for checking module permissions on incoming requests.
"""

from django.http import JsonResponse
from django.core.exceptions import PermissionDenied
from django.middleware.security import SecurityMiddleware
from utils.modules import get_module_config
import re


# Hosts used by local runserver and Cursor/SSH port-forwards to production.
_LOCAL_TUNNEL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


class LocalhostAwareSecurityMiddleware(SecurityMiddleware):
    """
    Like SecurityMiddleware, but never forces HTTPS for localhost / 127.0.0.1.

    Cursor Remote SSH auto-forwards production gunicorn (e.g. :8002) onto
    localhost. With SECURE_SSL_REDIRECT=True, that becomes a 301 to
    https://localhost:8002 which has no TLS listener. Skip the redirect (and
    clear the Secure cookie flag) for those hosts so admin works over HTTP.
    """

    def process_request(self, request):
        host = request.get_host().split(":")[0].lower().strip("[]")
        if host in _LOCAL_TUNNEL_HOSTS:
            return None
        return super().process_request(request)

    def process_response(self, request, response):
        response = super().process_response(request, response)
        host = request.get_host().split(":")[0].lower().strip("[]")
        if host in _LOCAL_TUNNEL_HOSTS:
            for morsel in response.cookies.values():
                morsel["secure"] = False
        return response


class ModulePermissionMiddleware:
    """
    Middleware to check if the current tenant has access to the requested module
    based on the URL path.

    This middleware extracts the module identifier from the URL and validates
    that the tenant has that module enabled.
    """

    def __init__(self, get_response):
        self.get_response = get_response

        # Define URL patterns that map to modules
        self.module_patterns = {
            "hotel": re.compile(r"^/api/hotel/"),
            # Add more module patterns as they are created
            # "restaurant": re.compile(r"^/api/restaurant/"),
        }

        # Paths that should bypass module checks
        self.bypass_patterns = [
            re.compile(r"^/api/auth/"),  # Authentication endpoints
            re.compile(r"^/api/company/"),  # Company management
            re.compile(r"^/api/users/"),  # User management
            re.compile(r"^/admin/"),  # Django admin
            re.compile(r"^/static/"),  # Static files
            re.compile(r"^/media/"),  # Media files
            # Add other patterns that should bypass module checks
        ]

    def __call__(self, request):
        # Check if this request should bypass module permission checks
        if self._should_bypass(request.path):
            return self.get_response(request)

        # Check module permissions
        module = self._extract_module_from_path(request.path)

        if module:
            # Verify tenant has access to this module
            if not self._check_module_permission(request, module):
                return self._permission_denied_response(request, module)

        # Continue with the request
        response = self.get_response(request)
        return response

    def _should_bypass(self, path):
        """
        Check if the path should bypass module permission checks

        Args:
            path: Request path

        Returns:
            bool: True if path should bypass checks
        """
        for pattern in self.bypass_patterns:
            if pattern.match(path):
                return True
        return False

    def _extract_module_from_path(self, path):
        """
        Extract module identifier from the request path

        Args:
            path: Request path

        Returns:
            str: Module identifier or None if no module-specific path
        """
        for module, pattern in self.module_patterns.items():
            if pattern.match(path):
                return module
        return None

    def _check_module_permission(self, request, module):
        """
        Check if tenant has permission to access the module

        Args:
            request: Django request object
            module: Module identifier

        Returns:
            bool: True if tenant has access, False otherwise
        """
        # django-tenants sets request.tenant
        if not hasattr(request, "tenant"):
            return False

        tenant = request.tenant

        # Check if tenant has has_module method
        if not hasattr(tenant, "has_module"):
            return False

        # Check if tenant has the module enabled
        return tenant.has_module(module)

    def _permission_denied_response(self, request, module):
        """
        Return appropriate permission denied response

        Args:
            request: Django request object
            module: Module identifier that was denied

        Returns:
            JsonResponse or raises PermissionDenied
        """
        # Get module display name for better error message
        module_config = get_module_config(module)
        module_name = module_config.display_name if module_config else module

        error_message = f"Access denied: '{module_name}' module is not enabled for your organization"

        # Return JSON response for API endpoints
        if request.path.startswith("/api/"):
            return JsonResponse(
                {
                    "error": error_message,
                    "module_required": module,
                    "message": "Please contact your administrator to enable this module",
                },
                status=403,
            )

        # Raise PermissionDenied for non-API endpoints
        raise PermissionDenied(error_message)


class ModuleContextMiddleware:
    """
    Middleware to add module context to requests

    This middleware adds information about available and enabled modules
    to the request object for easy access in views.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Add module information to request if tenant exists
        if hasattr(request, "tenant"):
            tenant = request.tenant
            if hasattr(tenant, "enabled_modules"):
                # Add enabled modules to request for easy access
                request.enabled_modules = tenant.enabled_modules or []

                # Add helper method to request
                request.has_module = lambda module: module in request.enabled_modules
            else:
                request.enabled_modules = []
                request.has_module = lambda module: False
        else:
            request.enabled_modules = []
            request.has_module = lambda module: False

        response = self.get_response(request)
        return response
