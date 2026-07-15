"""Tests for prepayment customer rules and POS record_from_pos validation."""
from contextlib import nullcontext
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework.exceptions import ValidationError as DRFValidationError

from prepayment.serializers import PreaymentDetailSerializer
from prepayment.views import PrepaymentViewSet


class PrepaymentSerializerCustomerTests(SimpleTestCase):
    def test_validate_customer_rejects_general(self):
        serializer = PreaymentDetailSerializer()
        customer = MagicMock()
        customer.customer_type = "General"
        with self.assertRaises(DRFValidationError):
            serializer.validate_customer(customer)

    def test_validate_customer_accepts_individual(self):
        serializer = PreaymentDetailSerializer()
        customer = MagicMock()
        customer.customer_type = "Individual"
        self.assertEqual(serializer.validate_customer(customer), customer)


class RecordFromPosViewTests(SimpleTestCase):
    """View validation without database (atomic and serializer mocked)."""

    def test_record_from_pos_rejects_missing_customer(self):
        view = PrepaymentViewSet()
        request = MagicMock()
        request.data = {
            "lines": [{"item": "X", "quantity": "1", "unit_price": "10"}],
            "installment_amount": "5",
            "payment_method_id": 1,
        }
        request.user = MagicMock()
        with patch.object(
            PrepaymentViewSet,
            "_has_permission",
            side_effect=[(True, ""), (True, "")],
        ):
            response = view.record_from_pos(request)
        self.assertEqual(response.status_code, 400)
        self.assertIn("customer", str(response.data).lower())

    def test_record_from_pos_rejects_empty_lines(self):
        view = PrepaymentViewSet()
        request = MagicMock()
        request.data = {
            "customer": 1,
            "lines": [],
            "installment_amount": "10",
            "payment_method_id": 1,
        }
        request.user = MagicMock()
        with patch.object(
            PrepaymentViewSet,
            "_has_permission",
            side_effect=[(True, ""), (True, "")],
        ):
            response = view.record_from_pos(request)
        self.assertEqual(response.status_code, 400)

    def test_record_from_pos_rejects_installment_over_total_after_save(self):
        view = PrepaymentViewSet()
        request = MagicMock()
        request.data = {
            "customer": 1,
            "lines": [{"item": "ITM1", "quantity": "1", "unit_price": "100"}],
            "installment_amount": "500",
            "payment_method_id": 1,
        }
        request.user = MagicMock()

        mock_doc = MagicMock()
        mock_doc.total_amount = Decimal("100.00")
        mock_doc.total_prepayment_invoiced = Decimal("0.00")
        mock_doc.customer = MagicMock()
        mock_doc.customer.customer_type = "Individual"

        mock_pm = MagicMock()
        mock_customer = MagicMock()
        mock_customer.customer_type = "Individual"
        mock_customer.customer_posting_group_id = 1
        mock_customer.general_business_posting_group_id = 1

        with patch.object(
            PrepaymentViewSet,
            "_has_permission",
            side_effect=[(True, ""), (True, "")],
        ):
            with patch(
                "prepayment.views.PaymentMethod.objects.get",
                return_value=mock_pm,
            ):
                with patch(
                    "sales.models.Customer.objects.select_related",
                ) as mock_cust_sr:
                    mock_cust_sr.return_value.get.return_value = mock_customer
                    with patch(
                        "prepayment.views.transaction.atomic",
                        return_value=nullcontext(),
                    ):
                        with patch(
                            "prepayment.views.PreaymentDetailSerializer"
                        ) as mock_ser_cls:
                            mock_ser = MagicMock()
                            mock_ser.is_valid = MagicMock(return_value=True)
                            mock_ser.save = MagicMock(return_value=mock_doc)
                            mock_ser_cls.return_value = mock_ser
                            response = view.record_from_pos(request)

        self.assertEqual(response.status_code, 400)
        self.assertIn("exceeds", str(response.data).lower())
