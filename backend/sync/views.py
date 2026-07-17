import uuid

from django.utils import timezone
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication

from financials.models import PaymentMethod
from financials.serializers import PaymentMethodSerializer
from items.models import Item
from items.serializers import ItemSerializer
from purchases.models import Vendor
from sales.models import Customer
from sync.serializers import CustomerSyncSerializer, VendorSyncSerializer
from sales.serializers import CustomerSerializer
from sync.mixins import DeltaSyncMixin
from sync.models import SyncDevice, SyncEvent
from sync.services.bootstrap import build_bootstrap_payload
from sync.services.sale_push import process_sale_completed

SALES_PAGE_OBJECT_ID = 10002
CUSTOMER_PAGE_OBJECT_ID = 10101
SUPPLIERS_PAGE_OBJECT_ID = 10303


def _check_sales_permission(user, action="read"):
    if not user or not user.is_authenticated:
        return False, "anonymous"
    return user.check_object_permission(SALES_PAGE_OBJECT_ID, action)


def _check_suppliers_permission(user, action="read"):
    if not user or not user.is_authenticated:
        return False, "anonymous"
    return user.check_object_permission(SUPPLIERS_PAGE_OBJECT_ID, action)


def _can_pull_customers(user):
    for page_id in (SALES_PAGE_OBJECT_ID, CUSTOMER_PAGE_OBJECT_ID):
        allowed, source = user.check_object_permission(page_id, "read")
        if allowed:
            return True, source
    return False, "denied"


def _can_pull_vendors(user):
    allowed_sales, _ = _check_sales_permission(user, "read")
    if allowed_sales:
        return True, "sales"
    allowed_suppliers, source = _check_suppliers_permission(user, "read")
    if allowed_suppliers:
        return True, source
    return False, "denied"


def _deny(source, detail):
    return Response(
        {"error": "Insufficient permissions", "detail": detail, "reason": source},
        status=status.HTTP_403_FORBIDDEN,
    )


