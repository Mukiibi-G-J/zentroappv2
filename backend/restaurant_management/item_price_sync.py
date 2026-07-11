"""When Item.unit_price changes, keep open restaurant / KDS lines in sync."""

from decimal import Decimal

from django.db import connection, transaction
from django_tenants.utils import get_public_schema_name

from restaurant_management.enums import OrderItemStatus, OrderStatus
from restaurant_management.models import (
    RestaurantOrderItem,
    restaurant_order_item_routes_to_kitchen,
)

_OPEN_ORDER_STATUSES = (
    OrderStatus.NEW,
    OrderStatus.IN_PROGRESS,
    OrderStatus.READY,
    OrderStatus.SERVED,
)


def _resolve_tenant_company():
    """
    Return the real Company row for module checks.

    schema_context() switches DB schema but leaves a FakeTenant on connection
    that lacks Company helpers like has_module().
    """
    tenant = getattr(connection, "tenant", None)
    if tenant is None:
        return None
    if hasattr(tenant, "has_module"):
        return tenant

    schema_name = getattr(tenant, "schema_name", None)
    if not schema_name:
        return None

    from company.models import Company

    try:
        return Company.objects.get(schema_name=schema_name)
    except Company.DoesNotExist:
        return None


def sync_kitchen_routing_restaurant_order_items_unit_price(item, new_unit_price) -> int:
    """
    For open restaurant orders, set line unit_price to match the item master price when the
    line routes to the kitchen (same rules as KDS).

    Only runs in a tenant schema with the restaurant module enabled.
    Returns the number of order lines updated.
    """
    if connection.schema_name == get_public_schema_name():
        return 0

    company = _resolve_tenant_company()
    if company is None or not company.has_module("restaurant"):
        return 0

    new_unit_price = Decimal(str(new_unit_price))

    qs = (
        RestaurantOrderItem.objects.filter(
            item=item,
            status__in=[
                OrderItemStatus.PENDING,
                OrderItemStatus.PREPARING,
                OrderItemStatus.READY,
                OrderItemStatus.SERVED,
            ],
            order__status__in=_OPEN_ORDER_STATUSES,
        )
        .select_related("item", "item__menu_item", "item__menu_item__category")
    )

    n = 0
    with transaction.atomic():
        for line in qs.iterator(chunk_size=100):
            if not restaurant_order_item_routes_to_kitchen(line):
                continue
            if line.unit_price == new_unit_price:
                continue
            line.unit_price = new_unit_price
            line.save()
            n += 1
    return n
