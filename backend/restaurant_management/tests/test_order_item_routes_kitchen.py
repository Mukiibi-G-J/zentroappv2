"""Unit tests for per-line kitchen routing helper (matches KDS Q object)."""

from unittest.mock import MagicMock

from django.core.exceptions import ObjectDoesNotExist
from django.test import SimpleTestCase

from restaurant_management.models import restaurant_order_item_routes_to_kitchen


class RestaurantOrderItemRoutesToKitchenTests(SimpleTestCase):
    def test_no_menu_item_row_routes_to_kitchen(self):
        oi = MagicMock()

        class _Item:
            pass

        item = _Item()

        def _raise(_self):
            raise ObjectDoesNotExist()

        type(item).menu_item = property(_raise)
        oi.item = item
        self.assertTrue(restaurant_order_item_routes_to_kitchen(oi))

    def test_menu_item_explicit_false_skips_kitchen(self):
        oi = MagicMock()
        mi = MagicMock()
        mi.routes_to_kitchen = False
        mi.category = MagicMock(routes_to_kitchen=True)
        oi.item.menu_item = mi
        self.assertFalse(restaurant_order_item_routes_to_kitchen(oi))

    def test_menu_item_explicit_true_routes(self):
        oi = MagicMock()
        mi = MagicMock()
        mi.routes_to_kitchen = True
        mi.category = None
        oi.item.menu_item = mi
        self.assertTrue(restaurant_order_item_routes_to_kitchen(oi))

    def test_inherit_null_uses_category_true(self):
        oi = MagicMock()
        mi = MagicMock()
        mi.routes_to_kitchen = None
        mi.category = MagicMock(routes_to_kitchen=True)
        oi.item.menu_item = mi
        self.assertTrue(restaurant_order_item_routes_to_kitchen(oi))

    def test_inherit_null_uses_category_false(self):
        oi = MagicMock()
        mi = MagicMock()
        mi.routes_to_kitchen = None
        mi.category = MagicMock(routes_to_kitchen=False)
        oi.item.menu_item = mi
        self.assertFalse(restaurant_order_item_routes_to_kitchen(oi))

    def test_inherit_null_no_category_routes(self):
        oi = MagicMock()
        mi = MagicMock()
        mi.routes_to_kitchen = None
        mi.category = None
        oi.item.menu_item = mi
        self.assertTrue(restaurant_order_item_routes_to_kitchen(oi))
