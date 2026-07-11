"""Home layout serialization for POS pos-tree."""

from django.test import TestCase

from restaurant_management import models
from restaurant_management.views import _home_layout_tile_payload


class HomeLayoutTilePayloadTests(TestCase):
    def setUp(self):
        self.menu = models.Menu.objects.create(name="HL Menu", code="HLMENU1")
        self.page = models.MenuLayoutPage.objects.create(
            menu=self.menu, page_number=1, title="Home"
        )

    def test_empty_tile_payload(self):
        t = models.MenuLayoutTile.objects.create(
            page=self.page,
            row=2,
            column=3,
            row_span=1,
            col_span=1,
            display_order=0,
        )
        p = _home_layout_tile_payload(t)
        self.assertEqual(p["kind"], "empty")
        self.assertEqual(p["row"], 2)
        self.assertEqual(p["column"], 3)

    def test_group_tile_payload(self):
        g = models.MenuDisplayGroup.objects.create(
            menu=self.menu,
            name="Drinks",
            display_order=1,
            tile_color="indigo",
            icon="HiOutlineBeaker",
        )
        t = models.MenuLayoutTile.objects.create(
            page=self.page,
            row=1,
            column=1,
            display_group=g,
            row_span=1,
            col_span=1,
            display_order=0,
        )
        p = _home_layout_tile_payload(t)
        self.assertEqual(p["kind"], "group")
        self.assertEqual(p["display_group"]["name"], "Drinks")
        self.assertEqual(p["display_group"]["id"], g.id)
