from rest_framework import status
from rest_framework.decorators import (
    api_view,
    permission_classes,
    authentication_classes,
)
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import SessionAuthentication
from authentication.authentication import JWTAuthenticationWithRevocationChecks as JWTAuthentication

from django.core.paginator import Paginator
from django.db.models import Q
from django.db import transaction
from utils.decorators import require_any_module


class CsrfExemptSessionAuthentication(SessionAuthentication):
    """
    SessionAuthentication that doesn't enforce CSRF for GET requests.
    Used for admin interface AJAX calls.
    """

    def enforce_csrf(self, request):
        return  # Skip CSRF check


from .models import (
    ProductionBOM,
    BOMLine,
    ProductionOrder,
    ProductionOrderLine,
    ProductionOrderComponent,
)
from .serializers import (
    ProductionBOMSerializer,
    ProductionBOMListSerializer,
    BOMLineSerializer,
    ProductionOrderSerializer,
    ProductionOrderListSerializer,
    ProductionOrderComponentSerializer,
)
from .utils import get_service_cost_breakdown
from .posting import (
    build_production_posting_preview,
    production_order_all_journals_posted,
    ProductionOrderPostingFromPreviewService,
    ProductionOrderPostingError,
)

# Same stack as items/dimension ViewSets: explicit auth classes (not only DEFAULT).
# JWT auth class enforces token_valid_after like CustomJWTAuthentication, without extra tenant checks.
PRODUCTION_API_AUTHENTICATION = [JWTAuthentication, SessionAuthentication]


@api_view(["GET"])
@authentication_classes(PRODUCTION_API_AUTHENTICATION)
@permission_classes([IsAuthenticated])
@require_any_module(["manufacturing", "restaurant"])
def list_boms(request):
    """
    List all production BOMs with filtering, search, and pagination.
    Note: Company isolation handled by Django Tenants schema.

    Query Parameters:
        - search: Search by code, name, or service item name
        - isActive: Filter by active status (true/false)
        - page: Page number for pagination (default: 1)
        - pageSize: Items per page (default: 20)
    """

    boms = ProductionBOM.objects.all()

    # Search
    search = request.GET.get("search", "").strip()
    if search:
        boms = boms.filter(
            Q(bom_code__icontains=search)
            | Q(name__icontains=search)
            | Q(item__item_name__icontains=search)
        )

    # Filter by active status
    is_active = request.GET.get("isActive")
    if is_active is not None:
        is_active_bool = is_active.lower() == "true"
        boms = boms.filter(is_active=is_active_bool)

    # Optimize query
    boms = boms.select_related("item").prefetch_related("lines").order_by("bom_code")

    # Pagination
    page = int(request.GET.get("page", 1))
    page_size = int(request.GET.get("pageSize", 20))

    paginator = Paginator(boms, page_size)
    page_obj = paginator.get_page(page)

    serializer = ProductionBOMListSerializer(page_obj.object_list, many=True)

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
@authentication_classes(PRODUCTION_API_AUTHENTICATION)
@permission_classes([IsAuthenticated])
@require_any_module(["manufacturing", "restaurant"])
def create_bom(request):
    """
    Create a new Production BOM with BOM lines.
    Note: Company isolation handled by Django Tenants schema.

    Request Body:
        - name (required): BOM name
        - serviceItem (required): Service item ID
        - notes (optional): Additional notes
        - lines (optional): Array of BOM lines
            - lineNumber: Line sequence number
            - lineType: 'item' or 'production_bom'
            - item: Item ID (for both line types)
            - quantityPer: Quantity per unit
            - Note: For production_bom type, item must have a Production BOM
            - notes: Line notes
    """

    try:
        with transaction.atomic():
            # Create the BOM
            bom_serializer = ProductionBOMSerializer(data=request.data)

            if not bom_serializer.is_valid():
                return Response(
                    bom_serializer.errors, status=status.HTTP_400_BAD_REQUEST
                )

            bom = bom_serializer.save()

            # Link BOM to item if serviceItem (item no/pk) provided
            # Note: Item uses 'no' (CharField) as primary key, not 'id'
            service_item_no = request.data.get("serviceItem")
            if service_item_no:
                from items.models import Item

                try:
                    # Item uses 'no' as primary key (pk)
                    item = Item.objects.get(no=service_item_no)
                    item.production_bom = bom
                    item.save()
                except Item.DoesNotExist:
                    pass  # BOM created but not linked

            # Create BOM lines if provided
            lines_data = request.data.get("lines", [])
            if lines_data:
                for line_data in lines_data:
                    line_data["bom"] = bom.id
                    line_serializer = BOMLineSerializer(data=line_data)

                    if line_serializer.is_valid():
                        line_serializer.save()
                    else:
                        return Response(
                            {
                                "error": "Invalid BOM line data",
                                "details": line_serializer.errors,
                            },
                            status=status.HTTP_400_BAD_REQUEST,
                        )

            # Return complete BOM with lines
            complete_bom = ProductionBOM.objects.prefetch_related("lines").get(
                id=bom.id
            )
            return Response(
                {
                    "message": "Production BOM created successfully",
                    "bom": ProductionBOMSerializer(complete_bom).data,
                },
                status=status.HTTP_201_CREATED,
            )

    except Exception as e:
        return Response(
            {"error": f"Error creating BOM: {str(e)}"},
            status=status.HTTP_400_BAD_REQUEST,
        )


