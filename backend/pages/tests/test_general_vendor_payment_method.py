from django.test import SimpleTestCase

from pages.views import (
    _filter_payment_method_relation_qs,
    _is_general_vendor,
    _validate_purchase_invoice_payment_method,
)


class _FakePaymentMethod:
    def __init__(self, code):
        self.code = code


class _FakeVendor:
    def __init__(self, no='', name=''):
        self.no = no
        self.name = name


class _FakeQuerySet:
    def __init__(self, excluded_codes=None):
        self.excluded_codes = excluded_codes or []

    def exclude(self, **kwargs):
        code = kwargs.get('code')
        qs = _FakeQuerySet(excluded_codes=[*self.excluded_codes, code])
        qs.filtered = code
        return qs


class GeneralVendorDetectionTests(SimpleTestCase):
    def test_vendor_000001_is_general(self):
        self.assertTrue(_is_general_vendor(vendor=_FakeVendor(no='VENDOR-000001')))

    def test_vendor_name_general_is_general(self):
        self.assertTrue(_is_general_vendor(vendor=_FakeVendor(no='V-99', name='General Supplier')))

    def test_regular_vendor_is_not_general(self):
        self.assertFalse(_is_general_vendor(vendor=_FakeVendor(no='VENDOR-000002', name='Acme Ltd')))

    def test_vendor_no_string_lookup(self):
        self.assertTrue(_is_general_vendor(vendor_no='VENDOR-000001'))


class GeneralVendorPaymentMethodFilterTests(SimpleTestCase):
    def test_filters_not_paid_for_general_vendor_on_purchase_invoice(self):
        qs = _FakeQuerySet()
        filtered = _filter_payment_method_relation_qs(
            qs,
            source_table='PurchaseInvoice',
            field_name='payment_method',
            record_values={'vendor': 'VENDOR-000001'},
        )
        self.assertEqual(filtered.filtered, 'NOT_PAID')

    def test_keeps_not_paid_for_other_vendors(self):
        qs = _FakeQuerySet()
        filtered = _filter_payment_method_relation_qs(
            qs,
            source_table='PurchaseInvoice',
            field_name='payment_method',
            record_values={'vendor': 'VENDOR-000099'},
        )
        self.assertIs(filtered, qs)


class GeneralVendorPaymentMethodValidationTests(SimpleTestCase):
    def test_rejects_not_paid_for_general_vendor(self):
        with self.assertRaises(ValueError) as ctx:
            _validate_purchase_invoice_payment_method(
                _FakeVendor(no='VENDOR-000001'),
                _FakePaymentMethod('NOT_PAID'),
            )
        self.assertIn('Not Paid Yet', str(ctx.exception))

    def test_allows_cash_for_general_vendor(self):
        _validate_purchase_invoice_payment_method(
            _FakeVendor(no='VENDOR-000001'),
            _FakePaymentMethod('CASH'),
        )

    def test_allows_not_paid_for_regular_vendor(self):
        _validate_purchase_invoice_payment_method(
            _FakeVendor(no='VENDOR-000099'),
            _FakePaymentMethod('NOT_PAID'),
        )
