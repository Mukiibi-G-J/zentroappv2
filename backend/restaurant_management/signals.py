from decimal import Decimal

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from items.models import Item
from restaurant_management.item_price_sync import (
    sync_kitchen_routing_restaurant_order_items_unit_price,
)


@receiver(pre_save, sender=Item)
def _cache_item_unit_price_before_save(sender, instance, **kwargs):
    if not instance.pk:
        instance._zentro_prev_unit_price = None
        return
    try:
        prev = (
            Item.objects.filter(pk=instance.pk)
            .values_list("unit_price", flat=True)
            .first()
        )
        instance._zentro_prev_unit_price = prev
    except Exception:
        instance._zentro_prev_unit_price = None


@receiver(post_save, sender=Item)
def _sync_restaurant_order_prices_after_item_save(sender, instance, created, **kwargs):
    if created:
        return
    prev = getattr(instance, "_zentro_prev_unit_price", None)
    old_val = Decimal(str(prev)) if prev is not None else Decimal("0")
    new_val = (
        Decimal(str(instance.unit_price))
        if instance.unit_price is not None
        else Decimal("0")
    )
    if new_val == old_val:
        return
    sync_kitchen_routing_restaurant_order_items_unit_price(instance, new_val)