@api_view(["GET"])
@authentication_classes(PRODUCTION_API_AUTHENTICATION)
@permission_classes([IsAuthenticated])
@require_any_module(["manufacturing", "restaurant"])
def get_bom_detail(request, bom_id):
    """
    Get a single Production BOM with all its lines.
    """

    try:
        bom = (
            ProductionBOM.objects.select_related("item")
            .prefetch_related("lines__item", "lines__unit_of_measure")
            .get(id=bom_id)
        )
    except ProductionBOM.DoesNotExist:
        return Response(
            {"error": "Production BOM not found"}, status=status.HTTP_404_NOT_FOUND
        )

    serializer = ProductionBOMSerializer(bom)
    return Response(serializer.data)


@api_view(["PUT", "PATCH"])
@authentication_classes(PRODUCTION_API_AUTHENTICATION)
@permission_classes([IsAuthenticated])
@require_any_module(["manufacturing", "restaurant"])
def update_bom(request, bom_id):
    """
    Update an existing Production BOM.
    """

    try:
        bom = ProductionBOM.objects.get(id=bom_id)
    except ProductionBOM.DoesNotExist:
        return Response(
            {"error": "Production BOM not found"}, status=status.HTTP_404_NOT_FOUND
        )

    serializer = ProductionBOMSerializer(
        bom, data=request.data, partial=(request.method == "PATCH")
    )

    if serializer.is_valid():
        bom = serializer.save()

        # Reload with lines
        bom = ProductionBOM.objects.prefetch_related("lines").get(id=bom.id)

        return Response(
            {
                "message": "Production BOM updated successfully",
                "bom": ProductionBOMSerializer(bom).data,
            }
        )

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["DELETE"])
@authentication_classes(PRODUCTION_API_AUTHENTICATION)
@permission_classes([IsAuthenticated])
@require_any_module(["manufacturing", "restaurant"])
def delete_bom(request, bom_id):
    """
    Delete a Production BOM.

    Query Parameters:
        - soft: If true, just deactivates the BOM (default: true)
    """

    try:
        bom = ProductionBOM.objects.get(id=bom_id)
    except ProductionBOM.DoesNotExist:
        return Response(
            {"error": "Production BOM not found"}, status=status.HTTP_404_NOT_FOUND
        )

    # Soft delete by default
    soft_delete = request.GET.get("soft", "true").lower() == "true"

    if soft_delete:
        bom.is_active = False
        bom.save()
        return Response(
            {
                "message": "Production BOM deactivated successfully",
                "bom": ProductionBOMSerializer(bom).data,
            }
        )
    else:
        bom.delete()
        return Response(
            {"message": "Production BOM deleted successfully"},
            status=status.HTTP_204_NO_CONTENT,
        )


