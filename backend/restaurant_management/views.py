from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .permissions import IsTenantSchema
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.authentication import SessionAuthentication
from authentication.authentication import (
    JWTAuthenticationWithRevocationChecks as JWTAuthentication,
)
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q, Sum, Count, Prefetch
from django.utils import timezone
from django.db import transaction
from django.db.models.deletion import ProtectedError
from django.db.utils import ProgrammingError
from django.utils.translation import gettext as _, ngettext
from datetime import datetime, timedelta
from decimal import Decimal
from collections import defaultdict
import json

from . import models
from . import serializers
from .enums import (
    OrderStatus,
    OrderItemStatus,
    FireState,
    PosActionType,
    TableShape,
    TableStatus,
    OrderType,
)
from .order_invoice import create_open_sales_invoice_from_restaurant_orders
from .order_guards import CLOSED_ORDER_ERROR, order_is_closed
from dimension.branch_filter import (
    filter_queryset_by_branch,
    filter_queryset_by_branch_location,
    filter_reservation_queryset,
    get_branch_for_request,
)


def _item_pos_stock_tracked_for_pos_tile(item) -> bool:
    """
    When False, POS should not show simple on-hand availability on the tile:
    non-inventory items, production BOM parents, and Prod. Order / Assembly flows.
    """
    from items.enums import InventoryType, ReplenishmentSystem

    if getattr(item, "type", None) != InventoryType.Inventory.value:
        return False
    if getattr(item, "production_bom_id", None):
        return False
    rs = (getattr(item, "replenishment_system", None) or "").strip()
    if rs in (ReplenishmentSystem.ProdOrder.value, ReplenishmentSystem.Assembly.value):
        return False
    return True


def _menu_item_primary_image_url(item, request):
    """First product image for POS tiles (absolute URL when request is present)."""
    if request is None:
        return None
    try:
        from items.models import ItemImages

        row = (
            ItemImages.objects.filter(item=item)
            .exclude(url__isnull=True)
            .exclude(url="")
            .order_by("-created_at")
            .first()
        )
        if not row or not row.url:
            return None
        rel = row.url.url
        if rel and str(rel).startswith(("http://", "https://")):
            return str(rel)
        return request.build_absolute_uri(rel)
    except Exception:
        return None


def _menu_item_pos_payload(mi: models.MenuItem, request=None):
    payload = {
        "id": mi.id,
        "item_no": mi.item.no,
        "item_name": mi.item.item_name,
        "unit_price": mi.item.unit_price,
        "tile_accent_color": (mi.tile_accent_color or "").strip(),
        "kitchen_facing_name": (mi.kitchen_facing_name or "").strip(),
        "display_order": mi.display_order,
    }
    img_url = _menu_item_primary_image_url(mi.item, request)
    if img_url:
        payload["primary_image_url"] = img_url
    if request is None:
        return payload
    user = getattr(request, "user", None)
    if not user or not getattr(user, "is_authenticated", False):
        return payload
    item = mi.item
    if not _item_pos_stock_tracked_for_pos_tile(item):
        payload["pos_stock_tracked"] = False
        return payload
    branch_dim = get_branch_for_request(request)
    branch_code = getattr(branch_dim, "code", None)
    if not branch_code:
        payload["pos_stock_tracked"] = True
        payload["pos_available_qty"] = None
        payload["pos_out_of_stock"] = False
        return payload
    from items.models import Location

    loc = Location.objects.filter(code=branch_code).first()
    if loc is None:
        payload["pos_stock_tracked"] = True
        payload["pos_available_qty"] = None
        payload["pos_out_of_stock"] = False
        return payload
    payload["pos_stock_tracked"] = True
    avail = _sum_on_hand(
        item,
        location=loc,
        global_dimension_1=branch_dim,
    )
    try:
        qty_int = int(avail)
    except (TypeError, ValueError):
        qty_int = int(Decimal(str(avail)))
    payload["pos_available_qty"] = qty_int
    payload["pos_out_of_stock"] = qty_int <= 0
    return payload


def _home_layout_tile_payload(t: models.MenuLayoutTile, request=None):
    """One cell on the POS home grid from MenuLayoutTile (page 1 / first page)."""
    base = {
        "id": t.id,
        "row": t.row,
        "column": t.column,
        "row_span": t.row_span,
        "col_span": t.col_span,
        "display_order": t.display_order,
        "accent_color": (t.accent_color or "").strip(),
    }
    if t.menu_item_id and getattr(t, "menu_item", None):
        mi_payload = _menu_item_pos_payload(t.menu_item, request=request)
        ac = (t.accent_color or "").strip()
        if ac:
            mi_payload["tile_accent_color"] = ac
        base["kind"] = "item"
        base["menu_item"] = mi_payload
        return base
    if t.display_group_id and getattr(t, "display_group", None):
        dg = t.display_group
        base["kind"] = "group"
        base["display_group"] = {
            "id": dg.id,
            "name": dg.name,
            "tile_color": (dg.tile_color or "").strip(),
            "icon": (dg.icon or "").strip(),
            "display_order": dg.display_order,
        }
        return base
    base["kind"] = "empty"
    return base


def _build_menu_display_group_branch(
    menu_pk: int, group: models.MenuDisplayGroup, request=None
):
    """Recursive POS node: either `children` (sub-groups) or `items` (leaf), never both."""
    has_sub = models.MenuDisplayGroup.objects.filter(
        parent=group, is_active=True
    ).exists()
    base = {
        "id": group.id,
        "name": group.name,
        "tile_color": (group.tile_color or "").strip(),
        "icon": (group.icon or "").strip(),
        "display_order": group.display_order,
    }
    if has_sub:
        kids = models.MenuDisplayGroup.objects.filter(
            parent=group, is_active=True
        ).order_by("display_order", "name")
        base["children"] = [
            _build_menu_display_group_branch(menu_pk, g, request=request) for g in kids
        ]
        return base
    items = (
        models.MenuItem.objects.filter(
            menu_id=menu_pk, display_group=group, is_available=True
        )
        .select_related("item")
        .order_by("display_order", "item__item_name")
    )
    base["items"] = [_menu_item_pos_payload(mi, request=request) for mi in items]
    return base


def _resolve_branch_location_for_request(request):
    """
    Resolve the inventory Location from the effective branch for this API request.
    Prefers X-Branch-Id header (POS branch switcher), then user.global_dimension_1.
    Zentro convention: branch DimensionValue.code == Location.code.
    """
    from items.models import Location

    branch_dim = get_branch_for_request(request)
    branch_code = getattr(branch_dim, "code", None)
    if not branch_code:
        return None, "User has no branch (global_dimension_1) assigned."

    loc = Location.objects.filter(code=branch_code).first()
    if not loc:
        return None, f"Location '{branch_code}' not found for user's branch."
    return loc, None


def _sum_on_hand(item, *, location, global_dimension_1):
    """
    BC-like on-hand: sum remaining_quantity from Item Ledger Entries at the given location/dimension.
    """
    from items.models import ItemLedgerEntries

    return (
        ItemLedgerEntries.objects.filter(
            item=item,
            location=location,
            global_dimension_1=global_dimension_1,
        ).aggregate(total=Sum("remaining_quantity"))["total"]
        or 0
    )


def _collect_bom_component_requirements(item, quantity, *, visited_bom_ids=None):
    """
    Return dict[item_no -> required_qty] for the *component* items needed to produce `item`.
    Includes nested Production BOM lines.
    """
    from production.models import ProductionBOM

    if visited_bom_ids is None:
        visited_bom_ids = set()

    bom = getattr(item, "production_bom", None)
    if not bom:
        return {}

    # Safety against cyclic BOM graphs.
    if isinstance(bom, ProductionBOM) and bom.pk in visited_bom_ids:
        return {}
    if isinstance(bom, ProductionBOM):
        visited_bom_ids.add(bom.pk)

    requirements = {}  # item_no -> Decimal
    bom_lines = getattr(bom, "lines", None)
    if not bom_lines:
        return requirements

    for line in bom.lines.all().select_related("item"):
        if not line.item:
            continue

        qty_per = Decimal(str(line.quantity_per or 0))
        if qty_per <= 0:
            continue

        scrap_pct = Decimal(str(line.scrap_pct or 0))
        scrap_multiplier = (
            (Decimal("1") + (scrap_pct / Decimal("100"))) if scrap_pct else Decimal("1")
        )
        required_qty = (Decimal(str(quantity)) * qty_per) * scrap_multiplier

        if line.line_type == "item":
            key = line.item.no
            requirements[key] = requirements.get(key, Decimal("0")) + required_qty
            continue

        if line.line_type == "production_bom":
            nested = _collect_bom_component_requirements(
                line.item,
                required_qty,
                visited_bom_ids=visited_bom_ids,
            )
            for nested_no, nested_qty in (nested or {}).items():
                requirements[nested_no] = requirements.get(
                    nested_no, Decimal("0")
                ) + Decimal(str(nested_qty))

    return requirements


def _selected_sides_equal(left, right) -> bool:
    return json.dumps(left or [], sort_keys=True) == json.dumps(
        right or [], sort_keys=True
    )


def _find_mergeable_pos_order_item(
    order, item_obj, unit_price: Decimal, item_data: dict
):
    """
    Merge repeated POS taps onto one open line: pending, not yet fired (hold), same
    price, seat, check, notes, sides, and spice level.
    """
    spec = (item_data.get("special_instructions") or "").strip()
    sides = item_data.get("selected_sides") or []
    spice = item_data.get("spice_level")
    check_raw = item_data.get("restaurant_check")
    seat = item_data.get("seat_no")

    qs = order.order_items.filter(
        item=item_obj,
        status=OrderItemStatus.PENDING,
        fire_state=FireState.HOLD,
        unit_price=unit_price,
        spice_level=spice,
    )
    if check_raw is None:
        qs = qs.filter(restaurant_check__isnull=True)
    else:
        qs = qs.filter(restaurant_check_id=check_raw)

    if seat is None:
        qs = qs.filter(seat_no__isnull=True)
    else:
        qs = qs.filter(seat_no=seat)

    for cand in qs.order_by("id")[:50]:
        if (cand.special_instructions or "").strip() != spec:
            continue
        if not _selected_sides_equal(cand.selected_sides, sides):
            continue
        return cand
    return None


