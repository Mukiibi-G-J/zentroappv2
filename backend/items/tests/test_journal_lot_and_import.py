from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from items.posting import ItemJournalFinalPoster
from items.tasks import _pick_fifo_lot_candidate, _resolve_unit_amount_for_import
from items.views import TrackingSpecificationViewSet


class _FakeAggregateQuerySet:
    def __init__(self, total=0):
        self._total = total

    def filter(self, **kwargs):
        return self

    def exclude(self, **kwargs):
        return self

    def aggregate(self, **kwargs):
        return {"total": self._total}


class NegativeAdjustmentLotSafetyTests(SimpleTestCase):
    def setUp(self):
        self.viewset = TrackingSpecificationViewSet()
        self.journal = SimpleNamespace(
            id=10,
            entry_type="NegativeAdjustment",
            item=SimpleNamespace(no="ITM-001"),
            location_code_id=3,
            global_dimension_1_id=2,
        )

    @patch("items.views.TrackingSpecification.objects.filter")
    @patch("items.views.ItemLedgerEntries.objects.filter")
    @patch("items.views.ItemJournal.objects.select_related")
    def test_negative_adjustment_lot_validation_rejects_missing_available_qty(
        self, mock_select_related, mock_ile_filter, mock_ts_filter
    ):
        mock_select_related.return_value.get.return_value = self.journal
        mock_ile_filter.return_value = _FakeAggregateQuerySet(total=0)
        mock_ts_filter.return_value = _FakeAggregateQuerySet(total=0)

        with self.assertRaises(ValidationError):
            self.viewset._validate_negative_adjustment_lot(
                {
                    "item_journal": self.journal.id,
                    "lot_no": "LOT-001",
                    "quantity_base": 2,
                }
            )

    @patch("items.views.TrackingSpecification.objects.filter")
    @patch("items.views.ItemLedgerEntries.objects.filter")
    @patch("items.views.ItemJournal.objects.select_related")
    def test_negative_adjustment_lot_validation_rejects_insufficient_qty(
        self, mock_select_related, mock_ile_filter, mock_ts_filter
    ):
        mock_select_related.return_value.get.return_value = self.journal
        # Available 3 in lot.
        mock_ile_filter.return_value = _FakeAggregateQuerySet(total=3)
        # Already requested 2 by sibling specs, incoming 2 -> 4 > 3.
        mock_ts_filter.return_value = _FakeAggregateQuerySet(total=2)

        with self.assertRaises(ValidationError):
            self.viewset._validate_negative_adjustment_lot(
                {
                    "item_journal": self.journal.id,
                    "lot_no": "LOT-001",
                    "quantity_base": 2,
                }
            )

    @patch("items.posting.ItemLedgerEntries.objects.filter")
    @patch("items.models.ItemUnitOfMeasure.objects.get")
    def test_reduce_inventory_from_tracking_specs_consumes_selected_lot_only(
        self, mock_uom_get, mock_ile_filter
    ):
        journal = SimpleNamespace(
            item=SimpleNamespace(no="ITM-001"),
            location_code_id=3,
            global_dimension_1_id=2,
            item_unit_of_measure=SimpleNamespace(id=1, quantity_per_unit=1),
            quantity=2,
        )
        poster = ItemJournalFinalPoster(preview_data={}, journal_entry=journal, user=None)
        mock_uom_get.return_value = SimpleNamespace(quantity_per_unit=1)

        lot_a_entry = SimpleNamespace(remaining_quantity=5, save=MagicMock())
        lot_b_entry = SimpleNamespace(remaining_quantity=6, save=MagicMock())

        lot_a_qs = MagicMock()
        lot_a_qs.filter.return_value = lot_a_qs
        lot_a_qs.order_by.return_value = [lot_a_entry]

        lot_b_qs = MagicMock()
        lot_b_qs.filter.return_value = lot_b_qs
        lot_b_qs.order_by.return_value = [lot_b_entry]

        def _filter_side_effect(*args, **kwargs):
            if kwargs.get("lot_no") == "LOT-A":
                return lot_a_qs
            if kwargs.get("lot_no") == "LOT-B":
                return lot_b_qs
            return lot_a_qs

        mock_ile_filter.side_effect = _filter_side_effect

        specs = [SimpleNamespace(lot_no="LOT-A", serial_no=None, quantity_base=2)]
        poster._reduce_inventory_from_tracking_specs(specs)

        self.assertEqual(lot_a_entry.remaining_quantity, 3)
        self.assertEqual(lot_b_entry.remaining_quantity, 6)
        lot_a_entry.save.assert_called()
        lot_b_entry.save.assert_not_called()


