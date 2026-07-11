"""Kitchen vs non-kitchen routing by menu category (Q object for KDS / fire split)."""

from django.db.models import Q
from django.test import SimpleTestCase

from restaurant_management.views import _order_items_routes_to_kitchen_q


class OrderItemsRoutesToKitchenQTests(SimpleTestCase):
    def test_routes_q_is_or_of_three_paths(self):
        q = _order_items_routes_to_kitchen_q()
        self.assertIsInstance(q, Q)
        self.assertEqual(q.connector, "OR")
        self.assertEqual(len(q.children), 3)
