from contextlib import nullcontext
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from restaurant_management.item_price_sync import (
    sync_kitchen_routing_restaurant_order_items_unit_price,
)


class ItemPriceSyncKitchenTests(SimpleTestCase):
    def test_sync_skips_public_schema(self):
        with patch("restaurant_management.item_price_sync.connection") as conn:
            with patch(
                "restaurant_management.item_price_sync.get_public_schema_name",
                return_value="public",
            ):
                conn.schema_name = "public"
                item = MagicMock()
                n = sync_kitchen_routing_restaurant_order_items_unit_price(
                    item, Decimal("100")
                )
        self.assertEqual(n, 0)

    def test_sync_skips_without_restaurant_module(self):
        tenant = MagicMock()
        tenant.has_module.return_value = False
        with patch("restaurant_management.item_price_sync.connection") as conn:
            with patch(
                "restaurant_management.item_price_sync.get_public_schema_name",
                return_value="public",
            ):
                conn.schema_name = "tenant1"
                conn.tenant = tenant
                item = MagicMock()
                n = sync_kitchen_routing_restaurant_order_items_unit_price(
                    item, Decimal("100")
                )
        self.assertEqual(n, 0)
        tenant.has_module.assert_called_once_with("restaurant")

    def test_sync_skips_fake_tenant_without_has_module(self):
        fake_tenant = MagicMock(spec=["schema_name"])
        fake_tenant.schema_name = "tenant1"
        company = MagicMock()
        company.has_module.return_value = False
        with patch("restaurant_management.item_price_sync.connection") as conn:
            with patch(
                "restaurant_management.item_price_sync.get_public_schema_name",
                return_value="public",
            ):
                with patch(
                    "company.models.Company.objects.get",
                    return_value=company,
                ):
                    conn.schema_name = "tenant1"
                    conn.tenant = fake_tenant
                    item = MagicMock()
                    n = sync_kitchen_routing_restaurant_order_items_unit_price(
                        item, Decimal("100")
                    )
        self.assertEqual(n, 0)
        company.has_module.assert_called_once_with("restaurant")

    def test_sync_skips_when_tenant_missing(self):
        with patch("restaurant_management.item_price_sync.connection") as conn:
            with patch(
                "restaurant_management.item_price_sync.get_public_schema_name",
                return_value="public",
            ):
                conn.schema_name = "tenant1"
                conn.tenant = None
                item = MagicMock()
                n = sync_kitchen_routing_restaurant_order_items_unit_price(
                    item, Decimal("100")
                )
        self.assertEqual(n, 0)

    @patch(
        "restaurant_management.item_price_sync.transaction.atomic",
        lambda **_: nullcontext(),
    )
    @patch("restaurant_management.item_price_sync.RestaurantOrderItem.objects")
    @patch("restaurant_management.item_price_sync.restaurant_order_item_routes_to_kitchen")
    def test_sync_updates_only_kitchen_routing_lines(self, mock_routes, mock_mgr):
        mock_routes.side_effect = [True, False]
        line1 = MagicMock()
        line1.unit_price = Decimal("50")
        line2 = MagicMock()
        line2.unit_price = Decimal("50")
        mock_qs = MagicMock()
        mock_mgr.filter.return_value.select_related.return_value = mock_qs
        mock_qs.iterator.return_value = iter([line1, line2])

        tenant = MagicMock()
        tenant.has_module.return_value = True
        item = MagicMock()

        with patch("restaurant_management.item_price_sync.connection") as conn:
            with patch(
                "restaurant_management.item_price_sync.get_public_schema_name",
                return_value="public",
            ):
                conn.schema_name = "tenant1"
                conn.tenant = tenant

                n = sync_kitchen_routing_restaurant_order_items_unit_price(
                    item, Decimal("100")
                )

        self.assertEqual(n, 1)
        self.assertEqual(line1.unit_price, Decimal("100"))
        line1.save.assert_called_once()
        line2.save.assert_not_called()
