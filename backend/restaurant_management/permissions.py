from django.db import connection
from django_tenants.utils import get_public_schema_name
from rest_framework.permissions import BasePermission


class IsTenantSchema(BasePermission):
    """
    Restaurant models live in tenant schemas only (TENANT_APPS).
    Requests resolved to the public schema hit tables that do not exist.
    """

    message = (
        "Restaurant API requires a tenant database context. Sign in from your "
        "company URL (subdomain), send the X-Tenant header, or use a JWT that "
        "includes schema_name."
    )

    def has_permission(self, request, view):
        return getattr(connection, "schema_name", None) != get_public_schema_name()
