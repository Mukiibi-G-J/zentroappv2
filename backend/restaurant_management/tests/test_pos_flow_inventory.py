from contextlib import nullcontext
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from items.enums import InventoryType, ReplenishmentSystem

from restaurant_management.enums import OrderStatus
from restaurant_management.views import RestaurantOrderViewSet, _menu_item_pos_payload


class RestaurantPosInventoryFlowTests(SimpleTestCase):
    def _request(self):
        r = MagicMock()
        r.META = {}
        return r

    def _make_order(self, *, status):
        order = MagicMock()
        order.status = status
        order.sales_invoice = None
        # MagicMock auto-creates truthy attrs; order_is_closed checks sales_invoice_id.
        order.sales_invoice_id = None
        order.no = "REST-0001"
        order.table = MagicMock()
        order.customer = MagicMock()
        order.customer.no = "CUST-0001"
        # order_items queryset-like
        order.order_items.filter.return_value.exists.return_value = False
        order.order_items.exclude.return_value = []
        order.recalculate_total = MagicMock()
        order.save = MagicMock()
        return order

    def test_add_items_blocks_when_bom_component_insufficient(self):
        view = RestaurantOrderViewSet()
        order = self._make_order(status=OrderStatus.NEW)
        view.get_object = MagicMock(return_value=order)
        view.get_serializer = MagicMock(return_value=MagicMock(data={"id": 1}))

        request = self._request()
        request.user = MagicMock()
        request.user.global_dimension_1 = MagicMock(code="BR1")
        request.data = {
            "order_items": [{"item": "BURGER", "quantity": 2, "unit_price": 10000}]
        }

        loc = MagicMock()
        loc.code = "BR1"

        burger = MagicMock()
        burger.no = "BURGER"
        burger.item_name = "Burger"
        burger.production_bom = MagicMock()

        # component requirements collection is already tested elsewhere; here we just ensure
        # add_items blocks when on-hand < required.
        with patch(
            "restaurant_management.views._resolve_branch_location_for_request",
            return_value=(loc, None),
        ):
            with patch("items.models.Item") as mock_item_model:
                mock_item_model.objects.get.return_value = burger
                bun = MagicMock()
                bun.no = "BUN"
                bun.item_name = "Bun"
                bun.type = InventoryType.Inventory.value
                mock_item_model.objects.filter.return_value.first.return_value = bun
                with patch(
                    "restaurant_management.views._collect_bom_component_requirements",
                    return_value={"BUN": 2},
                ):
                    with patch(
                        "restaurant_management.views._sum_on_hand",
                        return_value=0,
                    ):
                        response = view.add_items(request, pk="1")

        self.assertEqual(response.status_code, 400)
        self.assertIn("insufficient", str(response.data).lower())
        self.assertIn("details", response.data)

    def test_add_items_skips_ledger_check_for_non_inventory_without_bom(self):
        """Menu-style items (Service / Non-Inventory, no BOM) are not branch-ledger tracked."""
        view = RestaurantOrderViewSet()
        order = self._make_order(status=OrderStatus.NEW)
        view.get_object = MagicMock(return_value=order)
        view.get_serializer = MagicMock(
            return_value=MagicMock(data={"id": 1, "order_items": []})
        )
        view.update_order_status_from_items = MagicMock()

        request = self._request()
        request.user = MagicMock()
        request.user.global_dimension_1 = MagicMock(code="BR1")
        request.data = {
            "order_items": [{"item": "DISH1", "quantity": 1, "unit_price": 40000}]
        }

        loc = MagicMock()
        loc.code = "BR1"

        dish = MagicMock()
        dish.no = "DISH1"
        dish.type = InventoryType.NonInventory.value
        dish.production_bom = None
        dish.production_bom_id = None
        dish.replenishment_system = None

        created = MagicMock()

        with patch(
            "restaurant_management.views._resolve_branch_location_for_request",
            return_value=(loc, None),
        ):
            with patch("items.models.Item") as mock_item_model:
                mock_item_model.objects.get.return_value = dish
                with patch(
                    "restaurant_management.views._sum_on_hand",
                    return_value=0,
                ) as mock_sum:
                    with patch(
                        "restaurant_management.views._find_mergeable_pos_order_item",
                        return_value=None,
                    ):
                        with patch(
                            "restaurant_management.views.models.RestaurantOrderItem.objects.create",
                            return_value=created,
                        ):
                            view.request = request
                            view.get_queryset = MagicMock(
                                return_value=MagicMock(
                                    get=MagicMock(return_value=order)
                                )
                            )
                            response = view.add_items(request, pk="1")

        self.assertEqual(response.status_code, 200)
        mock_sum.assert_not_called()

    def test_add_items_creates_order_lines_when_stock_ok(self):
        view = RestaurantOrderViewSet()
        order = self._make_order(status=OrderStatus.NEW)
        view.get_object = MagicMock(return_value=order)
        view.get_serializer = MagicMock(
            return_value=MagicMock(data={"id": 1, "order_items": []})
        )
        view.update_order_status_from_items = MagicMock()

        request = self._request()
        request.user = MagicMock()
        request.user.global_dimension_1 = MagicMock(code="BR1")
        request.data = {
            "order_items": [{"item": "COKE", "quantity": 2, "unit_price": 5000}]
        }

        loc = MagicMock()
        loc.code = "LOC1"

        coke = MagicMock()
        coke.no = "COKE"
        coke.production_bom = None
        coke.production_bom_id = None
        coke.type = InventoryType.Inventory.value
        coke.replenishment_system = None

        created = MagicMock()

        with patch(
            "restaurant_management.views._resolve_branch_location_for_request",
            return_value=(loc, None),
        ):
            with patch("items.models.Item") as mock_item_model:
                mock_item_model.objects.get.return_value = coke
                with patch(
                    "restaurant_management.views._sum_on_hand",
                    return_value=999,
                ):
                    with patch(
                        "restaurant_management.views._find_mergeable_pos_order_item",
                        return_value=None,
                    ):
                        with patch(
                            "restaurant_management.views.models.RestaurantOrderItem.objects.create",
                            return_value=created,
                        ) as mock_create:
                            view.request = request
                            view.get_queryset = MagicMock(
                                return_value=MagicMock(
                                    get=MagicMock(return_value=order)
                                )
                            )
                            response = view.add_items(request, pk="1")

        self.assertEqual(response.status_code, 200)
        mock_create.assert_called_once()
        kwargs = mock_create.call_args.kwargs
        self.assertIs(kwargs["order"], order)
        self.assertIs(kwargs["item"], coke)
        self.assertEqual(kwargs["quantity"], Decimal("2"))
        self.assertEqual(kwargs["unit_price"], Decimal("5000"))

    def test_add_items_merges_quantity_when_mergeable_line_exists(self):
        view = RestaurantOrderViewSet()
        order = self._make_order(status=OrderStatus.NEW)
        view.get_object = MagicMock(return_value=order)
        view.get_serializer = MagicMock(
            return_value=MagicMock(data={"id": 1, "order_items": []})
        )
        view.update_order_status_from_items = MagicMock()

        request = self._request()
        request.user = MagicMock()
        request.user.global_dimension_1 = MagicMock(code="BR1")
        request.data = {
            "order_items": [{"item": "COKE", "quantity": 1, "unit_price": 5000}]
        }

        loc = MagicMock()
        loc.code = "LOC1"

        coke = MagicMock()
        coke.no = "COKE"
        coke.production_bom = None
        coke.production_bom_id = None
        coke.type = InventoryType.Inventory.value
        coke.replenishment_system = None

        class MergeLine:
            def __init__(self):
                self.quantity = Decimal("2")
                self.save_called = 0

            def save(self, *args, **kwargs):
                self.save_called += 1

        existing = MergeLine()

        with patch(
            "restaurant_management.views._resolve_branch_location_for_request",
            return_value=(loc, None),
        ):
            with patch("items.models.Item") as mock_item_model:
                mock_item_model.objects.get.return_value = coke
                with patch(
                    "restaurant_management.views._sum_on_hand",
                    return_value=999,
                ):
                    with patch(
                        "restaurant_management.views._find_mergeable_pos_order_item",
                        return_value=existing,
                    ):
                        with patch(
                            "restaurant_management.views.models.RestaurantOrderItem.objects.create",
                        ) as mock_create:
                            view.request = request
                            view.get_queryset = MagicMock(
                                return_value=MagicMock(
                                    get=MagicMock(return_value=order)
                                )
                            )
                            response = view.add_items(request, pk="1")

        self.assertEqual(response.status_code, 200)
        mock_create.assert_not_called()
        self.assertEqual(existing.quantity, Decimal("3"))
        self.assertEqual(existing.save_called, 1)

    def test_convert_to_invoice_stamps_dimensions_and_branch_location(self):
        view = RestaurantOrderViewSet()
        order = self._make_order(status=OrderStatus.SERVED)
        view.get_object = MagicMock(return_value=order)

        request = self._request()
        request.user = MagicMock()
        request.user.global_dimension_1 = MagicMock(code="BR1")
        request.data = {"combine_orders": False}

        loc = MagicMock()
        loc.code = "BR1"
        invoice_obj = MagicMock()

        with patch(
            "restaurant_management.views._resolve_branch_location_for_request",
            return_value=(loc, None),
        ):
            with patch(
                "restaurant_management.views.transaction.atomic",
                return_value=nullcontext(),
            ):
                with patch(
                    "restaurant_management.views.create_open_sales_invoice_from_restaurant_orders",
                    return_value=invoice_obj,
                ) as mock_create:
                    with patch(
                        "sales.serializers.SalesInvoiceSerializer",
                        return_value=MagicMock(data={"invoice_no": "INV-1"}),
                    ):
                        response = view.convert_to_invoice(request, pk="1")

        self.assertEqual(response.status_code, 200)
        mock_create.assert_called_once()
        args, kwargs = mock_create.call_args
        self.assertIs(args[0], request)
        self.assertEqual(list(args[1]), [order])
        self.assertIs(args[2], order.customer)
        self.assertIs(args[3], loc)
        self.assertFalse(kwargs.get("combine_orders"))

    def test_convert_to_invoice_bom_line_creates_and_finishes_production(self):
        """convert_to_invoice delegates BOM/production work to order_invoice helper."""
        view = RestaurantOrderViewSet()
        order = self._make_order(status=OrderStatus.SERVED)
        view.get_object = MagicMock(return_value=order)

        request = self._request()
        request.user = MagicMock()
        request.user.global_dimension_1 = MagicMock(code="BR1")
        request.data = {"combine_orders": False}

        loc = MagicMock()
        loc.code = "BR1"
        invoice_obj = MagicMock()

        with patch(
            "restaurant_management.views._resolve_branch_location_for_request",
            return_value=(loc, None),
        ):
            with patch(
                "restaurant_management.views.transaction.atomic",
                return_value=nullcontext(),
            ):
                with patch(
                    "restaurant_management.views.create_open_sales_invoice_from_restaurant_orders",
                    return_value=invoice_obj,
                ) as mock_create:
                    with patch(
                        "sales.serializers.SalesInvoiceSerializer",
                        return_value=MagicMock(data={"invoice_no": "INV-1"}),
                    ):
                        response = view.convert_to_invoice(request, pk="1")

        self.assertEqual(response.status_code, 200)
        mock_create.assert_called_once_with(
            request,
            [order],
            order.customer,
            loc,
            combine_orders=False,
        )


