"""
Celery tasks for mobile push notifications.
"""

import logging

from celery import shared_task
from django.db.models import Q
from django_tenants.utils import get_tenant_model, schema_context

from authentication.models import CustomUser, DevicePushToken
from helpers.push_notifications import send_push_to_users

logger = logging.getLogger(__name__)


@shared_task
def send_low_stock_push_alerts():
    """
    Daily: notify users with active device tokens when items are at/below minimum_stock.
    Register in Celery Beat or run: python manage.py setup_low_stock_push_task
    """
    from items.models import Item
    from items.enums import InventoryType

    Tenant = get_tenant_model()
    tenants_notified = 0
    pushes_sent = 0

    for tenant in Tenant.objects.exclude(schema_name="public").iterator():
        with schema_context(tenant.schema_name):
            low_stock_items = [
                item
                for item in Item.objects.filter(
                    minimum_stock__gt=0,
                    type=InventoryType.Inventory.value,
                ).iterator()
                if (item.inventory or 0) <= item.minimum_stock
            ]
            if not low_stock_items:
                continue

            user_ids = list(
                CustomUser.objects.filter(
                    is_active=True,
                    device_push_tokens__is_active=True,
                )
                .filter(
                    Q(roles__name__iexact="admin")
                    | Q(roles__name__iexact="manager")
                    | Q(roles__name__iexact="inventory")
                )
                .distinct()
                .values_list("id", flat=True)
            )
            if not user_ids:
                user_ids = list(
                    CustomUser.objects.filter(
                        is_active=True,
                        device_push_tokens__is_active=True,
                    )
                    .distinct()
                    .values_list("id", flat=True)
                )
            if not user_ids:
                continue

            count = len(low_stock_items)
            sample = ", ".join(item.item_name for item in low_stock_items[:3])
            if count > 3:
                sample = f"{sample} +{count - 3} more"

            result = send_push_to_users(
                user_ids,
                title="Low stock alert",
                body=f"{count} item(s) need attention: {sample}",
                data={"screen": "AllItems", "stockFilter": "low_stock"},
            )
            tenants_notified += 1
            pushes_sent += result.get("success", 0)

    logger.info(
        "Low stock push alerts complete: tenants=%s pushes=%s",
        tenants_notified,
        pushes_sent,
    )
    return {
        "status": "success",
        "tenants_notified": tenants_notified,
        "pushes_sent": pushes_sent,
    }


@shared_task
def send_push_notification_task(
    user_ids: list[int],
    title: str,
    body: str,
    data: dict | None = None,
    tenant_schema: str | None = None,
):
    """
    Generic push task for other Celery jobs.
    When tenant_schema is set, runs inside that tenant schema.
    """
    if tenant_schema:
        with schema_context(tenant_schema):
            return send_push_to_users(user_ids, title=title, body=body, data=data)
    return send_push_to_users(user_ids, title=title, body=body, data=data)
