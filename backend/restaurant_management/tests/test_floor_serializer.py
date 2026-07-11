"""FloorSerializer validation (location required on create / when missing on instance)."""

from django.test import TestCase

from items.models import Location
from restaurant_management import models
from restaurant_management.serializers import FloorSerializer


class FloorSerializerLocationTests(TestCase):
    def test_create_requires_location(self):
        loc = Location.objects.create(code="TLOC-FLOOR-1", description="Test Site")
        ser = FloorSerializer(data={"name": "Main dining", "location": loc.id})
        self.assertTrue(ser.is_valid(), ser.errors)
        floor = ser.save()
        self.assertEqual(floor.location_id, loc.id)

    def test_create_without_location_fails(self):
        ser = FloorSerializer(data={"name": "Orphan floor"})
        self.assertFalse(ser.is_valid())
        self.assertIn("location", ser.errors)

    def test_update_legacy_without_location_requires_location_in_payload(self):
        loc = Location.objects.create(code="TLOC-FLOOR-2", description="Fix site")
        floor = models.Floor.objects.create(name="Legacy", no="F-LEG-SER-1")
        floor.location = None
        floor.save(update_fields=["location"])

        ser = FloorSerializer(
            instance=floor,
            data={"description": "only desc"},
            partial=True,
        )
        self.assertFalse(ser.is_valid())
        self.assertIn("location", ser.errors)

        ser2 = FloorSerializer(
            instance=floor,
            data={"location": loc.id},
            partial=True,
        )
        self.assertTrue(ser2.is_valid(), ser2.errors)
        ser2.save()
        floor.refresh_from_db()
        self.assertEqual(floor.location_id, loc.id)

    def test_update_with_location_allows_other_partial_fields(self):
        loc = Location.objects.create(code="TLOC-FLOOR-3", description="Site B")
        floor = models.Floor.objects.create(name="With loc", no="F-WL-1")
        floor.location = loc
        floor.save()

        ser = FloorSerializer(
            instance=floor,
            data={"display_order": 99},
            partial=True,
        )
        self.assertTrue(ser.is_valid(), ser.errors)
        ser.save()
        floor.refresh_from_db()
        self.assertEqual(floor.display_order, 99)
