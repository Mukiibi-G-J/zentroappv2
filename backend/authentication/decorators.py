from functools import wraps
from django.shortcuts import redirect
from django.conf import settings
from urllib.parse import urlparse
from rest_framework.response import Response
from rest_framework import status as http_status


def tenant_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        host = request.get_host()

        # # Special handling for development
        # if settings.DEBUG:
        #     if host in ["localhost:8000", "127.0.0.1:8000"]:
        #         print("this is a local host")
        #         return view_func(request, *args, **kwargs)

        parsed_host = urlparse(f"//{host}")
        domain_parts = parsed_host.netloc.split(".")

        # Remove 'www' if present
        if domain_parts[0] == "www":
            domain_parts = domain_parts[1:]

        if settings.ENVIRONMENT == "development":
            if len(domain_parts) < 2 or domain_parts[1] != "localhost:8000":
                return redirect("authentication:verify-company")
        else:
            main_domain = settings.DOMAIN
            domain_without_subdomain = ".".join(domain_parts[1:])
            if len(domain_parts) < 2 or domain_without_subdomain != main_domain:
                return redirect("authentication:verify-company")

        return view_func(request, *args, **kwargs)

    return _wrapped_view


def require_object_permission(object_id, permission_type):
    """
    Decorator to check granular object permissions on API views.

    Usage:
        @api_view(['GET'])
        @permission_classes([IsAuthenticated])
        @require_object_permission(2600, 'read')
        def list_customers(request):
            # User has read permission on Customer table (2600)
            ...

    Args:
        object_id (int): The numeric ID of the object (e.g., 2600 for Customer)
        permission_type (str): 'read', 'insert', 'modify', 'delete', or 'execute'

    Returns:
        Decorated function that checks permissions before executing
    """

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            user = request.user

            # Check if user is authenticated
            if not user.is_authenticated:
                return Response(
                    {"error": "Authentication required"},
                    status=http_status.HTTP_401_UNAUTHORIZED,
                )

            # Check object permission
            has_permission, source = user.check_object_permission(
                object_id, permission_type
            )

            if not has_permission:
                return Response(
                    {
                        "error": "Insufficient permissions",
                        "detail": f"You need {permission_type} permission for this operation",
                        "object_id": object_id,
                        "reason": source,
                    },
                    status=http_status.HTTP_403_FORBIDDEN,
                )

            # Permission granted - proceed with the view
            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator
