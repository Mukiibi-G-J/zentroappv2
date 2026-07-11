from rest_framework import viewsets
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAuthenticated
from authentication.authentication import JWTAuthenticationWithRevocationChecks as JWTAuthentication
from .models import Dimension, DimensionValue, DimensionSet
from .serializers import (
    DimensionSerializer,
    DimensionValueSerializer,
    DimensionSetSerializer,
)


# Page Object IDs for permission checks (must match populate_page_objects)
TRACKING_CODES_PAGE_ID = 10902
DIMENSION_VALUES_PAGE_ID = 10903


def _check_page_permission(request, page_id, action="read"):
    """Check if user has permission to access page. Returns (has_permission, reason)."""
    if not hasattr(request.user, "check_object_permission"):
        return (True, None)
    has_perm, _ = request.user.check_object_permission(page_id, action)
    return (has_perm, "Insufficient permissions" if not has_perm else None)


class DimensionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for listing dimensions (tracking codes).
    Read-only - dimensions are managed in Django Admin.
    """

    queryset = Dimension.objects.all()
    serializer_class = DimensionSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    filterset_fields = []
    search_fields = ["code", "description"]
    ordering_fields = ["code", "description"]
    ordering = ["code"]

    def list(self, request, *args, **kwargs):
        has_perm, err = _check_page_permission(request, TRACKING_CODES_PAGE_ID)
        if not has_perm:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied(err)
        return super().list(request, *args, **kwargs)


class DimensionValueViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for retrieving dimension values.
    Read-only - dimension values are managed in Django Admin.
    Filter by dimension_code (dimension id) for drill-down.
    """

    queryset = DimensionValue.objects.select_related("dimension_code").all()
    serializer_class = DimensionValueSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    filterset_fields = ["dimension_code"]
    search_fields = ["code", "description"]
    ordering_fields = ["code", "description"]
    ordering = ["code"]

    def list(self, request, *args, **kwargs):
        has_perm, err = _check_page_permission(request, DIMENSION_VALUES_PAGE_ID)
        if not has_perm:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied(err)
        return super().list(request, *args, **kwargs)

    def get_queryset(self):
        """Filter by dimension_code (dimension id) for drill-down."""
        queryset = super().get_queryset()
        dimension_id = self.request.query_params.get("dimension_code", None)
        dimension_type = self.request.query_params.get("dimension_type", None)

        if dimension_id:
            queryset = queryset.filter(dimension_code_id=dimension_id)
        if dimension_type:
            queryset = queryset.filter(dimension_type=dimension_type)

        return queryset.order_by("code")


class DimensionSetViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for retrieving dimension sets.
    Read-only - dimension sets are created during posting.
    """

    queryset = DimensionSet.objects.all()
    serializer_class = DimensionSetSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication, SessionAuthentication]
