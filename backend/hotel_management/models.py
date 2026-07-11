from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from datetime import datetime

from utils.utils import BaseModel
from setup.models import NoSeries, NoSeriesLines
from helpers.helpers import increment_item_number
from .enums import RoomStatus


class RoomType(BaseModel):
    """Room type/category for hotel"""

    no = models.CharField(
        _("No."),
        max_length=50,
        unique=True,
        db_index=True,
        help_text=_("Room type code"),
    )
    name = models.CharField(_("Name"), max_length=100)
    description = models.TextField(_("Description"), blank=True, default="")
    base_rate = models.DecimalField(
        _("Base Rate"),
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text=_("Default nightly rate"),
    )
    max_occupancy = models.IntegerField(_("Max Occupancy"), default=2)
    is_active = models.BooleanField(_("Active"), default=True)

    class Meta:
        verbose_name = _("Room Type")
        verbose_name_plural = _("Room Types")
        ordering = ["name"]

    def __str__(self):
        return f"{self.no} - {self.name}"

    def save(self, *args, **kwargs):
        if not self.no:
            try:
                series = NoSeries.objects.filter(code="ROOM-TYPE").first()
                if series:
                    line = NoSeriesLines.objects.filter(no_series=series).first()
                    if line:
                        if line.last_used_number:
                            self.no = increment_item_number(
                                line.last_used_number, line.increment_by
                            )
                        else:
                            self.no = line.start_number
                        line.last_used_number = self.no
                        line.last_used_date = timezone.now().date()
                        line.save()
                    else:
                        self.no = f"RT-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                else:
                    self.no = f"RT-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            except Exception:
                self.no = f"RT-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        super().save(*args, **kwargs)


class RoomAmenity(BaseModel):
    """Room amenity (WiFi, AC, TV, etc.) - lookup/configuration data"""

    code = models.CharField(
        _("Code"),
        max_length=50,
        unique=True,
        db_index=True,
        help_text=_("Unique amenity code (e.g. WIFI, AC)"),
    )
    name = models.CharField(_("Name"), max_length=100)
    category = models.CharField(
        _("Category"),
        max_length=50,
        default="amenities",
        db_index=True,
    )
    icon = models.CharField(
        _("Icon"),
        max_length=50,
        default="cube",
        help_text=_("Icon identifier for UI"),
    )
    is_active = models.BooleanField(_("Active"), default=True)

    class Meta:
        verbose_name = _("Room Amenity")
        verbose_name_plural = _("Room Amenities")
        ordering = ["category", "name"]

    def __str__(self):
        return f"{self.code} - {self.name}"


class Room(BaseModel):
    """Hotel room"""

    no = models.CharField(
        _("No."),
        max_length=50,
        unique=True,
        db_index=True,
        help_text=_("Room code"),
    )
    room_number = models.CharField(_("Room Number"), max_length=50)
    room_type = models.ForeignKey(
        RoomType,
        on_delete=models.SET_NULL,
        related_name="rooms",
        null=True,
        blank=True,
    )
    floor = models.IntegerField(_("Floor"), default=1)
    status = models.CharField(
        _("Status"),
        max_length=20,
        choices=RoomStatus.choices,
        default=RoomStatus.AVAILABLE,
    )
    notes = models.TextField(_("Notes"), blank=True, default="")
    is_active = models.BooleanField(_("Active"), default=True)

    class Meta:
        verbose_name = _("Room")
        verbose_name_plural = _("Rooms")
        ordering = ["floor", "room_number"]

    def __str__(self):
        return f"{self.room_number} - {self.get_status_display()}"

    def save(self, *args, **kwargs):
        if not self.no:
            try:
                series = NoSeries.objects.filter(code="ROOM").first()
                if series:
                    line = NoSeriesLines.objects.filter(no_series=series).first()
                    if line:
                        if line.last_used_number:
                            self.no = increment_item_number(
                                line.last_used_number, line.increment_by
                            )
                        else:
                            self.no = line.start_number
                        line.last_used_number = self.no
                        line.last_used_date = timezone.now().date()
                        line.save()
                    else:
                        self.no = f"RM-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                else:
                    self.no = f"RM-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            except Exception:
                self.no = f"RM-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        super().save(*args, **kwargs)
