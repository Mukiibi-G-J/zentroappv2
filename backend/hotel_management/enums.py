from django.db import models
from django.utils.translation import gettext_lazy as _


class RoomStatus(models.TextChoices):
    AVAILABLE = "available", _("Available")
    OCCUPIED = "occupied", _("Occupied")
    CLEANING = "cleaning", _("Cleaning")
    MAINTENANCE = "maintenance", _("Maintenance")
    OUT_OF_ORDER = "out_of_order", _("Out of Order")
    RESERVED = "reserved", _("Reserved")
