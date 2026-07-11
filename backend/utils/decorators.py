"""
Module Access Control Decorators

Provides decorators for enforcing module-level access control on views.
"""

from functools import wraps
from django.http import JsonResponse
from django.core.exceptions import PermissionDenied
from typing import Callable, List, Union


def require_module(module_name: Union[str, List[str]]) -> Callable:
    """
    Decorator to require one or more modules to be enabled for the tenant

    Args:
        module_name: Single module identifier or list of module identifiers

    Usage:
        @require_module('hotel')
        def my_view(request):
            ...

        @require_module(['hotel', 'restaurant'])
        def my_multi_module_view(request):
            ...

    Raises:
        PermissionDenied: If tenant doesn't have required module(s) enabled
    """

    def decorator(view_func: Callable) -> Callable:
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Get the tenant (company) from request
            # django-tenants sets request.tenant
            if not hasattr(request, "tenant"):
                raise PermissionDenied("No tenant context available")

            tenant = request.tenant

            # Check if tenant has has_module method
            if not hasattr(tenant, "has_module"):
                raise PermissionDenied("Tenant does not support module system")

            # Handle single module or list of modules
            required_modules = (
                [module_name] if isinstance(module_name, str) else module_name
            )

            # Check each required module
            missing_modules = []
            for module in required_modules:
                if not tenant.has_module(module):
                    missing_modules.append(module)

            if missing_modules:
                error_message = f"Module(s) not enabled: {', '.join(missing_modules)}"
                # Return JSON response for API endpoints
                if request.path.startswith("/api/"):
                    return JsonResponse(
                        {"error": error_message, "required_modules": missing_modules},
                        status=403,
                    )
                # Raise PermissionDenied for other endpoints
                raise PermissionDenied(error_message)

            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator


def require_any_module(module_names: List[str]) -> Callable:
    """
    Decorator to require at least one of the specified modules to be enabled

    Args:
        module_names: List of module identifiers (requires at least one)

    Usage:
        @require_any_module(['hotel', 'restaurant'])
        def my_view(request):
            ...

    Raises:
        PermissionDenied: If tenant doesn't have at least one required module enabled
    """

    def decorator(view_func: Callable) -> Callable:
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Get the tenant from request
            if not hasattr(request, "tenant"):
                raise PermissionDenied("No tenant context available")

            tenant = request.tenant

            # Check if tenant has has_module method
            if not hasattr(tenant, "has_module"):
                raise PermissionDenied("Tenant does not support module system")

            # Check if tenant has at least one of the required modules
            has_module = any(tenant.has_module(module) for module in module_names)

            if not has_module:
                error_message = (
                    f"At least one of these modules required: {', '.join(module_names)}"
                )
                # Return JSON response for API endpoints
                if request.path.startswith("/api/"):
                    return JsonResponse(
                        {
                            "error": error_message,
                            "required_modules": module_names,
                            "require_any": True,
                        },
                        status=403,
                    )
                # Raise PermissionDenied for other endpoints
                raise PermissionDenied(error_message)

            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator


def module_required(module_name: str) -> Callable:
    """
    Class-based view decorator for module access control

    Usage:
        from django.utils.decorators import method_decorator

        @method_decorator(module_required('hotel'), name='dispatch')
        class HotelView(View):
            ...

        Or for specific methods:
        class HotelView(View):
            @method_decorator(module_required('hotel'))
            def get(self, request):
                ...
    """
    return require_module(module_name)
