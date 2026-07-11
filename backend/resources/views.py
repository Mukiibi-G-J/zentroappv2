from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from django.core.paginator import Paginator
from django.db.models import Q

from base.models import Objects
from dimension.models import DefaultDimension

from .models import Resource
from .serializers import ResourceListSerializer, ResourceSerializer


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_resources(request):
    """
    List all resources with filtering, search, and pagination.
    Note: Company isolation handled by Django Tenants schema.

    Query Parameters:
        - search: Search by code, name, or description
        - resourceType: Filter by resource type (person, equipment, space)
        - isActive: Filter by active status (true/false)
        - dimension: Filter by dimension/branch
        - page: Page number for pagination (default: 1)
        - pageSize: Items per page (default: 20)
    """

    resources = Resource.objects.all()

    # Search
    search = request.GET.get("search", "").strip()
    if search:
        resources = resources.filter(
            Q(code__icontains=search)
            | Q(name__icontains=search)
            | Q(description__icontains=search)
        )

    # Filter by resource type
    resource_type = request.GET.get("resourceType")
    if resource_type:
        resources = resources.filter(resource_type=resource_type)

    # Filter by active status
    is_active = request.GET.get("isActive")
    if is_active is not None:
        is_active_bool = is_active.lower() == "true"
        resources = resources.filter(is_active=is_active_bool)

    # Filter by dimension (branch/location)
    dimension = request.GET.get("dimension")
    if dimension:
        table_obj = Objects.objects.filter(
            object_type="Table",
            related_model="resources.Resource",
        ).first()

        if table_obj:
            resource_codes = DefaultDimension.objects.filter(
                table=table_obj,
                dimension_value_id=dimension,
            ).values_list("no", flat=True)

            resources = resources.filter(code__in=resource_codes)

    # Filter by blocked status
    blocked = request.GET.get("blocked")
    if blocked is not None:
        blocked_bool = blocked.lower() == "true"
        resources = resources.filter(blocked=blocked_bool)

    # Order by code
    resources = resources.select_related("general_product_posting_group").order_by(
        "code"
    )

    # Pagination
    page = int(request.GET.get("page", 1))
    page_size = int(request.GET.get("pageSize", 20))

    paginator = Paginator(resources, page_size)
    page_obj = paginator.get_page(page)

    serializer = ResourceSerializer(page_obj.object_list, many=True)

    return Response(
        {
            "count": paginator.count,
            "totalPages": paginator.num_pages,
            "currentPage": page,
            "pageSize": page_size,
            "results": serializer.data,
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_resource(request):
    """
    Create a new resource.
    Note: Company isolation handled by Django Tenants schema.

    Request Body:
        - name (required): Resource name
        - resourceType (required): person, equipment, or space
        - baseUnit (optional): Unit of Measure code from items.UnitOfMeasure (e.g. HOUR, MINUTE, DAY, SESSION; default: HOUR)
        - costRate (required): Cost rate per unit
        - chargeRate (required): Charge rate per unit
        - description (optional): Description
        - photo (optional): Photo file
        - dimension1 (optional): Dimension/branch ID
        - isActive (optional): Active status (default: true)
    """

    serializer = ResourceSerializer(data=request.data)

    if serializer.is_valid():
        resource = serializer.save()
        return Response(
            {
                "message": "Resource created successfully",
                "resource": ResourceSerializer(resource).data,
            },
            status=status.HTTP_201_CREATED,
        )

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_resource(request, resource_id):
    """
    Get a single resource by ID.
    Note: Company isolation handled by Django Tenants schema.
    """

    try:
        resource = Resource.objects.select_related(
            "general_product_posting_group"
        ).get(id=resource_id)
    except Resource.DoesNotExist:
        return Response(
            {"error": "Resource not found"}, status=status.HTTP_404_NOT_FOUND
        )

    serializer = ResourceSerializer(resource)
    return Response(serializer.data)


@api_view(["PUT", "PATCH"])
@permission_classes([IsAuthenticated])
def update_resource(request, resource_id):
    """
    Update an existing resource.
    Note: Company isolation handled by Django Tenants schema.
    """

    try:
        resource = Resource.objects.get(id=resource_id)
    except Resource.DoesNotExist:
        return Response(
            {"error": "Resource not found"}, status=status.HTTP_404_NOT_FOUND
        )

    serializer = ResourceSerializer(
        resource, data=request.data, partial=(request.method == "PATCH")
    )

    if serializer.is_valid():
        resource = serializer.save()
        return Response(
            {
                "message": "Resource updated successfully",
                "resource": ResourceSerializer(resource).data,
            }
        )

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def delete_resource(request, resource_id):
    """
    Delete or deactivate a resource.
    Note: Company isolation handled by Django Tenants schema.

    Query Parameters:
        - soft: If true, just deactivates the resource instead of deleting (default: true)
    """

    try:
        resource = Resource.objects.get(id=resource_id)
    except Resource.DoesNotExist:
        return Response(
            {"error": "Resource not found"}, status=status.HTTP_404_NOT_FOUND
        )

    # Soft delete by default (just deactivate)
    soft_delete = request.GET.get("soft", "true").lower() == "true"

    if soft_delete:
        resource.is_active = False
        resource.save()
        return Response(
            {
                "message": "Resource deactivated successfully",
                "resource": ResourceSerializer(resource).data,
            }
        )
    else:
        # Check if resource is used in any BOM lines
        if resource.bom_lines.exists():
            return Response(
                {
                    "error": "Cannot delete resource that is used in Production BOMs",
                    "bomCount": resource.bom_lines.count(),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        resource.delete()
        return Response(
            {"message": "Resource deleted successfully"},
            status=status.HTTP_204_NO_CONTENT,
        )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_available_resources(request):
    """
    Get list of active resources for POS/dropdown selection.
    Note: Company isolation handled by Django Tenants schema.

    Query Parameters:
        - resourceType: Filter by resource type (optional)
        - dimension: Filter by dimension/branch (optional)
    """

    resources = Resource.objects.filter(is_active=True, blocked=False).order_by("name")

    # Filter by resource type if specified
    resource_type = request.GET.get("resourceType")
    if resource_type:
        resources = resources.filter(resource_type=resource_type)

    # Filter by dimension if specified
    dimension = request.GET.get("dimension")
    if dimension:
        table_obj = Objects.objects.filter(
            object_type="Table",
            related_model="resources.Resource",
        ).first()

        if table_obj:
            resource_codes = DefaultDimension.objects.filter(
                table=table_obj,
                dimension_value_id=dimension,
            ).values_list("no", flat=True)

            resources = resources.filter(code__in=resource_codes)

    serializer = ResourceListSerializer(resources, many=True)

    return Response({"count": resources.count(), "resources": serializer.data})
