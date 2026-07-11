from django.db import models
from django.core.validators import MinValueValidator

from utils.utils import BaseModel


class ObjectType(models.Model):
    """Categories of objects in the system (Table, Page, Report, etc.)"""

    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, unique=True)
    description = models.TextField(blank=True)
    sort_order = models.IntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "name"]
        verbose_name = "Object Type"
        verbose_name_plural = "Object Types"

    def __str__(self):
        return self.name


class ObjectsManager(models.Manager):
    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .filter(object_subtype__in=["Custom", "Temporary", "Permanent"])
        )


class Objects(BaseModel):
    """
    Model for storing table data objects like the ones shown in the configuration package.

    ``object_id`` uses Business Central numeric IDs for Page objects (e.g. 31 = Item List).
    Zentro Table objects use the 2xxx–5xxx bands from ``populate_objects_table`` to avoid
  collisions with BC page IDs. Full BC table import (page 31 + table 31) requires a future
    composite-key migration.
    """

    OBJECT_TYPE_CHOICES = [
        ("Table", "Table"),
        ("Page", "Page"),
        ("Report", "Report"),
        ("Query", "Query"),
        ("XMLport", "XMLport"),
        ("Enum", "Enum"),
        ("MenuSuite", "MenuSuite"),
    ]

    OBJECT_SUBTYPE_CHOICES = [
        ("Temporary", "Temporary"),
        ("Permanent", "Permanent"),
        ("System", "System"),
        ("Custom", "Custom"),
        ("ThirdParty", "ThirdParty"),
    ]

    object_type = models.CharField(
        max_length=100, choices=OBJECT_TYPE_CHOICES, help_text="Type of the object"
    )
    object_id = models.IntegerField(
        help_text="BC object ID (Page) or Zentro table band ID", primary_key=True
    )
    object_name = models.CharField(
        max_length=255, unique=True, help_text="Name of the object"
    )
    object_caption = models.CharField(
        max_length=255, help_text="Caption/description of the object"
    )
    object_subtype = models.CharField(
        max_length=50,
        choices=OBJECT_SUBTYPE_CHOICES,
        default="Custom",
        help_text="Subtype classification of the object",
    )

    app_label = models.CharField(max_length=255, default="None")

    # Additional metadata fields
    is_active = models.BooleanField(default=True)

    # NEW FIELDS for permission system
    object_type_ref = models.ForeignKey(
        ObjectType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="application_objects",
        help_text="Link to ObjectType for permission system",
    )
    requires_permission = models.BooleanField(
        default=True, help_text="If False, object is accessible to all users"
    )
    related_model = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Full model path (e.g., 'customers.Customer')",
    )

    # TODO: Modal manageer to filter out only subtypes of  custom, temporary and permanent

    objects = ObjectsManager()

    class Meta:
        verbose_name = "Object"
        verbose_name_plural = "Objects"
        unique_together = ["object_type", "object_id"]
        ordering = ["object_type", "object_id"]

    def __str__(self):
        return f"{self.object_name} ({self.object_id})"

    @property
    def full_caption(self):
        """Returns the full caption with object type for display purposes"""
        return f"{self.object_type}: {self.object_caption}"
