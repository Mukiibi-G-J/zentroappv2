from django.db import transaction
from django.contrib import admin
from django.shortcuts import render, get_object_or_404
from django.core.paginator import Paginator, EmptyPage, InvalidPage
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters import rest_framework as filters
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.exceptions import ValidationError
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.authentication import SessionAuthentication
from authentication.authentication import JWTAuthenticationWithRevocationChecks as JWTAuthentication
from rest_framework.permissions import IsAuthenticated
from django.http import HttpRequest
from django.db.models import (
    Sum,
    Count,
    Avg,
    Q,
    F,
    Max,
    Min,
    FloatField,
    DecimalField,
    Value,
    Case,
    When,
    ExpressionWrapper,
    OuterRef,
    Subquery,
    Exists,
    BooleanField,
    DateTimeField,
    CharField,
)
from rest_framework.views import APIView
from rest_framework.decorators import (
    api_view,
    permission_classes,
    authentication_classes,
)
import random
import string
from datetime import datetime, timedelta
import uuid
from django.utils import timezone
from django.db.models.functions import TruncMonth, TruncYear, TruncQuarter, Coalesce
from decimal import Decimal
from django.db import models

from .models import (
    SalesInvoice,
    SalesInvoiceLine,
    Customer,
    CustomerLedgerEntry,
    SalesReceivable,
    SalesOrder,
    SalesOrderLine,
    PostedSalesInvoice,
    PostedSalesInvoiceLine,
    SalesCreditMemo,
    SalesFavoriteSlot,
)

from .admin import (
    SalesInvoiceAdmin,
    SalesInvoicePostingProcessor,
    SalesInvoiceReversalPostingProcessor,
)
from items.models import (
    Item,
    Location,
    ItemUnitOfMeasure,
    UnitOfMeasure,
    TrackingSpecification,
)
from .serializers import (
    SalesInvoiceSerializer,
    SalesHistoryListSerializer,
    SalesInvoiceLineSerializer,
    CustomerSerializer,
    CustomerLedgerSerializer,
    SalesOrderSerializer,
    SalesOrderLineSerializer,
    SalesFavoriteSlotSerializer,
)
from reports.utils.formatters import format_currency

# Import financial models for GL reporting
from financials.models import (
    GeneralLedgerEntry,
    GeneralLedgerSetup,
    G_LAccount,
    PaymentMethod,
)
from financials.services.balance_sheet_service import BalanceSheetService

