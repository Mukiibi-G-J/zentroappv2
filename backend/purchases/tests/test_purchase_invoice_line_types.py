from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from purchases.admin import PurchaseInvoiceProcessor
from purchases.models import PurchaseInvoiceLine


class PurchaseInvoiceLineTypeValidationTests(SimpleTestCase):
    def test_item_line_requires_item(self):
        line = PurchaseInvoiceLine(type="item")
        with self.assertRaises(ValidationError) as ctx:
            line.clean()
        self.assertIn("item", ctx.exception.message_dict)

    def test_resource_line_rejects_item_fk(self):
        line = PurchaseInvoiceLine(type="resource", resource_id=1, item_id=1)
        with self.assertRaises(ValidationError) as ctx:
            line.clean()
        self.assertIn("item", ctx.exception.message_dict)

    def test_gl_account_line_requires_gl_account(self):
        line = PurchaseInvoiceLine(type="gl_account")
        with self.assertRaises(ValidationError) as ctx:
            line.clean()
        self.assertIn("gl_account", ctx.exception.message_dict)

    def test_gl_account_line_rejects_resource_fk(self):
        line = PurchaseInvoiceLine(type="gl_account", gl_account_id=1, resource_id=1)
        with self.assertRaises(ValidationError) as ctx:
            line.clean()
        self.assertIn("resource", ctx.exception.message_dict)


class PurchaseInvoiceProcessorLineTypeTests(SimpleTestCase):
    def test_line_type_defaults_to_item(self):
        class Line:
            type = None

        self.assertEqual(PurchaseInvoiceProcessor._line_type(Line()), "item")

    def test_line_type_reads_explicit_value(self):
        class Line:
            type = "resource"

        self.assertEqual(PurchaseInvoiceProcessor._line_type(Line()), "resource")
