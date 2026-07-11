from types import SimpleNamespace
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from items.models import _parse_positive_quantity_base, _validate_purchase_tracking_quantity


class TrackingSpecificationQuantityValidationTests(SimpleTestCase):
    def test_parse_positive_quantity_base_accepts_decimal_strings(self):
        self.assertEqual(_parse_positive_quantity_base("9.0"), 9)
        self.assertEqual(_parse_positive_quantity_base("9"), 9)
        self.assertEqual(_parse_positive_quantity_base(9), 9)

    def test_parse_positive_quantity_base_rejects_invalid_values(self):
        with self.assertRaises(ValidationError) as ctx:
            _parse_positive_quantity_base("")
        self.assertIn("Enter a valid quantity (base).", str(ctx.exception))

    @patch("items.models.TrackingSpecification.objects.filter")
    @patch("items.models.apps.get_model")
    def test_validate_purchase_tracking_quantity_rejects_over_assignment(
        self, mock_get_model, mock_filter
    ):
        purchase_line = SimpleNamespace(
            id=5,
            quantity=1,
            item_unit_of_measure_id=1,
            item_unit_of_measure=SimpleNamespace(quantity_per_unit=1),
        )
        mock_get_model.return_value.objects.select_related.return_value.get.return_value = (
            purchase_line
        )
        mock_filter.return_value.exclude.return_value.aggregate.return_value = {"total": 0}

        with self.assertRaises(ValidationError) as ctx:
            _validate_purchase_tracking_quantity(purchase_line, 9, exclude_pk=99)

        self.assertIn(
            "Quantity in tracking specification must match purchase line quantity.",
            str(ctx.exception),
        )
        self.assertIn("Expected: 1, assigned: 9.", str(ctx.exception))