class MenuItemPosPayloadTests(SimpleTestCase):
    """POS tree menu line: optional branch on-hand when item is simple inventory."""

    def _mi(self, **item_attrs):
        mi = MagicMock()
        mi.id = 1
        mi.tile_accent_color = ""
        mi.kitchen_facing_name = ""
        mi.display_order = 0
        item = MagicMock()
        item.no = "SKU1"
        item.item_name = "Product"
        item.unit_price = 100
        item.type = InventoryType.Inventory.value
        item.production_bom_id = None
        item.replenishment_system = None
        for k, v in item_attrs.items():
            setattr(item, k, v)
        mi.item = item
        return mi

    def _menu_request(self):
        request = MagicMock()
        request.META = {}
        request.user = MagicMock()
        request.user.is_authenticated = True
        request.user.global_dimension_1 = MagicMock()
        return request

    def test_no_request_omits_stock_fields(self):
        mi = self._mi()
        p = _menu_item_pos_payload(mi)
        self.assertNotIn("pos_stock_tracked", p)

    def test_unauthenticated_omits_stock_fields(self):
        mi = self._mi()
        request = self._menu_request()
        request.user.is_authenticated = False
        p = _menu_item_pos_payload(mi, request=request)
        self.assertNotIn("pos_stock_tracked", p)

    def test_production_bom_parent_not_tracked(self):
        mi = self._mi(production_bom_id=42)
        with patch("restaurant_management.views._sum_on_hand") as mock_sum:
            p = _menu_item_pos_payload(mi, request=self._menu_request())
        mock_sum.assert_not_called()
        self.assertFalse(p["pos_stock_tracked"])

    def test_prod_order_replenishment_not_tracked(self):
        mi = self._mi(replenishment_system=ReplenishmentSystem.ProdOrder.value)
        with patch("restaurant_management.views._sum_on_hand") as mock_sum:
            p = _menu_item_pos_payload(mi, request=self._menu_request())
        mock_sum.assert_not_called()
        self.assertFalse(p["pos_stock_tracked"])

    def test_assembly_replenishment_not_tracked(self):
        mi = self._mi(replenishment_system=ReplenishmentSystem.Assembly.value)
        p = _menu_item_pos_payload(mi, request=self._menu_request())
        self.assertFalse(p["pos_stock_tracked"])

    def test_service_item_not_tracked(self):
        mi = self._mi(type=InventoryType.Service.value)
        p = _menu_item_pos_payload(mi, request=self._menu_request())
        self.assertFalse(p["pos_stock_tracked"])

    def test_tracked_out_of_stock(self):
        mi = self._mi()
        loc = MagicMock()
        branch = MagicMock()
        branch.code = "BR1"
        with patch(
            "restaurant_management.views.get_branch_for_request",
            return_value=branch,
        ):
            with patch("items.models.Location.objects.filter") as mock_filter:
                qs = MagicMock()
                qs.first.return_value = loc
                mock_filter.return_value = qs
                with patch(
                    "restaurant_management.views._sum_on_hand", return_value=0
                ):
                    p = _menu_item_pos_payload(mi, request=self._menu_request())
        self.assertTrue(p["pos_stock_tracked"])
        self.assertEqual(p["pos_available_qty"], 0)
        self.assertTrue(p["pos_out_of_stock"])

    def test_tracked_no_branch_location(self):
        mi = self._mi()
        branch = MagicMock()
        branch.code = "BR1"
        with patch(
            "restaurant_management.views.get_branch_for_request",
            return_value=branch,
        ):
            with patch("items.models.Location.objects.filter") as mock_filter:
                qs = MagicMock()
                qs.first.return_value = None
                mock_filter.return_value = qs
                with patch("restaurant_management.views._sum_on_hand") as mock_sum:
                    p = _menu_item_pos_payload(mi, request=self._menu_request())
        mock_sum.assert_not_called()
        self.assertTrue(p["pos_stock_tracked"])
        self.assertIsNone(p["pos_available_qty"])
        self.assertFalse(p["pos_out_of_stock"])

