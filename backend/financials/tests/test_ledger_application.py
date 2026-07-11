from django.test import SimpleTestCase
from unittest.mock import MagicMock, patch

from financials.ledger_application import (
    clear_ledger_applies_to,
    collect_applied_customer_ledger_entry_ids,
    collect_applied_vendor_ledger_entry_ids,
    set_ledger_applies_to,
)


class _FakeLedger:
    def __init__(self, **kwargs):
        self.pk = kwargs.get("pk", 1)
        self.applies_to_id = ""


def _mock_vendor_ledger_queries(*, reverse_ids, applies_to_id=None):
    reverse_qs = MagicMock()
    reverse_qs.values_list.return_value = reverse_ids

    source_qs = MagicMock()
    applies_to_values = MagicMock()
    applies_to_values.first.return_value = applies_to_id
    source_qs.values_list.return_value = applies_to_values

    return reverse_qs, source_qs


class LedgerApplicationTests(SimpleTestCase):
    def test_set_and_clear_applies_to(self):
        payment = _FakeLedger(pk=99)
        invoice = _FakeLedger(pk=42)
        set_ledger_applies_to(payment, invoice)
        self.assertEqual(payment.applies_to_id, "42")

        clear_ledger_applies_to(payment)
        self.assertEqual(payment.applies_to_id, "")


class CollectAppliedEntryIdsTests(SimpleTestCase):
    @patch('purchases.models.DetailedVendorLedgerEntry')
    @patch('purchases.models.VendorLedger')
    def test_vendor_applied_entries_excludes_source_entry(self, mock_vl, mock_dtld):
        mock_vl.objects.using.return_value.filter.side_effect = _mock_vendor_ledger_queries(
            reverse_ids=[200],
        )
        mock_dtld.objects.using.return_value.filter.return_value = []

        result = collect_applied_vendor_ledger_entry_ids(150)

        self.assertNotIn(150, result)
        self.assertEqual(result, {200})

    @patch('sales.models.DetailedCustomerLedgerEntry')
    @patch('sales.models.CustomerLedgerEntry')
    def test_customer_applied_entries_excludes_source_entry(self, mock_cle, mock_dtld):
        reverse_qs = MagicMock()
        reverse_qs.values_list.return_value = [100]
        source_qs = MagicMock()
        applies_to_values = MagicMock()
        applies_to_values.first.return_value = None
        source_qs.values_list.return_value = applies_to_values
        mock_cle.objects.using.return_value.filter.side_effect = [reverse_qs, source_qs]
        mock_dtld.objects.using.return_value.filter.return_value = []

        result = collect_applied_customer_ledger_entry_ids(200)

        self.assertNotIn(200, result)
        self.assertEqual(result, {100})

    @patch('purchases.models.DetailedVendorLedgerEntry')
    @patch('purchases.models.VendorLedger')
    def test_vendor_applied_entries_includes_applies_to_target(self, mock_vl, mock_dtld):
        mock_vl.objects.using.return_value.filter.side_effect = _mock_vendor_ledger_queries(
            reverse_ids=[],
            applies_to_id='140',
        )
        mock_dtld.objects.using.return_value.filter.return_value = []

        result = collect_applied_vendor_ledger_entry_ids(150)

        self.assertNotIn(150, result)
        self.assertEqual(result, {140})