def _coerce_seat_no_for_add_items(order, seat_raw):
    """
    Validate/normalize seat assignment for POS add-items lines.

    Returns:
        (seat_no, error_message) where seat_no is int or None (whole table).
    """
    if seat_raw is None or seat_raw == "":
        return None, None

    if isinstance(seat_raw, bool):
        return None, "seat_no must be a positive integer"

    if isinstance(seat_raw, str):
        try:
            seat = int(seat_raw.strip(), 10)
        except (ValueError, TypeError):
            return None, "seat_no must be a positive integer"
    elif isinstance(seat_raw, int):
        seat = seat_raw
    else:
        return None, "seat_no must be a positive integer"

    if seat < 1:
        return None, "seat_no must be at least 1"

    if order.covers is None:
        return None, (
            "Set cover count before assigning items to a seat, or use table assignment."
        )

    if seat > order.covers:
        return None, (
            f"Seat {seat} is not available for this check (covers={order.covers}). "
            "Add a seat or choose a different assignment."
        )

    return seat, None


def _order_items_routes_to_kitchen_q():
    """
    Match order lines that belong on KDS / should receive kitchen fire.

    MenuItem.routes_to_kitchen: True forces kitchen; False forces skip; null inherits category.
    Inherit path: no MenuItem, uncategorized, or category.routes_to_kitchen True.
    """
    return (
        Q(item__menu_item__isnull=True)
        | Q(item__menu_item__routes_to_kitchen=True)
        | (
            Q(item__menu_item__routes_to_kitchen__isnull=True)
            & (
                Q(item__menu_item__category__isnull=True)
                | Q(item__menu_item__category__routes_to_kitchen=True)
            )
        )
    )


def _bar_order_ticket_payload(order, item_ids):
    """Structured payload for POS to print a Bar Order Ticket (non-kitchen lines)."""
    if not item_ids:
        return None
    order = models.RestaurantOrder.objects.select_related("table", "waiter").get(
        pk=order.pk
    )
    qs = (
        models.RestaurantOrderItem.objects.filter(id__in=item_ids, order=order)
        .select_related("item")
        .order_by("id")
    )
    lines = []
    for it in qs:
        lines.append(
            {
                "item_name": it.item.item_name if it.item else "",
                "quantity": str(it.quantity),
                "seat_no": it.seat_no,
                "special_instructions": (it.special_instructions or "").strip(),
            }
        )
    table_label = ""
    if order.table_id and order.table:
        tn = getattr(order.table, "table_number", None)
        if tn is not None and str(tn).strip() != "":
            table_label = str(tn)
        else:
            table_label = f"Table #{order.table_id}"
    waiter_name = ""
    if order.waiter_id:
        w = order.waiter
        waiter_name = (
            w.get_full_name()
            if hasattr(w, "get_full_name")
            else (getattr(w, "full_name", None) or str(w))
        )
    return {
        "ticket_type": "bar",
        "title": "BAR ORDER TICKET",
        "order_no": order.no,
        "table_label": table_label,
        "order_type_display": order.get_order_type_display(),
        "waiter_name": waiter_name,
        "printed_at": timezone.now().isoformat(),
        "lines": lines,
    }


class FloorViewSet(viewsets.ModelViewSet):
    """ViewSet for Floor model"""

    queryset = (
        models.Floor.objects.select_related("location")
        .all()
        .order_by("display_order", "name")
    )
    serializer_class = serializers.FloorSerializer
    permission_classes = [IsAuthenticated, IsTenantSchema]
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["location"]
    search_fields = ["no", "name", "description"]
    ordering_fields = ["name", "display_order", "created_at"]
    ordering = ["display_order", "name"]

    def get_queryset(self):
        qs = super().get_queryset()
        return filter_queryset_by_branch_location(
            qs, self.request.user, self.request, location_lookup="location"
        )


