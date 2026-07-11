"""Model validation for display groups."""

from django.core.exceptions import ValidationError
from django.test import TestCase

from restaurant_management import models


class MenuDisplayGroupValidationTests(TestCase):
    def setUp(self):
        self.menu = models.Menu.objects.create(name="Test Menu", code="TMENU-DG-1")

    def test_parent_must_match_menu(self):
        other = models.Menu.objects.create(name="Other", code="TMENU-DG-2")
        parent = models.MenuDisplayGroup.objects.create(
            menu=self.menu, name="Parent", display_order=0
        )
        child = models.MenuDisplayGroup(
            menu=other, name="Bad", parent=parent, display_order=0
        )
        with self.assertRaises(ValidationError):
            child.full_clean()

    def test_max_nesting_depth_blocks_fourth_child_level(self):
        """MENU_DISPLAY_GROUP_MAX_DEPTH=4 allows root depth 0..3 (four group levels)."""
        g0 = models.MenuDisplayGroup.objects.create(
            menu=self.menu, name="L0", display_order=0
        )
        g1 = models.MenuDisplayGroup.objects.create(
            menu=self.menu, name="L1", parent=g0, display_order=0
        )
        g2 = models.MenuDisplayGroup.objects.create(
            menu=self.menu, name="L2", parent=g1, display_order=0
        )
        g3 = models.MenuDisplayGroup.objects.create(
            menu=self.menu, name="L3", parent=g2, display_order=0
        )
        too_deep = models.MenuDisplayGroup(
            menu=self.menu, name="L4", parent=g3, display_order=0
        )
        with self.assertRaises(ValidationError):
            too_deep.full_clean()
