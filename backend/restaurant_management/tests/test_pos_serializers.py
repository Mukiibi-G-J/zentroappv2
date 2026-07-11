from django.test import SimpleTestCase
from rest_framework.exceptions import ValidationError

from restaurant_management import models
from restaurant_management.serializers import OrderItemModifierSerializer


class OrderItemModifierSerializerTests(SimpleTestCase):
    def test_option_must_belong_to_group(self):
        g1 = models.ModifierGroup(
            name="Size",
            code="SIZE",
            selection_mode="single",
            min_selections=0,
            max_selections=1,
            required=False,
        )
        g1.id = 1
        g2 = models.ModifierGroup(
            name="Milk",
            code="MILK",
            selection_mode="single",
            min_selections=0,
            max_selections=1,
            required=False,
        )
        g2.id = 2
        opt = models.ModifierOption(
            group=g2,
            name="Large",
            code="LG",
        )
        opt.id = 10
        ser = OrderItemModifierSerializer()
        with self.assertRaises(ValidationError):
            ser.validate(
                {
                    "modifier_group": g1,
                    "modifier_option": opt,
                    "order_item": None,
                }
            )
