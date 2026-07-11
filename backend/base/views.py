from rest_framework import viewsets, permissions
from django.db.models import Count
from .models import ObjectType, Objects
from .serializers import ObjectTypeSerializer, ObjectsSerializer


class ObjectTypeViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for ObjectTypes - read-only
    """

    queryset = ObjectType.objects.annotate(object_count=Count("application_objects"))
    serializer_class = ObjectTypeSerializer
    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    filterset_fields = ["code"]
    search_fields = ["name", "code"]
    ordering_fields = ["sort_order", "name"]


class ObjectsViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for Objects - read-only
    Returns all objects without pagination for use in dropdown/selection modals
    """

    queryset = Objects.objects.select_related("object_type_ref")
    serializer_class = ObjectsSerializer
    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    filterset_fields = ["object_type_ref", "requires_permission"]
    search_fields = ["object_name", "object_caption", "object_id"]
    ordering_fields = ["object_id", "object_name", "created_at"]
    ordering = ["object_type_ref__sort_order", "object_id"]
    pagination_class = None  # Disable pagination to return all objects at once
