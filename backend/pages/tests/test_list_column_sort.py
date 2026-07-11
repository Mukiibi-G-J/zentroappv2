from django.test import SimpleTestCase
from unittest.mock import MagicMock, patch

from pages.views import (
    _allowed_list_sort_fields,
    _apply_user_list_sort,
    _resolve_list_sort_lookup,
)
from purchases.models import VendorLedger


class ListColumnSortTests(SimpleTestCase):
    def test_resolve_list_sort_lookup_direct_field(self):
        self.assertEqual(_resolve_list_sort_lookup(VendorLedger, 'document_no'), 'document_no')

    def test_resolve_list_sort_lookup_fk_id(self):
        self.assertEqual(_resolve_list_sort_lookup(VendorLedger, 'vendor'), 'vendor')

    def test_resolve_list_sort_lookup_rejects_property(self):
        self.assertIsNone(_resolve_list_sort_lookup(VendorLedger, 'remaining_amount'))

    def test_allowed_list_sort_includes_computed_remaining_amount(self):
        control = MagicMock()
        field = MagicMock()
        field.name = 'remaining_amount'
        with patch('pages.views._serialization_fields', return_value=[field]):
            allowed = _allowed_list_sort_fields(control, VendorLedger)
        self.assertIn('remaining_amount', allowed)

    def test_apply_user_list_sort_rejects_unknown_field(self):
        qs = MagicMock()
        control = MagicMock()
        with patch('pages.views._serialization_fields', return_value=[]):
            result = _apply_user_list_sort(qs, VendorLedger, control, 'not_allowed', 'asc')
        self.assertIs(result, qs)
        qs.order_by.assert_not_called()

    @patch('pages.views._serialization_fields')
    def test_apply_user_list_sort_applies_descending(self, mock_ser_fields):
        qs = MagicMock()
        qs.order_by.return_value = qs
        field = MagicMock()
        field.name = 'document_no'
        mock_ser_fields.return_value = [field]

        _apply_user_list_sort(qs, VendorLedger, MagicMock(), 'document_no', 'desc')
        qs.order_by.assert_called_with('-document_no')

    @patch('pages.views._serialization_fields')
    def test_apply_user_list_sort_annotates_remaining_amount(self, mock_ser_fields):
        qs = MagicMock()
        annotated = MagicMock()
        qs.annotate.return_value = annotated
        annotated.order_by.return_value = annotated
        field = MagicMock()
        field.name = 'remaining_amount'
        mock_ser_fields.return_value = [field]

        result = _apply_user_list_sort(qs, VendorLedger, MagicMock(), 'remaining_amount', 'desc')
        qs.annotate.assert_called_once()
        annotated.order_by.assert_called_with('-_sort_remaining_amount')
        self.assertIs(result, annotated)
