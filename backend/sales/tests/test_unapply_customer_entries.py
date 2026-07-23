"""Tests for BC-style Unapply Customer Entries."""

from datetime import date
from unittest.mock import MagicMock

from django.test import SimpleTestCase

from sales.unapply_customer_entries import (
    _build_reversing_dicts,
    assert_customer_ledger_entry_can_apply,
    serialize_unapply_line,
)


class UnapplyCustomerEntriesLogicTests(SimpleTestCase):
    def test_reversing_dicts_negate_amounts(self):
        app = MagicMock()
        app.entry_no = 10
        app.amount = 90000
        app.debit_amount = 90000
        app.credit_amount = 0
        app.entry_type = 'Application'
        app.document_type = 'Payment'
        app.customer = object()
        app.initial_entry_due_date = date(2026, 2, 23)
        app.initial_document_type = 'Invoice'
        app.customer_ledger_entry = object()
        app.applied_customer_ledger_entry_no = 5
        app.global_dimension_1 = object()
        app.dimension_set = object()

        rows = _build_reversing_dicts(
            [app],
            document_no='103042',
            posting_date=date(2026, 2, 23),
            transaction_no='UNAPPLY-TEST',
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['amount'], -90000)
        self.assertEqual(rows[0]['debit_amount'], 0)
        self.assertEqual(rows[0]['credit_amount'], 90000)
        self.assertEqual(rows[0]['document_no'], '103042')
        self.assertEqual(rows[0]['source_entry_no'], 10)

    def test_serialize_unapply_line_shape(self):
        dtld = MagicMock()
        dtld.entry_no = 1
        dtld.posting_date = date(2026, 2, 23)
        dtld.entry_type = 'Application'
        dtld.document_type = 'Payment'
        dtld.document_no = '103042'
        dtld.customer = MagicMock(no='C00020')
        dtld.initial_document_type = 'Invoice'
        dtld.customer_ledger_entry_id = 7
        dtld.customer_ledger_entry = MagicMock(document_no='INV-1')
        dtld.initial_entry_due_date = date(2026, 2, 23)
        dtld.amount = 90000
        dtld.debit_amount = 90000
        dtld.credit_amount = 0
        dtld.applied_customer_ledger_entry_no = 7
        dtld.transaction_no = 'TXN1'

        row = serialize_unapply_line(dtld)
        self.assertEqual(row['EntryNo'], 1)
        self.assertEqual(row['CustomerNo'], 'C00020')
        self.assertEqual(row['InitialDocumentType'], 'Invoice')
        self.assertEqual(row['Amount'], 90000)

    def test_apply_rejects_closed_entry_with_bc_message(self):
        cle = MagicMock()
        cle.open = False
        with self.assertRaises(ValueError) as ctx:
            assert_customer_ledger_entry_can_apply(cle)
        self.assertIn('closed', str(ctx.exception).lower())
        self.assertIn('cannot apply', str(ctx.exception).lower())

    def test_apply_allows_open_entry(self):
        cle = MagicMock()
        cle.open = True
        assert_customer_ledger_entry_can_apply(cle)