@api_view(["POST"])
@authentication_classes(PRODUCTION_API_AUTHENTICATION)
@permission_classes([IsAuthenticated])
@require_any_module(["manufacturing", "restaurant"])
def update_lines(request, bom_id):
    """
    Upsert/delete BOM lines in bulk.
    Follows Sales/Prepayment pattern for inline editing with autosave.

    Request Body:
        {
            "lines": [
                { "id": <line_id>, "item": "ITM-001", "quantity_per": 2.5, ... },
                { "id": <line_id>, "is_deleted": true },  # Delete line
                { "item": "ITM-002", "quantity_per": 1.0, ... }  # Create new
            ]
        }
    """
    try:
        bom = ProductionBOM.objects.get(id=bom_id)
    except ProductionBOM.DoesNotExist:
        return Response(
            {"error": "Production BOM not found"}, status=status.HTTP_404_NOT_FOUND
        )

    with transaction.atomic():
        raw_lines = request.data.get("lines", []) or []

        # First pass: hard-delete lines marked for deletion
        to_delete_ids = []
        remaining_lines = []
        for payload in raw_lines:
            line_id = payload.get("id")
            try:
                line_id = int(line_id) if line_id is not None else None
            except (TypeError, ValueError):
                line_id = None

            if payload.get("is_deleted") and line_id:
                to_delete_ids.append(line_id)
            else:
                if "is_deleted" in payload:
                    payload = {k: v for k, v in payload.items() if k != "is_deleted"}
                remaining_lines.append(payload)

        if to_delete_ids:
            bom.lines.filter(id__in=to_delete_ids).delete()

        # Second pass: upsert remaining lines
        existing_lines = {line.id: line for line in bom.lines.all()}
        from items.models import Item, UnitOfMeasure

        for line_data in remaining_lines:
            line_id = line_data.get("id")
            try:
                line_id = int(line_id) if line_id is not None else None
            except (TypeError, ValueError):
                line_id = None

            # Normalize item input (accept string 'no', int id, or object)
            item_value = line_data.get("item")
            item_obj = None
            if item_value:
                if isinstance(item_value, str):
                    # Item 'no' as string
                    try:
                        item_obj = Item.objects.get(no=item_value)
                    except Item.DoesNotExist:
                        continue  # Skip invalid item
                elif isinstance(item_value, int):
                    try:
                        item_obj = Item.objects.get(id=item_value)
                    except Item.DoesNotExist:
                        continue
                elif isinstance(item_value, dict):
                    item_no = item_value.get("no") or item_value.get("item_no")
                    if item_no:
                        try:
                            item_obj = Item.objects.get(no=item_no)
                        except Item.DoesNotExist:
                            continue

            # Normalize UOM (accept code string or object)
            uom_value = line_data.get("unit_of_measure")
            uom_obj = None
            if uom_value:
                if isinstance(uom_value, str):
                    uom_obj, _ = UnitOfMeasure.objects.get_or_create(
                        code=uom_value, defaults={"description": uom_value}
                    )
                elif isinstance(uom_value, dict):
                    code = uom_value.get("code")
                    if code:
                        uom_obj, _ = UnitOfMeasure.objects.get_or_create(
                            code=code, defaults={"description": code}
                        )

            if line_id and line_id in existing_lines:
                # Update existing line
                line = existing_lines[line_id]
                if item_obj:
                    line.item = item_obj
                if "quantity_per" in line_data:
                    line.quantity_per = line_data["quantity_per"]
                if "description" in line_data:
                    line.description = line_data["description"]
                if uom_obj:
                    line.unit_of_measure = uom_obj
                if "line_type" in line_data:
                    line.line_type = line_data["line_type"]
                if "scrap_pct" in line_data:
                    line.scrap_pct = line_data["scrap_pct"]
                line.save()
            else:
                # Create new line
                if not item_obj:
                    continue  # Skip lines without valid item

                BOMLine.objects.create(
                    bom=bom,
                    line_type=line_data.get("line_type", "item"),
                    item=item_obj,
                    description=line_data.get(
                        "description", item_obj.item_name if item_obj else ""
                    ),
                    quantity_per=line_data.get("quantity_per", 0),
                    unit_of_measure=uom_obj,
                    scrap_pct=line_data.get("scrap_pct", 0),
                    line_number=line_data.get("line_number"),
                )

        # Refresh and return updated BOM
        bom.refresh_from_db()
        serializer = ProductionBOMSerializer(bom)
        return Response(serializer.data)


@api_view(["GET"])
@authentication_classes(PRODUCTION_API_AUTHENTICATION)
@permission_classes([IsAuthenticated])
@require_any_module(["manufacturing", "restaurant"])
def get_cost_analysis(request, bom_id):
    """
    Get detailed cost analysis and breakdown for a Production BOM.
    """

    try:
        bom = ProductionBOM.objects.prefetch_related(
            "lines__item", "lines__unit_of_measure"
        ).get(id=bom_id)
    except ProductionBOM.DoesNotExist:
        return Response(
            {"error": "Production BOM not found"}, status=status.HTTP_404_NOT_FOUND
        )

    # Get cost breakdown
    breakdown = get_service_cost_breakdown(bom.item)

    return Response(breakdown)