class FloorSectionViewSet(viewsets.ModelViewSet):
    """Floor sections (table groupings) and bulk table generation."""

    queryset = (
        models.FloorSection.objects.select_related("floor")
        .all()
        .order_by("floor", "display_order", "name")
    )
    serializer_class = serializers.FloorSectionSerializer
    permission_classes = [IsAuthenticated, IsTenantSchema]
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["floor"]
    search_fields = ["name"]
    ordering_fields = ["name", "display_order", "created_at"]
    ordering = ["floor", "display_order", "name"]

    def get_queryset(self):
        qs = super().get_queryset()
        return filter_queryset_by_branch_location(
            qs, self.request.user, self.request, location_lookup="floor__location"
        )

    @action(detail=True, methods=["post"], url_path="generate-tables")
    def generate_tables(self, request, pk=None):
        """Create multiple tables in this section (automatic or custom names)."""
        section = self.get_object()
        naming_mode = (request.data.get("naming_mode") or "auto").strip().lower()
        label = (request.data.get("label") or "").strip()
        try:
            count = int(request.data.get("count", 1))
        except (TypeError, ValueError):
            return Response(
                {"error": "count must be a positive integer."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if count < 1 or count > 100:
            return Response(
                {"error": "count must be between 1 and 100."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if naming_mode not in ("auto", "custom"):
            return Response(
                {"error": "naming_mode must be auto or custom."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        names = request.data.get("names")
        if naming_mode == "auto" and not label:
            return Response(
                {"error": "label is required for automatic table names."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if naming_mode == "custom":
            if not isinstance(names, list) or len(names) != count:
                return Response(
                    {
                        "error": "For custom naming, provide names array with the same length as count."
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
        try:
            pw = int(request.data.get("plan_width") or 80)
            ph = int(request.data.get("plan_height") or 80)
        except (TypeError, ValueError):
            return Response(
                {"error": "plan_width and plan_height must be integers."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        pw = max(40, min(pw, 400))
        ph = max(40, min(ph, 400))
        shape = (request.data.get("shape") or "rectangular").strip()
        valid_shapes = [c[0] for c in TableShape.choices]
        if shape not in valid_shapes:
            shape = TableShape.RECTANGULAR
        try:
            cap = int(request.data.get("capacity") or 4)
        except (TypeError, ValueError):
            cap = 4
        cap = max(1, min(cap, 99))

        created = []
        with transaction.atomic():
            for i in range(count):
                if naming_mode == "custom":
                    tn = str(names[i]).strip()
                    if not tn:
                        return Response(
                            {"error": f"Empty custom name at index {i}."},
                            status=status.HTTP_400_BAD_REQUEST,
                        )
                else:
                    tn = f"{label} {i + 1}".strip()
                t = models.Table(
                    floor=section.floor,
                    section=section,
                    table_number=tn[:50],
                    capacity=cap,
                    status=TableStatus.AVAILABLE,
                    shape=shape,
                    location_x=Decimal(str(i * (pw + 16))),
                    location_y=Decimal("0"),
                    plan_width=pw,
                    plan_height=ph,
                )
                t.save()
                created.append(t)
        return Response(
            serializers.TableSerializer(created, many=True).data,
            status=status.HTTP_201_CREATED,
        )


class TableViewSet(viewsets.ModelViewSet):
    """ViewSet for Table model"""

    queryset = (
        models.Table.objects.select_related("floor", "section")
        .all()
        .order_by("floor", "section", "table_number")
    )
    serializer_class = serializers.TableSerializer
    permission_classes = [IsAuthenticated, IsTenantSchema]
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["floor", "section", "status", "shape"]
    search_fields = ["no", "table_number", "notes"]
    ordering_fields = ["table_number", "capacity", "created_at"]
    ordering = ["floor", "table_number"]

    def get_queryset(self):
        qs = super().get_queryset()
        return filter_queryset_by_branch_location(
            qs, self.request.user, self.request, location_lookup="floor__location"
        )

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        try:
            self.perform_destroy(instance)
        except ProtectedError as exc:
            n = len(exc.protected_objects)
            detail = ngettext(
                "This table cannot be deleted because a restaurant order still references it. "
                "Resolve that order before removing the table.",
                "This table cannot be deleted because %(count)d restaurant orders still reference it. "
                "Resolve those orders before removing the table.",
                n,
            ) % {"count": n}
            return Response({"detail": detail}, status=status.HTTP_409_CONFLICT)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=["get"])
    def by_status(self, request):
        """Get tables grouped by status"""
        tables = self.get_queryset()
        status_groups = {}
        for status_code, status_label in models.TableStatus.choices:
            status_groups[status_code] = {
                "label": status_label,
                "tables": serializers.TableSerializer(
                    tables.filter(status=status_code), many=True
                ).data,
            }
        return Response(status_groups)

    @action(detail=True, methods=["post"], url_path="open-pos")
    def open_pos(self, request, pk=None):
        table = self.get_object()
        order_item_qs = models.RestaurantOrderItem.objects.select_related(
            "item", "item__menu_item", "item__menu_item__category"
        )
        active_orders = models.RestaurantOrder.objects.filter(
            table=table,
            sales_invoice__isnull=True,
            status__in=[
                OrderStatus.NEW,
                OrderStatus.IN_PROGRESS,
                OrderStatus.READY,
                OrderStatus.SERVED,
            ],
        ).prefetch_related(
            Prefetch("order_items", queryset=order_item_qs),
            "checks",
        )
        payload = {
            "table": serializers.TableSerializer(table).data,
            "active_orders": serializers.RestaurantOrderSerializer(
                active_orders, many=True, context={"request": request}
            ).data,
            "active_checks_count": sum(
                o.checks.filter(is_voided=False).count() for o in active_orders
            ),
            # All check lines not yet "sent" (kitchen or direct-ready) — matches POS Send.
            "unsent_items_count": models.RestaurantOrderItem.objects.filter(
                order__in=active_orders,
                fire_state=FireState.HOLD,
                status=OrderItemStatus.PENDING,
            ).count(),
            "fired_items_count": models.RestaurantOrderItem.objects.filter(
                order__in=active_orders,
                fire_state=FireState.FIRE,
            ).count(),
        }
        return Response(payload)


class ReservationViewSet(viewsets.ModelViewSet):
    """ViewSet for Reservation model"""

    queryset = (
        models.Reservation.objects.select_related("customer", "table", "waiter")
        .all()
        .order_by("-reservation_date")
    )
    serializer_class = serializers.ReservationSerializer
    permission_classes = [IsAuthenticated, IsTenantSchema]
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["status", "table", "waiter"]
    search_fields = ["no", "customer__name", "special_requests"]
    ordering_fields = ["reservation_date", "created_at"]
    ordering = ["-reservation_date"]

    def get_queryset(self):
        queryset = super().get_queryset()
        date_from = self.request.query_params.get("date_from")
        date_to = self.request.query_params.get("date_to")
        if date_from:
            queryset = queryset.filter(reservation_date__gte=date_from)
        if date_to:
            queryset = queryset.filter(reservation_date__lte=date_to)
        return filter_reservation_queryset(queryset, self.request.user, self.request)


class MenuCategoryViewSet(viewsets.ModelViewSet):
    """ViewSet for MenuCategory model"""

    queryset = (
        models.MenuCategory.objects.filter(is_active=True)
        .all()
        .order_by("display_order", "name")
    )
    serializer_class = serializers.MenuCategorySerializer
    permission_classes = [IsAuthenticated, IsTenantSchema]
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["is_active"]
    search_fields = ["no", "name", "description"]
    ordering_fields = ["name", "display_order", "created_at"]
    ordering = ["display_order", "name"]


class MenuItemViewSet(viewsets.ModelViewSet):
    """ViewSet for MenuItem model"""

    queryset = (
        models.MenuItem.objects.select_related(
            "item", "category", "menu", "display_group"
        )
        .all()
        .order_by("category", "display_order", "item__item_name")
    )
    serializer_class = serializers.MenuItemSerializer
    permission_classes = [IsAuthenticated, IsTenantSchema]
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = [
        "category",
        "is_available",
        "is_featured",
        "menu",
        "display_group",
    ]
    search_fields = ["item__item_name", "description"]
    ordering_fields = ["item__item_name", "display_order", "created_at"]
    ordering = ["category", "display_order", "item__item_name"]

    def create(self, request, *args, **kwargs):
        """Create or return existing MenuItem for the same POS Item (OneToOne on item)."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        item = serializer.validated_data.get("item")
        if item is not None:
            existing = models.MenuItem.objects.filter(item=item).first()
            if existing:
                sm = serializer.validated_data.get("menu")
                if sm is not None and existing.menu_id != sm.id:
                    existing.menu = sm
                    existing.save(update_fields=["menu", "updated_at"])
                output = serializers.MenuItemSerializer(
                    existing, context=self.get_serializer_context()
                )
                headers = self.get_success_headers(output.data)
                return Response(output.data, status=status.HTTP_200_OK, headers=headers)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(
            serializer.data, status=status.HTTP_201_CREATED, headers=headers
        )

    @action(detail=False, methods=["get"])
    def by_category(self, request):
        """Get menu items grouped by category"""
        items = self.get_queryset().filter(is_available=True)
        categories = {}
        for item in items:
            category_name = item.category.name if item.category else "Uncategorized"
            if category_name not in categories:
                categories[category_name] = []
            categories[category_name].append(serializers.MenuItemSerializer(item).data)
        return Response(categories)


class RestaurantOrderViewSet(viewsets.ModelViewSet):
    """ViewSet for RestaurantOrder model"""

    queryset = (
        models.RestaurantOrder.objects.select_related(
            "table", "customer", "waiter", "reservation"
        )
        .prefetch_related("order_items__item")
        .all()
        .order_by("-created_at")
    )
    serializer_class = serializers.RestaurantOrderSerializer
    permission_classes = [IsAuthenticated, IsTenantSchema]
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["status", "order_type", "table", "waiter"]
    search_fields = ["no", "table__table_number", "customer__name", "notes"]
    ordering_fields = ["created_at", "total_amount"]
    ordering = ["-created_at"]

    def get_serializer_class(self):
        # Use RestaurantOrderCreateSerializer for create and update (when order_items are present)
        if self.action == "create":
            return serializers.RestaurantOrderCreateSerializer
        elif self.action in ["update", "partial_update"]:
            # Check if order_items are in the request data
            if (
                hasattr(self, "request")
                and self.request
                and "order_items" in self.request.data
            ):
                return serializers.RestaurantOrderCreateSerializer
        return serializers.RestaurantOrderSerializer

    def get_queryset(self):
        hide_fired = self.request.query_params.get("hide_fired")
        item_qs = models.RestaurantOrderItem.objects.select_related(
            "item", "item__menu_item", "item__menu_item__category"
        )
        if hide_fired in ("1", "true", "True"):
            item_qs = item_qs.exclude(fire_state=FireState.FIRE)
        qs = (
            models.RestaurantOrder.objects.select_related(
                "table", "customer", "waiter", "reservation", "global_dimension_1"
            )
            .prefetch_related(
                Prefetch("order_items", queryset=item_qs),
                "checks",
            )
            .all()
            .order_by("-created_at")
        )
        return filter_queryset_by_branch(qs, self.request.user, request=self.request)

    def _log_action(self, order, action_type, order_item=None, metadata=None):
        models.OrderActionLog.objects.create(
            order=order,
            order_item=order_item,
            actor=self.request.user if self.request.user.is_authenticated else None,
            action_type=action_type,
            metadata=metadata or {},
        )

    def _closed_order_response(self):
        return Response(
            {"error": CLOSED_ORDER_ERROR},
            status=status.HTTP_400_BAD_REQUEST,
        )

    def update(self, request, *args, **kwargs):
        if order_is_closed(self.get_object()):
            return self._closed_order_response()
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        if order_is_closed(self.get_object()):
            return self._closed_order_response()
        return super().partial_update(request, *args, **kwargs)

    @action(detail=True, methods=["post"])
    def update_status(self, request, pk=None):
        """Update order status"""
        order = self.get_object()
        if order_is_closed(order):
            return self._closed_order_response()
        new_status = request.data.get("status")
        if new_status not in dict(OrderStatus.choices):
            return Response(
                {"error": "Invalid status"}, status=status.HTTP_400_BAD_REQUEST
            )
        order.status = new_status
        order.save()
        return Response(
            serializers.RestaurantOrderSerializer(
                order, context={"request": request}
            ).data
        )

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        """Close out an order as completed (mobile POS)."""
        order = self.get_object()
        order.status = OrderStatus.COMPLETED
        order.save()
        return Response(
            serializers.RestaurantOrderSerializer(
                order, context={"request": request}
            ).data
        )

    @action(detail=False, methods=["get"])
    def kitchen_orders(self, request):
        """Get orders for kitchen display (new, in_progress, ready)"""
        orders = self.get_queryset().filter(
            status__in=[OrderStatus.NEW, OrderStatus.IN_PROGRESS, OrderStatus.READY]
        )
        serializer = self.get_serializer(orders, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def active_tables(self, request):
        """Get tables with active orders"""
        active_orders = self.get_queryset().filter(
            status__in=[OrderStatus.NEW, OrderStatus.IN_PROGRESS, OrderStatus.READY]
        )
        table_ids = active_orders.values_list("table_id", flat=True).distinct()
        tables = models.Table.objects.filter(id__in=table_ids)
        return Response(serializers.TableSerializer(tables, many=True).data)

    @action(detail=True, methods=["post"])
    def recalculate_total(self, request, pk=None):
        """Manually recalculate order total (useful for fixing incorrect totals)"""
        order = self.get_object()
        old_total = order.total_amount
        order.recalculate_total()
        order.refresh_from_db()
        # Align header status with lines (e.g. all lines cancelled → order cancelled)
        self.update_order_status_from_items(order)
        order.save(update_fields=["status"])

        return Response(
            {
                "message": "Order total recalculated",
                "old_total": str(old_total),
                "new_total": str(order.total_amount),
                "order": serializers.RestaurantOrderSerializer(
                    order, context={"request": request}
                ).data,
            }
        )

    def destroy(self, request, *args, **kwargs):
        order = self.get_object()
        if order.sales_invoice_id:
            return Response(
                {"error": "Cannot delete an order that has been invoiced."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if order.status == OrderStatus.COMPLETED:
            return Response(
                {"error": "Cannot delete a completed order."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().destroy(request, *args, **kwargs)

    def update_order_status_from_items(self, order):
        """Intelligently update order status based on item statuses"""
        items = order.order_items.all()

        if not items.exists():
            order.status = OrderStatus.NEW
            return

        # Count items by status
        status_counts = {
            "pending": items.filter(status=OrderItemStatus.PENDING).count(),
            "preparing": items.filter(status=OrderItemStatus.PREPARING).count(),
            "ready": items.filter(status=OrderItemStatus.READY).count(),
            "served": items.filter(status=OrderItemStatus.SERVED).count(),
            "cancelled": items.filter(status=OrderItemStatus.CANCELLED).count(),
        }

        total_items = items.count()
        active_items = total_items - status_counts["cancelled"]

        # If all items are cancelled, mark order as cancelled
        if status_counts["cancelled"] == total_items and total_items > 0:
            order.status = OrderStatus.CANCELLED
        # Determine order status based on item statuses
        elif status_counts["served"] == active_items:
            # All items served
            order.status = OrderStatus.SERVED
        elif status_counts["ready"] == active_items:
            # All items ready (but not all served)
            order.status = OrderStatus.READY
        elif status_counts["preparing"] > 0 or status_counts["ready"] > 0:
            # Some items are being prepared or ready
            order.status = OrderStatus.IN_PROGRESS
        elif status_counts["pending"] == active_items:
            # All items are pending: unsent (hold) vs sent to kitchen (fire)
            if items.filter(
                status=OrderItemStatus.PENDING, fire_state=FireState.FIRE
            ).exists():
                order.status = OrderStatus.IN_PROGRESS
            else:
                order.status = OrderStatus.NEW
        else:
            # Mixed state - default to in_progress
            order.status = OrderStatus.IN_PROGRESS

    def _get_status_message(self, old_status, new_status, items_added):
        """Generate human-readable status message"""
        if (
            old_status == OrderStatus.IN_PROGRESS
            and new_status == OrderStatus.IN_PROGRESS
        ):
            return f"{items_added} item(s) added. Kitchen is already preparing other items. New items are pending and will be picked up by kitchen."
        elif old_status == OrderStatus.READY and new_status == OrderStatus.IN_PROGRESS:
            return f"{items_added} item(s) added. Order status updated to 'In Progress' as new items need preparation."
        elif old_status == OrderStatus.SERVED and new_status == OrderStatus.NEW:
            return f"{items_added} item(s) added. Order reset to 'New' and will be sent to kitchen."
        else:
            return f"{items_added} item(s) added successfully."

    @action(detail=True, methods=["post"], url_path="add-items")
    def add_items(self, request, pk=None):
        """Add items to existing order with smart status management"""
        order = self.get_object()

        # Validate order can accept new items
        if order_is_closed(order):
            return Response(
                {"error": CLOSED_ORDER_ERROR},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Voided check with no payment — reopen when adding new items (quick sale / table).
        if order.status == OrderStatus.CANCELLED and not order.sales_invoice_id:
            order.status = OrderStatus.NEW
            order.save(update_fields=["status", "updated_at"])

        order_items_data = request.data.get("order_items", [])
        if not order_items_data:
            return Response(
                {"error": "No items provided"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get current order status before adding items
        current_order_status = order.status
        has_preparing_items = order.order_items.filter(
            Q(status=OrderItemStatus.PREPARING)
            | Q(status=OrderItemStatus.PENDING, fire_state=FireState.FIRE)
        ).exists()
        has_ready_items = order.order_items.filter(
            status=OrderItemStatus.READY
        ).exists()

        # Resolve inventory context (Branch + Location); honor X-Branch-Id from POS.
        location_to_use, loc_err = _resolve_branch_location_for_request(request)
        if loc_err:
            return Response({"error": loc_err}, status=status.HTTP_400_BAD_REQUEST)

        effective_branch = get_branch_for_request(request)

        # Create new order items with status "pending"
        from items.models import Item

        created_items = []
        insufficient = []

        # Stage 1 rule: stock check on add (BOM checks components, non-BOM checks item)
        from items.enums import InventoryType

        for item_data in order_items_data:
            # Resolve item by 'no' if it's a string (Item uses 'no' as primary key)
            item_value = item_data.get("item")
            if isinstance(item_value, str):
                try:
                    item_obj = Item.objects.get(no=item_value)
                except Item.DoesNotExist:
                    return Response(
                        {"error": f"Item with no '{item_value}' not found"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            else:
                item_obj = item_value

            try:
                requested_qty = Decimal(str(item_data.get("quantity", 1) or 1))
            except Exception:
                requested_qty = Decimal("1")
            if requested_qty <= 0:
                return Response(
                    {"error": "Quantity must be greater than 0"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if getattr(item_obj, "production_bom", None):
                reqs = _collect_bom_component_requirements(item_obj, requested_qty)
                for comp_no, comp_required in (reqs or {}).items():
                    comp_item = Item.objects.filter(no=comp_no).first()
                    if not comp_item:
                        insufficient.append(
                            {
                                "itemNo": comp_no,
                                "itemName": comp_no,
                                "requiredQty": float(comp_required),
                                "availableQty": 0,
                                "reason": "Component item not found",
                            }
                        )
                        continue
                    if (
                        getattr(comp_item, "type", None)
                        != InventoryType.Inventory.value
                    ):
                        continue
                    available = _sum_on_hand(
                        comp_item,
                        location=location_to_use,
                        global_dimension_1=effective_branch,
                    )
                    if Decimal(str(available)) < Decimal(str(comp_required)):
                        insufficient.append(
                            {
                                "itemNo": comp_item.no,
                                "itemName": comp_item.item_name,
                                "requiredQty": float(comp_required),
                                "availableQty": int(available),
                                "forItemNo": item_obj.no,
                                "forItemName": item_obj.item_name,
                            }
                        )
            else:
                # Finished good with no BOM: only true Inventory items consume branch ledger qty.
                if not _item_pos_stock_tracked_for_pos_tile(item_obj):
                    continue
                available = _sum_on_hand(
                    item_obj,
                    location=location_to_use,
                    global_dimension_1=effective_branch,
                )
                if Decimal(str(available)) < requested_qty:
                    insufficient.append(
                        {
                            "itemNo": item_obj.no,
                            "itemName": item_obj.item_name,
                            "requiredQty": float(requested_qty),
                            "availableQty": int(available),
                        }
                    )

        if insufficient:
            return Response(
                {
                    "error": "Insufficient stock",
                    "reason": "Insufficient stock",
                    "details": insufficient,
                    "location": getattr(location_to_use, "code", None),
                    "branch": getattr(effective_branch, "code", None),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        for item_data in order_items_data:
            item_value = item_data.get("item")
            if isinstance(item_value, str):
                item_obj = Item.objects.get(no=item_value)
            else:
                item_obj = item_value

            try:
                add_qty = Decimal(str(item_data.get("quantity", 1) or 1))
            except Exception:
                add_qty = Decimal("1")

            unit_price_dec = Decimal(str(item_data.get("unit_price", 0) or 0))

            seat_no, seat_err = _coerce_seat_no_for_add_items(
                order, item_data.get("seat_no")
            )
            if seat_err:
                return Response(
                    {"error": seat_err},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            item_data["seat_no"] = seat_no

            existing = _find_mergeable_pos_order_item(
                order, item_obj, unit_price_dec, item_data
            )
            if existing is not None:
                existing.quantity = existing.quantity + add_qty
                existing.save()
                created_items.append(existing)
            else:
                order_item = models.RestaurantOrderItem.objects.create(
                    order=order,
                    item=item_obj,
                    quantity=add_qty,
                    unit_price=unit_price_dec,
                    special_instructions=item_data.get("special_instructions"),
                    selected_sides=item_data.get("selected_sides", []),
                    spice_level=item_data.get("spice_level"),
                    seat_no=seat_no,
                    status=OrderItemStatus.PENDING,
                )
                created_items.append(order_item)

        # Recalculate order total
        order.recalculate_total()

        # Smart status management based on current state
        if current_order_status == OrderStatus.SERVED:
            # Customer wants more after being served - reset to new
            order.status = OrderStatus.NEW
        elif has_preparing_items or has_ready_items:
            # Kitchen is already working - keep as in_progress
            # New items are "pending" and will be picked up by kitchen
            order.status = OrderStatus.IN_PROGRESS
        elif current_order_status == OrderStatus.READY:
            # All items were ready, but new items added - back to in_progress
            order.status = OrderStatus.IN_PROGRESS
        else:
            # Order was "new" - keep as "new" (all items pending)
            # Or use intelligent status update
            self.update_order_status_from_items(order)

        order.save(update_fields=["status", "total_amount", "updated_at"])

        # `get_object()` used an order with prefetched `order_items`; new lines do not appear
        # in that cache. Refetch so the serializer returns the lines just created.
        order = self.get_queryset().get(pk=order.pk)

        # Return response with status message
        response_data = self.get_serializer(order).data
        response_data["status_message"] = self._get_status_message(
            current_order_status, order.status, len(created_items)
        )

        return Response(response_data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    def fire(self, request, pk=None):
        order = self.get_object()
        if order_is_closed(order):
            return Response(
                {"error": CLOSED_ORDER_ERROR},
                status=status.HTTP_400_BAD_REQUEST,
            )
        item_ids = request.data.get("item_ids", [])
        target_items = order.order_items.filter(
            status=OrderItemStatus.PENDING, fire_state=FireState.HOLD
        )
        if item_ids:
            target_items = target_items.filter(id__in=item_ids)

        kitchen_q = _order_items_routes_to_kitchen_q()
        kitchen_qs = target_items.filter(kitchen_q)
        non_kitchen_qs = target_items.exclude(kitchen_q)
        non_kitchen_ids = list(non_kitchen_qs.values_list("id", flat=True))

        now = timezone.now()
        kitchen_ids = list(kitchen_qs.values_list("id", flat=True))
        with transaction.atomic():
            k_count = kitchen_qs.update(
                fire_state=FireState.FIRE,
                fired_at=now,
                status=OrderItemStatus.PENDING,
            )
            # Bar / counter lines: ready at bar; BOT printed at POS (not on KDS).
            nk_count = non_kitchen_qs.update(status=OrderItemStatus.READY)

        total_updated = k_count + nk_count
        if total_updated > 0:
            order = self.get_object()
            self.update_order_status_from_items(order)
            order.save(update_fields=["status", "updated_at"])
        self._log_action(
            order,
            PosActionType.FIRE_ITEMS,
            metadata={
                "item_ids": item_ids,
                "updated_count": total_updated,
                "kitchen_count": k_count,
                "direct_ready_count": nk_count,
            },
        )
        parts = []
        if k_count:
            parts.append(
                ngettext(
                    "Sent %(count)d item to kitchen",
                    "Sent %(count)d items to kitchen",
                    k_count,
                )
                % {"count": k_count}
            )
        if nk_count:
            parts.append(
                ngettext(
                    "Bar: %(count)d item — print bar ticket",
                    "Bar: %(count)d items — print bar ticket",
                    nk_count,
                )
                % {"count": nk_count}
            )
        message = "; ".join(parts) if parts else _("No pending items to send")
        bar_order_ticket = None
        if nk_count and non_kitchen_ids:
            from receipt_templates.services.payloads import build_kot_bar_ticket_payload

            bar_order_ticket = build_kot_bar_ticket_payload(
                self.get_object(),
                non_kitchen_ids,
                receipt_type="bar",
                title="BAR ORDER TICKET",
            )
        kitchen_order_ticket = None
        if k_count:
            from receipt_templates.services.payloads import build_kot_bar_ticket_payload

            kitchen_order_ticket = build_kot_bar_ticket_payload(
                self.get_object(),
                kitchen_ids,
                receipt_type="kot",
                title="KITCHEN ORDER",
            )
        return Response(
            {
                "message": message,
                "updated_count": total_updated,
                "kitchen_count": k_count,
                "direct_ready_count": nk_count,
                "bar_order_ticket": bar_order_ticket,
                "kitchen_order_ticket": kitchen_order_ticket,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], url_path="split-check")
    def split_check(self, request, pk=None):
        order = self.get_object()
        source_check_id = request.data.get("source_check_id")
        item_ids = request.data.get("item_ids", [])
        target_name = request.data.get("target_name") or "Split Check"
        if not item_ids:
            return Response({"error": "item_ids are required"}, status=400)
        with transaction.atomic():
            target_check = models.RestaurantCheck.objects.create(
                order=order,
                name=target_name,
                status=order.status,
            )
            moved = models.RestaurantOrderItem.objects.filter(
                order=order,
                id__in=item_ids,
            ).update(restaurant_check=target_check)
            target_check.subtotal_amount = (
                models.RestaurantOrderItem.objects.filter(restaurant_check=target_check)
                .exclude(status=OrderItemStatus.CANCELLED)
                .aggregate(total=Sum("total_price"))
                .get("total")
                or 0
            )
            target_check.total_amount = target_check.subtotal_amount
            target_check.save(
                update_fields=["subtotal_amount", "total_amount", "updated_at"]
            )
        self._log_action(
            order,
            PosActionType.SPLIT_CHECK,
            metadata={
                "source_check_id": source_check_id,
                "target_check_id": target_check.id,
                "moved_count": moved,
                "item_ids": item_ids,
            },
        )
        return Response(serializers.RestaurantCheckSerializer(target_check).data)

    @action(detail=True, methods=["post"], url_path="move-items")
    def move_items(self, request, pk=None):
        order = self.get_object()
        item_ids = request.data.get("item_ids", [])
        target_check_id = request.data.get("target_check_id")
        if not item_ids or not target_check_id:
            return Response(
                {"error": "item_ids and target_check_id are required"}, status=400
            )
        target_check = models.RestaurantCheck.objects.filter(
            order=order, id=target_check_id
        ).first()
        if not target_check:
            return Response({"error": "Target check not found"}, status=404)
        moved = models.RestaurantOrderItem.objects.filter(
            order=order, id__in=item_ids
        ).update(restaurant_check=target_check)
        self._log_action(
            order,
            PosActionType.MOVE_ITEMS,
            metadata={
                "target_check_id": target_check_id,
                "item_ids": item_ids,
                "moved_count": moved,
            },
        )
        return Response({"moved_count": moved})

    @action(detail=True, methods=["post"], url_path="void-check")
    def void_check(self, request, pk=None):
        order = self.get_object()
        check_id = request.data.get("check_id")
        check = models.RestaurantCheck.objects.filter(order=order, id=check_id).first()
        if not check:
            return Response({"error": "Check not found"}, status=404)
        check.is_voided = True
        check.status = OrderStatus.CANCELLED
        check.save(update_fields=["is_voided", "status", "updated_at"])
        models.RestaurantOrderItem.objects.filter(restaurant_check=check).update(
            status=OrderItemStatus.CANCELLED
        )
        order.recalculate_total()
        self._log_action(
            order,
            PosActionType.VOID_CHECK,
            metadata={"check_id": check_id},
        )
        return Response({"message": "Check voided"})

    @action(detail=True, methods=["post"], url_path="comp-check")
    def comp_check(self, request, pk=None):
        order = self.get_object()
        check_id = request.data.get("check_id")
        check = models.RestaurantCheck.objects.filter(order=order, id=check_id).first()
        if not check:
            return Response({"error": "Check not found"}, status=404)
        check.is_comped = True
        check.total_amount = 0
        check.save(update_fields=["is_comped", "total_amount", "updated_at"])
        models.RestaurantOrderItem.objects.filter(restaurant_check=check).update(
            total_price=0
        )
        order.recalculate_total()
        self._log_action(
            order,
            PosActionType.COMP_CHECK,
            metadata={"check_id": check_id},
        )
        return Response({"message": "Check comped"})

    @action(detail=True, methods=["post"], url_path="clear-new-items")
    def clear_new_items(self, request, pk=None):
        order = self.get_object()
        item_ids = list(
            order.order_items.filter(
                status=OrderItemStatus.PENDING, fire_state=FireState.HOLD
            ).values_list("id", flat=True)
        )
        cleared = order.order_items.filter(id__in=item_ids).delete()[0]
        order.recalculate_total()
        self._log_action(
            order,
            PosActionType.CLEAR_NEW_ITEMS,
            metadata={"item_ids": item_ids, "cleared_count": cleared},
        )
        return Response({"cleared_count": cleared})

    @action(detail=False, methods=["get"], url_path="open-counter-pos")
    def open_counter_pos(self, request):
        """Resume walk-in / counter quick-sale session for the current waiter."""
        order_item_qs = models.RestaurantOrderItem.objects.select_related(
            "item", "item__menu_item", "item__menu_item__category"
        )
        order_base = filter_queryset_by_branch(
            models.RestaurantOrder.objects.all(),
            request.user,
            request=request,
        )
        active_orders = (
            order_base.filter(
                table__isnull=True,
                sales_invoice__isnull=True,
                order_type__in=[OrderType.TAKEOUT, OrderType.DELIVERY],
                status__in=[
                    OrderStatus.NEW,
                    OrderStatus.IN_PROGRESS,
                    OrderStatus.READY,
                    OrderStatus.SERVED,
                ],
            )
            .prefetch_related(
                Prefetch("order_items", queryset=order_item_qs),
                "checks",
            )
            .order_by("-created_at")
        )
        payload = {
            "table": None,
            "active_orders": serializers.RestaurantOrderSerializer(
                active_orders, many=True, context={"request": request}
            ).data,
            "active_checks_count": sum(
                o.checks.filter(is_voided=False).count() for o in active_orders
            ),
            "unsent_items_count": models.RestaurantOrderItem.objects.filter(
                order__in=active_orders,
                fire_state=FireState.HOLD,
                status=OrderItemStatus.PENDING,
            ).count(),
            "fired_items_count": models.RestaurantOrderItem.objects.filter(
                order__in=active_orders,
                fire_state=FireState.FIRE,
            ).count(),
        }
        return Response(payload)

    @action(detail=False, methods=["get"])
    def my_orders(self, request):
        """Get orders for current waiter"""
        waiter_id = request.user.id
        orders = self.get_queryset().filter(waiter_id=waiter_id)

        # Filter by status if provided
        status_filter = request.query_params.get("status")
        if status_filter:
            orders = orders.filter(status=status_filter)

        serializer = self.get_serializer(orders, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def ready_orders(self, request):
        """Get orders with ready items for current waiter (orders with at least one ready item)"""
        waiter_id = request.user.id

        # Get orders that have at least one ready item
        from django.db.models import Count, Q

        orders = (
            self.get_queryset()
            .filter(waiter_id=waiter_id)
            .annotate(
                ready_items_count=Count(
                    "order_items", filter=Q(order_items__status=OrderItemStatus.READY)
                )
            )
            .filter(ready_items_count__gt=0)
            .prefetch_related("order_items")
        )

        serializer = self.get_serializer(orders, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"], url_path="convert-to-invoice")
    def convert_to_invoice(self, request, pk=None):
        """Convert RestaurantOrder to SalesInvoice (with option to combine)"""
        order = self.get_object()

        # Check if should combine with other orders for same table
        combine_orders = request.data.get("combine_orders", False)

        if combine_orders:
            # Get all orders for same table that are served/completed
            table_orders = models.RestaurantOrder.objects.filter(
                table=order.table,
                status__in=[OrderStatus.SERVED, OrderStatus.COMPLETED],
                sales_invoice__isnull=True,  # Not yet invoiced
            ).order_by("created_at")

            if table_orders.count() == 0:
                return Response(
                    {"error": "No orders found to combine"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            # Single order only
            table_orders = [order]

        # Validate all orders can be converted
        for o in table_orders:
            if o.status not in [OrderStatus.SERVED, OrderStatus.COMPLETED]:
                return Response(
                    {"error": f"Order {o.no} must be served or completed"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if o.sales_invoice:
                return Response(
                    {"error": f"Order {o.no} is already invoiced"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Validate customer exists (use first order's customer)
        if not order.customer:
            return Response(
                {"error": "Order must have a customer to create an invoice"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            with transaction.atomic():
                # Use cashier branch to resolve inventory Location (BC-like)
                location_to_use, loc_err = _resolve_branch_location_for_request(request)
                if loc_err:
                    return Response(
                        {"error": loc_err},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                if not location_to_use:
                    return Response(
                        {
                            "error": "No location configured. Please set up a location first."
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                invoice = create_open_sales_invoice_from_restaurant_orders(
                    request,
                    list(table_orders),
                    order.customer,
                    location_to_use,
                    combine_orders=combine_orders,
                )

                # Serialize invoice for response
                from sales.serializers import SalesInvoiceSerializer

                invoice_serializer = SalesInvoiceSerializer(invoice)

                return Response(
                    {
                        "message": f"{'Combined' if combine_orders else 'Order'} converted to invoice successfully",
                        "invoice": invoice_serializer.data,
                        "combined_orders": (
                            [o.no for o in table_orders]
                            if combine_orders
                            else [order.no]
                        ),
                        "total_orders": len(table_orders),
                    },
                    status=status.HTTP_200_OK,
                )
        except Exception as e:
            import traceback

            traceback.print_exc()
            return Response(
                {"error": f"Failed to convert order to invoice: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=True, methods=["post"], url_path="checkout-and-post")
    def checkout_and_post(self, request, pk=None):
        """
        Close check in one step: create sales invoice from served order(s), apply
        payment, post (inventory + G/L), return posted invoice for receipt printing.
        Same combine_orders rules as convert-to-invoice (optional whole-table bill).
        """
        import uuid

        from django.contrib import admin

        from financials.models import PaymentMethod
        from sales.admin import SalesInvoiceAdmin, SalesInvoicePostingProcessor
        from sales.models import Customer, SalesInvoice
        from sales.serializers import SalesInvoiceSerializer

        order = self.get_object()
        combine_orders = request.data.get("combine_orders", False)
        raw_check_id = request.data.get("check_id", None)
        check_id = None
        if raw_check_id is not None and raw_check_id != "" and raw_check_id != "all":
            if str(raw_check_id).lower() == "main":
                check_id = "main"
            else:
                try:
                    check_id = int(raw_check_id)
                except (TypeError, ValueError):
                    return Response(
                        {"error": _("Invalid check_id.")},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

        if combine_orders and check_id is not None:
            return Response(
                {"error": _("Cannot combine table orders while settling a single split check.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if combine_orders:
            table_orders = list(
                models.RestaurantOrder.objects.filter(
                    table=order.table,
                    status__in=[OrderStatus.SERVED, OrderStatus.COMPLETED],
                    sales_invoice__isnull=True,
                ).order_by("created_at")
            )
            if not table_orders:
                return Response(
                    {"error": "No orders found to combine"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            table_orders = [order]

        from .order_invoice import _unpaid_order_items_qs

        for o in table_orders:
            if o.sales_invoice_id and check_id is None:
                return Response(
                    {"error": f"Order {o.no} is already invoiced"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            unpaid = _unpaid_order_items_qs(o, check_id=check_id)
            if not unpaid.exists():
                return Response(
                    {"error": _("No unpaid items found for this check.")},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            # Full settle still requires the order (or remaining lines) to be served.
            # Split-check settle only requires the selected segment's lines to be served.
            if check_id is None:
                if o.status not in [OrderStatus.SERVED, OrderStatus.COMPLETED]:
                    return Response(
                        {
                            "error": f"Order {o.no} must be served or completed",
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            else:
                unserved = unpaid.exclude(status=OrderItemStatus.SERVED)
                if unserved.exists():
                    return Response(
                        {
                            "error": _(
                                "All items on this check must be served before payment."
                            ),
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )

        customer = None
        customer_id = request.data.get("customer_id")
        try:
            if customer_id is not None:
                customer = Customer.objects.get(id=int(customer_id))
                for o in table_orders:
                    if o.customer_id != customer.id:
                        o.customer = customer
                        o.save(update_fields=["customer", "updated_at"])
                order.refresh_from_db()
            else:
                customer = order.customer
        except (Customer.DoesNotExist, TypeError, ValueError):
            return Response(
                {"error": "Customer not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not customer:
            customer = (
                Customer.objects.filter(name__icontains="general").first()
                or Customer.objects.filter(no__icontains="general").first()
                or Customer.objects.order_by("id").first()
            )
        if not customer:
            return Response(
                {
                    "error": _(
                        "Order must have a bill-to customer, or configure a "
                        "walk-in / General customer."
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        # Ensure every order in this checkout has the resolved customer before invoicing.
        for o in table_orders:
            if o.customer_id is None:
                o.customer = customer
                o.save(update_fields=["customer", "updated_at"])
        order.refresh_from_db()

        payment_method_id = request.data.get("payment_method_id")
        if not payment_method_id:
            return Response(
                {"error": _("payment_method_id is required.")},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            pm = PaymentMethod.objects.get(id=int(payment_method_id))
        except (PaymentMethod.DoesNotExist, TypeError, ValueError):
            return Response(
                {"error": _("Invalid payment method.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        amount_received = request.data.get("amount_received")
        change_amount = request.data.get("change_amount")

        try:
            with transaction.atomic():
                location_to_use, loc_err = _resolve_branch_location_for_request(request)
                if loc_err:
                    return Response(
                        {"error": loc_err},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                if not location_to_use:
                    return Response(
                        {
                            "error": "No location configured. Please set up a location first.",
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                invoice = create_open_sales_invoice_from_restaurant_orders(
                    request,
                    table_orders,
                    customer,
                    location_to_use,
                    combine_orders=combine_orders,
                    check_id=check_id,
                )
                invoice.payment_method = pm
                if amount_received is not None:
                    try:
                        invoice.amount_received = int(amount_received)
                    except (TypeError, ValueError):
                        pass
                if change_amount is not None:
                    try:
                        invoice.change_amount = int(change_amount)
                    except (TypeError, ValueError):
                        pass
                invoice.save()

                mock_admin = SalesInvoiceAdmin(SalesInvoice, admin.site)
                can_post, reason = mock_admin.can_post_invoice(invoice)
                if not can_post:
                    raise ValueError(reason)

                receipt_no = (
                    f"RCP-{timezone.now().strftime('%Y%m%d')}-"
                    f"{uuid.uuid4().hex[:6].upper()}"
                )
                processor = SalesInvoicePostingProcessor(invoice, request, receipt_no)
                result = processor.post()
                if not result.get("success"):
                    raise ValueError(result.get("message", _("Posting failed")))

                invoice.refresh_from_db()
                for o in table_orders:
                    o.refresh_from_db()
                return Response(
                    {
                        "message": _("Payment completed."),
                        "invoice": SalesInvoiceSerializer(invoice).data,
                        "receipt_no": receipt_no,
                        "order_completed": all(
                            o.status == OrderStatus.COMPLETED for o in table_orders
                        ),
                    },
                    status=status.HTTP_200_OK,
                )
        except ValueError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            import traceback

            traceback.print_exc()
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=True, methods=["post"], url_path="counter-checkout")
    def counter_checkout(self, request, pk=None):
        """
        Walk-in / counter sale: no table, takeout (or delivery) order, pay and post
        immediately (creates posted sales invoice; receipt-only UX at POS).
        """
        import uuid

        from django.contrib import admin

        from financials.models import PaymentMethod
        from sales.admin import SalesInvoiceAdmin, SalesInvoicePostingProcessor
        from sales.models import Customer, SalesInvoice
        from sales.serializers import SalesInvoiceSerializer

        order = self.get_object()
        if order.table_id is not None:
            return Response(
                {"error": _("Counter sale requires an order with no table.")},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if order.order_type not in (OrderType.TAKEOUT, OrderType.DELIVERY):
            return Response(
                {"error": _("Counter sale must use takeout or delivery order type.")},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if order.sales_invoice_id:
            return Response(
                {"error": _("This order is already settled.")},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not order.order_items.exclude(status=OrderItemStatus.CANCELLED).exists():
            return Response(
                {"error": _("Add at least one line before checkout.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        payment_method_id = request.data.get("payment_method_id")
        if not payment_method_id:
            return Response(
                {"error": _("payment_method_id is required.")},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            pm = PaymentMethod.objects.get(id=int(payment_method_id))
        except (PaymentMethod.DoesNotExist, TypeError, ValueError):
            return Response(
                {"error": _("Invalid payment method.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        customer_id = request.data.get("customer_id")
        try:
            if customer_id is not None:
                customer = Customer.objects.get(id=int(customer_id))
            else:
                customer = (
                    Customer.objects.filter(name__icontains="general").first()
                    or Customer.objects.filter(no__icontains="general").first()
                    or Customer.objects.order_by("id").first()
                )
        except (Customer.DoesNotExist, TypeError, ValueError):
            return Response(
                {"error": _("Customer not found.")},
                status=status.HTTP_404_NOT_FOUND,
            )
        if not customer:
            return Response(
                {"error": _("No walk-in customer configured.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        location_to_use, loc_err = _resolve_branch_location_for_request(request)
        if loc_err:
            return Response({"error": loc_err}, status=status.HTTP_400_BAD_REQUEST)
        if not location_to_use:
            return Response(
                {"error": _("No location configured. Please set up a location first.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        amount_received = request.data.get("amount_received")
        change_amount = request.data.get("change_amount")

        try:
            with transaction.atomic():
                order.order_items.exclude(status=OrderItemStatus.CANCELLED).update(
                    status=OrderItemStatus.SERVED
                )
                order.customer = customer
                order.status = OrderStatus.SERVED
                order.save(update_fields=["customer", "status", "updated_at"])
                order.refresh_from_db()

                invoice = create_open_sales_invoice_from_restaurant_orders(
                    request,
                    [order],
                    customer,
                    location_to_use,
                    combine_orders=False,
                )
                invoice.payment_method = pm
                if amount_received is not None:
                    try:
                        invoice.amount_received = int(amount_received)
                    except (TypeError, ValueError):
                        pass
                if change_amount is not None:
                    try:
                        invoice.change_amount = int(change_amount)
                    except (TypeError, ValueError):
                        pass
                invoice.save()

                mock_admin = SalesInvoiceAdmin(SalesInvoice, admin.site)
                can_post, reason = mock_admin.can_post_invoice(invoice)
                if not can_post:
                    raise ValueError(reason)

                receipt_no = (
                    f"RCP-{timezone.now().strftime('%Y%m%d')}-"
                    f"{uuid.uuid4().hex[:6].upper()}"
                )
                processor = SalesInvoicePostingProcessor(invoice, request, receipt_no)
                result = processor.post()
                if not result.get("success"):
                    raise ValueError(result.get("message", _("Posting failed")))

                invoice.refresh_from_db()
                return Response(
                    {
                        "message": _("Counter sale completed."),
                        "invoice": SalesInvoiceSerializer(invoice).data,
                        "receipt_no": receipt_no,
                    },
                    status=status.HTTP_200_OK,
                )
        except ValueError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            import traceback

            traceback.print_exc()
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )


class RestaurantOrderItemViewSet(viewsets.ModelViewSet):
    """ViewSet for RestaurantOrderItem model"""

    queryset = (
        models.RestaurantOrderItem.objects.select_related("order", "item")
        .all()
        .order_by("order", "id")
    )
    serializer_class = serializers.RestaurantOrderItemSerializer
    permission_classes = [IsAuthenticated, IsTenantSchema]
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["order", "status"]
    search_fields = ["order__no", "item__item_name"]
    ordering_fields = ["created_at"]
    ordering = ["order", "id"]

    def get_queryset(self):
        qs = super().get_queryset()
        return filter_queryset_by_branch(qs, self.request.user, request=self.request)

    @action(detail=True, methods=["post"])
    def update_status(self, request, pk=None):
        """Update order item status and intelligently update order status"""
        order_item = self.get_object()
        if order_is_closed(order_item.order):
            return Response(
                {"error": CLOSED_ORDER_ERROR},
                status=status.HTTP_400_BAD_REQUEST,
            )
        new_status = request.data.get("status")
        if new_status not in dict(OrderItemStatus.choices):
            return Response(
                {"error": "Invalid status"}, status=status.HTTP_400_BAD_REQUEST
            )

        # Validation: Cannot cancel items that are already served
        if (
            new_status == OrderItemStatus.CANCELLED
            and order_item.status == OrderItemStatus.SERVED
        ):
            return Response(
                {"error": "Cannot cancel items that have already been served"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validation: Cannot cancel items that are already cancelled
        if (
            new_status == OrderItemStatus.CANCELLED
            and order_item.status == OrderItemStatus.CANCELLED
        ):
            return Response(
                {"error": "Item is already cancelled"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Transition to preparing: must be sent to kitchen first (see start_preparing).
        if new_status == OrderItemStatus.PREPARING:
            if order_item.status == OrderItemStatus.PREPARING:
                from .models import RestaurantOrder

                order = RestaurantOrder.objects.get(id=order_item.order_id)
                item_data = serializers.RestaurantOrderItemSerializer(order_item).data
                item_data["order_total"] = str(order.total_amount)
                item_data["order_id"] = order.id
                return Response(item_data)
            if order_item.status != OrderItemStatus.PENDING:
                return Response(
                    {"error": "Only pending items can be moved to preparing."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if order_item.fire_state != FireState.FIRE:
                return Response(
                    {
                        "error": "Item must be sent to the kitchen before starting preparation.",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if not models.restaurant_order_item_routes_to_kitchen(order_item):
                return Response(
                    {"error": "This item does not route to the kitchen."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        order_item.status = new_status
        update_fields = ["status", "updated_at"]
        if new_status == OrderItemStatus.PREPARING:
            order_item.started_at = timezone.now()
            update_fields = ["status", "started_at", "updated_at"]
        order_item.save(update_fields=update_fields)

        # Force database commit by refreshing the item to ensure status is saved
        order_item.refresh_from_db()

        # Get fresh order instance from database (not from cached relationship)
        order_id = order_item.order_id
        from .models import RestaurantOrder

        order = RestaurantOrder.objects.get(id=order_id)

        # Explicitly recalculate total after status change (especially important for cancellations)
        # This uses a fresh database query that will see the updated item status
        order.recalculate_total()

        # Refresh order to get the updated total_amount
        order.refresh_from_db()

        # Refresh items after recalculation for status counting
        items = order.order_items.all()

        if not items.exists():
            order.status = OrderStatus.NEW
            order.save(update_fields=["status"])
        else:
            # Count items by status
            status_counts = {
                "pending": items.filter(status=OrderItemStatus.PENDING).count(),
                "preparing": items.filter(status=OrderItemStatus.PREPARING).count(),
                "ready": items.filter(status=OrderItemStatus.READY).count(),
                "served": items.filter(status=OrderItemStatus.SERVED).count(),
                "cancelled": items.filter(status=OrderItemStatus.CANCELLED).count(),
            }

            total_items = items.count()
            active_items = total_items - status_counts["cancelled"]

            # If all items are cancelled, mark order as cancelled
            if status_counts["cancelled"] == total_items and total_items > 0:
                order.status = OrderStatus.CANCELLED
            # Determine order status based on item statuses
            elif status_counts["served"] == active_items:
                # All items served
                order.status = OrderStatus.SERVED
            elif status_counts["ready"] == active_items:
                # All items ready (but not all served)
                order.status = OrderStatus.READY
            elif (
                status_counts["preparing"] > 0
                or status_counts["ready"] > 0
                or status_counts["served"] > 0
            ):
                # Some items are being prepared, ready, or served
                order.status = OrderStatus.IN_PROGRESS
            elif status_counts["pending"] == active_items:
                if items.filter(
                    status=OrderItemStatus.PENDING, fire_state=FireState.FIRE
                ).exists():
                    order.status = OrderStatus.IN_PROGRESS
                else:
                    order.status = OrderStatus.NEW
            else:
                # Mixed state - default to in_progress
                order.status = OrderStatus.IN_PROGRESS

            # Save only status, total_amount is already updated by recalculate_total()
            # Include total_amount in update_fields to prevent save() from recalculating
            order.save(update_fields=["status", "total_amount"])

        # Refresh order from database to ensure we have the latest total_amount
        order.refresh_from_db()

        # Double-check: Verify the total is correct by recalculating one more time
        # This ensures we have the absolute latest value
        order.recalculate_total()
        order.refresh_from_db()

        # Return item data along with updated order total
        item_data = serializers.RestaurantOrderItemSerializer(order_item).data
        item_data["order_total"] = str(order.total_amount)
        item_data["order_id"] = order.id

        return Response(item_data)

    @action(detail=True, methods=["post"], url_path="repeat")
    def repeat_item(self, request, pk=None):
        source = self.get_object()
        order = source.order

        if order_is_closed(order):
            return Response(
                {"error": CLOSED_ORDER_ERROR},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if source.status == OrderItemStatus.CANCELLED:
            return Response(
                {"error": "Cannot repeat a cancelled line"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Pending, not yet fired: add the same quantity on this row (no extra cart lines).
        if (
            source.status == OrderItemStatus.PENDING
            and source.fire_state == FireState.HOLD
        ):
            bump = source.quantity
            source.quantity = source.quantity + bump
            source.save()
            order.recalculate_total()
            order.refresh_from_db()
            models.OrderActionLog.objects.create(
                order=order,
                order_item=source,
                actor=self.request.user if self.request.user.is_authenticated else None,
                action_type=PosActionType.REPEAT_ITEM,
                metadata={
                    "source_item_id": source.id,
                    "mode": "increment_same_line",
                    "added_quantity": str(bump),
                },
            )
            return Response(
                serializers.RestaurantOrderItemSerializer(source).data,
                status=status.HTTP_200_OK,
            )

        # Already sent / in-flight: duplicate as a new pending line (kitchen workflow).
        clone = models.RestaurantOrderItem.objects.create(
            order=source.order,
            restaurant_check=source.restaurant_check,
            item=source.item,
            quantity=source.quantity,
            unit_price=source.unit_price,
            status=OrderItemStatus.PENDING,
            seat_no=source.seat_no,
            course=source.course,
            fire_state=FireState.HOLD,
            special_instructions=source.special_instructions,
            selected_sides=source.selected_sides,
            spice_level=source.spice_level,
            preparation_time=source.preparation_time,
        )
        order.recalculate_total()
        models.OrderActionLog.objects.create(
            order=source.order,
            order_item=clone,
            actor=self.request.user if self.request.user.is_authenticated else None,
            action_type=PosActionType.REPEAT_ITEM,
            metadata={"source_item_id": source.id, "mode": "clone"},
        )
        return Response(
            serializers.RestaurantOrderItemSerializer(clone).data, status=201
        )

    @action(detail=True, methods=["post"], url_path="delete-or-cancel")
    def delete_or_cancel(self, request, pk=None):
        order_item = self.get_object()
        order = order_item.order
        if order_is_closed(order):
            return Response(
                {"error": CLOSED_ORDER_ERROR},
                status=status.HTTP_400_BAD_REQUEST,
            )
        item_id = order_item.id
        action = "deleted"
        if order_item.fire_state == FireState.FIRE or order_item.status in (
            OrderItemStatus.PREPARING,
            OrderItemStatus.READY,
            OrderItemStatus.SERVED,
        ):
            order_item.status = OrderItemStatus.CANCELLED
            order_item.save(update_fields=["status", "updated_at"])
            action = "cancelled"
        else:
            order_item.delete()
        order.recalculate_total()
        order.refresh_from_db()
        RestaurantOrderViewSet().update_order_status_from_items(order)
        order.save(update_fields=["status", "updated_at"])
        models.OrderActionLog.objects.create(
            order=order,
            order_item=order_item if action == "cancelled" else None,
            actor=self.request.user if self.request.user.is_authenticated else None,
            action_type=PosActionType.DELETE_OR_CANCEL_ITEM,
            metadata={"item_id": item_id, "result": action},
        )
        return Response({"result": action})

    @action(detail=False, methods=["post"], url_path="start-preparing")
    def start_preparing(self, request):
        """Kitchen: move fired lines from pending to preparing (batch)."""
        raw_ids = request.data.get("item_ids")
        if not raw_ids or not isinstance(raw_ids, (list, tuple)):
            return Response(
                {"error": "item_ids must be a non-empty list"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            item_ids = [int(x) for x in raw_ids]
        except (TypeError, ValueError):
            return Response(
                {"error": "item_ids must be integers"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not item_ids:
            return Response(
                {"error": "item_ids must be a non-empty list"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        kitchen_q = _order_items_routes_to_kitchen_q()
        now = timezone.now()
        order_vset = RestaurantOrderViewSet()
        from .models import RestaurantOrder

        with transaction.atomic():
            to_update = (
                self.get_queryset()
                .filter(id__in=item_ids)
                .filter(
                    status=OrderItemStatus.PENDING,
                    fire_state=FireState.FIRE,
                )
                .filter(kitchen_q)
            )
            rows = list(to_update.values("id", "order_id"))
            found_set = {r["id"] for r in rows}
            requested_set = set(item_ids)
            if found_set != requested_set:
                return Response(
                    {
                        "error": (
                            "Some items are missing, not pending+fired, or do not "
                            "route to the kitchen."
                        ),
                        "invalid_ids": sorted(requested_set - found_set),
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            by_order = defaultdict(list)
            for row in rows:
                by_order[row["order_id"]].append(row["id"])
            to_update.update(status=OrderItemStatus.PREPARING, started_at=now)
            for oid, o_item_ids in by_order.items():
                order = RestaurantOrder.objects.select_for_update().get(pk=oid)
                order_vset.update_order_status_from_items(order)
                order.save(update_fields=["status", "updated_at"])
                models.OrderActionLog.objects.create(
                    order=order,
                    actor=request.user if request.user.is_authenticated else None,
                    action_type=PosActionType.START_PREPARING,
                    metadata={"item_ids": o_item_ids, "count": len(o_item_ids)},
                )

        updated_qs = (
            self.get_queryset()
            .filter(id__in=item_ids)
            .select_related("order__waiter", "item__menu_item__category")
        )
        return Response(
            serializers.RestaurantOrderItemSerializer(updated_qs, many=True).data
        )

    @action(detail=False, methods=["get"])
    def kitchen_items(self, request):
        """Get order items for kitchen display"""
        items = (
            self.get_queryset()
            .select_related("order__waiter", "item__menu_item__category")
            .filter(_order_items_routes_to_kitchen_q())
            .filter(
                Q(status__in=[OrderItemStatus.PREPARING, OrderItemStatus.READY])
                | Q(
                    status=OrderItemStatus.PENDING,
                    fire_state=FireState.FIRE,
                )
            )
        )
        serializer = self.get_serializer(items, many=True)
        return Response(serializer.data)


class MenuViewSet(viewsets.ModelViewSet):
    queryset = models.Menu.objects.all().order_by("name")
    serializer_class = serializers.MenuSerializer
    permission_classes = [IsAuthenticated, IsTenantSchema]
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["is_active"]
    search_fields = ["name", "code"]

    @action(detail=False, methods=["get"], url_path="active-for-location")
    def active_for_location(self, request):
        location_id = request.query_params.get("location_id")
        now_time = timezone.localtime().time()
        try:
            qs = self.get_queryset().filter(is_active=True)
            if location_id:
                qs = qs.filter(locations__location_id=location_id)
            qs = qs.filter(
                Q(start_time__isnull=True) | Q(start_time__lte=now_time),
                Q(end_time__isnull=True) | Q(end_time__gte=now_time),
            ).distinct()
            return Response(self.get_serializer(qs, many=True).data)
        except ProgrammingError as exc:
            if "does not exist" not in str(exc):
                raise
            return Response(
                {
                    "error": (
                        "Restaurant POS tables are missing for this tenant. "
                        "Apply migrations on the tenant schema, e.g. "
                        "`python manage.py migrate_schemas --tenant -s <schema_name> restaurant_management` "
                        "(or `migrate_schemas --tenant` for all tenants)."
                    ),
                    "detail": str(exc),
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

    @action(detail=True, methods=["get"], url_path="pos-tree")
    def pos_tree(self, request, pk=None):
        """Root display groups (nested) plus ungrouped menu items for POS."""
        menu = self.get_object()
        roots = models.MenuDisplayGroup.objects.filter(
            menu=menu, parent__isnull=True, is_active=True
        ).order_by("display_order", "name")
        root_groups = [
            _build_menu_display_group_branch(menu.id, g, request=request) for g in roots
        ]
        # Only treat the menu as "grouped" when there is at least one *active* display group.
        # Inactive-only rows used to force strict ungrouped filtering while roots stayed empty,
        # which hid every item on POS (items sat on inactive / unreachable groups).
        has_active_display_groups = models.MenuDisplayGroup.objects.filter(
            menu=menu, is_active=True
        ).exists()
        ungrouped_qs = models.MenuItem.objects.filter(
            menu=menu, is_available=True
        ).select_related("item")
        if has_active_display_groups:
            ungrouped_qs = ungrouped_qs.filter(display_group__isnull=True)
        ungrouped = list(ungrouped_qs.order_by("display_order", "item__item_name"))
        if not root_groups and not ungrouped:
            ungrouped = list(
                models.MenuItem.objects.filter(menu=menu, is_available=True)
                .select_related("item")
                .order_by("display_order", "item__item_name")
            )
        home_page = (
            models.MenuLayoutPage.objects.filter(menu=menu)
            .order_by("page_number")
            .prefetch_related(
                Prefetch(
                    "tiles",
                    queryset=models.MenuLayoutTile.objects.select_related(
                        "display_group",
                        "menu_item",
                        "menu_item__item",
                        "menu_item__menu",
                    ).order_by("row", "column", "display_order"),
                )
            )
            .first()
        )
        home_layout = (
            [
                _home_layout_tile_payload(t, request=request)
                for t in home_page.tiles.all()
            ]
            if home_page
            else []
        )

        return Response(
            {
                "menu": menu.id,
                "root_groups": root_groups,
                "ungrouped_items": [
                    _menu_item_pos_payload(mi, request=request) for mi in ungrouped
                ],
                "home_layout": home_layout,
            }
        )


class MenuLocationViewSet(viewsets.ModelViewSet):
    queryset = models.MenuLocation.objects.select_related("menu", "location").all()
    serializer_class = serializers.MenuLocationSerializer
    permission_classes = [IsAuthenticated, IsTenantSchema]
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["menu", "location"]


class MenuDisplayGroupViewSet(viewsets.ModelViewSet):
    queryset = (
        models.MenuDisplayGroup.objects.select_related("menu", "parent")
        .prefetch_related(
            Prefetch(
                "children",
                queryset=models.MenuDisplayGroup.objects.select_related(
                    "menu", "parent"
                ).order_by("display_order", "name"),
            )
        )
        .all()
    )
    serializer_class = serializers.MenuDisplayGroupSerializer
    permission_classes = [IsAuthenticated, IsTenantSchema]
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["menu", "parent", "is_active"]
    search_fields = ["name"]


class MenuLayoutPageViewSet(viewsets.ModelViewSet):
    queryset = (
        models.MenuLayoutPage.objects.select_related("menu")
        .prefetch_related(
            Prefetch(
                "tiles",
                queryset=models.MenuLayoutTile.objects.select_related(
                    "display_group", "menu_item", "menu_item__item", "menu_item__menu"
                ).order_by("display_order", "row", "column"),
            )
        )
        .all()
    )
    serializer_class = serializers.MenuLayoutPageSerializer
    permission_classes = [IsAuthenticated, IsTenantSchema]
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["menu"]


class MenuLayoutTileViewSet(viewsets.ModelViewSet):
    queryset = models.MenuLayoutTile.objects.select_related(
        "page", "display_group", "menu_item", "menu_item__item", "menu_item__menu"
    ).all()
    serializer_class = serializers.MenuLayoutTileSerializer
    permission_classes = [IsAuthenticated, IsTenantSchema]
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    # Never expose ``page`` as a filter query param — it collides with DRF
    # PageNumberPagination (``?page=2`` → HTTP 404 when layout page id is 2).
    filterset_fields = ["display_group", "menu_item"]

    def get_queryset(self):
        qs = super().get_queryset()
        layout_page = self.request.query_params.get("layout_page")
        if layout_page not in (None, ""):
            qs = qs.filter(page_id=layout_page)
        return qs


class RestaurantCheckViewSet(viewsets.ModelViewSet):
    queryset = models.RestaurantCheck.objects.select_related("order").all()
    serializer_class = serializers.RestaurantCheckSerializer
    permission_classes = [IsAuthenticated, IsTenantSchema]
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["order", "status", "is_voided", "is_comped"]

    def get_queryset(self):
        qs = super().get_queryset()
        return filter_queryset_by_branch(qs, self.request.user, request=self.request)


class ModifierGroupViewSet(viewsets.ModelViewSet):
    queryset = models.ModifierGroup.objects.prefetch_related("options").all()
    serializer_class = serializers.ModifierGroupSerializer
    permission_classes = [IsAuthenticated, IsTenantSchema]
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["selection_mode", "required", "is_active"]
    search_fields = ["name", "code"]


class ModifierOptionViewSet(viewsets.ModelViewSet):
    queryset = models.ModifierOption.objects.select_related("group").all()
    serializer_class = serializers.ModifierOptionSerializer
    permission_classes = [IsAuthenticated, IsTenantSchema]
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["group", "is_active"]
    search_fields = ["name", "code"]


class MenuItemModifierGroupViewSet(viewsets.ModelViewSet):
    queryset = models.MenuItemModifierGroup.objects.select_related(
        "menu_item", "modifier_group"
    ).all()
    serializer_class = serializers.MenuItemModifierGroupSerializer
    permission_classes = [IsAuthenticated, IsTenantSchema]
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["menu_item", "modifier_group", "required"]


class OrderItemModifierViewSet(viewsets.ModelViewSet):
    queryset = models.OrderItemModifier.objects.select_related(
        "order_item", "modifier_group", "modifier_option"
    ).all()
    serializer_class = serializers.OrderItemModifierSerializer
    permission_classes = [IsAuthenticated, IsTenantSchema]
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["order_item", "modifier_group", "modifier_option"]

    def get_queryset(self):
        qs = super().get_queryset()
        return filter_queryset_by_branch(qs, self.request.user, request=self.request)


class OrderActionLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = models.OrderActionLog.objects.select_related(
        "order", "order_item", "actor"
    ).all()
    serializer_class = serializers.OrderActionLogSerializer
    permission_classes = [IsAuthenticated, IsTenantSchema]
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["order", "order_item", "actor", "action_type"]

    def get_queryset(self):
        qs = super().get_queryset()
        return filter_queryset_by_branch(qs, self.request.user, request=self.request)


class RestaurantDashboardViewSet(viewsets.ViewSet):
    """ViewSet for Restaurant Dashboard statistics"""

    permission_classes = [IsAuthenticated, IsTenantSchema]
    authentication_classes = [JWTAuthentication, SessionAuthentication]

    @action(detail=False, methods=["get"])
    def stats(self, request):
        """Get dashboard statistics"""
        today = timezone.now().date()

        order_base = filter_queryset_by_branch(
            models.RestaurantOrder.objects.all(),
            request.user,
            request=request,
        )
        res_base = filter_reservation_queryset(
            models.Reservation.objects.all(),
            request.user,
            request,
        )

        # Active tables
        active_orders = order_base.filter(
            status__in=[OrderStatus.NEW, OrderStatus.IN_PROGRESS, OrderStatus.READY]
        )
        active_table_count = active_orders.values("table").distinct().count()

        # Pending orders
        pending_orders_count = order_base.filter(status=OrderStatus.NEW).count()

        # Today's reservations
        today_reservations = res_base.filter(reservation_date__date=today).count()

        # Today's revenue
        today_revenue = (
            order_base.filter(
                status=OrderStatus.COMPLETED, created_at__date=today
            ).aggregate(total=Sum("total_amount"))["total"]
            or 0
        )

        return Response(
            {
                "active_tables": active_table_count,
                "pending_orders": pending_orders_count,
                "today_reservations": today_reservations,
                "today_revenue": float(today_revenue),
            }
        )
