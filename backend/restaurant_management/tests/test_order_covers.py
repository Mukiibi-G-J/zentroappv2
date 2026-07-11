"""Covers (guest count) on restaurant orders — nullable for "No covers"."""

from django.test import SimpleTestCase

from restaurant_management.serializers import (
    RestaurantOrderCreateSerializer,
    RestaurantOrderSerializer,
)


class RestaurantOrderCoversFieldTests(SimpleTestCase):
    def test_create_serializer_covers_allows_null(self):
        ser = RestaurantOrderCreateSerializer()
        self.assertTrue(ser.fields["covers"].allow_null)

    def test_detail_serializer_covers_allows_null(self):
        ser = RestaurantOrderSerializer()
        self.assertTrue(ser.fields["covers"].allow_null)