# BOM Line endpoints
@api_view(["POST"])
@authentication_classes(PRODUCTION_API_AUTHENTICATION)
@permission_classes([IsAuthenticated])
@require_any_module(["manufacturing", "restaurant"])
def create_bom_line(request, bom_id):
    """
    Add a new line to an existing BOM.
    Note: Company isolation handled by Django Tenants schema.
    """

    try:
        bom = ProductionBOM.objects.get(id=bom_id)
    except ProductionBOM.DoesNotExist:
        return Response(
            {"error": "Production BOM not found"}, status=status.HTTP_404_NOT_FOUND
        )

    data = request.data.copy()

    serializer = BOMLineSerializer(data=data)

    if serializer.is_valid():
        line = serializer.save(bom=bom)
        return Response(
            {
                "message": "BOM line created successfully",
                "line": BOMLineSerializer(line).data,
            },
            status=status.HTTP_201_CREATED,
        )

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["PUT", "PATCH"])
@authentication_classes(PRODUCTION_API_AUTHENTICATION)
@permission_classes([IsAuthenticated])
@require_any_module(["manufacturing", "restaurant"])
def update_bom_line(request, line_id):
    """
    Update an existing BOM line.
    """

    try:
        line = BOMLine.objects.select_related("bom").get(id=line_id)
    except BOMLine.DoesNotExist:
        return Response(
            {"error": "BOM line not found"}, status=status.HTTP_404_NOT_FOUND
        )

    serializer = BOMLineSerializer(
        line, data=request.data, partial=(request.method == "PATCH")
    )

    if serializer.is_valid():
        line = serializer.save()
        return Response(
            {
                "message": "BOM line updated successfully",
                "line": BOMLineSerializer(line).data,
            }
        )

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["DELETE"])
@authentication_classes(PRODUCTION_API_AUTHENTICATION)
@permission_classes([IsAuthenticated])
@require_any_module(["manufacturing", "restaurant"])
def delete_bom_line(request, line_id):
    """
    Delete a BOM line.
    """

    try:
        line = BOMLine.objects.select_related("bom").get(id=line_id)
    except BOMLine.DoesNotExist:
        return Response(
            {"error": "BOM line not found"}, status=status.HTTP_404_NOT_FOUND
        )

    line.delete()

    return Response(
        {"message": "BOM line deleted successfully"}, status=status.HTTP_204_NO_CONTENT
    )


@api_view(["GET"])
@authentication_classes(
    [CsrfExemptSessionAuthentication, JWTAuthentication]
)
@permission_classes([IsAuthenticated])
@require_any_module(["manufacturing", "restaurant"])
def get_item_unit_of_measures(request, item_no):
    """
    Get all unit of measures for a specific item.
    Used for filtering UOM dropdown in BOM lines.

    URL: /api/production/items/<item_no>/unit-of-measures/

    Uses CsrfExemptSessionAuthentication to work with Django admin sessions.
    """
    from items.models import Item, ItemUnitOfMeasure

    try:
        item = Item.objects.get(no=item_no)
    except Item.DoesNotExist:
        return Response({"error": "Item not found"}, status=status.HTTP_404_NOT_FOUND)

    # Get all unit of measures for this item
    item_uoms = ItemUnitOfMeasure.objects.filter(item=item).select_related(
        "unit_of_measure"
    )

    # Build response
    uoms = [
        {
            "code": iuom.unit_of_measure.code,
            "description": iuom.unit_of_measure.description,
            "quantityPerUnit": iuom.quantity_per_unit,
            "isDefault": iuom.default,
        }
        for iuom in item_uoms
    ]

    # Also include the item's base unit of measure if it exists and not already in list
    if item.unit_of_measure:
        base_uom_code = item.unit_of_measure.code
        if not any(uom["code"] == base_uom_code for uom in uoms):
            uoms.insert(
                0,
                {
                    "code": item.unit_of_measure.code,
                    "description": item.unit_of_measure.description,
                    "quantityPerUnit": 1,
                    "isDefault": True,
                },
            )

    return Response({"unitOfMeasures": uoms}, status=status.HTTP_200_OK)