class TrackedNegativeAdjustmentLineSplitTests(SimpleTestCase):
    def test_build_tracked_line_splits_journal_total_per_spec(self):
        from items.services.item_journal_reversal import (
            build_tracked_line_quantity_and_total,
        )

        qty, total = build_tracked_line_quantity_and_total(
            100,
            200,
            2200.0,
            {"quantity": -200, "remaining_quantity": 0, "total": -2200.0},
        )
        self.assertEqual(qty, -100)
        self.assertEqual(total, -1100.0)

    def test_zero_quantity_spec_is_skipped_in_merge_pattern(self):
        from items.services.item_journal_reversal import (
            build_tracked_line_quantity_and_total,
        )

        qty, total = build_tracked_line_quantity_and_total(
            0,
            200,
            2200.0,
            {"quantity": -200},
        )
        self.assertEqual(qty, 0)
        self.assertEqual(total, 0.0)


class AdjustmentImportAutoPickTests(SimpleTestCase):
    def test_pick_fifo_lot_candidate_prefers_oldest_with_sufficient_qty(self):
        candidates = [
            {"lot_no": "LOT-OLD", "available_qty": 3, "first_seen": 1},
            {"lot_no": "LOT-NEW", "available_qty": 10, "first_seen": 2},
        ]
        chosen = _pick_fifo_lot_candidate(candidates, required_base_qty=2)
        self.assertIsNotNone(chosen)
        self.assertEqual(chosen["lot_no"], "LOT-OLD")

    def test_pick_fifo_lot_candidate_returns_none_when_insufficient(self):
        candidates = [{"lot_no": "LOT-1", "available_qty": 1, "first_seen": 1}]
        chosen = _pick_fifo_lot_candidate(candidates, required_base_qty=5)
        self.assertIsNone(chosen)

    @patch("items.tasks.ValueEntry.objects.filter")
    def test_resolve_unit_amount_uses_lot_cost_then_fallbacks(self, mock_ve_filter):
        lot_entry = SimpleNamespace(id=1)
        ve_qs = MagicMock()
        ve_qs.order_by.return_value.first.return_value = SimpleNamespace(cost_per_unit=1450)
        mock_ve_filter.return_value = ve_qs

        resolved = _resolve_unit_amount_for_import(
            raw_unit_amount="",
            lot_entry=lot_entry,
            item=SimpleNamespace(unit_cost=1200, unit_price=1500),
        )
        self.assertEqual(resolved, Decimal("1450"))

    @patch("items.tasks.ValueEntry.objects.filter")
    def test_resolve_unit_amount_fallbacks_to_item_cost(self, mock_ve_filter):
        lot_entry = SimpleNamespace(id=1)
        ve_qs = MagicMock()
        ve_qs.order_by.return_value.first.return_value = None
        mock_ve_filter.return_value = ve_qs

        resolved = _resolve_unit_amount_for_import(
            raw_unit_amount="",
            lot_entry=lot_entry,
            item=SimpleNamespace(unit_cost=1000, unit_price=1200),
        )
        self.assertEqual(resolved, Decimal("1000"))

    def test_resolve_unit_amount_uses_unit_cost_when_amount_blank(self):
        resolved = _resolve_unit_amount_for_import(
            raw_unit_amount="",
            raw_unit_cost="1791.67",
            lot_entry=None,
            item=SimpleNamespace(unit_cost=1000, unit_price=1200),
        )
        self.assertEqual(resolved, Decimal("1791.67"))

    def test_resolve_unit_amount_keeps_import_value_when_provided(self):
        resolved = _resolve_unit_amount_for_import(
            raw_unit_amount="1750",
            lot_entry=None,
            item=SimpleNamespace(unit_cost=1000, unit_price=1200),
        )
        self.assertEqual(resolved, Decimal("1750"))