# Import permission decorator (NEW - Day 2)
from authentication.decorators import require_object_permission
from dimension.branch_filter import (
    branch_scope_is_all,
    filter_queryset_by_branch,
    get_branch_for_request,
)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
@authentication_classes([SessionAuthentication, JWTAuthentication])
def get_company_info(request):
    """
    Get company information for receipt generation
    """
    try:
        from sales.setup_data import fetch_company_info_data

        return Response(fetch_company_info_data(request))

    except Exception as e:
        return Response(
            {"error": f"Failed to get company info: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
@authentication_classes([SessionAuthentication, JWTAuthentication])
def sales_history_detail(request):
    """
    Aggregated sales history detail for posted invoices.
    Groups by product and returns pricing and profit metrics.

    Query params:
      - start_date (YYYY-MM-DD, optional)
      - end_date (YYYY-MM-DD, optional)
    """
    has_permission, source = request.user.check_object_permission(10004, "read")
    if not has_permission:
        return Response(
            {"error": "Insufficient permissions", "reason": source},
            status=status.HTTP_403_FORBIDDEN,
        )

    start_date = request.query_params.get("start_date")
    end_date = request.query_params.get("end_date")

    lines = SalesInvoiceLine.objects.filter(
        sales_invoice__status="Posted", quantity__gt=0
    )

    if start_date:
        lines = lines.filter(sales_invoice__document_date__gte=start_date)
    if end_date:
        lines = lines.filter(sales_invoice__document_date__lte=end_date)

    # Aggregate by product
    aggregated = (
        lines.values("item__item_name")
        .annotate(
            total_qty=Coalesce(Sum("quantity"), 0),
            # Compute line amount as unit_price * quantity (Decimal)
            total_selling=Coalesce(
                Sum(
                    F("unit_price") * F("quantity"),
                    output_field=DecimalField(max_digits=18, decimal_places=2),
                ),
                Decimal("0"),
            ),
            total_buying=Coalesce(
                Sum("total_cost"),
                Decimal("0"),
            ),
        )
        .order_by("item__item_name")
    )

    results = []
    for row in aggregated:
        qty = float(row["total_qty"]) or 1
        avg_selling = float(row["total_selling"]) / qty
        avg_buying = float(row["total_buying"]) / qty
        profit = float(row["total_selling"]) - float(row["total_buying"])
        results.append(
            {
                "product_name": row["item__item_name"],
                "selling_price": avg_selling,
                "buying_price": avg_buying,
                "total_buying_price": float(row["total_buying"]),
                "total_selling_price": float(row["total_selling"]),
                "quantity_sold": float(row["total_qty"]),
                "profit": profit,
            }
        )

    return Response({"results": results})


MIN_SALES_FAVORITES_GRID_SLOTS = 4


def _parse_item_system_id(value):
    if value is None or value == "":
        return None
    s = str(value).strip()
    if not s:
        return None
    try:
        return str(uuid.UUID(s))
    except (ValueError, TypeError, AttributeError):
        raise ValidationError(
            {"slots": f"item_system_id must be a valid UUID (got {value!r})."}
        )


def _normalize_favorites_slot_entries(raw_slots, implicit_positions: bool):
    if raw_slots is None:
        raise ValidationError({"slots": "This field is required."})
    if not isinstance(raw_slots, list):
        raise ValidationError({"slots": "Expected a list."})
    normalized = []
    seen_positions = set()
    for idx, entry in enumerate(raw_slots):
        if not isinstance(entry, dict):
            raise ValidationError({"slots": f"Entry {idx} must be an object."})
        pos = entry.get("position")
        if pos is None and entry.get("sort_order") is not None:
            pos = entry.get("sort_order")
        if pos is None:
            if not implicit_positions:
                raise ValidationError(
                    {
                        "slots": (
                            f"Entry {idx} is missing position "
                            "(or use an ordered array with implicit indices)."
                        )
                    }
                )
            pos = idx
        try:
            pos = int(pos)
        except (TypeError, ValueError):
            raise ValidationError({"slots": f"Invalid position at index {idx}."})
        if pos < 0:
            raise ValidationError({"slots": f"position must be >= 0 (got {pos})."})
        if pos in seen_positions:
            raise ValidationError({"slots": f"Duplicate position {pos}."})
        seen_positions.add(pos)
        sid = _parse_item_system_id(entry.get("item_system_id"))
        normalized.append({"position": pos, "item_system_id": sid})
    return normalized


def _resolved_favorite_slot_fields(item_system_id: str):
    item = Item.objects.filter(system_id=item_system_id).first()
    if not item:
        raise ValidationError(
            {
                "slots": (
                    f"No item found for item_system_id {item_system_id!r} "
                    "(use the same id as /api/items/)."
                )
            }
        )
    return {
        "item_system_id": str(item.system_id),
        "item_no": item.no,
        "item_name": item.item_name,
        "unit_price": item.unit_price,
    }


class SalesFavoritesView(APIView):
    """
    Per-user POS favorites grid for the mobile sales screen.

    GET: current layout (occupied slots only). Client infers empty cells; min_slots is at least 4.

    PUT: replace entire layout. Body: {"slots": [{ "position", "item_system_id" | null }, ...]}.
         Positions may be omitted if slots is an ordered array (index = position).

    PATCH: upsert or clear only the positions sent. Same slot shape as PUT.
    """

    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication, SessionAuthentication]

    def get(self, request):
        has_permission, source = request.user.check_object_permission(10002, "read")
        if not has_permission:
            return Response(
                {
                    "error": "Insufficient permissions",
                    "detail": "You need read permission on Sales to view favorites",
                    "reason": source,
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        slots_list = list(
            SalesFavoriteSlot.objects.filter(user=request.user).order_by("position")
        )
        data = SalesFavoriteSlotSerializer(slots_list, many=True).data
        max_pos = max((s.position for s in slots_list), default=-1)
        suggested = max(MIN_SALES_FAVORITES_GRID_SLOTS, max_pos + 1)
        return Response(
            {
                "slots": data,
                "min_slots": MIN_SALES_FAVORITES_GRID_SLOTS,
                "suggested_slot_count": suggested,
            }
        )

    def put(self, request):
        has_permission, source = request.user.check_object_permission(10002, "modify")
        if not has_permission:
            return Response(
                {
                    "error": "Insufficient permissions",
                    "detail": "You need modify permission on Sales to update favorites",
                    "reason": source,
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        entries = _normalize_favorites_slot_entries(
            request.data.get("slots"), implicit_positions=True
        )
        rows = []
        for e in entries:
            if not e["item_system_id"]:
                continue
            fields = _resolved_favorite_slot_fields(e["item_system_id"])
            rows.append(
                SalesFavoriteSlot(
                    user=request.user,
                    position=e["position"],
                    **fields,
                )
            )
        with transaction.atomic():
            SalesFavoriteSlot.objects.filter(user=request.user).delete()
            if rows:
                SalesFavoriteSlot.objects.bulk_create(rows)
        return self.get(request)

    def patch(self, request):
        has_permission, source = request.user.check_object_permission(10002, "modify")
        if not has_permission:
            return Response(
                {
                    "error": "Insufficient permissions",
                    "detail": "You need modify permission on Sales to update favorites",
                    "reason": source,
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        entries = _normalize_favorites_slot_entries(
            request.data.get("slots"), implicit_positions=False
        )
        with transaction.atomic():
            for e in entries:
                pos = e["position"]
                sid = e["item_system_id"]
                if sid:
                    defaults = _resolved_favorite_slot_fields(sid)
                    SalesFavoriteSlot.objects.update_or_create(
                        user=request.user,
                        position=pos,
                        defaults=defaults,
                    )
                else:
                    SalesFavoriteSlot.objects.filter(
                        user=request.user, position=pos
                    ).delete()
        return self.get(request)


# FILTERS
class CustomerFilter(filters.FilterSet):
    class Meta:
        model = Customer
        fields = {
            "name": ["exact", "icontains"],
            "no": ["exact", "icontains"],
            "city": ["exact", "icontains"],
        }


class SalesFilter(filters.FilterSet):
    date_range = filters.DateFromToRangeFilter(field_name="document_date")
    date_range_after = filters.DateFilter(field_name="document_date", lookup_expr="gte")
    date_range_before = filters.DateFilter(
        field_name="document_date", lookup_expr="lte"
    )

    class Meta:
        model = SalesInvoice
        fields = {
            "customer": ["exact"],
            "status": ["exact"],
            "document_date": ["exact", "gte", "lte"],
            "posting_date": ["exact", "gte", "lte"],
            "payment_method": ["exact"],
        }


class SalesOrderFilter(filters.FilterSet):
    date_range = filters.DateFromToRangeFilter(field_name="order_date")

    class Meta:
        model = SalesOrder
        fields = {
            "customer": ["exact"],
            "status": ["exact"],
            "order_date": ["exact", "gte", "lte"],
        }


# VIEWSETS
class CustomerViewSet(viewsets.ModelViewSet):
    """
    Customer ViewSet with granular page permissions
    Page ID: 10101 (Customer Management Page)
    """

    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer
    filterset_class = CustomerFilter
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    search_fields = ["name", "no", "phone_number"]
    ordering_fields = ["name", "no", "city"]
    ordering = ["name"]

    def get_queryset(self):
        return Customer.objects.all().order_by("name")

    def list(self, request, *args, **kwargs):
        """List customers - requires READ permission"""
        has_permission, source = request.user.check_object_permission(10101, "read")
        if not has_permission:
            return Response(
                {
                    "error": "Insufficient permissions",
                    "detail": "You need read permission to view customers",
                    "reason": source,
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        """Get single customer - requires READ permission"""
        has_permission, source = request.user.check_object_permission(10101, "read")
        if not has_permission:
            return Response(
                {
                    "error": "Insufficient permissions",
                    "detail": "You need read permission to view customers",
                    "reason": source,
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().retrieve(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        """Create customer - requires INSERT permission"""
        # Check INSERT permission
        has_permission, source = request.user.check_object_permission(10101, "insert")
        if not has_permission:
            return Response(
                {
                    "error": "Insufficient permissions",
                    "detail": "You need insert permission to create customers",
                    "reason": source,
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            # Check if a customer with the same name already exists
            customer_name = request.data.get("name")
            print(f"DEBUG: Creating customer with name: {customer_name}")

            if customer_name:
                existing_customer = Customer.objects.filter(name=customer_name).first()
                print(f"DEBUG: Existing customer found: {existing_customer}")

                if existing_customer:
                    # Updating existing customer requires MODIFY permission
                    has_modify, source = request.user.check_object_permission(
                        10101, "modify"
                    )
                    if not has_modify:
                        return Response(
                            {
                                "error": "Insufficient permissions",
                                "detail": "Customer exists - you need modify permission to update",
                                "reason": source,
                            },
                            status=status.HTTP_403_FORBIDDEN,
                        )

                    print(
                        f"DEBUG: Updating existing customer with ID: {existing_customer.id}"
                    )
                    serializer = self.get_serializer(
                        existing_customer, data=request.data, partial=True
                    )
                    serializer.is_valid(raise_exception=True)
                    updated_customer = serializer.save()
                    print(
                        f"DEBUG: Customer updated successfully: {updated_customer.id}"
                    )
                    return Response(serializer.data, status=status.HTTP_200_OK)

            print(f"DEBUG: No existing customer found, creating new one")
            return super().create(request, *args, **kwargs)
        except Exception as e:
            print(f"DEBUG: Error in create method: {str(e)}")
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def update(self, request, *args, **kwargs):
        """Update customer - requires MODIFY permission"""
        has_permission, source = request.user.check_object_permission(10101, "modify")
        if not has_permission:
            return Response(
                {
                    "error": "Insufficient permissions",
                    "detail": "You need modify permission to update customers",
                    "reason": source,
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        """Partial update customer - requires MODIFY permission"""
        has_permission, source = request.user.check_object_permission(10101, "modify")
        if not has_permission:
            return Response(
                {
                    "error": "Insufficient permissions",
                    "detail": "You need modify permission to update customers",
                    "reason": source,
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        """Delete customer - requires DELETE permission"""
        has_permission, source = request.user.check_object_permission(10101, "delete")
        if not has_permission:
            return Response(
                {
                    "error": "Insufficient permissions",
                    "detail": "You need delete permission to remove customers",
                    "reason": source,
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().destroy(request, *args, **kwargs)


class SalesViewSet(viewsets.ModelViewSet):
    """
    Sales Invoice ViewSet with granular page permissions
    Page ID: 10002 (Sales Page - for creating/managing sales)
    """

    queryset = SalesInvoice.objects.all()
    serializer_class = SalesInvoiceSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    filterset_class = SalesFilter
    search_fields = ["customer__name", "customer_invoice_no", "invoice_no"]
    ordering_fields = ["document_date", "posting_date", "created_at"]
    ordering = ["-created_at"]

    @staticmethod
    def _with_invoice_totals(queryset):
        decimal_zero = Value(
            Decimal("0.00"), output_field=DecimalField(max_digits=18, decimal_places=2)
        )
        line_total_expr = ExpressionWrapper(
            F("lines__unit_price") * F("lines__quantity")
            - Coalesce(F("lines__line_discount_amount"), decimal_zero),
            output_field=DecimalField(max_digits=18, decimal_places=2),
        )
        queryset = queryset.annotate(
            line_subtotal=Coalesce(
                Sum(line_total_expr),
                decimal_zero,
                output_field=DecimalField(max_digits=18, decimal_places=2),
            )
        )
        return queryset.annotate(
            computed_total_amount=Case(
                When(
                    invoice_discount_type="amount",
                    then=ExpressionWrapper(
                        F("line_subtotal")
                        - Coalesce(F("invoice_discount_amount"), decimal_zero),
                        output_field=DecimalField(max_digits=18, decimal_places=2),
                    ),
                ),
                When(
                    invoice_discount_type="percentage",
                    then=ExpressionWrapper(
                        F("line_subtotal")
                        - (
                            F("line_subtotal")
                            * Coalesce(F("invoice_discount_percentage"), decimal_zero)
                            / Value(
                                Decimal("100.00"),
                                output_field=DecimalField(
                                    max_digits=18, decimal_places=2
                                ),
                            )
                        ),
                        output_field=DecimalField(max_digits=18, decimal_places=2),
                    ),
                ),
                default=F("line_subtotal"),
                output_field=DecimalField(max_digits=18, decimal_places=2),
            )
        )

    @staticmethod
    def _with_posted_sales_invoice_totals(queryset):
        """Annotate PostedSalesInvoice rows with computed_total_amount (header + line discounts)."""
        decimal_zero = Value(
            Decimal("0.00"), output_field=DecimalField(max_digits=18, decimal_places=2)
        )
        queryset = queryset.annotate(
            line_subtotal=Coalesce(
                Sum("posted_sales_invoice_lines__amount"),
                decimal_zero,
                output_field=DecimalField(max_digits=18, decimal_places=2),
            )
        )
        return queryset.annotate(
            computed_total_amount=Case(
                When(
                    invoice_discount_type="amount",
                    then=ExpressionWrapper(
                        F("line_subtotal")
                        - Coalesce(F("invoice_discount_amount"), decimal_zero),
                        output_field=DecimalField(max_digits=18, decimal_places=2),
                    ),
                ),
                When(
                    invoice_discount_type="percentage",
                    then=ExpressionWrapper(
                        F("line_subtotal")
                        - (
                            F("line_subtotal")
                            * Coalesce(F("invoice_discount_percentage"), decimal_zero)
                            / Value(
                                Decimal("100.00"),
                                output_field=DecimalField(
                                    max_digits=18, decimal_places=2
                                ),
                            )
                        ),
                        output_field=DecimalField(max_digits=18, decimal_places=2),
                    ),
                ),
                default=F("line_subtotal"),
                output_field=DecimalField(max_digits=18, decimal_places=2),
            )
        )

    @staticmethod
    def _posted_sales_history_queryset(request):
        """PostedSalesInvoice queryset with Sales History filters (date, payment, user, branch)."""
        queryset = PostedSalesInvoice.objects.select_related(
            "customer",
            "payment_method",
            "global_dimension_1",
        ).order_by("-posting_date", "-id")

        payment_method_filter = request.query_params.get("payment_method")
        if payment_method_filter == "not_paid":
            queryset = queryset.filter(payment_method__isnull=True)
        elif payment_method_filter and payment_method_filter != "not_paid":
            queryset = queryset.filter(payment_method=payment_method_filter)

        user_filter = request.query_params.get("user")
        if user_filter not in (None, ""):
            try:
                user_filter_id = int(user_filter)
                sales_invoice_no = (
                    SalesInvoice.objects.filter(
                        customer_invoice_no=OuterRef("customer_invoice_no"),
                        customer_id=OuterRef("customer_id"),
                    )
                    .order_by("-id")
                    .values("invoice_no")[:1]
                )
                invoice_user_id_subquery = (
                    CustomerLedgerEntry.objects.filter(
                        document_no=Subquery(sales_invoice_no),
                        customer_id=OuterRef("customer_id"),
                    )
                    .order_by("-id")
                    .values("user_id")[:1]
                )
                queryset = queryset.annotate(
                    ledger_user_id=Subquery(
                        invoice_user_id_subquery, output_field=models.IntegerField()
                    )
                ).filter(ledger_user_id=user_filter_id)
            except (TypeError, ValueError):
                pass

        posting_date = request.query_params.get("posting_date")
        if posting_date:
            queryset = queryset.filter(posting_date=posting_date)
        posting_date_gte = request.query_params.get("posting_date__gte")
        if posting_date_gte:
            queryset = queryset.filter(posting_date__gte=posting_date_gte)
        posting_date_lte = request.query_params.get("posting_date__lte")
        if posting_date_lte:
            queryset = queryset.filter(posting_date__lte=posting_date_lte)

        queryset = filter_queryset_by_branch(
            queryset, request.user, request=request
        )
        return SalesViewSet._with_posted_sales_invoice_totals(queryset)

    @staticmethod
    def _with_reverse_metadata(queryset):
        posted_invoice_qs = PostedSalesInvoice.objects.filter(
            customer_invoice_no=OuterRef("customer_invoice_no"),
            customer_id=OuterRef("customer_id"),
        )
        credit_memo_qs = SalesCreditMemo.objects.filter(
            Q(
                original_invoice__customer_invoice_no=OuterRef("customer_invoice_no"),
                original_invoice__customer_id=OuterRef("customer_id"),
            )
            | Q(original_invoice_no=OuterRef("invoice_no")),
            status="Posted",
        ).order_by("-created_at")
        return queryset.annotate(
            reversed=Case(
                When(
                    Exists(posted_invoice_qs.filter(reversed=True)),
                    then=Value(True),
                ),
                When(Exists(credit_memo_qs), then=Value(True)),
                default=Value(False),
                output_field=BooleanField(),
            ),
            reversed_by_user=Subquery(
                credit_memo_qs.values("reversed_by_user__full_name")[:1],
                output_field=CharField(),
            ),
            reversed_date=Subquery(
                credit_memo_qs.values("created_at")[:1],
                output_field=DateTimeField(),
            ),
        )

    def get_serializer_class(self):
        if self.action == "list":
            return SalesHistoryListSerializer
        return SalesInvoiceSerializer

    def get_queryset(self):
        queryset = (
            SalesInvoice.objects.select_related(
                "customer",
                "payment_method",
                "global_dimension_1",
            )
            .all()
            .order_by("-created_at")
        )

        # Handle special "not_paid" payment method filter
        payment_method_filter = self.request.query_params.get("payment_method")
        if payment_method_filter == "not_paid":
            # Filter for sales where payment_method is null or empty
            queryset = queryset.filter(payment_method__isnull=True)
        elif payment_method_filter and payment_method_filter != "not_paid":
            # Regular payment method filtering
            queryset = queryset.filter(payment_method=payment_method_filter)

        # Optional user-level filter (used by Sales History "view only own sales").
        # Sales ownership is derived from the latest customer ledger entry per invoice.
        user_filter = self.request.query_params.get("user")
        if user_filter not in (None, ""):
            try:
                user_filter_id = int(user_filter)
                invoice_user_id_subquery = (
                    CustomerLedgerEntry.objects.filter(
                        document_no=OuterRef("invoice_no")
                    )
                    .order_by("-id")
                    .values("user_id")[:1]
                )
                queryset = queryset.annotate(
                    ledger_user_id=Subquery(
                        invoice_user_id_subquery, output_field=models.IntegerField()
                    )
                ).filter(ledger_user_id=user_filter_id)
            except (TypeError, ValueError):
                # Ignore invalid user filter values and keep normal queryset behavior.
                pass

        queryset = filter_queryset_by_branch(
            queryset, self.request.user, request=self.request
        )
        if self.action in ("list", "summary"):
            queryset = self._with_invoice_totals(queryset)
        if self.action == "list":
            queryset = self._with_reverse_metadata(queryset)
            exclude_reversed = (
                self.request.query_params.get("exclude_reversed", "").lower()
            )
            if exclude_reversed in ("true", "1", "yes"):
                queryset = queryset.filter(reversed=False)
        return queryset

    def get_object(self):
        queryset = self.filter_queryset(self.get_queryset())
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
        pk = self.kwargs[lookup_url_kwarg]
        try:
            return queryset.get(id=pk)
        except (SalesInvoice.DoesNotExist, ValueError):
            if "-" in str(pk):
                return queryset.get(system_id=pk)
            raise

    def list(self, request, *args, **kwargs):
        """List invoices - requires READ permission"""
        has_permission, source = request.user.check_object_permission(10002, "read")
        if not has_permission:
            return Response(
                {
                    "error": "Insufficient permissions",
                    "detail": "You need read permission to view invoices",
                    "reason": source,
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().list(request, *args, **kwargs)

    @action(detail=False, methods=["get"], url_path="summary")
    def summary(self, request, *args, **kwargs):
        """Return aggregated totals for Sales History (PostedSalesInvoice archive)."""
        has_permission, source = request.user.check_object_permission(10004, "read")
        if not has_permission:
            return Response(
                {
                    "error": "Insufficient permissions",
                    "detail": "You need sales history permission to view summaries",
                    "reason": source,
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        queryset = self._posted_sales_history_queryset(request)
        group_by = request.query_params.get("group_by")
        posted_ids = list(queryset.values_list("id", flat=True))

        if not posted_ids:
            if group_by == "user":
                return Response({"users": []})
            return Response(
                {
                    "total_sales": 0.0,
                    "total_products": 0.0,
                    "total_invoices": 0,
                }
            )

        if group_by == "user":
            posted_rows = list(
                queryset.values(
                    "id",
                    "customer_invoice_no",
                    "customer_id",
                    "computed_total_amount",
                )
            )
            link_keys = {
                (row["customer_id"], row["customer_invoice_no"]) for row in posted_rows
            }
            customer_invoice_nos = {key[1] for key in link_keys if key[1]}
            sales_invoice_map = {}
            if customer_invoice_nos:
                for si in SalesInvoice.objects.filter(
                    customer_invoice_no__in=customer_invoice_nos
                ).values("customer_id", "customer_invoice_no", "invoice_no"):
                    sales_invoice_map[
                        (si["customer_id"], si["customer_invoice_no"])
                    ] = si["invoice_no"]

            invoice_numbers = list(set(sales_invoice_map.values()))
            ledger_user_map = {}
            if invoice_numbers:
                ledger_entries = (
                    CustomerLedgerEntry.objects.filter(document_no__in=invoice_numbers)
                    .select_related("user")
                    .order_by("document_no", "-id")
                    .distinct("document_no")
                )
                for entry in ledger_entries:
                    if entry.user:
                        ledger_user_map[entry.document_no] = entry.user

            qty_rows = (
                PostedSalesInvoiceLine.objects.filter(
                    posted_sales_invoice_id__in=posted_ids
                )
                .values("posted_sales_invoice_id")
                .annotate(total_products=Coalesce(Sum("quantity"), 0))
            )
            qty_by_posted = {
                row["posted_sales_invoice_id"]: Decimal(str(row["total_products"] or 0))
                for row in qty_rows
            }

            user_totals = {}
            for row in posted_rows:
                invoice_no = sales_invoice_map.get(
                    (row["customer_id"], row["customer_invoice_no"])
                )
                user = ledger_user_map.get(invoice_no) if invoice_no else None
                user_id = user.id if user else None
                user_name = (
                    getattr(user, "full_name", None)
                    or getattr(user, "username", None)
                    or "Unknown"
                )
                if user_id not in user_totals:
                    user_totals[user_id] = {
                        "user_id": user_id,
                        "user_name": user_name,
                        "total_sales": Decimal("0"),
                        "total_products": Decimal("0"),
                        "total_invoices": 0,
                    }
                user_totals[user_id]["total_sales"] += Decimal(
                    str(row["computed_total_amount"] or 0)
                )
                user_totals[user_id]["total_products"] += qty_by_posted.get(
                    row["id"], Decimal("0")
                )
                user_totals[user_id]["total_invoices"] += 1

            users = sorted(
                [
                    {
                        "user_id": values["user_id"],
                        "user_name": values["user_name"],
                        "total_sales": float(values["total_sales"]),
                        "total_products": float(values["total_products"]),
                        "total_invoices": values["total_invoices"],
                    }
                    for values in user_totals.values()
                ],
                key=lambda item: item["total_sales"],
                reverse=True,
            )
            return Response({"users": users})

        totals = queryset.aggregate(
            total_sales=Coalesce(
                Sum("computed_total_amount"),
                Value(
                    Decimal("0.00"),
                    output_field=DecimalField(max_digits=18, decimal_places=2),
                ),
            )
        )
        qty_totals = PostedSalesInvoiceLine.objects.filter(
            posted_sales_invoice_id__in=posted_ids
        ).aggregate(total_products=Coalesce(Sum("quantity"), 0))

        return Response(
            {
                "total_sales": float(totals.get("total_sales") or 0),
                "total_products": float(qty_totals.get("total_products") or 0),
                "total_invoices": queryset.count(),
            }
        )

    def _check_home_snapshot_permission(self, request):
        """Sales Dashboard (10001) or Sales History (10004) read access."""
        source = "permission_denied"
        for page_id in (10001, 10004):
            has_permission, source = request.user.check_object_permission(
                page_id, "read"
            )
            if has_permission:
                return True, source
        return False, source

    def _day_sales_totals(self, request, day):
        """Aggregate revenue, order count, and units sold for a single day."""
        decimal_zero = Value(
            Decimal("0.00"), output_field=DecimalField(max_digits=18, decimal_places=2)
        )
        queryset = SalesInvoice.objects.filter(
            document_date=day,
            status__in=["Posted", "Open"],
        )
        queryset = filter_queryset_by_branch(
            queryset, request.user, request=request
        )
        queryset = self._with_invoice_totals(queryset)
        invoice_count = queryset.count()
        if invoice_count == 0:
            return {
                "total_sales": 0.0,
                "total_products": 0.0,
                "total_invoices": 0,
            }

        totals = queryset.aggregate(
            total_sales=Coalesce(
                Sum("computed_total_amount"),
                decimal_zero,
                output_field=DecimalField(max_digits=18, decimal_places=2),
            )
        )
        qty_totals = SalesInvoiceLine.objects.filter(
            sales_invoice_id__in=queryset.values("id")
        ).aggregate(total_products=Coalesce(Sum("quantity"), 0))

        return {
            "total_sales": float(totals.get("total_sales") or 0),
            "total_products": float(qty_totals.get("total_products") or 0),
            "total_invoices": invoice_count,
        }

    def _top_selling_items_for_day(self, request, day, limit=5):
        decimal_zero = Value(
            Decimal("0.00"), output_field=DecimalField(max_digits=18, decimal_places=2)
        )
        decimal_field = DecimalField(max_digits=18, decimal_places=2)
        invoice_qs = filter_queryset_by_branch(
            SalesInvoice.objects.filter(
                document_date=day,
                status__in=["Posted", "Open"],
            ),
            request.user,
            request=request,
        )
        line_qs = SalesInvoiceLine.objects.filter(
            sales_invoice_id__in=invoice_qs.values("id")
        )
        # Quantity ranking first (matches sales dashboard pattern); amount per item
        # is computed separately to avoid nested Sum(ExpressionWrapper) ORM errors.
        rows = (
            line_qs.values("item__no", "item__item_name")
            .annotate(quantity=Coalesce(Sum("quantity"), 0))
            .order_by("-quantity")[:limit]
        )
        results = []
        for row in rows:
            item_no = row["item__no"]
            if not item_no:
                continue
            amount_row = line_qs.filter(item__no=item_no).aggregate(
                total=Coalesce(
                    Sum(
                        F("unit_price") * F("quantity"),
                        output_field=decimal_field,
                    ),
                    decimal_zero,
                    output_field=decimal_field,
                )
            )
            results.append(
                {
                    "item_no": item_no,
                    "name": row["item__item_name"] or "Unknown Item",
                    "quantity": float(row["quantity"] or 0),
                    "total": float(amount_row.get("total") or 0),
                }
            )
        return results

    @action(detail=False, methods=["get"], url_path="home-snapshot")
    def home_snapshot(self, request):
        """
        Mobile home snapshot: today/yesterday KPIs, top sellers, and catalog count
        in one aggregated response (avoids paginated /sales/ list fetches).
        """
        has_permission, source = self._check_home_snapshot_permission(request)
        if not has_permission:
            return Response(
                {
                    "error": "Insufficient permissions",
                    "detail": "You need sales dashboard or sales history read access",
                    "reason": source,
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            today = timezone.now().date()
            yesterday = today - timedelta(days=1)
            try:
                top_items_limit = int(request.query_params.get("top_items_limit", 5))
            except (TypeError, ValueError):
                top_items_limit = 5
            top_items_limit = max(1, min(top_items_limit, 20))

            items_qs = filter_queryset_by_branch(
                Item.objects.all(), request.user, request=request
            )

            return Response(
                {
                    "today": self._day_sales_totals(request, today),
                    "yesterday": self._day_sales_totals(request, yesterday),
                    "top_selling_items": self._top_selling_items_for_day(
                        request, today, limit=top_items_limit
                    ),
                    "total_catalog_products": items_qs.count(),
                }
            )
        except Exception as e:
            return Response(
                {"detail": f"Error generating home snapshot: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    def retrieve(self, request, *args, **kwargs):
        """Get single invoice - requires READ permission"""
        has_permission, source = request.user.check_object_permission(10002, "read")
        if not has_permission:
            return Response(
                {
                    "error": "Insufficient permissions",
                    "detail": "You need read permission to view invoices",
                    "reason": source,
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            instance = self.get_object()
            # Recalculate VAT when opening (ensures fresh vat_percent, vat_amount, total_vat_amount)
            if instance.status != "Posted":
                instance.recalculate_vat()
                instance = SalesInvoice.objects.prefetch_related("lines").get(
                    pk=instance.pk
                )
            serializer = self.get_serializer(instance)
            return Response(serializer.data)
        except SalesInvoice.DoesNotExist:
            return Response(
                {"detail": "Sale not found"}, status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def create(self, request, *args, **kwargs):
        """Create invoice - requires INSERT permission"""
        has_permission, source = request.user.check_object_permission(10002, "insert")
        if not has_permission:
            return Response(
                {
                    "error": "Insufficient permissions",
                    "detail": "You need insert permission to create invoices",
                    "reason": source,
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        """Update invoice - requires MODIFY permission"""
        has_permission, source = request.user.check_object_permission(10002, "modify")
        if not has_permission:
            return Response(
                {
                    "error": "Insufficient permissions",
                    "detail": "You need modify permission to update invoices",
                    "reason": source,
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        """Partial update invoice - requires MODIFY permission"""
        has_permission, source = request.user.check_object_permission(10002, "modify")
        if not has_permission:
            return Response(
                {
                    "error": "Insufficient permissions",
                    "detail": "You need modify permission to update invoices",
                    "reason": source,
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        """Delete invoice - requires DELETE permission"""
        has_permission, source = request.user.check_object_permission(10002, "delete")
        if not has_permission:
            return Response(
                {
                    "error": "Insufficient permissions",
                    "detail": "You need delete permission to remove invoices",
                    "reason": source,
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=["post"], url_path="edit-dimension-set")
    def edit_dimension_set(self, request, pk=None):
        """BC-style Edit Dimension Set: update header dimensions and propagate to lines."""
        from dimension.models import (
            Dimension,
            DimensionValue,
            get_or_create_dimension_set,
            update_global_dim_from_dimension_set,
            update_all_line_dim,
        )

        invoice = self.get_object()
        dimensions = request.data.get("dimensions") or {}

        if not isinstance(dimensions, dict):
            return Response(
                {"error": "dimensions must be a dict of dimension_code: value_id"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        dim_values = {}
        for dim_code, value_id in dimensions.items():
            if not value_id:
                continue
            dim = Dimension.objects.filter(code=dim_code).first()
            if not dim:
                continue
            try:
                dv = DimensionValue.objects.get(pk=value_id)
            except (DimensionValue.DoesNotExist, (TypeError, ValueError)):
                continue
            if dv.dimension_code_id != dim.pk:
                continue
            dim_values[dim] = dv

        new_set = get_or_create_dimension_set(dim_values) if dim_values else None
        old_dim_set_id = invoice.dimension_set_id
        invoice.dimension_set = new_set
        update_global_dim_from_dimension_set(invoice)
        invoice.save()

        if invoice.dimension_set_id != old_dim_set_id:
            update_all_line_dim(invoice, invoice.dimension_set_id, old_dim_set_id)

        serializer = self.get_serializer(invoice)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def reverse_sales(self, request, pk=None):
        """
        Reverse a posted sales invoice by:
        1. Creating a credit memo from the posted sales invoice
        2. Automatically posting the credit memo with all reversal entries
        """
        try:
            sales_invoice = self.get_object()

            # Check user permission to reverse sales invoices
            # This permission is controlled in User Setup (can_reverse_sales_invoice)
            from authentication.models import UserSetup

            try:
                user_setup = UserSetup.objects.get(user=request.user)
            except UserSetup.DoesNotExist:
                # If no setup exists, deny by default (security-first approach)
                return Response(
                    {
                        "error": "Permission denied",
                        "detail": "You do not have permission to reverse sales invoices. Please contact your administrator to enable this permission in your User Setup.",
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

            # Check the permission flag
            if not user_setup.can_reverse_sales_invoice:
                return Response(
                    {
                        "error": "Permission denied",
                        "detail": "You do not have permission to reverse sales invoices. Please contact your administrator to enable this permission in your User Setup.",
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

            # Validate sales invoice is posted
            if sales_invoice.status != "Posted":
                return Response(
                    {
                        "error": "Cannot reverse sales invoice",
                        "detail": f"Sales invoice {sales_invoice.invoice_no} is not posted. Only posted invoices can be reversed.",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Check if already reversed by finding PostedSalesInvoice and checking for credit memos
            customer_invoice_no = getattr(sales_invoice, "customer_invoice_no", None)

            # Try to find by customer_invoice_no first (most reliable)
            if customer_invoice_no:
                posted_sales_invoice = PostedSalesInvoice.objects.filter(
                    customer_invoice_no=customer_invoice_no,
                    customer=sales_invoice.customer,
                ).first()
            else:
                # Fallback: match by customer and document_date
                posted_sales_invoice = PostedSalesInvoice.objects.filter(
                    customer=sales_invoice.customer,
                    document_date=sales_invoice.document_date,
                ).first()

            if posted_sales_invoice:
                # Check if already reversed
                if posted_sales_invoice.reversed:
                    return Response(
                        {
                            "error": "Sales invoice already reversed",
                            "detail": f"Sales invoice {sales_invoice.invoice_no} has already been reversed on {posted_sales_invoice.reversed_date}.",
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                # Check if there are posted credit memos
                if posted_sales_invoice.credit_memos.filter(status="Posted").exists():
                    return Response(
                        {
                            "error": "Sales invoice already reversed",
                            "detail": f"Sales invoice {sales_invoice.invoice_no} already has credit memos posted against it.",
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            # Get reason from request (optional)
            reason = request.data.get(
                "reason", f"Manual reversal by {request.user.username}"
            )

            # Find the PostedSalesInvoice if not already found
            if not posted_sales_invoice:
                return Response(
                    {
                        "error": "Posted sales invoice not found",
                        "detail": f"Could not find posted invoice for {sales_invoice.invoice_no}. The invoice may not have been properly posted.",
                    },
                    status=status.HTTP_404_NOT_FOUND,
                )

            # Create wrapper object (similar to ReversalInvoiceWrapper in admin)
            class ReversalInvoiceWrapper:
                """Wrapper to make SalesInvoice compatible with reversal processor"""

                def __init__(self, sales_invoice, posted_sales_invoice):
                    self.no = sales_invoice.invoice_no
                    self.invoice_no = sales_invoice.invoice_no
                    self.customer = sales_invoice.customer
                    self.document_date = sales_invoice.document_date
                    self.posting_date = sales_invoice.posting_date
                    self.vat_date = getattr(sales_invoice, "vat_date", None)
                    self.due_date = getattr(sales_invoice, "due_date", None)
                    self.customer_invoice_no = customer_invoice_no
                    self.status = sales_invoice.status
                    self.reversed = False
                    # Use PostedSalesInvoiceLine objects which have 'amount' field
                    self.posted_sales_invoice_lines = (
                        posted_sales_invoice.posted_sales_invoice_lines.all()
                    )
                    # Add credit_memos as empty queryset
                    self.credit_memos = SalesCreditMemo.objects.none()

            invoice_wrapper = ReversalInvoiceWrapper(
                sales_invoice, posted_sales_invoice
            )

            # Execute reversal using wrapper
            # All operations wrapped in atomic transaction for complete rollback on failure
            with transaction.atomic():
                processor = SalesInvoiceReversalPostingProcessor(
                    invoice_wrapper, request, reason=reason
                )

                result = processor.post()

                if not result.get("success", False):
                    error_msg = result.get("message", "Unknown error during reversal")
                    raise Exception(error_msg)

                # Reversal successful - continue with status updates
                credit_memo = result.get("credit_memo")
                credit_memo_no = result.get("credit_memo_no")
                transaction_no = result.get("transaction_no", "N/A")
                posted_sales_invoice = result.get(
                    "posted_sales_invoice"
                )  # Already marked as reversed in processor

                # Keep status as "Posted" - the reversed boolean field indicates reversal
                # This matches the purchase invoice reversal pattern
                # PostedSalesInvoice is already marked as reversed in the processor

                return Response(
                    {
                        "message": "Sales invoice reversed successfully",
                        "sales_invoice_no": sales_invoice.invoice_no,
                        "credit_memo_no": credit_memo_no,
                        "credit_memo_id": credit_memo.id if credit_memo else None,
                        "status": "Posted",
                        "transaction_no": transaction_no,
                    },
                    status=status.HTTP_200_OK,
                )

        except Exception as e:
            import traceback
            import logging
            from django.conf import settings

            logger = logging.getLogger(__name__)
            logger.error(f"Error reversing sales invoice: {str(e)}")
            logger.error(f"Full traceback: {traceback.format_exc()}")

            error_message = str(e)
            # Clean up error message
            if error_message.startswith("Error reversing invoice: "):
                error_message = error_message.replace("Error reversing invoice: ", "")
            if error_message.startswith("❌ Error reversing invoice: "):
                error_message = error_message.replace(
                    "❌ Error reversing invoice: ", ""
                )

            return Response(
                {
                    "error": "Failed to reverse sales invoice",
                    "detail": error_message,
                    "traceback": traceback.format_exc() if settings.DEBUG else None,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=False, methods=["post"])
    def upsert(self, request):
        system_id = request.data.get("system_id")
        customer_name = request.data.get("customer_name")
        deleted = request.data.get("deleted", False)
        id = request.data.get("id")
        with transaction.atomic():
            if system_id:
                try:
                    # Try to find by system_id and id if both provided, or just system_id
                    if id:
                        sale = SalesInvoice.objects.get(system_id=system_id, id=id)
                    else:
                        sale = SalesInvoice.objects.get(system_id=system_id)
                    if deleted:
                        sale.delete()
                        return Response(
                            {"message": "Sale deleted successfully"},
                            status=status.HTTP_200_OK,
                        )
                    else:
                        serializer = self.get_serializer(
                            sale, data=request.data, partial=True
                        )
                        if serializer.is_valid(raise_exception=True):
                            sale = serializer.save()
                            return Response(serializer.data, status=status.HTTP_200_OK)
                except SalesInvoice.DoesNotExist:
                    serializer = self.get_serializer(data=request.data)
                    if serializer.is_valid(raise_exception=True):
                        sale = serializer.save()
                        return Response(serializer.data, status=status.HTTP_201_CREATED)
            elif id:
                # Handle update by ID only (no system_id)
                try:
                    sale = SalesInvoice.objects.get(id=id)
                    if deleted:
                        sale.delete()
                        return Response(
                            {"message": "Sale deleted successfully"},
                            status=status.HTTP_200_OK,
                        )
                    else:
                        # Update existing sale by ID
                        serializer = self.get_serializer(
                            sale, data=request.data, partial=True
                        )
                        if serializer.is_valid(raise_exception=True):
                            sale = serializer.save()
                            return Response(serializer.data, status=status.HTTP_200_OK)
                except SalesInvoice.DoesNotExist:
                    return Response(
                        {"error": f"Sales Invoice with ID {id} not found"},
                        status=status.HTTP_404_NOT_FOUND,
                    )
            else:
                # Create new sale - requires customer_name
                if not customer_name:
                    return Response(
                        {"customer_name": "Customer name is required"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                serializer = self.get_serializer(data=request.data)
                if serializer.is_valid(raise_exception=True):
                    sale = serializer.save()
                    return Response(serializer.data, status=status.HTTP_201_CREATED)
            return Response(
                {"detail": "Invalid request"}, status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=["post"], url_path="update_lines")
    def update_lines(self, request, pk=None):
        from decimal import Decimal
        from resources.models import Resource

        sale = self.get_object()
        lines_data = request.data.get("lines", [])
        try:
            with transaction.atomic():
                existing_lines = {line.id: line for line in sale.lines.all()}
                processed_line_ids = set()
                for line_data in lines_data:
                    line_data.pop("total_amount", None)
                    line_id = line_data.get("id")
                    line_system_id = line_data.get("system_id")
                    if line_data.get("deleted"):
                        if line_id in existing_lines:
                            existing_lines[line_id].delete()
                            processed_line_ids.add(line_id)
                        continue

                    line_type = line_data.get("type", "item")
                    discount_value = line_data.get(
                        "line_discount_amount"
                    ) or line_data.get("lineDiscountAmount")
                    try:
                        if discount_value is None or discount_value == "":
                            discount_amount = Decimal("0")
                        elif isinstance(discount_value, str):
                            discount_amount = (
                                Decimal(discount_value.strip())
                                if discount_value.strip()
                                else Decimal("0")
                            )
                        elif isinstance(discount_value, (int, float)):
                            discount_amount = Decimal(str(discount_value))
                        else:
                            discount_amount = Decimal("0")
                    except (TypeError, ValueError):
                        discount_amount = Decimal("0")

                    if line_type == "resource":
                        resource_val = line_data.get("resource")
                        if not resource_val:
                            raise ValidationError(
                                "Resource is required when line type is Resource."
                            )
                        if isinstance(resource_val, int):
                            resource = Resource.objects.filter(pk=resource_val).first()
                        elif isinstance(resource_val, str):
                            resource = Resource.objects.filter(
                                code=resource_val
                            ).first()
                        else:
                            resource = resource_val
                        if not resource:
                            raise ValidationError(f"Resource {resource_val} not found.")
                        uom_code = line_data.get("unit_of_measure")
                        if uom_code and isinstance(uom_code, str):
                            unit_of_measure, _ = UnitOfMeasure.objects.get_or_create(
                                code=uom_code, defaults={"description": uom_code}
                            )
                        else:
                            unit_of_measure = getattr(resource, "base_unit", None)
                        prepared_line_data = {
                            "type": "resource",
                            "resource": resource,
                            "item": None,
                            "quantity": int(float(line_data.get("quantity", 0))),
                            "unit_price": (
                                Decimal(str(line_data.get("unit_price", 0)))
                                if line_data.get("unit_price") is not None
                                else Decimal("0")
                            ),
                            "description": line_data.get("description", "")
                            or resource.name,
                            "line_discount_amount": discount_amount,
                            "location_code": None,
                            "item_unit_of_measure": None,
                            "unit_of_measure": unit_of_measure,
                            "tracking_code": None,
                        }
                        from dimension.models import get_merged_line_dimensions

                        # Prefer X-Branch-Id (selected branch) over user.global_dimension_1
                        branch = get_branch_for_request(request) or getattr(
                            request.user, "global_dimension_1", None
                        )
                        line_data_for_dims = dict(line_data) if line_data else {}
                        if branch:
                            line_data_for_dims["global_dimension_1"] = branch

                        customer_no = (
                            getattr(sale.customer, "no", None)
                            if sale.customer
                            else None
                        )
                        dims = get_merged_line_dimensions(
                            customer_no=customer_no,
                            resource=resource,
                            request_user=request.user,
                            line_data=line_data_for_dims,
                            header_dimensions=sale,
                        )
                        prepared_line_data["dimension_set"] = dims.get("dimension_set")
                        prepared_line_data["global_dimension_1"] = dims.get(
                            "global_dimension_1"
                        )
                    else:
                        item_no = line_data.get("item_no") or line_data.get("item")
                        item_name = line_data.get("item_name")
                        item_system_id = line_data.get("item_system_id")
                        item = None
                        if item_no:
                            item = Item.objects.filter(no=item_no).first()
                        if not item and item_name:
                            item = Item.objects.filter(item_name=item_name).first()
                        if not item and item_system_id:
                            item = Item.objects.filter(system_id=item_system_id).first()
                        if not item:
                            raise ValidationError(
                                f"Item with number/name {item_no or item_name} not found"
                            )
                        unit_of_measure_code = line_data.get("unit_of_measure", "PCS")
                        unit_of_measure, _ = UnitOfMeasure.objects.get_or_create(
                            code=unit_of_measure_code,
                            defaults={"description": unit_of_measure_code},
                        )
                        item_unit_of_measure, _ = (
                            ItemUnitOfMeasure.objects.get_or_create(
                                unit_of_measure=unit_of_measure,
                                item=item,
                                defaults={"quantity_per_unit": 1},
                            )
                        )
                        # Use branch from X-Branch-Id or user for location lookup
                        branch_for_loc = get_branch_for_request(request) or getattr(
                            request.user, "global_dimension_1", None
                        )
                        try:
                            loc = (
                                Location.objects.get(code=branch_for_loc.code)
                                if branch_for_loc
                                else Location.objects.first()
                            )
                        except Exception:
                            loc = Location.objects.first()
                        prepared_line_data = {
                            "type": "item",
                            "item": item,
                            "resource": None,
                            "quantity": int(float(line_data.get("quantity", 0))),
                            "unit_price": (
                                Decimal(str(line_data.get("unit_price", 0)))
                                if line_data.get("unit_price") is not None
                                else Decimal("0")
                            ),
                            "description": line_data.get("description", "")
                            or item.item_name,
                            "tracking_code": line_data.get("tracking_code") or "",
                            "item_unit_of_measure": item_unit_of_measure,
                            "unit_of_measure": unit_of_measure,
                            "line_discount_amount": discount_amount,
                            "location_code": loc,
                        }
                        from dimension.models import get_merged_line_dimensions

                        # Prefer X-Branch-Id (selected branch) over user.global_dimension_1
                        branch = get_branch_for_request(request) or getattr(
                            request.user, "global_dimension_1", None
                        )
                        line_data_for_dims = dict(line_data) if line_data else {}
                        if branch:
                            line_data_for_dims["global_dimension_1"] = branch

                        customer_no = (
                            getattr(sale.customer, "no", None)
                            if sale.customer
                            else None
                        )
                        dims = get_merged_line_dimensions(
                            customer_no=customer_no,
                            item=item,
                            request_user=request.user,
                            line_data=line_data_for_dims,
                            header_dimensions=sale,
                        )
                        prepared_line_data["dimension_set"] = dims.get("dimension_set")
                        prepared_line_data["global_dimension_1"] = dims.get(
                            "global_dimension_1"
                        )

                    if line_data.get("dimension_1") is not None:
                        from dimension.models import resolve_dimension_value

                        dv = resolve_dimension_value(line_data["dimension_1"])
                        if dv:
                            prepared_line_data["dimension_1"] = dv

                    if line_id and line_system_id and line_id in existing_lines:
                        line = existing_lines[line_id]
                        for field, value in prepared_line_data.items():
                            if value is not None:
                                setattr(line, field, value)
                        line.save()
                        processed_line_ids.add(line_id)
                    else:
                        SalesInvoiceLine.objects.create(
                            sales_invoice=sale, **prepared_line_data
                        )
                lines_to_delete = set(existing_lines.keys()) - processed_line_ids
                # Optionally delete lines not present in request
                # if lines_to_delete:
                #     sale.lines.filter(id__in=lines_to_delete).delete()
                # Ensure VAT is recalculated (uses vat_business_posting_group + vat_product_posting_group)
                sale.recalculate_vat()
                sale = SalesInvoice.objects.prefetch_related("lines").get(pk=sale.pk)
                serializer = self.get_serializer(sale)
                return Response(serializer.data)
        except ValidationError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"])
    def post_sale(self, request, pk=None):
        """Post a sales invoice - alias for post_invoice"""
        try:
            sale = self.get_object()
            mock_admin = SalesInvoiceAdmin(SalesInvoice, admin.site)
            with transaction.atomic():
                mock_admin.post_invoice(request, [sale])
            return Response(
                {
                    "message": "Sale posted successfully",
                    "sale": self.get_serializer(sale).data,
                }
            )
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"])
    def post_invoice(self, request, pk=None):
        """
        Post a sales invoice - this will handle all the admin posting actions
        including inventory reduction, GL entries, customer ledger entries, etc.
        """
        try:
            invoice = self.get_object()

            # Check if invoice is already posted
            if invoice.status == "Posted":
                return Response(
                    {"error": "Invoice is already posted"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Check if invoice status is Open (only Open invoices can be posted)
            if invoice.status != "Open":
                return Response(
                    {
                        "error": f"Cannot post invoice with status '{invoice.status}'. Only 'Open' invoices can be posted."
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Check if user can post previous dates
            from authentication.models import UserSetup
            from django.utils import timezone

            user_setup = UserSetup.get_or_create_for_user(request.user)
            today = timezone.now().date()

            # Check document_date if it exists
            if invoice.document_date and invoice.document_date < today:
                if not user_setup.can_post_previous_dates:
                    return Response(
                        {
                            "error": "Cannot post invoice with previous document date",
                            "detail": f"Document date ({invoice.document_date}) is in the past. You do not have permission to post invoices for previous dates.",
                            "invoice_no": invoice.invoice_no,
                            "document_date": invoice.document_date,
                        },
                        status=status.HTTP_403_FORBIDDEN,
                    )

            # Check posting_date if it exists
            if invoice.posting_date and invoice.posting_date < today:
                if not user_setup.can_post_previous_dates:
                    return Response(
                        {
                            "error": "Cannot post invoice with previous posting date",
                            "detail": f"Posting date ({invoice.posting_date}) is in the past. You do not have permission to post invoices for previous dates.",
                            "invoice_no": invoice.invoice_no,
                            "posting_date": invoice.posting_date,
                        },
                        status=status.HTTP_403_FORBIDDEN,
                    )

            # Reuse admin helpers to validate/post but surface errors to API
            mock_admin = SalesInvoiceAdmin(SalesInvoice, admin.site)

            can_post, reason = mock_admin.can_post_invoice(invoice)
            if not can_post:
                return Response(
                    {
                        "error": "Cannot post invoice",
                        "detail": reason,
                        "invoice_no": invoice.invoice_no,
                        "status": invoice.status,
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            receipt_no = f"RCP-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"

            posting_processor = SalesInvoicePostingProcessor(
                invoice, request, receipt_no
            )
            result = posting_processor.post()

            if not result.get("success"):
                return Response(
                    {
                        "error": "Posting failed",
                        "detail": result.get("message", "Unknown error"),
                        "invoice_no": invoice.invoice_no,
                        "status": invoice.status,
                    },
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

            invoice.refresh_from_db()
            # Reload lines to ensure discounts are included in total_amount calculation
            from django.db.models import Prefetch

            invoice = SalesInvoice.objects.prefetch_related("lines").get(pk=invoice.pk)

            return Response(
                {
                    "message": "Sales invoice posted successfully",
                    "invoice": self.get_serializer(invoice).data,
                    "invoice_no": invoice.invoice_no,
                    "status": invoice.status,
                }
            )
        except (ValidationError, DjangoValidationError) as e:
            # Handle validation errors (like insufficient inventory)
            return Response(
                {"error": f"Validation error: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            # Log the full error for debugging
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"Error posting invoice {pk}: {str(e)}", exc_info=True)

            return Response(
                {"error": f"Failed to post invoice: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class SalesOrderViewSet(viewsets.ModelViewSet):
    """
    Sales Order ViewSet – mirrors SalesViewSet but does NOT post accounting/inventory.
    Page ID: 10003 (Sales Order Page)
    """

    queryset = SalesOrder.objects.all()
    serializer_class = SalesOrderSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    filterset_class = SalesOrderFilter
    search_fields = ["customer__name", "order_no"]
    ordering_fields = ["order_date", "created_at"]
    ordering = ["-created_at"]

    def get_queryset(self):
        queryset = SalesOrder.objects.all().order_by("-created_at")
        return filter_queryset_by_branch(
            queryset, self.request.user, request=self.request
        )

    def get_object(self):
        queryset = self.filter_queryset(self.get_queryset())
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
        pk = self.kwargs[lookup_url_kwarg]
        try:
            return queryset.get(id=pk)
        except (SalesOrder.DoesNotExist, ValueError):
            if "-" in str(pk):
                return queryset.get(system_id=pk)
            raise

    def list(self, request, *args, **kwargs):
        """List orders - requires READ permission"""
        has_permission, source = request.user.check_object_permission(10003, "read")
        if not has_permission:
            return Response(
                {
                    "error": "Insufficient permissions",
                    "detail": "You need read permission to view sales orders",
                    "reason": source,
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        """Get single order - requires READ permission"""
        has_permission, source = request.user.check_object_permission(10003, "read")
        if not has_permission:
            return Response(
                {
                    "error": "Insufficient permissions",
                    "detail": "You need read permission to view sales orders",
                    "reason": source,
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    def create(self, request, *args, **kwargs):
        """Create order - requires INSERT permission"""
        has_permission, source = request.user.check_object_permission(10003, "insert")
        if not has_permission:
            return Response(
                {
                    "error": "Insufficient permissions",
                    "detail": "You need insert permission to create sales orders",
                    "reason": source,
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        """Update order - requires MODIFY permission"""
        has_permission, source = request.user.check_object_permission(10003, "modify")
        if not has_permission:
            return Response(
                {
                    "error": "Insufficient permissions",
                    "detail": "You need modify permission to update sales orders",
                    "reason": source,
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        """Partial update order - requires MODIFY permission"""
        has_permission, source = request.user.check_object_permission(10003, "modify")
        if not has_permission:
            return Response(
                {
                    "error": "Insufficient permissions",
                    "detail": "You need modify permission to update sales orders",
                    "reason": source,
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        """Delete order - requires DELETE permission"""
        has_permission, source = request.user.check_object_permission(10003, "delete")
        if not has_permission:
            return Response(
                {
                    "error": "Insufficient permissions",
                    "detail": "You need delete permission to remove sales orders",
                    "reason": source,
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=["post"], url_path="update_lines")
    def update_lines(self, request, pk=None):
        """
        Upsert/delete Sales Order lines - follows Prepayment pattern using serializer.
        Payload:
        {
          "system_id": "<optional>",
          "id": <order id>,
          "lines": [{ id, ... } | { id, deleted: true } | { ...create... }]
        }
        """
        print("=" * 80)
        print("DEBUG: SalesOrderViewSet.update_lines called")
        print(f"DEBUG: pk = {pk}")

        has_permission, source = request.user.check_object_permission(10003, "modify")
        if not has_permission:
            return Response(
                {
                    "error": "Insufficient permissions",
                    "detail": "You need modify permission to update sales order lines",
                    "reason": source,
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        order = self.get_object()
        lines_data = request.data.get("lines", []) or []

        try:
            with transaction.atomic():
                serializer = self.get_serializer(instance=order)
                serializer._lines_data = lines_data
                serializer.update(order, {})
                order.refresh_from_db()
                order.recalculate_totals()

                # Return fresh order
                serializer = self.get_serializer(self.get_object())
                return Response(serializer.data)
        except ValidationError as e:
            print(f"DEBUG: ValidationError caught: {str(e)}")
            import traceback

            print(f"DEBUG: ValidationError traceback:\n{traceback.format_exc()}")
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            import traceback

            print(f"DEBUG: Exception caught in outer handler: {type(e)}")
            print(f"DEBUG: Exception message: {str(e)}")
            print(f"DEBUG: Full traceback:\n{traceback.format_exc()}")
            error_detail = str(e)
            traceback_str = traceback.format_exc()
            return Response(
                {
                    "error": error_detail,
                    "detail": error_detail,
                    "traceback": traceback_str,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=True, methods=["post"], url_path="convert-to-invoice")
    def convert_to_invoice(self, request, pk=None):
        """
        Convert this Sales Order into a Sales Invoice.
        Does NOT post the invoice or touch accounting/inventory;
        posting is still handled by existing invoice posting actions.
        """
        has_permission, source = request.user.check_object_permission(10003, "modify")
        if not has_permission:
            return Response(
                {
                    "error": "Insufficient permissions",
                    "detail": "You need modify permission to convert sales orders",
                    "reason": source,
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        order = self.get_object()

        if order.status == "Converted to Invoice":
            return Response(
                {"error": "Sales order is already converted to an invoice"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            with transaction.atomic():
                # Resolve branch for header dimensions
                from dimension.branch_filter import get_branch_for_request
                from dimension.models import get_posting_dimension_payload
                from dimension.utils import get_first_branch_dimension_value

                branch = get_branch_for_request(self.request) if self.request else None
                if not branch and self.request and self.request.user:
                    branch = getattr(self.request.user, "global_dimension_1", None)
                if not branch:
                    branch = get_first_branch_dimension_value()
                dim_payload = get_posting_dimension_payload(global_dimension_1=branch)
                if not dim_payload.get("dimension_set"):
                    return Response(
                        {
                            "error": (
                                "Could not resolve posting dimensions for the invoice. "
                                "Check General Ledger Setup (Global Dimension 1)."
                            )
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                g1_header = dim_payload["global_dimension_1"] or branch
                if not g1_header:
                    return Response(
                        {
                            "error": (
                                "Could not resolve Global Dimension 1 for the invoice header."
                            )
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                # Create invoice header
                invoice = SalesInvoice(
                    customer=order.customer,
                    contact_person=order.contact_person,
                    document_date=order.order_date or timezone.now().date(),
                    posting_date=order.order_date or timezone.now().date(),
                    vat_date=order.order_date or timezone.now().date(),
                    due_date=order.order_date or timezone.now().date(),
                    status="Open",
                    dimension_set=dim_payload["dimension_set"],
                    global_dimension_1=g1_header,
                    global_dimension_2=dim_payload.get("global_dimension_2"),
                )
                invoice.save()

                # Copy lines
                from items.models import Location

                for line in order.lines.all():
                    SalesInvoiceLine.objects.create(
                        sales_invoice=invoice,
                        item=line.item,
                        gl_account=line.gl_account,
                        description=line.description,
                        location_code=line.location_code or Location.objects.first(),
                        quantity=line.quantity,
                        item_unit_of_measure=line.item_unit_of_measure,
                        unit_of_measure=line.unit_of_measure,
                        unit_price=line.unit_price,
                        line_discount_amount=line.line_discount_amount,
                        global_dimension_1=line.global_dimension_1,
                    )

                # Update order status
                from .enums import SalesOrderStatus

                order.status = SalesOrderStatus.CONVERTED_TO_INVOICE.value
                order.save(update_fields=["status", "updated_at"])

                serializer = SalesInvoiceSerializer(invoice)
                return Response(
                    {
                        "message": "Sales order converted to invoice successfully",
                        "invoice": serializer.data,
                    }
                )
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=["post"])
    def upsert(self, request):
        """Upsert sales order - create or update based on system_id and id"""
        has_permission, source = request.user.check_object_permission(10003, "modify")
        if not has_permission:
            return Response(
                {
                    "error": "Insufficient permissions",
                    "detail": "You need modify permission to upsert sales orders",
                    "reason": source,
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        system_id = request.data.get("system_id")
        customer_name = request.data.get("customer_name")
        deleted = request.data.get("deleted", False)
        id = request.data.get("id")
        with transaction.atomic():
            if system_id:
                try:
                    order = SalesOrder.objects.get(system_id=system_id, id=id)
                    if deleted:
                        order.delete()
                        return Response(
                            {"message": "Sales order deleted successfully"},
                            status=status.HTTP_200_OK,
                        )
                    else:
                        serializer = self.get_serializer(
                            order, data=request.data, partial=True
                        )
                        if serializer.is_valid(raise_exception=True):
                            order = serializer.save()
                            return Response(serializer.data, status=status.HTTP_200_OK)
                except SalesOrder.DoesNotExist:
                    serializer = self.get_serializer(data=request.data)
                    if serializer.is_valid(raise_exception=True):
                        order = serializer.save()
                        return Response(serializer.data, status=status.HTTP_201_CREATED)
            else:
                if not customer_name:
                    return Response(
                        {"customer_name": "Customer name is required"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                serializer = self.get_serializer(data=request.data)
                if serializer.is_valid(raise_exception=True):
                    order = serializer.save()
                    return Response(serializer.data, status=status.HTTP_201_CREATED)
            return Response(
                {"detail": "Invalid request"}, status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=["get"], url_path="print")
    def print_order(self, request, pk=None):
        """
        Generate PDF for sales order print/proforma.
        Returns a PDF document that can be downloaded or printed.
        """
        has_permission, source = request.user.check_object_permission(10003, "read")
        if not has_permission:
            return Response(
                {
                    "error": "Insufficient permissions",
                    "detail": "You need read permission to print sales orders",
                    "reason": source,
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            from django_tenants.utils import get_tenant
            from django.http import HttpResponse
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.units import mm
            from reportlab.platypus import (
                SimpleDocTemplate,
                Table,
                TableStyle,
                Paragraph,
                Spacer,
                Image,
                HRFlowable,
            )
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.enums import TA_CENTER
            from reportlab.lib import colors
            from io import BytesIO
            import os

            order = self.get_object()

            # Get company information
            company = get_tenant(request)

            # Get order with lines
            serializer = self.get_serializer(order)
            order_data = serializer.data

            # Create PDF response
            response = HttpResponse(content_type="application/pdf")
            filename = f"sales-order-{order.order_no}.pdf"
            response["Content-Disposition"] = f'attachment; filename="{filename}"'

            # Create PDF document
            doc = SimpleDocTemplate(
                response,
                pagesize=A4,
                leftMargin=18 * mm,
                rightMargin=18 * mm,
                topMargin=16 * mm,
                bottomMargin=16 * mm,
            )

            story = []
            styles = getSampleStyleSheet()

            # Create custom styles for centered text (don't modify shared styles)
            center_normal_style = ParagraphStyle(
                "CenterNormal",
                parent=styles["Normal"],
                alignment=TA_CENTER,
                fontSize=10,
                spaceAfter=1,
            )

            center_title_style = ParagraphStyle(
                "CenterTitle",
                parent=styles["Title"],
                alignment=TA_CENTER,
                fontSize=18,
                fontName="Helvetica-Bold",
                spaceAfter=1,
            )

            # Company Header - Centered and Professional
            header_elements = []

            # Logo (centered) - Improved with better error handling and tenant-aware storage
            logo_img = None
            try:
                # Check if logo field has a value
                if company.logo and company.logo.name:
                    # Skip default placeholder
                    if (
                        company.logo.name != "company_logos/default.png"
                        and company.logo.name
                    ):
                        logo_path = None

                        # Method 1: Try using the file's path property (works with FileField)
                        try:
                            if hasattr(company.logo, "path"):
                                logo_path = company.logo.path
                                if logo_path and os.path.exists(logo_path):
                                    # Load image and maintain aspect ratio
                                    try:
                                        from PIL import Image as PILImage

                                        pil_img = PILImage.open(logo_path)
                                        img_width, img_height = pil_img.size
                                        aspect_ratio = (
                                            img_width / img_height
                                            if img_height > 0
                                            else 1
                                        )

                                        max_width = 60 * mm
                                        max_height = 60 * mm

                                        if aspect_ratio > 1:
                                            # Landscape
                                            width = max_width
                                            height = max_width / aspect_ratio
                                        else:
                                            # Portrait or square
                                            height = max_height
                                            width = max_height * aspect_ratio

                                        logo_img = Image(
                                            logo_path, width=width, height=height
                                        )
                                    except ImportError:
                                        # PIL not available, use fixed size
                                        logo_img = Image(
                                            logo_path, width=60 * mm, height=60 * mm
                                        )
                                    except Exception as img_error:
                                        print(f"Image processing error: {img_error}")
                                        # Fallback to fixed size
                                        logo_img = Image(
                                            logo_path, width=60 * mm, height=60 * mm
                                        )
                        except Exception as path_error:
                            # Method 2: Try using Django's file storage system
                            try:
                                from django.core.files.storage import default_storage

                                if default_storage.exists(company.logo.name):
                                    # Open file and save to temporary location for ReportLab
                                    logo_file = default_storage.open(
                                        company.logo.name, "rb"
                                    )
                                    import tempfile
                                    import shutil

                                    # Get file extension
                                    ext = (
                                        os.path.splitext(company.logo.name)[1] or ".png"
                                    )

                                    # Create temporary file
                                    with tempfile.NamedTemporaryFile(
                                        delete=False, suffix=ext
                                    ) as tmp_file:
                                        shutil.copyfileobj(logo_file, tmp_file)
                                        tmp_path = tmp_file.name

                                    logo_file.close()

                                    # Load image with aspect ratio preservation
                                    try:
                                        from PIL import Image as PILImage

                                        pil_img = PILImage.open(tmp_path)
                                        img_width, img_height = pil_img.size
                                        aspect_ratio = (
                                            img_width / img_height
                                            if img_height > 0
                                            else 1
                                        )

                                        max_width = 60 * mm
                                        max_height = 60 * mm

                                        if aspect_ratio > 1:
                                            width = max_width
                                            height = max_width / aspect_ratio
                                        else:
                                            height = max_height
                                            width = max_height * aspect_ratio

                                        logo_img = Image(
                                            tmp_path, width=width, height=height
                                        )
                                    except:
                                        logo_img = Image(
                                            tmp_path, width=60 * mm, height=60 * mm
                                        )

                                    # Note: temp file will be cleaned up by system eventually
                            except Exception as storage_error:
                                print(
                                    f"Error accessing logo via storage: {storage_error}"
                                )
                                # Logo will remain None if all methods fail
            except Exception as e:
                print(f"Logo loading error: {str(e)}")
                # Logo will remain None, document will continue without logo

            # Build header content
            if logo_img:
                # Create a table to center the logo
                logo_table_data = [[logo_img]]
                logo_table = Table(logo_table_data, colWidths=[A4[0] - 36 * mm])
                logo_table.setStyle(
                    TableStyle(
                        [
                            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ]
                    )
                )
                header_elements.append(logo_table)
                header_elements.append(Spacer(1, 3 * mm))

            # Company Display Name (centered, bold) - Always show
            display_name = company.display_name or company.name or "Company Name"
            header_elements.append(Paragraph(display_name, center_title_style))
            header_elements.append(Spacer(1, 1 * mm))

            # Company Details (centered) - Always show if available
            if company.address:
                header_elements.append(Paragraph(company.address, center_normal_style))
            if company.phone:
                header_elements.append(
                    Paragraph(f"Tel: {company.phone}", center_normal_style)
                )
            if company.email:
                header_elements.append(Paragraph(company.email, center_normal_style))
            if company.website:
                header_elements.append(Paragraph(company.website, center_normal_style))
            if company.tin:
                header_elements.append(
                    Paragraph(f"TIN: {company.tin}", center_normal_style)
                )

            # Add all header elements
            for element in header_elements:
                story.append(element)

            # Horizontal line separator - Reduced spacing
            story.append(Spacer(1, 3 * mm))
            story.append(
                HRFlowable(width="100%", thickness=2, color=colors.HexColor("#000000"))
            )
            story.append(Spacer(1, 4 * mm))

            # Document Title (centered, bold)
            doc_title_style = ParagraphStyle(
                "DocTitle",
                parent=styles["Title"],
                alignment=TA_CENTER,
                fontSize=20,
                fontName="Helvetica-Bold",
                spaceAfter=6,
            )
            story.append(Paragraph("SALES ORDER", doc_title_style))

            # Order Information - Two Column Layout
            from reportlab.platypus import KeepTogether

            # Left column: Order details
            order_info_data = [
                ["Order No:", order_data.get("order_no", "N/A")],
                ["Order Date:", order_data.get("order_date", "N/A")],
                ["Status:", order_data.get("status", "Open")],
            ]

            # Right column: Customer details
            customer_info_data = [
                ["Customer:", order_data.get("customer_name", "N/A")],
            ]

            if order_data.get("expected_delivery_date"):
                customer_info_data.append(
                    ["Expected Delivery:", order_data.get("expected_delivery_date")]
                )

            # Create tables for both columns
            order_table = Table(order_info_data, colWidths=[45 * mm, 75 * mm])
            order_table.setStyle(
                TableStyle(
                    [
                        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, -1), 10),
                        ("ALIGN", (0, 0), (0, -1), "LEFT"),
                        ("ALIGN", (1, 0), (1, -1), "LEFT"),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("TOPPADDING", (0, 0), (-1, -1), 4),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ]
                )
            )

            customer_table = Table(customer_info_data, colWidths=[45 * mm, 75 * mm])
            customer_table.setStyle(
                TableStyle(
                    [
                        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, -1), 10),
                        ("ALIGN", (0, 0), (0, -1), "LEFT"),
                        ("ALIGN", (1, 0), (1, -1), "LEFT"),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("TOPPADDING", (0, 0), (-1, -1), 4),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ]
                )
            )

            # Combine into two-column layout
            info_table_data = [[order_table, customer_table]]
            info_table = Table(info_table_data, colWidths=[120 * mm, 60 * mm])
            info_table.setStyle(
                TableStyle(
                    [
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 0),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                    ]
                )
            )
            story.append(info_table)
            story.append(Spacer(1, 8 * mm))

            # Order Lines Table
            lines = order_data.get("lines", [])
            if lines:
                # Header row
                data = [["Item", "Quantity", "Unit Price", "Total"]]

                for line in lines:
                    item_name = line.get("item_name", "N/A")
                    item_no = line.get("item_no", "")
                    quantity = str(line.get("quantity", "0"))
                    unit_price = f"{float(line.get('unit_price', 0)):,.2f}"
                    total_amount = f"{float(line.get('total_amount', 0)):,.2f}"

                    # Add item with item number if available
                    item_display = item_name
                    if item_no:
                        item_display = f"{item_name}<br/><font size=8>{item_no}</font>"

                    data.append(
                        [
                            Paragraph(item_display, styles["Normal"]),
                            quantity,
                            f"{format_currency(float(line.get('unit_price', 0)))}",
                            f"{format_currency(float(line.get('total_amount', 0)))}",
                        ]
                    )

                # Create table
                table = Table(data, colWidths=[80 * mm, 30 * mm, 35 * mm, 35 * mm])
                table.setStyle(
                    TableStyle(
                        [
                            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f0f3ff")),
                            ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#1f3fff")),
                            ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                            ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
                            ("ALIGN", (0, 1), (0, -1), "LEFT"),
                            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                            ("FONTSIZE", (0, 0), (-1, 0), 10),
                            ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                            ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ]
                    )
                )
                story.append(table)
                story.append(Spacer(1, 6 * mm))
            else:
                story.append(Paragraph("No items in this order", styles["Normal"]))
                story.append(Spacer(1, 6 * mm))

            # Total
            total_amount = float(order_data.get("total_amount", 0))
            total_data = [["Total Amount:", format_currency(total_amount)]]
            total_table = Table(total_data, colWidths=[115 * mm, 65 * mm])
            total_table.setStyle(
                TableStyle(
                    [
                        ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, -1), 12),
                        ("ALIGN", (0, 0), (0, 0), "RIGHT"),
                        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
                        ("TOPPADDING", (0, 0), (-1, -1), 6),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ]
                )
            )
            story.append(total_table)

            # Notes
            if order_data.get("notes"):
                story.append(Spacer(1, 6 * mm))
                story.append(Paragraph("<b>Notes:</b>", styles["Normal"]))
                story.append(Paragraph(order_data.get("notes"), styles["Normal"]))

            # Footer
            story.append(Spacer(1, 12 * mm))
            footer_text = f"Generated on {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}"
            story.append(Paragraph(footer_text, styles["Normal"]))

            # Build PDF
            doc.build(story)

            return response

        except Exception as e:
            import traceback

            traceback.print_exc()
            return Response(
                {"error": f"Failed to generate PDF: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=True, methods=["post"])
    def duplicate(self, request, pk=None):
        """Duplicate a sales order - creates a new order with same lines but new order number"""
        has_permission, source = request.user.check_object_permission(10003, "insert")
        if not has_permission:
            return Response(
                {
                    "error": "Insufficient permissions",
                    "detail": "You need insert permission to duplicate sales orders",
                    "reason": source,
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            original_order = self.get_object()
            with transaction.atomic():
                # Create new order with same header data but new order number
                new_order_data = {
                    "customer": original_order.customer,
                    "contact_person": original_order.contact_person,
                    "order_date": original_order.order_date,
                    "expected_delivery_date": original_order.expected_delivery_date,
                    "notes": original_order.notes,
                    "status": "Open",  # New order starts as Open
                }
                new_order = SalesOrder.objects.create(**new_order_data)

                # Copy all lines
                for line in original_order.lines.all():
                    SalesOrderLine.objects.create(
                        sales_order=new_order,
                        item=line.item,
                        description=line.description,
                        location_code=line.location_code,
                        quantity=line.quantity,
                        item_unit_of_measure=line.item_unit_of_measure,
                        unit_of_measure=line.unit_of_measure,
                        unit_price=line.unit_price,
                        global_dimension_1=line.global_dimension_1,
                    )

                # Recalculate totals
                new_order.recalculate_totals()

                serializer = self.get_serializer(new_order)
                return Response(serializer.data, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class SalesDashboardViewSet(viewsets.ViewSet):
    """ViewSet for Sales Dashboard Analytics"""

    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication, SessionAuthentication]

    def _get_dim1_id(self, request):
        """
        Resolve the effective Global Dimension 1 (branch) filter for dashboard endpoints.

        Priority:
        - Explicit query param: global_dimension_1_id (backward compatibility / power users)
        - X-Branch-Scope: all (org-wide; allowed for can_switch_branch users)
        - X-Branch-Id header (or fallback to request.user.global_dimension_1)
        """
        dim1_id = request.query_params.get("global_dimension_1_id")
        if dim1_id not in (None, ""):
            try:
                return int(dim1_id)
            except (TypeError, ValueError):
                return None

        branch_param = request.query_params.get("branch")
        if branch_param not in (None, ""):
            if str(branch_param).strip().lower() == "all":
                return None
            try:
                return int(branch_param)
            except (TypeError, ValueError):
                return None

        if branch_scope_is_all(request):
            return None

        branch = get_branch_for_request(request)
        return getattr(branch, "id", None)

    def list(self, request):
        """Get comprehensive sales dashboard data"""
        try:
            # Import models at the top
            from financials.models import GeneralLedgerEntry, G_LAccount
            from sales.models import SalesInvoiceLine
            from purchases.models import PurchaseInvoice, PurchaseInvoiceLine

            # Get date range and dimension filter from query params
            start_date = request.query_params.get("start_date")
            end_date = request.query_params.get("end_date")
            all_time = request.query_params.get("all_time") in ["true", "1", "yes"]
            dim1_id = self._get_dim1_id(request)

            # Default to current month if no dates provided
            if not start_date:
                start_date = timezone.now().replace(day=1).date()
            else:
                start_date = datetime.strptime(start_date, "%Y-%m-%d").date()

            if not end_date:
                end_date = timezone.now().date()
            else:
                end_date = datetime.strptime(end_date, "%Y-%m-%d").date()

            if all_time:
                earliest_date = (
                    SalesInvoice.objects.aggregate(Min("document_date"))[
                        "document_date__min"
                    ]
                    or start_date
                )
                start_date = earliest_date
                end_date = timezone.now().date()

            # Base querysets
            sales_queryset = SalesInvoice.objects.filter(
                document_date__range=[start_date, end_date], status="Posted"
            )
            if dim1_id is not None:
                sales_queryset = sales_queryset.filter(global_dimension_1_id=dim1_id)

            ledger_queryset = CustomerLedgerEntry.objects.filter(
                posting_date__range=[start_date, end_date]
            )
            if dim1_id is not None:
                ledger_queryset = ledger_queryset.filter(global_dimension_1_id=dim1_id)

            # 1. Sales Overview - Use G/L entries (same source as P&L) for accuracy
            gl_queryset = GeneralLedgerEntry.objects.filter(
                posting_date__range=[start_date, end_date]
            )
            if dim1_id is not None:
                gl_queryset = gl_queryset.filter(global_dimension_1_id=dim1_id)

            revenue_accounts = G_LAccount.objects.filter(
                income_balance="Income Statement",
                accountcategory="Income",
            )
            total_sales_amount = gl_queryset.filter(
                gl_account__in=revenue_accounts
            ).aggregate(amount=Sum(F("amount") * -1))["amount"] or Decimal("0")

            total_sales_count = sales_queryset.count()

            # Calculate average order value
            avg_order_value = (
                total_sales_amount / total_sales_count if total_sales_count > 0 else 0
            )

            sales_by_status = sales_queryset.values("status").annotate(
                count=Count("id")
            )

            # 2. Revenue Analytics - Calculate actual monthly sales amounts
            monthly_revenue = []

            # Get the last 12 months - simple calculation without external dependencies
            today = timezone.now().date()

            for i in range(12):
                # Calculate month start and end
                current_month = today.month - i
                current_year = today.year

                # Handle year rollover
                while current_month <= 0:
                    current_month += 12
                    current_year -= 1

                month_start = today.replace(
                    year=current_year, month=current_month, day=1
                )

                # Calculate month end
                if current_month == 12:
                    month_end = month_start.replace(
                        year=current_year + 1, month=1, day=1
                    ) - timedelta(days=1)
                else:
                    month_end = month_start.replace(
                        month=current_month + 1, day=1
                    ) - timedelta(days=1)

                month_gl_qs = GeneralLedgerEntry.objects.filter(
                    posting_date__range=[month_start, month_end],
                    gl_account__in=revenue_accounts,
                )
                if dim1_id is not None:
                    month_gl_qs = month_gl_qs.filter(global_dimension_1_id=dim1_id)
                month_sales = abs(
                    float(
                        month_gl_qs.aggregate(amount=Sum(F("amount") * -1))["amount"]
                        or 0
                    )
                )

                monthly_revenue.append(
                    {
                        "month": month_start,
                        "amount": float(month_sales),
                        "count": sales_queryset.filter(
                            document_date__range=[month_start, month_end]
                        ).count(),
                    }
                )

            # Reverse to show oldest to newest (left to right)
            monthly_revenue.reverse()

            # 3. Top Customers
            top_customers = (
                sales_queryset.values("customer__name", "customer__no")
                .annotate(order_count=Count("id"))
                .order_by("-order_count")[:10]
            )

            # 4. Accounts Receivable
            # Calculate outstanding receivables manually since remaining_amount is now a property
            outstanding_filter = {"open": True, "document_type": "Invoice"}
            if dim1_id is not None:
                outstanding_filter["global_dimension_1_id"] = dim1_id
            outstanding_entries = CustomerLedgerEntry.objects.filter(
                **outstanding_filter
            )
            total_outstanding = 0
            for entry in outstanding_entries:
                total_outstanding += entry.remaining_amount

            outstanding_receivables = {
                "total_outstanding": total_outstanding,
                "count": outstanding_entries.count(),
            }

            # Aging analysis
            today = timezone.now().date()
            aging_base = {"open": True, "document_type": "Invoice"}
            if dim1_id is not None:
                aging_base["global_dimension_1_id"] = dim1_id
            current_entries = CustomerLedgerEntry.objects.filter(
                **{**aging_base, "due_date__gte": today}
            )
            overdue_30_entries = CustomerLedgerEntry.objects.filter(
                **{
                    **aging_base,
                    "due_date__lt": today,
                    "due_date__gte": today - timedelta(days=30),
                }
            )
            overdue_60_entries = CustomerLedgerEntry.objects.filter(
                **{
                    **aging_base,
                    "due_date__lt": today - timedelta(days=30),
                    "due_date__gte": today - timedelta(days=60),
                }
            )
            overdue_90_entries = CustomerLedgerEntry.objects.filter(
                **{
                    **aging_base,
                    "due_date__lt": today - timedelta(days=60),
                }
            )

            aging_analysis = {
                "current": sum(entry.remaining_amount for entry in current_entries),
                "overdue_30": sum(
                    entry.remaining_amount for entry in overdue_30_entries
                ),
                "overdue_60": sum(
                    entry.remaining_amount for entry in overdue_60_entries
                ),
                "overdue_90": sum(
                    entry.remaining_amount for entry in overdue_90_entries
                ),
            }

            # 5. Top Selling Items
            # Get limit from query params, default to 10 for dashboard
            top_items_limit = int(request.query_params.get("top_items_limit", 10))
            top_items_filter = {
                "sales_invoice__document_date__range": [start_date, end_date]
            }
            if dim1_id is not None:
                top_items_filter["sales_invoice__global_dimension_1_id"] = dim1_id
            top_items = (
                SalesInvoiceLine.objects.filter(**top_items_filter)
                .select_related("item")
                .values("item__item_name", "item__no", "item_id")
                .annotate(
                    total_quantity=Sum("quantity"),
                    order_count=Count("sales_invoice", distinct=True),
                )
                .order_by("-total_quantity")[:top_items_limit]
            )

            # Pre-fetch all item images to avoid N+1 queries
            from items.models import Item, ItemImages
            from items.serializers import ImageSerializers

            item_nos = [item["item__no"] for item in top_items]
            items_with_images = Item.objects.filter(no__in=item_nos).prefetch_related(
                "itemimages_set"
            )

            # Create a dictionary for quick lookup
            item_images_map = {}
            for item_obj in items_with_images:
                first_image = item_obj.itemimages_set.first()
                if first_image and first_image.url:
                    # Use the serializer to get the URL in the same format as the API
                    serializer = ImageSerializers(
                        first_image, context={"request": request}
                    )
                    image_data = serializer.data
                    # The serializer returns the URL as a string when serialized
                    image_url = image_data.get("url")
                    if image_url:
                        # Always build absolute URL to ensure it's accessible from frontend
                        if not image_url.startswith("http"):
                            image_url = request.build_absolute_uri(image_url)
                        item_images_map[item_obj.no] = image_url
                    else:
                        item_images_map[item_obj.no] = None
                else:
                    item_images_map[item_obj.no] = None

            # Calculate total amounts for top items manually
            top_items_with_amounts = []
            for item in top_items:
                # Get all lines for this item in the period
                item_lines_filter = {
                    "sales_invoice__document_date__range": [start_date, end_date],
                    "item__no": item["item__no"],
                }
                if dim1_id is not None:
                    item_lines_filter["sales_invoice__global_dimension_1_id"] = dim1_id
                item_lines = SalesInvoiceLine.objects.filter(**item_lines_filter)

                # Calculate total amount for this item
                total_amount = 0
                for line in item_lines:
                    total_amount += line.unit_price * line.quantity

                # Get item image URL from pre-fetched map
                image_url = item_images_map.get(item["item__no"])

                top_items_with_amounts.append(
                    {
                        "item_name": item["item__item_name"],
                        "item_no": item["item__no"],
                        "total_quantity": item["total_quantity"],
                        "total_amount": total_amount,
                        "order_count": item["order_count"],
                        "image_url": image_url,
                    }
                )

            # Sort by total amount
            top_items_with_amounts.sort(key=lambda x: x["total_amount"], reverse=True)

            # 6. Sales by Location/Dimension
            sales_by_loc_filter = {
                "sales_invoice__document_date__range": [start_date, end_date]
            }
            if dim1_id is not None:
                sales_by_loc_filter["sales_invoice__global_dimension_1_id"] = dim1_id
            sales_by_location_raw = (
                SalesInvoiceLine.objects.filter(**sales_by_loc_filter)
                .values("location_code__description", "location_code__code")
                .annotate(total_quantity=Sum("quantity"))
                .order_by("-total_quantity")
            )

            # Calculate total amounts for sales by location manually
            sales_by_location = []
            for location in sales_by_location_raw:
                # Get all lines for this location in the period
                loc_lines_filter = {
                    "sales_invoice__document_date__range": [start_date, end_date],
                    "location_code__code": location["location_code__code"],
                }
                if dim1_id is not None:
                    loc_lines_filter["sales_invoice__global_dimension_1_id"] = dim1_id
                location_lines = SalesInvoiceLine.objects.filter(**loc_lines_filter)

                # Calculate total amount for this location
                total_amount = 0
                for line in location_lines:
                    total_amount += line.unit_price * line.quantity

                sales_by_location.append(
                    {
                        "location_name": location["location_code__description"],
                        "location_code": location["location_code__code"],
                        "total_amount": total_amount,
                        "total_quantity": location["total_quantity"],
                    }
                )

            # Sort by total amount
            sales_by_location.sort(key=lambda x: x["total_amount"], reverse=True)

            # 7. Payment Method Analysis
            payment_method_analysis = (
                ledger_queryset.values(
                    "payment_method__description", "payment_method__code"
                )
                .annotate(total_amount=Sum("amount"), count=Count("id"))
                .order_by("-total_amount")
            )

            # 8. Recent Activity
            recent_sales = sales_queryset.select_related("customer").order_by(
                "-created_at"
            )[:5]
            recent_sales_data = []
            for sale in recent_sales:
                # Calculate total amount manually
                total_amount = 0
                for line in sale.lines.all():
                    total_amount += line.unit_price * line.quantity

                recent_sales_data.append(
                    {
                        "id": sale.id,
                        "invoice_no": sale.invoice_no,
                        "customer_name": sale.customer.name,
                        "document_date": sale.document_date,
                        "status": sale.status,
                        "total_amount": total_amount,
                    }
                )

            # 9. Growth Metrics - Compare with previous period
            previous_period_start = start_date - timedelta(
                days=(end_date - start_date).days
            )

            prev_gl_queryset = GeneralLedgerEntry.objects.filter(
                posting_date__range=[
                    previous_period_start,
                    start_date - timedelta(days=1),
                ]
            )
            if dim1_id is not None:
                prev_gl_queryset = prev_gl_queryset.filter(
                    global_dimension_1_id=dim1_id
                )
            previous_period_sales = (
                prev_gl_queryset.filter(gl_account__in=revenue_accounts).aggregate(
                    amount=Sum(F("amount") * -1)
                )["amount"]
                or 0
            )

            # Use float for both to avoid Decimal/float mix (GeneralLedgerEntry.amount is FloatField)
            current_sales = float(total_sales_amount or 0)
            prev_sales = float(previous_period_sales or 0)

            if prev_sales > 0:
                growth_percentage = ((current_sales - prev_sales) / prev_sales) * 100
            else:
                growth_percentage = 0

            return Response(
                {
                    "period": {"start_date": start_date, "end_date": end_date},
                    "sales_overview": {
                        "total_amount": float(total_sales_amount),
                        "total_count": total_sales_count,
                        "avg_order_value": float(avg_order_value),
                        "growth_percentage": round(growth_percentage, 2),
                        "by_status": list(sales_by_status),
                    },
                    "revenue_analytics": {
                        "monthly_revenue": monthly_revenue,
                        "top_customers": list(top_customers),
                    },
                    "accounts_receivable": {
                        "total_outstanding": float(
                            outstanding_receivables["total_outstanding"] or 0
                        ),
                        "outstanding_count": outstanding_receivables["count"],
                        "aging_analysis": aging_analysis,
                    },
                    "inventory_analytics": {
                        "top_items": list(top_items_with_amounts),
                        "sales_by_location": list(sales_by_location),
                    },
                    "payment_analysis": {
                        "by_payment_method": list(payment_method_analysis)
                    },
                    "recent_activity": {"recent_sales": recent_sales_data},
                }
            )

        except Exception as e:
            return Response(
                {"detail": f"Error generating dashboard data: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=False, methods=["get"])
    def trends(self, request):
        """Get sales trends over time"""
        try:
            period = request.query_params.get("period", "month")  # month, quarter, year
            limit = int(request.query_params.get("limit", 12))

            if period == "month":
                trunc_func = TruncMonth
            elif period == "quarter":
                trunc_func = TruncQuarter
            else:
                trunc_func = TruncYear

            trends = (
                SalesInvoice.objects.annotate(period=trunc_func("document_date"))
                .values("period")
                .annotate(
                    revenue=Sum("lines__total_amount"),
                    count=Count("id"),
                    avg_order_value=Avg("lines__total_amount"),
                )
                .order_by("period")[:limit]
            )

            return Response({"period": period, "trends": list(trends)})

        except Exception as e:
            return Response(
                {"detail": f"Error generating trends: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=False, methods=["get"])
    def customer_performance(self, request):
        """Get detailed customer performance metrics"""
        try:
            start_date = request.query_params.get("start_date")
            end_date = request.query_params.get("end_date")

            if start_date:
                start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
            if end_date:
                end_date = datetime.strptime(end_date, "%Y-%m-%d").date()

            queryset = SalesInvoice.objects.all()
            if start_date and end_date:
                queryset = queryset.filter(document_date__range=[start_date, end_date])

            customer_performance = (
                queryset.values("customer__name", "customer__no", "customer__city")
                .annotate(
                    order_count=Count("id"),
                    last_order_date=Max("document_date"),
                    first_order_date=Min("document_date"),
                )
                .order_by("-order_count")
            )

            # Calculate total sales for each customer manually
            customer_performance_with_sales = []
            for customer in customer_performance:
                customer_sales = queryset.filter(customer__no=customer["customer__no"])

                # Calculate total sales manually
                total_sales = 0
                total_amount_sum = 0
                for sale in customer_sales:
                    for line in sale.lines.all():
                        total_sales += line.unit_price * line.quantity
                        total_amount_sum += line.unit_price * line.quantity

                avg_order_value = (
                    total_amount_sum / customer["order_count"]
                    if customer["order_count"] > 0
                    else 0
                )

                customer_performance_with_sales.append(
                    {
                        "customer_name": customer["customer__name"],
                        "customer_no": customer["customer__no"],
                        "customer_city": customer["customer__city"],
                        "total_sales": total_sales,
                        "order_count": customer["order_count"],
                        "avg_order_value": avg_order_value,
                        "last_order_date": customer["last_order_date"],
                        "first_order_date": customer["first_order_date"],
                    }
                )

            # Sort by total sales
            customer_performance_with_sales.sort(
                key=lambda x: x["total_sales"], reverse=True
            )

            return Response(
                {"customer_performance": list(customer_performance_with_sales)}
            )

        except Exception as e:
            return Response(
                {"detail": f"Error generating customer performance: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=False, methods=["get"])
    def inventory_analytics(self, request):
        """Get inventory sales analytics"""
        try:
            start_date = request.query_params.get("start_date")
            end_date = request.query_params.get("end_date")

            if start_date:
                start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
            if end_date:
                end_date = datetime.strptime(end_date, "%Y-%m-%d").date()

            inventory_analytics = (
                SalesInvoiceLine.objects.filter(
                    sales_invoice__document_date__range=[start_date, end_date]
                )
                .select_related("item")
                .values("item__item_name", "item__no", "item__description", "item_id")
                .annotate(
                    total_quantity=Sum("quantity"),
                    order_count=Count("sales_invoice", distinct=True),
                )
                .order_by("-total_quantity")[:10]
            )

            # Pre-fetch all item images to avoid N+1 queries
            from items.models import Item, ItemImages
            from items.serializers import ImageSerializers

            item_nos = [item["item__no"] for item in inventory_analytics]
            items_with_images = Item.objects.filter(no__in=item_nos).prefetch_related(
                "itemimages_set"
            )

            # Create a dictionary for quick lookup
            item_images_map = {}
            for item_obj in items_with_images:
                first_image = item_obj.itemimages_set.first()
                if first_image and first_image.url:
                    # Use the serializer to get the URL in the same format as the API
                    serializer = ImageSerializers(
                        first_image, context={"request": request}
                    )
                    image_data = serializer.data
                    # The serializer returns the URL as a string when serialized
                    image_url = image_data.get("url")
                    if image_url:
                        # Always build absolute URL to ensure it's accessible from frontend
                        if not image_url.startswith("http"):
                            image_url = request.build_absolute_uri(image_url)
                        item_images_map[item_obj.no] = image_url
                    else:
                        item_images_map[item_obj.no] = None
                else:
                    item_images_map[item_obj.no] = None

            # Calculate total amounts for inventory analytics manually
            inventory_analytics_with_amounts = []
            for item in inventory_analytics:
                # Get all lines for this item in the period
                item_lines = SalesInvoiceLine.objects.filter(
                    sales_invoice__document_date__range=[start_date, end_date],
                    item__no=item["item__no"],
                )

                # Calculate total amount for this item
                total_amount = 0
                for line in item_lines:
                    total_amount += line.unit_price * line.quantity

                # Get item image URL from pre-fetched map
                image_url = item_images_map.get(item["item__no"])

                inventory_analytics_with_amounts.append(
                    {
                        "item_name": item["item__item_name"],
                        "item_no": item["item__no"],
                        "item_description": item["item__description"],
                        "total_quantity": item["total_quantity"],
                        "total_amount": total_amount,
                        "order_count": item["order_count"],
                        "image_url": image_url,
                    }
                )

            # Sort by total amount
            inventory_analytics_with_amounts.sort(
                key=lambda x: x["total_amount"], reverse=True
            )

            # Sales by category
            sales_by_category = (
                SalesInvoiceLine.objects.filter(
                    sales_invoice__document_date__range=[start_date, end_date]
                )
                .values("item__item_category__description")
                .annotate(
                    total_quantity=Sum("quantity"),
                )
                .order_by("-total_quantity")
            )

            # Calculate total amounts for sales by category manually
            sales_by_category_with_amounts = []
            for category in sales_by_category:
                # Get all lines for this category in the period
                category_lines = SalesInvoiceLine.objects.filter(
                    sales_invoice__document_date__range=[start_date, end_date],
                    item__item_category__description=category[
                        "item__item_category__description"
                    ],
                )

                # Calculate total amount for this category
                total_amount = 0
                for line in category_lines:
                    total_amount += line.unit_price * line.quantity

                sales_by_category_with_amounts.append(
                    {
                        "category_name": category["item__item_category__description"],
                        "total_quantity": category["total_quantity"],
                        "total_amount": total_amount,
                    }
                )

            # Sort by total amount
            sales_by_category_with_amounts.sort(
                key=lambda x: x["total_amount"], reverse=True
            )

            # Sales by location
            sales_by_location = (
                SalesInvoiceLine.objects.filter(
                    sales_invoice__document_date__range=[start_date, end_date]
                )
                .values("location_code__description", "location_code__code")
                .annotate(
                    total_quantity=Sum("quantity"),
                )
                .order_by("-total_quantity")
            )

            # Calculate total amounts for sales by location manually
            sales_by_location_with_amounts = []
            for location in sales_by_location:
                # Get all lines for this location in the period
                location_lines = SalesInvoiceLine.objects.filter(
                    sales_invoice__document_date__range=[start_date, end_date],
                    location_code__code=location["location_code__code"],
                )

                # Calculate total amount for this location
                total_amount = 0
                for line in location_lines:
                    total_amount += line.unit_price * line.quantity

                sales_by_location_with_amounts.append(
                    {
                        "location_name": location["location_code__description"],
                        "location_code": location["location_code__code"],
                        "total_quantity": location["total_quantity"],
                        "total_amount": total_amount,
                    }
                )

            # Sort by total amount
            sales_by_location_with_amounts.sort(
                key=lambda x: x["total_amount"], reverse=True
            )

            return Response(
                {
                    "top_items": list(inventory_analytics_with_amounts),
                    "sales_by_category": list(sales_by_category_with_amounts),
                    "sales_by_location": list(sales_by_location_with_amounts),
                }
            )

        except Exception as e:
            return Response(
                {"detail": f"Error generating inventory analytics: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=False, methods=["get"])
    def kpi_metrics(self, request):
        """Get key performance indicators"""
        try:
            # Get current month data
            current_month_start = timezone.now().replace(day=1).date()
            current_month_end = timezone.now().date()

            # Previous month for comparison
            prev_month_start = (current_month_start - timedelta(days=1)).replace(day=1)
            prev_month_end = current_month_start - timedelta(days=1)

            # Current month sales
            current_month_sales = SalesInvoice.objects.filter(
                document_date__range=[current_month_start, current_month_end]
            ).aggregate(
                total_amount=Sum("lines__total_amount"), total_count=Count("id")
            )

            # Previous month sales
            prev_month_sales = SalesInvoice.objects.filter(
                document_date__range=[prev_month_start, prev_month_end]
            ).aggregate(
                total_amount=Sum("lines__total_amount"), total_count=Count("id")
            )

            # Calculate growth rates
            revenue_growth = 0
            order_growth = 0

            if (
                prev_month_sales["total_amount"]
                and prev_month_sales["total_amount"] > 0
            ):
                revenue_growth = (
                    (
                        (current_month_sales["total_amount"] or 0)
                        - prev_month_sales["total_amount"]
                    )
                    / prev_month_sales["total_amount"]
                    * 100
                )

            if prev_month_sales["total_count"] and prev_month_sales["total_count"] > 0:
                order_growth = (
                    (
                        (current_month_sales["total_count"] or 0)
                        - prev_month_sales["total_count"]
                    )
                    / prev_month_sales["total_count"]
                    * 100
                )

            # Days Sales Outstanding (DSO)
            dso_entries = CustomerLedgerEntry.objects.filter(
                open=True, document_type="Invoice"
            )
            total_receivables = sum(entry.remaining_amount for entry in dso_entries)

            avg_daily_sales = (
                current_month_sales["total_amount"] or 0
            ) / 30  # Assuming 30 days
            dso = total_receivables / avg_daily_sales if avg_daily_sales > 0 else 0

            # Customer metrics
            total_customers = Customer.objects.count()
            active_customers = (
                SalesInvoice.objects.filter(
                    document_date__range=[current_month_start, current_month_end]
                )
                .values("customer")
                .distinct()
                .count()
            )

            return Response(
                {
                    "current_month": {
                        "revenue": float(current_month_sales["total_amount"] or 0),
                        "orders": current_month_sales["total_count"] or 0,
                        "avg_order_value": float(
                            (current_month_sales["total_amount"] or 0)
                            / (current_month_sales["total_count"] or 1)
                        ),
                    },
                    "growth_rates": {
                        "revenue_growth": round(revenue_growth, 2),
                        "order_growth": round(order_growth, 2),
                    },
                    "financial_metrics": {
                        "dso": round(dso, 1),
                        "total_receivables": float(total_receivables),
                    },
                    "customer_metrics": {
                        "total_customers": total_customers,
                        "active_customers": active_customers,
                        "customer_activity_rate": round(
                            (
                                (active_customers / total_customers * 100)
                                if total_customers > 0
                                else 0
                            ),
                            2,
                        ),
                    },
                }
            )

        except Exception as e:
            return Response(
                {"detail": f"Error generating KPI metrics: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=False, methods=["get"])
    def financial_dashboard(self, request):
        """Get financial dashboard data from General Ledger"""
        try:
            # Get date range and dimension filter from query params
            start_date = request.query_params.get("start_date")
            end_date = request.query_params.get("end_date")
            all_time = request.query_params.get("all_time") in ["true", "1", "yes"]
            dim1_id = self._get_dim1_id(request)

            # Default to current month if no dates provided
            if not start_date:
                start_date = timezone.now().replace(day=1).date()
            else:
                start_date = datetime.strptime(start_date, "%Y-%m-%d").date()

            if not end_date:
                end_date = timezone.now().date()
            else:
                end_date = datetime.strptime(end_date, "%Y-%m-%d").date()

            if all_time:
                earliest_entry_date = (
                    GeneralLedgerEntry.objects.aggregate(Min("posting_date"))[
                        "posting_date__min"
                    ]
                    or start_date
                )
                start_date = earliest_entry_date
                end_date = timezone.now().date()

            # Base queryset for GL entries
            gl_queryset = GeneralLedgerEntry.objects.filter(
                posting_date__range=[start_date, end_date]
            )
            if dim1_id is not None:
                gl_queryset = gl_queryset.filter(global_dimension_1_id=dim1_id)

            # 1. Revenue Analysis (all Income Statement income accounts, including services)
            revenue_accounts = G_LAccount.objects.filter(
                income_balance="Income Statement",
                accountcategory="Income",
            )

            revenue_data = (
                gl_queryset.filter(gl_account__in=revenue_accounts)
                .values("gl_account__name", "gl_account__no")
                .annotate(total_amount=Sum("amount"), transaction_count=Count("id"))
                .order_by("-total_amount")
            )

            # 2. Cost of Goods Sold Analysis
            cogs_accounts = G_LAccount.objects.filter(
                income_balance="Income Statement", accountcategory="Cost of Goods Sold"
            )

            cogs_data = (
                gl_queryset.filter(gl_account__in=cogs_accounts)
                .values("gl_account__name", "gl_account__no")
                .annotate(total_amount=Sum("amount"), transaction_count=Count("id"))
                .order_by("-total_amount")
            )

            # 3. Operating Expenses Analysis
            expense_accounts = G_LAccount.objects.filter(
                income_balance="Income Statement", accountcategory="Expense"
            )

            expense_data = (
                gl_queryset.filter(gl_account__in=expense_accounts)
                .values("gl_account__name", "gl_account__no")
                .annotate(total_amount=Sum("amount"), transaction_count=Count("id"))
                .order_by("-total_amount")
            )

            # 4. Balance Sheet Analysis
            # Assets
            asset_accounts = G_LAccount.objects.filter(
                income_balance="Balance Sheet", accountcategory="Assets"
            )

            asset_balances = (
                gl_queryset.filter(gl_account__in=asset_accounts)
                .values("gl_account__name", "gl_account__no")
                .annotate(total_amount=Sum("amount"), transaction_count=Count("id"))
                .order_by("-total_amount")
            )

            # Liabilities
            liability_accounts = G_LAccount.objects.filter(
                income_balance="Balance Sheet", accountcategory="Liabilities"
            )

            liability_balances = (
                gl_queryset.filter(gl_account__in=liability_accounts)
                .values("gl_account__name", "gl_account__no")
                .annotate(total_amount=Sum("amount"), transaction_count=Count("id"))
                .order_by("-total_amount")
            )

            # 5. Cash Flow Analysis
            cash_accounts = G_LAccount.objects.filter(name__icontains="Cash")

            cash_flow = (
                gl_queryset.filter(gl_account__in=cash_accounts)
                .values("gl_account__name", "gl_account__no")
                .annotate(total_amount=Sum("amount"), transaction_count=Count("id"))
                .order_by("-total_amount")
            )

            # 6. VAT Analysis
            vat_accounts = G_LAccount.objects.filter(name__icontains="VAT")

            vat_data = (
                gl_queryset.filter(gl_account__in=vat_accounts)
                .values("gl_account__name", "gl_account__no")
                .annotate(total_amount=Sum("amount"), transaction_count=Count("id"))
                .order_by("-total_amount")
            )

            # 7. Monthly Financial Trends
            monthly_financials = (
                gl_queryset.annotate(month=TruncMonth("posting_date"))
                .values("month")
                .annotate(
                    total_debits=Sum("amount", filter=Q(amount__gt=0)),
                    total_credits=Sum("amount", filter=Q(amount__lt=0)),
                    transaction_count=Count("id"),
                )
                .order_by("month")
            )

            # 8. Account Category Summary
            category_summary = (
                gl_queryset.values("gl_account__accountcategory")
                .annotate(total_amount=Sum("amount"), transaction_count=Count("id"))
                .order_by("-total_amount")
            )

            # 9. Top GL Accounts by Transaction Volume
            top_accounts = (
                gl_queryset.values(
                    "gl_account__name", "gl_account__no", "gl_account__accountcategory"
                )
                .annotate(total_amount=Sum("amount"), transaction_count=Count("id"))
                .order_by("-transaction_count")[:15]
            )

            # 10. Financial Ratios and KPIs
            # Use absolute values to ensure correct calculation regardless of debit/credit convention
            total_revenue = abs(sum(item["total_amount"] for item in revenue_data))
            total_cogs = abs(sum(item["total_amount"] for item in cogs_data))
            total_expenses = abs(sum(item["total_amount"] for item in expense_data))

            gross_profit = total_revenue - total_cogs
            net_income = gross_profit - total_expenses

            # Return actual signed values (losses as negative) to match P&L behavior
            gross_margin = (
                (gross_profit / total_revenue * 100) if total_revenue > 0 else 0
            )
            net_margin = (net_income / total_revenue * 100) if total_revenue > 0 else 0

            return Response(
                {
                    "period": {"start_date": start_date, "end_date": end_date},
                    "income_statement": {
                        "revenue": {
                            "total": abs(float(total_revenue)),
                            "accounts": list(revenue_data),
                        },
                        "cost_of_goods_sold": {
                            "total": float(total_cogs),
                            "accounts": list(cogs_data),
                        },
                        "operating_expenses": {
                            "total": float(total_expenses),
                            "accounts": list(expense_data),
                        },
                        "total_expenses": float(
                            total_expenses
                        ),  # Alias for frontend compatibility
                        "gross_profit": float(gross_profit),
                        "net_income": float(net_income),
                        "gross_margin": round(gross_margin, 2),
                        "net_margin": round(net_margin, 2),
                    },
                    "balance_sheet": {
                        "assets": list(asset_balances),
                        "liabilities": list(liability_balances),
                    },
                    "cash_flow": {"cash_accounts": list(cash_flow)},
                    "vat_analysis": {"vat_accounts": list(vat_data)},
                    "trends": {"monthly_financials": list(monthly_financials)},
                    "summary": {
                        "category_summary": list(category_summary),
                        "top_accounts": list(top_accounts),
                    },
                }
            )

        except Exception as e:
            return Response(
                {"detail": f"Error generating financial dashboard: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=False, methods=["get"])
    def profit_loss_statement(self, request):
        """Get detailed Profit & Loss statement"""
        try:
            start_date = request.query_params.get("start_date")
            end_date = request.query_params.get("end_date")

            if not start_date:
                start_date = timezone.now().replace(day=1).date()
            else:
                start_date = datetime.strptime(start_date, "%Y-%m-%d").date()

            if not end_date:
                end_date = timezone.now().date()
            else:
                end_date = datetime.strptime(end_date, "%Y-%m-%d").date()

            dim1_id = self._get_dim1_id(request)
            gl_queryset = GeneralLedgerEntry.objects.filter(
                posting_date__range=[start_date, end_date]
            )
            if dim1_id is not None:
                gl_queryset = gl_queryset.filter(global_dimension_1_id=dim1_id)

            # Revenue Section
            revenue_accounts = G_LAccount.objects.filter(
                income_balance="Income Statement", accountcategory="Income"
            )

            revenue_section = (
                gl_queryset.filter(gl_account__in=revenue_accounts)
                .values("gl_account__name", "gl_account__no", "gl_account__indentation")
                .annotate(amount=Sum(F("amount") * -1))
                .order_by("gl_account__indentation", "gl_account__no")
            )

            # Cost of Goods Sold Section
            cogs_accounts = G_LAccount.objects.filter(
                income_balance="Income Statement", accountcategory="Cost of Goods Sold"
            )

            cogs_section = (
                gl_queryset.filter(gl_account__in=cogs_accounts)
                .values("gl_account__name", "gl_account__no", "gl_account__indentation")
                .annotate(amount=Sum("amount"))
                .order_by("gl_account__indentation", "gl_account__no")
            )

            # Operating Expenses Section
            expense_accounts = G_LAccount.objects.filter(
                income_balance="Income Statement", accountcategory="Expense"
            )

            expense_section = (
                gl_queryset.filter(gl_account__in=expense_accounts)
                .values("gl_account__name", "gl_account__no", "gl_account__indentation")
                .annotate(amount=Sum("amount"))
                .order_by("gl_account__indentation", "gl_account__no")
            )

            # Calculate totals
            total_revenue = sum(item["amount"] for item in revenue_section)
            total_cogs = sum(item["amount"] for item in cogs_section)
            total_expenses = sum(item["amount"] for item in expense_section)

            gross_profit = total_revenue - total_cogs
            net_income = gross_profit - total_expenses

            return Response(
                {
                    "period": {"start_date": start_date, "end_date": end_date},
                    "revenue": {
                        "total": float(total_revenue),
                        "accounts": list(revenue_section),
                    },
                    "cost_of_goods_sold": {
                        "total": float(total_cogs),
                        "accounts": list(cogs_section),
                    },
                    "gross_profit": float(gross_profit),
                    "operating_expenses": {
                        "total": float(total_expenses),
                        "accounts": list(expense_section),
                    },
                    "net_income": float(net_income),
                }
            )

        except Exception as e:
            return Response(
                {"detail": f"Error generating P&L statement: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=False, methods=["get"])
    def balance_sheet_report(self, request):
        """Get Balance Sheet report"""
        try:
            as_of_date = request.query_params.get("as_of_date")

            if not as_of_date:
                as_of_date = timezone.now().date()
            else:
                as_of_date = datetime.strptime(as_of_date, "%Y-%m-%d").date()

            dim1_id = self._get_dim1_id(request)
            base_qs = GeneralLedgerEntry.objects.all()
            if dim1_id is not None:
                base_qs = base_qs.filter(global_dimension_1_id=dim1_id)
            data = BalanceSheetService(queryset=base_qs).generate(as_of_date)
            return Response(data)

        except Exception as e:
            return Response(
                {"detail": f"Error generating balance sheet: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=False, methods=["get"])
    def cash_flow_statement(self, request):
        """Get Cash Flow statement"""
        try:
            start_date = request.query_params.get("start_date")
            end_date = request.query_params.get("end_date")

            if not start_date:
                start_date = timezone.now().replace(day=1).date()
            else:
                start_date = datetime.strptime(start_date, "%Y-%m-%d").date()

            if not end_date:
                end_date = timezone.now().date()
            else:
                end_date = datetime.strptime(end_date, "%Y-%m-%d").date()

            gl_queryset = GeneralLedgerEntry.objects.filter(
                posting_date__range=[start_date, end_date]
            )

            # Operating Activities - Cash accounts
            cash_accounts = G_LAccount.objects.filter(name__icontains="Cash")

            operating_cash = (
                gl_queryset.filter(gl_account__in=cash_accounts)
                .values("gl_account__name", "gl_account__no")
                .annotate(net_change=Sum("amount"))
                .order_by("-net_change")
            )

            # Investing Activities - Fixed Assets
            fixed_asset_accounts = G_LAccount.objects.filter(
                name__icontains="Fixed Assets"
            )

            investing_cash = (
                gl_queryset.filter(gl_account__in=fixed_asset_accounts)
                .values("gl_account__name", "gl_account__no")
                .annotate(net_change=Sum("amount"))
                .order_by("-net_change")
            )

            # Financing Activities - Loans and Equity
            financing_accounts = G_LAccount.objects.filter(
                Q(name__icontains="Loan")
                | Q(name__icontains="Capital")
                | Q(name__icontains="Equity")
            )

            financing_cash = (
                gl_queryset.filter(gl_account__in=financing_accounts)
                .values("gl_account__name", "gl_account__no")
                .annotate(net_change=Sum("amount"))
                .order_by("-net_change")
            )

            # Calculate totals
            total_operating = sum(item["net_change"] for item in operating_cash)
            total_investing = sum(item["net_change"] for item in investing_cash)
            total_financing = sum(item["net_change"] for item in financing_cash)

            net_cash_change = total_operating + total_investing + total_financing

            return Response(
                {
                    "period": {"start_date": start_date, "end_date": end_date},
                    "operating_activities": {
                        "total": float(total_operating),
                        "accounts": list(operating_cash),
                    },
                    "investing_activities": {
                        "total": float(total_investing),
                        "accounts": list(investing_cash),
                    },
                    "financing_activities": {
                        "total": float(total_financing),
                        "accounts": list(financing_cash),
                    },
                    "net_cash_change": float(net_cash_change),
                }
            )

        except Exception as e:
            return Response(
                {"detail": f"Error generating cash flow statement: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=False, methods=["get"])
    def account_analysis(self, request):
        """Get detailed analysis for specific GL accounts"""
        try:
            account_no = request.query_params.get("account_no")
            start_date = request.query_params.get("start_date")
            end_date = request.query_params.get("end_date")

            if not account_no:
                return Response(
                    {"detail": "Account number is required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if not start_date:
                start_date = timezone.now().replace(day=1).date()
            else:
                start_date = datetime.strptime(start_date, "%Y-%m-%d").date()

            if not end_date:
                end_date = timezone.now().date()
            else:
                end_date = datetime.strptime(end_date, "%Y-%m-%d").date()

            # Get account details
            try:
                account = G_LAccount.objects.get(no=account_no)
            except G_LAccount.DoesNotExist:
                return Response(
                    {"detail": "Account not found"}, status=status.HTTP_404_NOT_FOUND
                )

            # Get transactions for this account
            transactions = GeneralLedgerEntry.objects.filter(
                gl_account=account, posting_date__range=[start_date, end_date]
            ).order_by("-posting_date")

            # Monthly breakdown
            monthly_activity = (
                transactions.annotate(month=TruncMonth("posting_date"))
                .values("month")
                .annotate(
                    total_amount=Sum("amount"),
                    transaction_count=Count("id"),
                    avg_amount=Avg("amount"),
                )
                .order_by("month")
            )

            # Transaction details
            transaction_details = transactions.values(
                "posting_date", "document_no", "description", "amount", "document_type"
            )[
                :50
            ]  # Limit to last 50 transactions

            # Summary statistics
            summary = transactions.aggregate(
                total_debits=Sum("amount", filter=Q(amount__gt=0)),
                total_credits=Sum("amount", filter=Q(amount__lt=0)),
                transaction_count=Count("id"),
                avg_amount=Avg("amount"),
            )

            return Response(
                {
                    "account_info": {
                        "no": account.no,
                        "name": account.name,
                        "category": account.accountcategory,
                        "type": account.accounttype,
                        "income_balance": account.income_balance,
                    },
                    "period": {"start_date": start_date, "end_date": end_date},
                    "summary": {
                        "total_debits": float(summary["total_debits"] or 0),
                        "total_credits": float(summary["total_credits"] or 0),
                        "transaction_count": summary["transaction_count"],
                        "avg_amount": float(summary["avg_amount"] or 0),
                    },
                    "monthly_activity": list(monthly_activity),
                    "recent_transactions": list(transaction_details),
                }
            )

        except Exception as e:
            return Response(
                {"detail": f"Error generating account analysis: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=False, methods=["get"])
    def top_sales_people(self, request):
        """Get top performing sales people based on sales data"""
        try:
            # Get date range and dimension filter from query params
            start_date = request.query_params.get("start_date")
            end_date = request.query_params.get("end_date")
            dim1_id = self._get_dim1_id(request)

            # Default to current month if no dates provided
            if not start_date:
                start_date = timezone.now().replace(day=1).date()
            else:
                start_date = datetime.strptime(start_date, "%Y-%m-%d").date()

            if not end_date:
                end_date = timezone.now().date()
            else:
                end_date = datetime.strptime(end_date, "%Y-%m-%d").date()

            # Get top sales people based on CustomerLedgerEntry data
            # This includes both sales invoices and payments
            top_sales_filter = {
                "posting_date__range": [start_date, end_date],
                "document_type__in": ["Invoice", "Payment"],
                "user__isnull": False,
            }
            if dim1_id is not None:
                top_sales_filter["global_dimension_1_id"] = dim1_id
            top_sales_people = (
                CustomerLedgerEntry.objects.filter(**top_sales_filter)
                .values(
                    "user__id",
                    "user__username",
                    "user__full_name",
                    "user__email",
                )
                .annotate(
                    total_sales_count=Count(
                        "id", filter=models.Q(document_type="Invoice")
                    ),
                    total_revenue=Sum(
                        "amount", filter=models.Q(document_type="Invoice")
                    ),
                    total_payments=Sum(
                        "amount", filter=models.Q(document_type="Payment")
                    ),
                )
                .filter(total_revenue__gt=0)  # Only include people with actual sales
                .order_by("-total_revenue")[:10]
            )

            # Format the data for frontend
            sales_people_data = []
            for person in top_sales_people:
                sales_people_data.append(
                    {
                        "id": str(person["user__id"]),
                        "name": person["user__full_name"] or person["user__username"],
                        "username": person["user__username"],
                        "email": person["user__email"],
                        "sales": person["total_sales_count"] or 0,
                        "revenue": float(person["total_revenue"] or 0),
                        "payments": float(person["total_payments"] or 0),
                    }
                )

            return Response(
                {
                    "period": {"start_date": start_date, "end_date": end_date},
                    "top_sales_people": sales_people_data,
                }
            )

        except Exception as e:
            return Response(
                {"detail": f"Error generating top sales people data: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=False, methods=["get"])
    def stock_value(self, request):
        """Get current stock value.

        Uses G/L account 2110 ("Resale Items") for both branch and all-branches
        views so the dashboard is reconciled from one valuation source.
        """
        try:
            from financials.models import G_LAccount, GeneralLedgerEntry
            from django.db.models import Sum

            dim1_id = self._get_dim1_id(request)

            resale_items_account = G_LAccount.objects.filter(
                no="2110", name__icontains="Resale Items"
            ).first()

            if not resale_items_account:
                return Response(
                    {"detail": "Resale Items account (2110) not found"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            current_month_start = timezone.now().replace(day=1).date()
            prev_month_start = (current_month_start - timedelta(days=1)).replace(day=1)
            prev_month_end = current_month_start - timedelta(days=1)

            current_gl_filter = {"gl_account": resale_items_account}
            prev_gl_filter = {
                "gl_account": resale_items_account,
                "posting_date__range": [prev_month_start, prev_month_end],
            }

            if dim1_id is not None:
                current_gl_filter["global_dimension_1_id"] = dim1_id
                prev_gl_filter["global_dimension_1_id"] = dim1_id

            current_balance = (
                GeneralLedgerEntry.objects.filter(**current_gl_filter).aggregate(
                    total=Sum("amount")
                )["total"]
                or 0.0
            )

            prev_month_balance = (
                GeneralLedgerEntry.objects.filter(**prev_gl_filter).aggregate(
                    total=Sum("amount")
                )["total"]
                or 0.0
            )

            growth_percentage = 0.0
            if prev_month_balance != 0:
                growth_percentage = (
                    (current_balance - prev_month_balance) / abs(prev_month_balance)
                ) * 100

            return Response(
                {
                    "stock_value": {
                        "value": float(current_balance),
                        "growShrink": round(growth_percentage, 1),
                        "account_no": resale_items_account.no,
                        "account_name": resale_items_account.name,
                        "prev_month_balance": float(prev_month_balance),
                    }
                }
            )

        except Exception as e:
            return Response(
                {"detail": f"Error getting stock value: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=False, methods=["get"])
    def purchases(self, request):
        """Get purchases data for dashboard"""
        try:
            # Get date range and dimension filter from query params
            start_date = request.query_params.get("start_date")
            end_date = request.query_params.get("end_date")
            all_time = request.query_params.get("all_time") in ["true", "1", "yes"]
            dim1_id = self._get_dim1_id(request)

            # Default to current month if no dates provided
            if not start_date:
                start_date = timezone.now().replace(day=1).date()
            else:
                start_date = datetime.strptime(start_date, "%Y-%m-%d").date()

            if not end_date:
                end_date = timezone.now().date()
            else:
                end_date = datetime.strptime(end_date, "%Y-%m-%d").date()

            # Calculate previous period for growth comparison
            period_days = (end_date - start_date).days
            previous_period_start = start_date - timedelta(days=period_days)
            previous_period_end = start_date - timedelta(days=1)

            # Get purchases data from G/L Account 6111 "Purchases"
            from purchases.models import PurchaseInvoice, PurchaseInvoiceLine
            from financials.models import GeneralLedgerEntry, G_LAccount

            if all_time:
                earliest_purchase_date = (
                    PurchaseInvoice.objects.aggregate(Min("posting_date"))[
                        "posting_date__min"
                    ]
                    or start_date
                )
                start_date = earliest_purchase_date
                end_date = timezone.now().date()

            purchase_account = G_LAccount.objects.filter(
                no="6111", name__icontains="Purchases"
            ).first()

            if purchase_account:
                # Import models needed for reversal check
                from purchases.models import (
                    PostedPurchaseInvoice,
                    PostedPurchaseCreditMemo,
                )

                # Get only Posted Purchase Invoices (status="Posted", not Open)
                # Filter by posting_date (not document_date or created_at)
                # Also ensure posting_date is not null
                pi_filter = {
                    "status": "Posted",
                    "posting_date__isnull": False,
                    "posting_date__range": [start_date, end_date],
                }
                if dim1_id is not None:
                    pi_filter["global_dimension_1_id"] = dim1_id
                posted_purchase_invoices = PurchaseInvoice.objects.filter(**pi_filter)

                # Get reversed invoice numbers in two ways:
                # 1. By vendor_invoice_no (from PostedPurchaseCreditMemo -> PostedPurchaseInvoice -> vendor_invoice_no)
                reversed_vendor_invoice_nos = PostedPurchaseCreditMemo.objects.filter(
                    original_posted_invoice__isnull=False
                ).values_list("original_posted_invoice__vendor_invoice_no", flat=True)

                # 2. By invoice_no (from PostedPurchaseCreditMemo.original_invoice_no)
                reversed_invoice_nos = PostedPurchaseCreditMemo.objects.filter(
                    original_invoice_no__isnull=False
                ).values_list("original_invoice_no", flat=True)

                # Exclude reversed invoices by matching both vendor_invoice_no and invoice_no
                non_reversed_invoices = posted_purchase_invoices.exclude(
                    vendor_invoice_no__in=reversed_vendor_invoice_nos
                ).exclude(invoice_no__in=reversed_invoice_nos)

                # Get invoice_no values for GL entry matching
                # GL entries use PurchaseInvoice.invoice_no as document_no
                invoice_numbers = non_reversed_invoices.values_list(
                    "invoice_no", flat=True
                )

                # Get GL entries for non-reversed posted invoices only
                gle_filter = {
                    "gl_account": purchase_account,
                    "posting_date__range": [start_date, end_date],
                    "document_no__in": invoice_numbers,
                }
                if dim1_id is not None:
                    gle_filter["global_dimension_1_id"] = dim1_id
                purchase_gl_entries = GeneralLedgerEntry.objects.filter(
                    **gle_filter
                ).exclude(
                    document_type__in=["Credit Memo", "Refund", "Purchase Credit Memo"]
                )

                total_purchases_amount = (
                    purchase_gl_entries.aggregate(total_amount=Sum("amount"))[
                        "total_amount"
                    ]
                    or 0
                )

                # Ensure purchases amount is positive
                total_purchases_amount = abs(total_purchases_amount)

                # Get purchases count (non-reversed posted invoices only)
                total_purchases_count = non_reversed_invoices.count()

                # Get previous period purchases (same logic)
                prev_pi_filter = {
                    "status": "Posted",
                    "posting_date__range": [previous_period_start, previous_period_end],
                }
                if dim1_id is not None:
                    prev_pi_filter["global_dimension_1_id"] = dim1_id
                previous_period_posted_invoices = PurchaseInvoice.objects.filter(
                    **prev_pi_filter
                )

                # Exclude reversed invoices for previous period
                previous_period_reversed_vendor_invoice_nos = (
                    PostedPurchaseCreditMemo.objects.filter(
                        original_posted_invoice__isnull=False,
                        original_posted_invoice__posting_date__range=[
                            previous_period_start,
                            previous_period_end,
                        ],
                    ).values_list(
                        "original_posted_invoice__vendor_invoice_no", flat=True
                    )
                )

                previous_period_reversed_invoice_nos = (
                    PostedPurchaseCreditMemo.objects.filter(
                        original_invoice_no__isnull=False,
                        posting_date__range=[
                            previous_period_start,
                            previous_period_end,
                        ],
                    ).values_list("original_invoice_no", flat=True)
                )

                previous_period_non_reversed = previous_period_posted_invoices.exclude(
                    vendor_invoice_no__in=previous_period_reversed_vendor_invoice_nos
                ).exclude(invoice_no__in=previous_period_reversed_invoice_nos)

                previous_period_invoice_numbers = (
                    previous_period_non_reversed.values_list("invoice_no", flat=True)
                )

                prev_gle_filter = {
                    "gl_account": purchase_account,
                    "posting_date__range": [
                        previous_period_start,
                        previous_period_end,
                    ],
                    "document_no__in": previous_period_invoice_numbers,
                }
                if dim1_id is not None:
                    prev_gle_filter["global_dimension_1_id"] = dim1_id
                previous_period_purchase_entries = GeneralLedgerEntry.objects.filter(
                    **prev_gle_filter
                ).exclude(
                    document_type__in=["Credit Memo", "Refund", "Purchase Credit Memo"]
                )
                previous_period_purchases = (
                    previous_period_purchase_entries.aggregate(
                        total_amount=Sum("amount")
                    )["total_amount"]
                    or 0
                )
                previous_period_purchases = abs(previous_period_purchases)
            else:
                # Fallback to purchase invoice aggregation
                # Only include Posted invoices, filter by posting_date, exclude reversed
                from purchases.models import PostedPurchaseCreditMemo

                # Get Posted invoices only
                posted_inv_filter = {
                    "status": "Posted",
                    "posting_date__isnull": False,
                    "posting_date__range": [start_date, end_date],
                }
                if dim1_id is not None:
                    posted_inv_filter["global_dimension_1_id"] = dim1_id
                posted_invoices = PurchaseInvoice.objects.filter(**posted_inv_filter)

                # Exclude reversed invoices
                reversed_vendor_invoice_nos = PostedPurchaseCreditMemo.objects.filter(
                    original_posted_invoice__isnull=False
                ).values_list("original_posted_invoice__vendor_invoice_no", flat=True)

                reversed_invoice_nos = PostedPurchaseCreditMemo.objects.filter(
                    original_invoice_no__isnull=False
                ).values_list("original_invoice_no", flat=True)

                non_reversed_invoices = posted_invoices.exclude(
                    vendor_invoice_no__in=reversed_vendor_invoice_nos
                ).exclude(invoice_no__in=reversed_invoice_nos)

                purchase_lines = PurchaseInvoiceLine.objects.filter(
                    purchase_invoice__in=non_reversed_invoices
                )

                # Calculate total amount using unit_cost * quantity
                total_purchases_amount = 0
                for line in purchase_lines:
                    total_purchases_amount += line.unit_cost * line.quantity

                total_purchases_count = purchase_lines.count()

                # Calculate previous period purchases
                prev_pl_filter = {
                    "purchase_invoice__document_date__range": [
                        previous_period_start,
                        previous_period_end,
                    ]
                }
                if dim1_id is not None:
                    prev_pl_filter["purchase_invoice__global_dimension_1_id"] = dim1_id
                previous_period_purchase_lines = PurchaseInvoiceLine.objects.filter(
                    **prev_pl_filter
                )

                previous_period_purchases = 0
                for line in previous_period_purchase_lines:
                    previous_period_purchases += line.unit_cost * line.quantity

            # Calculate growth percentage
            if previous_period_purchases > 0:
                growth_percentage = (
                    (total_purchases_amount - previous_period_purchases)
                    / previous_period_purchases
                ) * 100
            else:
                growth_percentage = 0

            return Response(
                {
                    "purchases": {
                        "value": float(total_purchases_amount),
                        "growShrink": round(growth_percentage, 2),
                    }
                }
            )

        except Exception as e:
            return Response(
                {"detail": f"Error generating purchases data: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=False, methods=["get"])
    def monthly_performance(self, request):
        """Get monthly performance data for the last 12 months"""
        try:
            from financials.models import GeneralLedgerEntry, G_LAccount
            from decimal import Decimal

            dim1_id = self._get_dim1_id(request)

            end_date = timezone.now().date()

            sales_account = G_LAccount.objects.filter(
                no="6110", name__icontains="Sales, Retail - Dom."
            ).first()

            monthly_performance = []

            for i in range(12):
                month_start = end_date.replace(day=1) - timedelta(days=30 * i)
                month_end = (month_start + timedelta(days=32)).replace(
                    day=1
                ) - timedelta(days=1)

                if dim1_id is not None:
                    # Per-branch: use SalesInvoice objects which have
                    # reliable dimension tagging (GL entries may not).
                    month_invoices = SalesInvoice.objects.filter(
                        document_date__range=[month_start, month_end],
                        status="Posted",
                        global_dimension_1_id=dim1_id,
                    ).prefetch_related("lines")
                    month_sales = Decimal("0")
                    for inv in month_invoices:
                        subtotal = sum(
                            Decimal(str(ln.total_amount)) for ln in inv.lines.all()
                        )
                        month_sales += subtotal - Decimal(
                            str(inv.invoice_discount_value)
                        )
                    month_sales = abs(float(month_sales))
                elif sales_account:
                    month_sales = abs(
                        GeneralLedgerEntry.objects.filter(
                            gl_account=sales_account,
                            posting_date__range=[month_start, month_end],
                        ).aggregate(total_amount=Sum("amount"))["total_amount"]
                        or 0
                    )
                else:
                    from sales.models import SalesInvoiceLine

                    month_sales_lines = SalesInvoiceLine.objects.filter(
                        sales_invoice__document_date__range=[
                            month_start,
                            month_end,
                        ]
                    )
                    month_sales = 0
                    for line in month_sales_lines:
                        month_sales += line.unit_price * line.quantity

                month_name = month_start.strftime("%b")
                monthly_performance.append(
                    {"month": month_name, "value": float(month_sales)}
                )

            monthly_performance.reverse()

            return Response({"monthly_performance": monthly_performance})

        except Exception as e:
            return Response(
                {"detail": f"Error generating monthly performance data: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )


class CustomerLedgerFilter(filters.FilterSet):
    date_range = filters.DateFromToRangeFilter(field_name="posting_date")
    amount_range = filters.NumericRangeFilter(field_name="amount")
    customer_no = filters.CharFilter(field_name="customer__no", lookup_expr="iexact")

    class Meta:
        model = CustomerLedgerEntry
        fields = {
            "customer": ["exact"],
            "document_type": ["exact"],
            "open": ["exact"],
            "posting_date": ["exact", "gte", "lte"],
            "due_date": ["exact", "gte", "lte"],
        }


class CustomerLedgerViewSet(viewsets.ModelViewSet):
    """Match SalesInvoiceViewSet auth so mobile JWT works the same (default CustomJWT was 401 + force-logout cascade)."""

    queryset = CustomerLedgerEntry.objects.all()
    serializer_class = CustomerLedgerSerializer
    filterset_class = CustomerLedgerFilter
    search_fields = ["document_no", "external_document_no", "customer__name"]
    ordering_fields = ["posting_date", "due_date", "amount"]
    ordering = ["-posting_date"]
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication, SessionAuthentication]

    def get_queryset(self):
        queryset = super().get_queryset()
        queryset = filter_queryset_by_branch(
            queryset, self.request.user, request=self.request
        )
        if self.action == "list":
            return queryset.select_related("customer", "payment_method").order_by(
                "-posting_date"
            )
        return queryset.order_by("-posting_date")

    @action(detail=True, methods=["get"])
    def ledger_entries(self, request, pk=None):
        customer = get_object_or_404(Customer, id=pk)
        queryset = CustomerLedgerEntry.objects.filter(
            customer=customer, open=True
        ).order_by("-posting_date")
        queryset = filter_queryset_by_branch(queryset, request.user, request=request)

        # Mirror vendor logic: compute totals from detailed entries
        from .models import DetailedCustomerLedgerEntry

        total_amount = 0
        for entry in queryset:
            details = DetailedCustomerLedgerEntry.objects.filter(
                customer_ledger_entry=entry
            )
            for detail in details:
                total_amount += detail.amount

        serializer = self.get_serializer(queryset, many=True)
        return Response(
            {
                "ledger_entries": serializer.data,
                "summary": {
                    "total_amount": float(total_amount or 0),
                    "total_remaining": float(total_amount or 0),
                },
            }
        )

    @action(detail=True, methods=["get"])
    def ledger_entries_paginated(self, request, pk=None):
        """Paginated version of ledger entries with search and filtering"""
        customer = get_object_or_404(Customer, id=pk)

        # Get query parameters
        page = request.query_params.get("page", 1)
        page_size = request.query_params.get("page_size", 20)
        search = request.query_params.get("search", "")
        document_type = request.query_params.get("document_type", "")
        start_date = request.query_params.get("start_date", "")
        end_date = request.query_params.get("end_date", "")

        # Build queryset
        queryset = CustomerLedgerEntry.objects.filter(
            customer=customer, open=True
        ).order_by("-posting_date")
        queryset = filter_queryset_by_branch(queryset, request.user, request=request)

        # Apply search filter
        if search:
            queryset = queryset.filter(
                Q(document_no__icontains=search)
                | Q(description__icontains=search)
                | Q(external_document_no__icontains=search)
            )

        # Apply document type filter
        if document_type:
            queryset = queryset.filter(document_type=document_type)

        # Apply date range filter
        if start_date:
            queryset = queryset.filter(posting_date__gte=start_date)
        if end_date:
            queryset = queryset.filter(posting_date__lte=end_date)

        # Get summary for all entries (not just current page)
        summary_queryset = CustomerLedgerEntry.objects.filter(
            customer=customer, open=True
        )
        summary_queryset = filter_queryset_by_branch(
            summary_queryset, request.user, request=request
        )
        if search:
            summary_queryset = summary_queryset.filter(
                Q(document_no__icontains=search)
                | Q(description__icontains=search)
                | Q(external_document_no__icontains=search)
            )
        if document_type:
            summary_queryset = summary_queryset.filter(document_type=document_type)
        if start_date:
            summary_queryset = summary_queryset.filter(posting_date__gte=start_date)
        if end_date:
            summary_queryset = summary_queryset.filter(posting_date__lte=end_date)

        # Calculate totals manually since remaining_amount is now a property
        total_amount = sum(entry.amount for entry in summary_queryset)
        total_remaining = sum(entry.remaining_amount for entry in summary_queryset)

        summary = {"total_amount": total_amount, "total_remaining": total_remaining}

        # Paginate
        paginator = Paginator(queryset, page_size)
        try:
            page_obj = paginator.page(page)
        except (EmptyPage, InvalidPage):
            page_obj = paginator.page(paginator.num_pages)

        serializer = self.get_serializer(page_obj, many=True)

        return Response(
            {
                "ledger_entries": serializer.data,
                "summary": {
                    "total_amount": float(summary["total_amount"] or 0),
                    "total_remaining": float(summary["total_remaining"] or 0),
                },
                "pagination": {
                    "count": paginator.count,
                    "next": page_obj.has_next(),
                    "previous": page_obj.has_previous(),
                    "current_page": page_obj.number,
                    "total_pages": paginator.num_pages,
                    "page_size": int(page_size),
                },
            }
        )

    @action(detail=False, methods=["get"])
    def receivables_dashboard(self, request):
        """Get accounts receivable dashboard data"""
        try:
            # Get date range from query params
            start_date = request.query_params.get("start_date")
            end_date = request.query_params.get("end_date")

            if start_date:
                start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
            if end_date:
                end_date = datetime.strptime(end_date, "%Y-%m-%d").date()

            # Base queryset for open invoices
            open_invoices = CustomerLedgerEntry.objects.filter(
                open=True, document_type="Invoice"
            ).select_related("customer")

            # Get top customers with outstanding invoices - calculate manually
            customer_totals = {}
            for invoice in open_invoices:
                customer_key = (invoice.customer.name, invoice.customer.no)
                if customer_key not in customer_totals:
                    customer_totals[customer_key] = {
                        "total_outstanding": 0,
                        "invoice_count": 0,
                    }
                customer_totals[customer_key][
                    "total_outstanding"
                ] += invoice.remaining_amount
                customer_totals[customer_key]["invoice_count"] += 1

            top_customers_outstanding = [
                {
                    "customer__name": name,
                    "customer__no": no,
                    "total_outstanding": data["total_outstanding"],
                    "invoice_count": data["invoice_count"],
                }
                for (name, no), data in sorted(
                    customer_totals.items(),
                    key=lambda x: x[1]["total_outstanding"],
                    reverse=True,
                )[:10]
            ]

            # Get recent open invoices - calculate manually
            recent_customer_totals = {}
            recent_invoices = open_invoices.order_by("-created_at")[
                :50
            ]  # Get recent 50 to calculate from
            for invoice in recent_invoices:
                customer_key = (invoice.customer.name, invoice.customer.no)
                if customer_key not in recent_customer_totals:
                    recent_customer_totals[customer_key] = {
                        "total_outstanding": 0,
                        "invoice_count": 0,
                    }
                recent_customer_totals[customer_key][
                    "total_outstanding"
                ] += invoice.remaining_amount
                recent_customer_totals[customer_key]["invoice_count"] += 1

            recent_open_invoices = [
                {
                    "customer__name": name,
                    "customer__no": no,
                    "total_outstanding": data["total_outstanding"],
                    "invoice_count": data["invoice_count"],
                }
                for (name, no), data in sorted(
                    recent_customer_totals.items(),
                    key=lambda x: x[1]["total_outstanding"],
                    reverse=True,
                )[:10]
            ]

            # Aging analysis
            today = timezone.now().date()
            aging_buckets = {
                "current": open_invoices.filter(due_date__gte=today),
                "overdue_30": open_invoices.filter(
                    due_date__lt=today, due_date__gte=today - timedelta(days=30)
                ),
                "overdue_60": open_invoices.filter(
                    due_date__lt=today - timedelta(days=30),
                    due_date__gte=today - timedelta(days=60),
                ),
                "overdue_90": open_invoices.filter(
                    due_date__lt=today - timedelta(days=60)
                ),
            }

            aging_analysis = {}
            for bucket, queryset in aging_buckets.items():
                aging_analysis[bucket] = {
                    "amount": float(sum(entry.remaining_amount for entry in queryset)),
                    "count": queryset.count(),
                }

            # Payment collection trends
            if start_date and end_date:
                payments = CustomerLedgerEntry.objects.filter(
                    document_type="Payment", posting_date__range=[start_date, end_date]
                )
            else:
                payments = CustomerLedgerEntry.objects.filter(document_type="Payment")

            payment_trends = (
                payments.annotate(month=TruncMonth("posting_date"))
                .values("month")
                .annotate(total_payments=Sum("amount"), payment_count=Count("id"))
                .order_by("month")
            )

            # Customer payment performance - calculate manually
            customer_performance_totals = {}
            for invoice in open_invoices:
                customer_key = (invoice.customer.name, invoice.customer.no)
                if customer_key not in customer_performance_totals:
                    customer_performance_totals[customer_key] = {
                        "total_outstanding": 0,
                        "days_overdue": [],
                    }
                customer_performance_totals[customer_key][
                    "total_outstanding"
                ] += invoice.remaining_amount
                if invoice.due_date:
                    days_overdue = (today - invoice.due_date).days
                    customer_performance_totals[customer_key]["days_overdue"].append(
                        days_overdue
                    )

            customer_payment_performance = []
            for (name, no), data in customer_performance_totals.items():
                avg_days_overdue = (
                    sum(data["days_overdue"]) / len(data["days_overdue"])
                    if data["days_overdue"]
                    else 0
                )
                customer_payment_performance.append(
                    {
                        "customer__name": name,
                        "customer__no": no,
                        "total_outstanding": data["total_outstanding"],
                        "avg_days_overdue": avg_days_overdue,
                    }
                )

            # Sort by total_outstanding and take top 15
            customer_payment_performance.sort(
                key=lambda x: x["total_outstanding"], reverse=True
            )
            customer_payment_performance = customer_payment_performance[:15]

            return Response(
                {
                    "total_outstanding": {
                        "amount": float(
                            sum(entry.remaining_amount for entry in open_invoices)
                        ),
                        "count": open_invoices.count(),
                    },
                    "aging_analysis": aging_analysis,
                    "top_customers_outstanding": list(top_customers_outstanding),
                    "payment_trends": list(payment_trends),
                    "customer_payment_performance": list(customer_payment_performance),
                }
            )

        except Exception as e:
            return Response(
                {"detail": f"Error generating receivables dashboard: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )


class GenerateInvoiceNoView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def post(self, request):
        today_str = datetime.now().strftime("%Y%m%d")
        customer_invoice_no = f"SAL-{today_str}-" + "".join(
            random.choices(string.digits, k=6)
        )

        # Ensure uniqueness
        while SalesInvoice.objects.filter(
            customer_invoice_no=customer_invoice_no
        ).exists():
            customer_invoice_no = f"SAL-{today_str}-" + "".join(
                random.choices(string.digits, k=6)
            )

        return Response({"customer_invoice_no": customer_invoice_no})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
@authentication_classes([JWTAuthentication, SessionAuthentication])
def get_sales_setup(request):
    from sales.setup_data import fetch_sales_setup_data

    return Response(fetch_sales_setup_data())


@api_view(["PUT"])
@permission_classes([IsAuthenticated])
@authentication_classes([SessionAuthentication, JWTAuthentication])
def update_customer_payment_method(request):
    """Update customer's preferred payment method and optionally invoice's payment method"""
    try:
        customer_id = request.data.get("customer_id")
        payment_method_id = request.data.get("payment_method_id")
        invoice_id = request.data.get("invoice_id")  # Optional: invoice ID to update

        if not customer_id:
            return Response(
                {"error": "Customer ID is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        if not payment_method_id:
            return Response(
                {"error": "Payment method ID is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get customer
        try:
            customer = Customer.objects.get(id=customer_id)
        except Customer.DoesNotExist:
            return Response(
                {"error": "Customer not found"}, status=status.HTTP_404_NOT_FOUND
            )

        # Get payment method
        try:
            payment_method = PaymentMethod.objects.get(id=payment_method_id)
        except PaymentMethod.DoesNotExist:
            return Response(
                {"error": "Payment method not found"}, status=status.HTTP_404_NOT_FOUND
            )

        # Check if this is General customer and trying to set "Not Paid Yet"
        if (
            customer.name.lower().find("general") != -1
            or customer.no.lower().find("general") != -1
        ) and payment_method.code == "NOT_PAID":
            return Response(
                {
                    "error": "General customer cannot have 'Not Paid Yet' as payment method. Please select a different payment method."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Update customer's payment method
        customer.payment_method = payment_method
        customer.save(update_fields=["payment_method", "updated_at"])

        # If invoice_id is provided, also update the invoice's payment method
        if invoice_id:
            try:
                from .models import SalesInvoice

                invoice = SalesInvoice.objects.get(id=invoice_id)
                # Only update if invoice is not yet posted
                if invoice.status != "Posted":
                    invoice.payment_method = payment_method
                    invoice.save(update_fields=["payment_method", "updated_at"])
            except SalesInvoice.DoesNotExist:
                # Invoice not found - not critical, continue
                pass

        return Response(
            {
                "message": f"Customer payment method updated to {payment_method.description}",
                "customer_id": customer.id,
                "payment_method_id": payment_method.id,
                "payment_method_name": payment_method.description,
            }
        )

    except Exception as e:
        return Response(
            {"error": f"Failed to update customer payment method: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


# ============================================
# SERVICE SALES & BOM PROCESSING ENDPOINTS
# ============================================


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@authentication_classes([SessionAuthentication, JWTAuthentication])
def process_service_sale(request):
    """
    Process a service sale with BOM processing and inventory deduction.

    Request Body:
        - saleLineId: ID of the SalesInvoiceLine to process

    Returns:
        - Processing result with cost breakdown and inventory deductions
    """

    from production.utils import process_service_sale as process_bom

    try:
        sale_line_id = request.data.get("saleLineId")

        if not sale_line_id:
            return Response(
                {"error": "Sale line ID is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get sale line
        try:
            sale_line = SalesInvoiceLine.objects.select_related(
                "item", "sales_invoice", "assigned_resource"
            ).get(id=sale_line_id)
        except SalesInvoiceLine.DoesNotExist:
            return Response(
                {"error": "Sale line not found"}, status=status.HTTP_404_NOT_FOUND
            )

        # Process the service sale through BOM
        result = process_bom(sale_line)

        return Response(
            {
                "message": "Service sale processed successfully",
                "processingResult": result,
                "saleLine": {
                    "id": sale_line.id,
                    "lineType": sale_line.line_type,
                    "unitCost": float(sale_line.unit_cost),
                    "totalCost": float(sale_line.total_cost),
                    "profit": float(sale_line.profit),
                    "profitMargin": float(sale_line.profit_margin),
                },
            }
        )

    except DjangoValidationError as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response(
            {"error": f"Error processing service sale: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
@authentication_classes([SessionAuthentication, JWTAuthentication])
def get_service_profitability(request):
    """
    Get service profitability report.

    Query Parameters:
        - startDate: Start date for report (YYYY-MM-DD)
        - endDate: End date for report (YYYY-MM-DD)
        - serviceId: Filter by specific service item (optional)

    Returns:
        - Profitability metrics for service sales
    """

    try:
        # Get date range
        start_date = request.GET.get("startDate")
        end_date = request.GET.get("endDate")
        service_id = request.GET.get("serviceId")

        # Base query: service sales only
        # Note: Company isolation handled by Django Tenants schema
        service_sales = SalesInvoiceLine.objects.filter(
            line_type="service",
        )

        # Filter by date range
        if start_date:
            service_sales = service_sales.filter(
                sales_invoice__document_date__gte=start_date
            )
        if end_date:
            service_sales = service_sales.filter(
                sales_invoice__document_date__lte=end_date
            )

        # Filter by service item
        if service_id:
            service_sales = service_sales.filter(item_id=service_id)

        # Calculate metrics
        total_sales = service_sales.count()
        total_revenue = sum(float(line.line_amount) for line in service_sales)
        total_cost = sum(float(line.total_cost) for line in service_sales)
        total_profit = total_revenue - total_cost
        avg_profit_margin = (
            (total_profit / total_revenue * 100) if total_revenue > 0 else 0
        )

        # Get top services by profit
        from django.db.models import Sum, Count

        top_services = (
            service_sales.values("item__item_name", "item_id")
            .annotate(
                sales_count=Count("id"),
                total_revenue=Sum(F("quantity") * F("unit_price")),
                total_cost_sum=Sum("total_cost"),
            )
            .order_by("-total_revenue")[:10]
        )

        top_services_data = []
        for service in top_services:
            revenue = float(service["total_revenue"]) if service["total_revenue"] else 0
            cost = float(service["total_cost_sum"]) if service["total_cost_sum"] else 0
            profit = revenue - cost
            margin = (profit / revenue * 100) if revenue > 0 else 0

            top_services_data.append(
                {
                    "itemId": service["item_id"],
                    "serviceName": service["item__item_name"],
                    "salesCount": service["sales_count"],
                    "totalRevenue": revenue,
                    "totalCost": cost,
                    "totalProfit": profit,
                    "profitMargin": margin,
                }
            )

        return Response(
            {
                "summary": {
                    "totalSales": total_sales,
                    "totalRevenue": total_revenue,
                    "totalCost": total_cost,
                    "totalProfit": total_profit,
                    "avgProfitMargin": avg_profit_margin,
                },
                "topServices": top_services_data,
                "dateRange": {
                    "startDate": start_date,
                    "endDate": end_date,
                },
            }
        )

    except Exception as e:
        return Response(
            {"error": f"Error generating profitability report: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
@authentication_classes([SessionAuthentication, JWTAuthentication])
def get_service_cost_breakdown(request, service_id):
    """
    Get detailed cost breakdown for a service item based on its BOM.

    Path Parameters:
        - service_id: ID of the service item

    Returns:
        - Detailed cost breakdown with resources and inventory
    """

    from production.utils import get_service_cost_breakdown as get_breakdown

    try:
        # Get service item
        try:
            service_item = Item.objects.get(id=service_id, type="Service")
        except Item.DoesNotExist:
            return Response(
                {"error": "Service item not found"}, status=status.HTTP_404_NOT_FOUND
            )

        # Get cost breakdown
        breakdown = get_breakdown(service_item)

        return Response(breakdown)

    except Exception as e:
        return Response(
            {"error": f"Error getting cost breakdown: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
