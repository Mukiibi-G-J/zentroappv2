"""Tests for POS quick customer payment (validation + orchestration)."""

from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from payments.quick_customer_payment import (
    QuickCustomerPaymentError,
    _coerce_amount,
    quick_customer_payment,
)
from payments.views import PaymentJournalViewSet


class CoerceAmountTests(SimpleTestCase):
    def test_rejects_missing(self):
        with self.assertRaises(QuickCustomerPaymentError):
            _coerce_amount(None)
        with self.assertRaises(QuickCustomerPaymentError):
            _coerce_amount("")

    def test_rejects_zero_and_negative(self):
        with self.assertRaises(QuickCustomerPaymentError):
            _coerce_amount(0)
        with self.assertRaises(QuickCustomerPaymentError):
            _coerce_amount(-10)

    def test_accepts_positive(self):
        self.assertEqual(_coerce_amount(50000), 50000)
        self.assertEqual(_coerce_amount("12,500"), 12500)


class QuickCustomerPaymentServiceTests(SimpleTestCase):
    def test_requires_customer_id(self):
        with self.assertRaises(QuickCustomerPaymentError) as ctx:
            quick_customer_payment(
                customer_id=None,
                amount=100,
                payment_method_id=1,
                request=MagicMock(),
            )
        self.assertIn("customer_id", ctx.exception.message)

    def test_requires_payment_method_id(self):
        with self.assertRaises(QuickCustomerPaymentError) as ctx:
            quick_customer_payment(
                customer_id=1,
                amount=100,
                payment_method_id=None,
                request=MagicMock(),
            )
        self.assertIn("payment_method_id", ctx.exception.message)

    @patch("payments.quick_customer_payment.Customer")
    def test_customer_not_found(self, mock_customer):
        mock_customer.DoesNotExist = type("DoesNotExist", (Exception,), {})
        mock_customer.objects.get.side_effect = mock_customer.DoesNotExist
        with self.assertRaises(QuickCustomerPaymentError) as ctx:
            quick_customer_payment(
                customer_id=99,
                amount=100,
                payment_method_id=1,
                request=MagicMock(),
            )
        self.assertIn("Customer not found", ctx.exception.message)

    @patch("payments.quick_customer_payment.PaymentMethod")
    @patch("payments.quick_customer_payment.Customer")
    def test_payment_method_not_found(self, mock_customer, mock_pm):
        mock_customer.DoesNotExist = type("DoesNotExist", (Exception,), {})
        mock_customer.objects.get.return_value = MagicMock(pk=1, no="C1", name="A")
        mock_pm.DoesNotExist = type("DoesNotExist", (Exception,), {})
        mock_pm.objects.get.side_effect = mock_pm.DoesNotExist
        with self.assertRaises(QuickCustomerPaymentError) as ctx:
            quick_customer_payment(
                customer_id=1,
                amount=100,
                payment_method_id=9,
                request=MagicMock(),
            )
        self.assertIn("Payment method not found", ctx.exception.message)

    @patch("payments.quick_customer_payment._oldest_open_invoice")
    @patch("payments.quick_customer_payment._customer_outstanding")
    @patch("payments.quick_customer_payment.PaymentMethod")
    @patch("payments.quick_customer_payment.Customer")
    def test_rejects_no_open_balance(
        self, mock_customer, mock_pm, mock_outstanding, mock_invoice
    ):
        mock_customer.DoesNotExist = type("DoesNotExist", (Exception,), {})
        mock_customer.objects.get.return_value = MagicMock(pk=1, no="C1", name="A")
        mock_pm.DoesNotExist = type("DoesNotExist", (Exception,), {})
        mock_pm.objects.get.return_value = MagicMock(pk=1, code="CASH")
        mock_outstanding.return_value = 0
        with self.assertRaises(QuickCustomerPaymentError) as ctx:
            quick_customer_payment(
                customer_id=1,
                amount=100,
                payment_method_id=1,
                request=MagicMock(),
            )
        self.assertIn("no open balance", ctx.exception.message.lower())
        mock_invoice.assert_not_called()


class QuickCustomerPaymentViewTests(SimpleTestCase):
    def test_view_maps_validation_error_to_400(self):
        view = PaymentJournalViewSet()
        request = MagicMock()
        request.data = {"customer_id": 1, "amount": 0, "payment_method_id": 1}
        response = view.quick_customer_payment(request)
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.data)

    def test_view_returns_201_on_success(self):
        view = PaymentJournalViewSet()
        request = MagicMock()
        request.data = {
            "customer_id": 1,
            "amount": 5000,
            "payment_method_id": 1,
        }
        payload = {
            "document_no": "PAY-001",
            "system_id": "abc",
            "amount": 5000,
            "customer_no": "C1",
            "applied_document_no": "INV-1",
            "remaining_balance": 0,
        }
        with patch(
            "payments.quick_customer_payment.quick_customer_payment",
            return_value=payload,
        ):
            response = view.quick_customer_payment(request)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["document_no"], "PAY-001")
