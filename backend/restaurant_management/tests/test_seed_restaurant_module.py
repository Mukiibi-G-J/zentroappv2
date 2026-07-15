"""Tests for seed_restaurant_module (pipeline + static config; no DB required)."""

from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import SimpleTestCase


class SeedRestaurantModuleTests(SimpleTestCase):
    @patch("pages.restaurant_seed.seed_restaurant_pages")
    @patch("receipt_templates.seed.seed_receipt_templates", return_value=(7, 0))
    @patch(
        "restaurant_management.management.commands.seed_restaurant_module._ensure_user_groups"
    )
    @patch(
        "restaurant_management.management.commands.seed_restaurant_module._ensure_restaurant_roles"
    )
    @patch(
        "restaurant_management.management.commands.seed_restaurant_module._apply_permission_sets"
    )
    @patch(
        "restaurant_management.management.commands.seed_restaurant_module.call_command"
    )
    @patch(
        "restaurant_management.management.commands.seed_restaurant_module._ensure_number_series",
        return_value=(0, 0),
    )
    def test_command_runs_series_menu_permissions_and_groups(
        self,
        _m_series,
        m_call,
        m_perm,
        m_roles,
        m_groups,
        m_receipt_templates,
        m_pages,
    ):
        call_command("seed_restaurant_module", stdout=StringIO())
        subcommands = [c.args[0] for c in m_call.call_args_list]
        self.assertEqual(
            subcommands,
            ["seed_service_menu_no_series", "populate_page_objects"],
        )
        m_receipt_templates.assert_called_once()
        m_pages.assert_called_once()
        m_perm.assert_called_once()
        m_roles.assert_called_once()
        m_groups.assert_called_once()

    @patch("pages.restaurant_seed.seed_restaurant_pages")
    @patch("receipt_templates.seed.seed_receipt_templates", return_value=(7, 0))
    @patch(
        "restaurant_management.management.commands.seed_restaurant_module._ensure_user_groups"
    )
    @patch(
        "restaurant_management.management.commands.seed_restaurant_module._ensure_restaurant_roles"
    )
    @patch(
        "restaurant_management.management.commands.seed_restaurant_module._apply_permission_sets"
    )
    @patch(
        "restaurant_management.management.commands.seed_restaurant_module.call_command"
    )
    @patch(
        "restaurant_management.management.commands.seed_restaurant_module._ensure_number_series",
        return_value=(0, 0),
    )
    def test_skip_permissions_skips_permission_helpers(
        self,
        _m_series,
        m_call,
        m_perm,
        m_roles,
        m_groups,
        m_receipt_templates,
        m_pages,
    ):
        call_command(
            "seed_restaurant_module",
            skip_permissions=True,
            stdout=StringIO(),
        )
        m_call.assert_called_once_with("seed_service_menu_no_series")
        m_receipt_templates.assert_called_once()
        m_pages.assert_not_called()
        m_perm.assert_not_called()
        m_roles.assert_not_called()
        m_groups.assert_not_called()

    @patch("pages.restaurant_seed.seed_restaurant_pages")
    @patch("receipt_templates.seed.seed_receipt_templates", return_value=(7, 0))
    @patch(
        "restaurant_management.management.commands.seed_restaurant_module._ensure_user_groups"
    )
    @patch(
        "restaurant_management.management.commands.seed_restaurant_module._ensure_restaurant_roles"
    )
    @patch(
        "restaurant_management.management.commands.seed_restaurant_module._apply_permission_sets"
    )
    @patch(
        "restaurant_management.management.commands.seed_restaurant_module.call_command"
    )
    @patch(
        "restaurant_management.management.commands.seed_restaurant_module._ensure_number_series",
        return_value=(0, 0),
    )
    def test_skip_groups_still_applies_permissions(
        self,
        _m_series,
        m_call,
        m_perm,
        m_roles,
        m_groups,
        m_receipt_templates,
        m_pages,
    ):
        call_command(
            "seed_restaurant_module",
            skip_groups=True,
            stdout=StringIO(),
        )
        subcommands = [c.args[0] for c in m_call.call_args_list]
        self.assertEqual(
            subcommands,
            ["seed_service_menu_no_series", "populate_page_objects"],
        )
        m_pages.assert_called_once()
        m_perm.assert_called_once()
        m_roles.assert_called_once()
        m_groups.assert_not_called()

    @patch("pages.restaurant_seed.seed_restaurant_pages")
    @patch("receipt_templates.seed.seed_receipt_templates", return_value=(7, 0))
    @patch(
        "restaurant_management.management.commands.seed_restaurant_module._ensure_user_groups"
    )
    @patch(
        "restaurant_management.management.commands.seed_restaurant_module._ensure_restaurant_roles"
    )
    @patch(
        "restaurant_management.management.commands.seed_restaurant_module._apply_permission_sets"
    )
    @patch(
        "restaurant_management.management.commands.seed_restaurant_module.call_command"
    )
    @patch(
        "restaurant_management.management.commands.seed_restaurant_module._ensure_number_series",
        return_value=(0, 0),
    )
    def test_skip_receipt_templates_skips_receipt_seed(
        self,
        _m_series,
        m_call,
        m_perm,
        m_roles,
        m_groups,
        m_receipt_templates,
        m_pages,
    ):
        call_command(
            "seed_restaurant_module",
            skip_receipt_templates=True,
            stdout=StringIO(),
        )
        m_receipt_templates.assert_not_called()
        m_pages.assert_called_once()
        m_perm.assert_called_once()

    def test_restaurant_full_lists_distinct_pages(self):
        from restaurant_management.management.commands import (
            seed_restaurant_module as mod,
        )

        full = next(x for x in mod.RESTAURANT_PERMISSION_SETS if x[0] == "RESTAURANT_FULL")
        pages = [p for p, flags in full[3] if flags]
        # Legacy SPA routes + page-engine pages
        self.assertEqual(len(pages), 21)
        self.assertEqual(len(set(pages)), 21)