# Production Order APIs
@api_view(["GET"])
@authentication_classes(PRODUCTION_API_AUTHENTICATION)
@permission_classes([IsAuthenticated])
@require_any_module(["manufacturing", "restaurant"])
def list_items_with_bom(request):
    """List items that have a Production BOM (for source selection).
    Tries both: (1) ProductionBOM with linked item, (2) Item with production_bom.
    Items are shared across branches."""
    from .models import ProductionBOM
    from items.models import Item

    seen = set()
    results = []

    # Approach 1: ProductionBOM -> item (reverse relation)
    boms = (
        ProductionBOM.objects.exclude(item=None)
        .select_related("item")
        .order_by("bom_code")[:200]
    )
    for bom in boms:
        if bom.item and bom.item.no not in seen:
            seen.add(bom.item.no)
            results.append(
                {
                    "no": bom.item.no,
                    "item_name": bom.item.item_name,
                    "bom_code": bom.bom_code,
                }
            )

    # Approach 2: Item -> production_bom (fallback if approach 1 returns nothing)
    if not results:
        items = (
            Item.objects.exclude(production_bom=None)
            .select_related("production_bom")
            .order_by("no")[:200]
        )
        for item in items:
            if item.no not in seen and item.production_bom:
                seen.add(item.no)
                results.append(
                    {
                        "no": item.no,
                        "item_name": item.item_name,
                        "bom_code": item.production_bom.bom_code,
                    }
                )

    search = request.GET.get("search", "").strip()
    if search:
        search_lower = search.lower()
        results = [
            r
            for r in results
            if search_lower in (r["no"] or "").lower()
            or search_lower in (r["item_name"] or "").lower()
        ]

    return Response({"results": results})


