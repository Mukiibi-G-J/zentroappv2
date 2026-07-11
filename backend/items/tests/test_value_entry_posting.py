from django.test import SimpleTestCase

from items.enums import DocumentType, EntryType
from items.value_entry_posting import (
    bc_normalize_value_entry_fields,
    entry_type_stock_direction,
    resolve_inventory_entry_type,
)


class ValueEntryPostingSignTests(SimpleTestCase):
    def test_positive_adjustment_from_positive_journal_qty(self):
        """User enters +20 on journal; ILE +20 — stays positive (BC)."""
        out = bc_normalize_value_entry_fields(
            EntryType.PositiveAdjustment.name,
            20,
            100_000,
        )
        self.assertEqual(out["item_ledger_entry_quantity"], 20)
        self.assertEqual(out["cost_amount"], "100000")
        self.assertEqual(entry_type_stock_direction(EntryType.PositiveAdjustment.name), "in")

    def test_negative_adjustment_from_negative_ile(self):
        """ILE already -2 / -10000 — must stay negative (no double negation)."""
        out = bc_normalize_value_entry_fields(
            EntryType.NegativeAdjustment.name,
            -2,
            -10_000,
        )
        self.assertEqual(out["item_ledger_entry_quantity"], -2)
        self.assertEqual(out["invoiced_quantity"], -2)
        self.assertIn(out["cost_amount"], ("-10000", "-10000.0"))
        self.assertEqual(entry_type_stock_direction(EntryType.NegativeAdjustment.name), "out")

    def test_negative_adjustment_from_positive_journal_qty(self):
        """User enters +2 on journal — normalized to -2 / -10000 (BC)."""
        out = bc_normalize_value_entry_fields(
            EntryType.NegativeAdjustment.name,
            2,
            10_000,
        )
        self.assertEqual(out["item_ledger_entry_quantity"], -2)
        self.assertEqual(out["cost_amount"], "-10000")

    def test_matches_bc_example_document_default(self):
        """BC rows: +20/100k in, -2/-10k out."""
        pos = bc_normalize_value_entry_fields(
            EntryType.PositiveAdjustment.name, 20, 100_000
        )
        neg = bc_normalize_value_entry_fields(
            EntryType.NegativeAdjustment.name, -2, -10_000
        )
        self.assertGreater(int(pos["cost_amount"].replace(",", "")), 0)
        self.assertLess(int(neg["cost_amount"].replace(",", "")), 0)

    def test_preserves_fractional_cost_per_unit(self):
        out = bc_normalize_value_entry_fields(
            EntryType.PositiveAdjustment.name,
            1,
            1791.67,
            cost_per_unit=1791.67,
        )
        self.assertEqual(out["cost_per_unit"], 1791.67)
        self.assertEqual(out["cost_amount"], "1791.67")

    def test_direct_cost_purchase_invoice_resolves_to_purchase(self):
        resolved = resolve_inventory_entry_type(
            EntryType.DirectCost.value,
            DocumentType.Purchase.value,
        )
        self.assertEqual(resolved, EntryType.Purchase.value)
        self.assertEqual(
            entry_type_stock_direction(
                EntryType.DirectCost.value, DocumentType.Purchase.value
            ),
            "in",
        )