@api_view(["GET"])
@permission_classes([AllowAny])
def sync_ping(request):
    return Response(
        {
            "status": "ok",
            "server_time": timezone.now().isoformat(),
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@authentication_classes([JWTAuthentication, SessionAuthentication])
def register_device(request):
    allowed, source = _check_sales_permission(request.user, "read")
    if not allowed:
        return _deny(source, "You need read permission to register a sync device.")

    device_id = (request.data.get("device_id") or "").strip() or str(uuid.uuid4())
    name = (request.data.get("name") or "").strip() or "POS Device"
    client_type = request.data.get("client_type") or SyncDevice.CLIENT_DESKTOP
    branch_id = request.data.get("branch_id")
    app_version = (request.data.get("app_version") or "").strip()

    device, _ = SyncDevice.objects.update_or_create(
        device_id=device_id,
        defaults={
            "name": name,
            "client_type": client_type,
            "branch_id": branch_id,
            "app_version": app_version,
            "last_seen_at": timezone.now(),
        },
    )

    from sales.setup_data import fetch_sales_setup_data

    setup = fetch_sales_setup_data()
    branches = setup.get("branch_values") or []

    return Response(
        {
            "device_id": device.device_id,
            "server_time": timezone.now().isoformat(),
            "branches": branches,
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@authentication_classes([JWTAuthentication, SessionAuthentication])
def sync_bootstrap(request):
    allowed, source = _check_sales_permission(request.user, "read")
    if not allowed:
        return _deny(source, "You need read permission to bootstrap sync data.")

    device_id = (request.data.get("device_id") or "").strip()
    if device_id:
        SyncDevice.objects.filter(device_id=device_id).update(
            last_seen_at=timezone.now(),
            branch_id=request.data.get("branch_id"),
        )

    payload = build_bootstrap_payload(request, device_id=device_id)
    return Response(payload)


def _pull_items(request):
    allowed, source = _check_sales_permission(request.user, "read")
    if not allowed:
        return _deny(source, "You need read permission to pull items.")

    mixin = DeltaSyncMixin()
    updated_since = mixin.parse_updated_since(request)
    page, page_size = mixin.get_page_params(request)
    qs = mixin.delta_queryset(Item.objects.all(), updated_since)

    def serialize_item(obj):
        return ItemSerializer(obj, context={"request": request}).data

    return mixin.build_delta_response(qs, page, page_size, serialize_item)


def _pull_customers(request):
    allowed, source = _can_pull_customers(request.user)
    if not allowed:
        return _deny(
            source,
            "You need read permission on Sales or Customer Management to pull customers.",
        )

    mixin = DeltaSyncMixin()
    updated_since = mixin.parse_updated_since(request)
    page, page_size = mixin.get_page_params(request)
    qs = mixin.delta_queryset(Customer.objects.all(), updated_since)

    def serialize_customer(obj):
        return CustomerSyncSerializer(obj).data

    return mixin.build_delta_response(qs, page, page_size, serialize_customer)


def _pull_payment_methods(request):
    allowed, source = _check_sales_permission(request.user, "read")
    if not allowed:
        return _deny(source, "You need read permission to pull payment methods.")

    mixin = DeltaSyncMixin()
    updated_since = mixin.parse_updated_since(request)
    page, page_size = mixin.get_page_params(request)
    qs = mixin.delta_queryset(PaymentMethod.objects.all(), updated_since)

    def serialize_pm(obj):
        return PaymentMethodSerializer(obj).data

    return mixin.build_delta_response(qs, page, page_size, serialize_pm)


def _pull_vendors(request):
    allowed, source = _can_pull_vendors(request.user)
    if not allowed:
        return _deny(
            source,
            "You need read permission on Sales or Suppliers to pull vendors.",
        )

    mixin = DeltaSyncMixin()
    updated_since = mixin.parse_updated_since(request)
    page, page_size = mixin.get_page_params(request)
    qs = mixin.delta_queryset(Vendor.objects.all(), updated_since)

    def serialize_vendor(obj):
        return VendorSyncSerializer(obj, context={"request": request}).data

    return mixin.build_delta_response(qs, page, page_size, serialize_vendor)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
@authentication_classes([JWTAuthentication, SessionAuthentication])
def pull_items(request):
    return _pull_items(request)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
@authentication_classes([JWTAuthentication, SessionAuthentication])
def pull_customers(request):
    return _pull_customers(request)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
@authentication_classes([JWTAuthentication, SessionAuthentication])
def pull_payment_methods(request):
    return _pull_payment_methods(request)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
@authentication_classes([JWTAuthentication, SessionAuthentication])
def pull_vendors(request):
    return _pull_vendors(request)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
@authentication_classes([JWTAuthentication, SessionAuthentication])
def sync_changes(request):
    """Aggregator: items + customers + payment_methods deltas."""
    allowed, source = _check_sales_permission(request.user, "read")
    if not allowed:
        return _deny(source, "You need read permission to pull changes.")

    items_resp = _pull_items(request)
    customers_resp = _pull_customers(request)
    payments_resp = _pull_payment_methods(request)

    return Response(
        {
            "cursor": timezone.now().isoformat(),
            "items": items_resp.data,
            "customers": customers_resp.data,
            "payment_methods": payments_resp.data,
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@authentication_classes([JWTAuthentication, SessionAuthentication])
def sync_push(request):
    allowed, source = _check_sales_permission(request.user, "modify")
    if not allowed:
        return _deny(source, "You need modify permission to push sync events.")

    device_id = (request.data.get("device_id") or "").strip()
    if not device_id:
        return Response(
            {"error": "device_id is required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    SyncDevice.objects.update_or_create(
        device_id=device_id,
        defaults={"last_seen_at": timezone.now()},
    )

    events = request.data.get("events") or []
    results = []
    for entry in events:
        event_id = (entry.get("event_id") or "").strip()
        event_type = entry.get("event_type") or entry.get("type")
        payload = entry.get("payload") or entry
        if not event_id:
            results.append(
                {"ok": False, "error": "event_id is required", "event_id": None}
            )
            continue
        try:
            if event_type == "SALE_COMPLETED":
                out = process_sale_completed(
                    request, device_id, event_id, payload
                )
                results.append({"event_id": event_id, **out})
            elif event_type == "CUSTOMER_PAYMENT_COMPLETED":
                from sync.services.customer_payment_push import (
                    process_customer_payment_completed,
                )

                out = process_customer_payment_completed(
                    request, device_id, event_id, payload
                )
                results.append({"event_id": event_id, **out})
            else:
                results.append(
                    {
                        "event_id": event_id,
                        "ok": False,
                        "error": f"Unsupported event_type: {event_type}",
                    }
                )
        except Exception as exc:
            results.append(
                {
                    "event_id": event_id,
                    "ok": False,
                    "error": str(exc),
                }
            )

    return Response({"results": results})