@api_view(["GET"])
@authentication_classes(PRODUCTION_API_AUTHENTICATION)
@permission_classes([IsAuthenticated])
@require_any_module(["manufacturing", "restaurant"])
def list_production_orders(request):
    """List production orders with search and pagination."""
    from dimension.branch_filter import filter_queryset_by_branch

    orders = (
        ProductionOrder.objects.all()
        .select_related("item")
        .prefetch_related("components", "lines")
    )
    orders = filter_queryset_by_branch(
        orders, request.user, request=request
    )

    search = request.GET.get("search", "").strip()
    if search:
        orders = orders.filter(
            Q(no__icontains=search)
            | Q(name__icontains=search)
            | Q(item__no__icontains=search)
            | Q(item__item_name__icontains=search)
        )

    status_filter = request.GET.get("status", "").strip().lower()
    if status_filter:
        allowed_statuses = {c[0] for c in ProductionOrder.STATUS_CHOICES}
        if status_filter in allowed_statuses:
            orders = orders.filter(status=status_filter)
    else:
        # Make Production (and similar) lists: hide completed work; use ?status=finished for Finished view.
        orders = orders.exclude(status="finished")

    page = int(request.GET.get("page", 1))
    page_size = int(request.GET.get("pageSize", 20))
    paginator = Paginator(orders.order_by("-created_at"), page_size)
    page_obj = paginator.get_page(page)

    serializer = ProductionOrderListSerializer(page_obj.object_list, many=True)
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
@authentication_classes(PRODUCTION_API_AUTHENTICATION)
@permission_classes([IsAuthenticated])
@require_any_module(["manufacturing", "restaurant"])
def create_production_order(request):
    """Create a new production order."""
    from items.models import Item

    item_no = request.data.get("itemNo") or request.data.get(
        "sourceNo"
    )  # Item 'no' (pk), support legacy
    if not item_no:
        return Response(
            {"error": "itemNo (Item) is required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        item = Item.objects.get(no=item_no)
    except Item.DoesNotExist:
        return Response(
            {"error": f"Item '{item_no}' not found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    if not hasattr(item, "production_bom") or not item.production_bom:
        return Response(
            {"error": f"Item '{item.item_name}' does not have a Production BOM"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    quantity = float(request.data.get("quantity", 1))
    if quantity <= 0:
        return Response(
            {"error": "Quantity must be greater than 0"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    name = (request.data.get("name") or "").strip() or item.item_name
    try:
        with transaction.atomic():
            order = ProductionOrder.objects.create(
                name=name,
                description=request.data.get("description", ""),
                source_type="item",
                item=item,
                quantity=quantity,
                blocked=request.data.get("blocked", False),
                status="released",
            )
            order.refresh_production_details(user=request.user, request=request)
            order.refresh_from_db()
            serializer = ProductionOrderSerializer(
                ProductionOrder.objects.prefetch_related("lines", "components").get(
                    id=order.id
                )
            )
            return Response(
                {"message": "Production order created", "order": serializer.data},
                status=status.HTTP_201_CREATED,
            )
    except ValueError as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
@authentication_classes(PRODUCTION_API_AUTHENTICATION)
@permission_classes([IsAuthenticated])
@require_any_module(["manufacturing", "restaurant"])
def upsert_production_order(request):
    """
    Items-style upsert for Make Production:
    - With id: update header fields; if order is draft and itemNo is sent, attach item and release + refresh BOM.
    - Without id + itemNo: same as create_production_order (released).
    - Without id and no itemNo: create a draft (name/description only) so Name can autosave before item pick.
    """
    from decimal import Decimal, InvalidOperation

    from items.models import Item

    order_id = request.data.get("id")
    if order_id:
        try:
            order = ProductionOrder.objects.get(id=int(order_id))
        except (ProductionOrder.DoesNotExist, TypeError, ValueError):
            return Response(
                {"error": "Production order not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        item_no = request.data.get("itemNo") or request.data.get("sourceNo")

        if item_no and order.status == "draft":
            try:
                item = Item.objects.get(no=item_no)
            except Item.DoesNotExist:
                return Response(
                    {"error": f"Item '{item_no}' not found"},
                    status=status.HTTP_404_NOT_FOUND,
                )
            if not hasattr(item, "production_bom") or not item.production_bom:
                return Response(
                    {
                        "error": f"Item '{item.item_name}' does not have a Production BOM",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            data = request.data
            if "name" in data:
                order.name = (data.get("name") or "").strip() or item.item_name
            if "description" in data:
                order.description = data.get("description", "") or ""
            if "quantity" in data:
                qty = float(data["quantity"])
                if qty <= 0:
                    return Response(
                        {"error": "Quantity must be greater than 0"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                order.quantity = qty
            if "blocked" in data:
                order.blocked = bool(data["blocked"])

            order.item = item
            order.status = "released"
            try:
                with transaction.atomic():
                    order.save()
                    order.refresh_production_details(user=request.user, request=request)
                    order.refresh_from_db()
            except ValueError as e:
                return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

            serializer = ProductionOrderSerializer(
                ProductionOrder.objects.prefetch_related("lines", "components").get(
                    id=order.id
                )
            )
            return Response(
                {"message": "Production order updated", "order": serializer.data},
                status=status.HTTP_200_OK,
            )

        # Non-finalize: same as update_production_order
        data = request.data
        if "name" in data:
            order.name = data["name"]
        if "description" in data:
            order.description = data.get("description", "")
        if "quantity" in data:
            qty = float(data["quantity"])
            if qty <= 0:
                return Response(
                    {"error": "Quantity must be greater than 0"}, status=400
                )
            order.quantity = qty
        if "blocked" in data:
            order.blocked = data["blocked"]

        order.save()
        serializer = ProductionOrderSerializer(
            ProductionOrder.objects.prefetch_related("lines", "components").get(
                id=order.id
            )
        )
        return Response(
            {"message": "Updated", "order": serializer.data},
            status=status.HTTP_200_OK,
        )

    item_no = request.data.get("itemNo") or request.data.get("sourceNo")
    if item_no:
        return create_production_order(request)

    name = (request.data.get("name") or "").strip()
    description = (request.data.get("description") or "").strip()
    if not name and not description:
        return Response(
            {"error": "Provide name or description to create a draft order"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    qty_raw = request.data.get("quantity", 1)
    try:
        quantity = Decimal(str(qty_raw))
    except (ValueError, TypeError, InvalidOperation):
        quantity = Decimal("1")
    if quantity <= 0:
        quantity = Decimal("1")

    from dimension.branch_filter import get_branch_for_request

    try:
        with transaction.atomic():
            order = ProductionOrder.objects.create(
                name=name or "Draft",
                description=description or "",
                source_type="item",
                item=None,
                quantity=quantity,
                blocked=request.data.get("blocked", False),
                status="draft",
                global_dimension_1=get_branch_for_request(request),
            )
            order.refresh_from_db()
            serializer = ProductionOrderSerializer(
                ProductionOrder.objects.prefetch_related("lines", "components").get(
                    id=order.id
                )
            )
            return Response(
                {"message": "Draft production order created", "order": serializer.data},
                status=status.HTTP_201_CREATED,
            )
    except ValueError as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET"])
@authentication_classes(PRODUCTION_API_AUTHENTICATION)
@permission_classes([IsAuthenticated])
@require_any_module(["manufacturing", "restaurant"])
def get_production_order_detail(request, order_id):
    """Get a single production order with lines and components."""
    try:
        order = (
            ProductionOrder.objects.select_related("item")
            .prefetch_related(
                "lines__item",
                "lines__unit_of_measure_code",
                "components__item",
                "components__unit_of_measure_code",
            )
            .get(id=order_id)
        )
    except ProductionOrder.DoesNotExist:
        return Response(
            {"error": "Production order not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    serializer = ProductionOrderSerializer(order)
    return Response(serializer.data)


@api_view(["PUT", "PATCH"])
@authentication_classes(PRODUCTION_API_AUTHENTICATION)
@permission_classes([IsAuthenticated])
@require_any_module(["manufacturing", "restaurant"])
def update_production_order(request, order_id):
    """Update production order header."""
    try:
        order = ProductionOrder.objects.get(id=order_id)
    except ProductionOrder.DoesNotExist:
        return Response(
            {"error": "Production order not found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    data = request.data
    if "name" in data:
        order.name = data["name"]
    if "description" in data:
        order.description = data.get("description", "")
    if "quantity" in data:
        qty = float(data["quantity"])
        if qty <= 0:
            return Response({"error": "Quantity must be greater than 0"}, status=400)
        order.quantity = qty
    if "blocked" in data:
        order.blocked = data["blocked"]

    order.save()
    serializer = ProductionOrderSerializer(
        ProductionOrder.objects.prefetch_related("lines", "components").get(id=order.id)
    )
    return Response({"message": "Updated", "order": serializer.data})


@api_view(["POST"])
@authentication_classes(PRODUCTION_API_AUTHENTICATION)
@permission_classes([IsAuthenticated])
@require_any_module(["manufacturing", "restaurant"])
def refresh_production_order(request, order_id):
    """Refresh production order from BOM (reload components)."""
    try:
        order = ProductionOrder.objects.get(id=order_id)
    except ProductionOrder.DoesNotExist:
        return Response(
            {"error": "Production order not found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    try:
        with transaction.atomic():
            result = order.refresh_production_details(user=request.user, request=request)
        order.refresh_from_db()
        serializer = ProductionOrderSerializer(
            ProductionOrder.objects.prefetch_related("lines", "components").get(
                id=order.id
            )
        )
        return Response(
            {"message": "Refreshed", "order": serializer.data, "result": result}
        )
    except ValueError as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
@authentication_classes(PRODUCTION_API_AUTHENTICATION)
@permission_classes([IsAuthenticated])
@require_any_module(["manufacturing", "restaurant"])
def update_production_order_components(request, order_id):
    """Upsert/delete production order components (for inline editing)."""
    try:
        order = ProductionOrder.objects.get(id=order_id)
    except ProductionOrder.DoesNotExist:
        return Response(
            {"error": "Production order not found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    raw = request.data.get("components", []) or []
    to_delete = []
    remaining = []

    for payload in raw:
        cid = payload.get("id")
        if payload.get("is_deleted") and cid:
            to_delete.append(cid)
        else:
            if "is_deleted" in payload:
                payload = {k: v for k, v in payload.items() if k != "is_deleted"}
            remaining.append(payload)

    with transaction.atomic():
        if to_delete:
            order.components.filter(id__in=to_delete).delete()

        existing = {c.id: c for c in order.components.all()}
        for comp_data in remaining:
            cid = comp_data.get("id")
            if cid and cid in existing:
                comp = existing[cid]
                if "expectedQuantity" in comp_data:
                    comp.expected_quantity = comp_data["expectedQuantity"]
                if "quantity" in comp_data:
                    comp.quantity = comp_data["quantity"]
                comp.save()
            # No create - components come from BOM refresh

    order.refresh_from_db()
    serializer = ProductionOrderSerializer(
        ProductionOrder.objects.prefetch_related("lines", "components").get(id=order.id)
    )
    return Response(serializer.data)


@api_view(["POST"])
@authentication_classes(PRODUCTION_API_AUTHENTICATION)
@permission_classes([IsAuthenticated])
@require_any_module(["manufacturing", "restaurant"])
def update_production_order_lines(request, order_id):
    """Update/delete production order lines (inline editing). Update only; no create (lines come from BOM refresh)."""
    try:
        order = ProductionOrder.objects.get(id=order_id)
    except ProductionOrder.DoesNotExist:
        return Response(
            {"error": "Production order not found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    raw = request.data.get("lines", []) or []
    to_delete = []
    remaining = []

    for payload in raw:
        try:
            line_id = int(payload.get("id")) if payload.get("id") is not None else None
        except (TypeError, ValueError):
            line_id = None
        if payload.get("is_deleted") and line_id:
            to_delete.append(line_id)
        else:
            if "is_deleted" in payload:
                payload = {k: v for k, v in payload.items() if k != "is_deleted"}
            remaining.append(payload)

    with transaction.atomic():
        if to_delete:
            order.lines.filter(id__in=to_delete).delete()

        existing = {line.id: line for line in order.lines.all()}
        for line_data in remaining:
            try:
                line_id = (
                    int(line_data.get("id"))
                    if line_data.get("id") is not None
                    else None
                )
            except (TypeError, ValueError):
                line_id = None
            if line_id and line_id in existing:
                line = existing[line_id]
                if "quantity" in line_data:
                    try:
                        line.quantity = float(line_data["quantity"])
                    except (TypeError, ValueError):
                        pass
                if "finished_quantity" in line_data:
                    try:
                        line.finished_quantity = float(line_data["finished_quantity"])
                    except (TypeError, ValueError):
                        pass
                if "status" in line_data:
                    line.status = line_data["status"]
                if "start_date" in line_data and line_data["start_date"]:
                    from django.utils.dateparse import parse_date

                    parsed = parse_date(line_data["start_date"])
                    if parsed:
                        line.start_date = parsed
                if "ending_date" in line_data and line_data["ending_date"]:
                    from django.utils.dateparse import parse_date

                    parsed = parse_date(line_data["ending_date"])
                    if parsed:
                        line.ending_date = parsed
                if "due_date" in line_data and line_data["due_date"]:
                    from django.utils.dateparse import parse_date

                    parsed = parse_date(line_data["due_date"])
                    if parsed:
                        line.due_date = parsed
                line.save()

    order.refresh_from_db()
    serializer = ProductionOrderSerializer(
        ProductionOrder.objects.prefetch_related("lines", "components").get(id=order.id)
    )
    return Response(serializer.data)


@api_view(["POST"])
@authentication_classes(PRODUCTION_API_AUTHENTICATION)
@permission_classes([IsAuthenticated])
@require_any_module(["manufacturing", "restaurant"])
def finish_production_order(request, order_id):
    """
    Finish a released production order.

    - If every linked item journal is already **Posted** (e.g. posted from Item Journals),
      only updates order/lines/components to finished—no second posting run.
    - Otherwise posts **open** journals via manufacturing posting, then marks finished.
    """
    try:
        order = ProductionOrder.objects.get(id=order_id)
    except ProductionOrder.DoesNotExist:
        return Response(
            {"error": "Production order not found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    if order.status != "released":
        return Response(
            {
                "error": "Only released production orders can be finished.",
                "status": order.status,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Journals were posted from the item journal UI: nothing left to post; close the order only.
    if production_order_all_journals_posted(order):
        try:
            with transaction.atomic():
                order.status = "finished"
                order.save(update_fields=["status"])
                order.lines.update(status="completed")
                order.components.update(status="finished")
        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        serializer = ProductionOrderSerializer(
            ProductionOrder.objects.prefetch_related("lines", "components").get(
                id=order.id
            )
        )
        return Response(
            {
                "message": "Production finished. Item journals were already posted; order marked finished.",
                "order": serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    preview_data, errors = build_production_posting_preview(order)
    if errors:
        return Response(
            {"error": "Posting validation failed.", "errors": errors},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if not preview_data:
        return Response(
            {
                "error": "No posting data. Refresh from BOM or ensure open item journals exist."
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        with transaction.atomic():
            ProductionOrderPostingFromPreviewService(
                order, request.user, preview_data
            ).post()
            order.status = "finished"
            order.save(update_fields=["status"])
            order.lines.update(status="completed")
            order.components.update(status="finished")
    except ProductionOrderPostingError as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    serializer = ProductionOrderSerializer(
        ProductionOrder.objects.prefetch_related("lines", "components").get(id=order.id)
    )
    return Response(
        {"message": "Production finished.", "order": serializer.data},
        status=status.HTTP_200_OK,
    )


@api_view(["DELETE"])
@authentication_classes(PRODUCTION_API_AUTHENTICATION)
@permission_classes([IsAuthenticated])
@require_any_module(["manufacturing", "restaurant"])
def delete_production_order(request, order_id):
    """Delete a production order."""
    try:
        order = ProductionOrder.objects.get(id=order_id)
    except ProductionOrder.DoesNotExist:
        return Response(
            {"error": "Production order not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    order.delete()
    return Response(
        {"message": "Production order deleted successfully"},
        status=status.HTTP_200_OK,
    )
