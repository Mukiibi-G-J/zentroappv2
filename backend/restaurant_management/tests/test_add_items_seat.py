"""Seat assignment validation for POS add-items."""

from unittest.mock import MagicMock

from django.test import SimpleTestCase

from restaurant_management.views import _coerce_seat_no_for_add_items


class CoerceSeatNoForAddItemsTests(SimpleTestCase):
    def test_omitted_or_none_is_whole_table(self):
        order = MagicMock(covers=3)
        self.assertEqual(_coerce_seat_no_for_add_items(order, None), (None, None))
        self.assertEqual(_coerce_seat_no_for_add_items(order, ""), (None, None))

    def test_valid_seat_within_covers(self):
        order = MagicMock(covers=3)
        self.assertEqual(_coerce_seat_no_for_add_items(order, 1), (1, None))
        self.assertEqual(_coerce_seat_no_for_add_items(order, 3), (3, None))
        self.assertEqual(_coerce_seat_no_for_add_items(order, "2"), (2, None))

    def test_rejects_seat_when_covers_not_set(self):
        order = MagicMock(covers=None)
        seat, err = _coerce_seat_no_for_add_items(order, 1)
        self.assertIsNone(seat)
        self.assertIsNotNone(err)

    def test_rejects_seat_above_covers(self):
        order = MagicMock(covers=2)
        seat, err = _coerce_seat_no_for_add_items(order, 3)
        self.assertIsNone(seat)
        self.assertIsNotNone(err)

    def test_rejects_non_integer(self):
        order = MagicMock(covers=3)
        seat, err = _coerce_seat_no_for_add_items(order, "x")
        self.assertIsNone(seat)
        self.assertIsNotNone(err)

    def test_rejects_bool(self):
        order = MagicMock(covers=3)
        seat, err = _coerce_seat_no_for_add_items(order, True)
        self.assertIsNone(seat)
        self.assertIsNotNone(err)
