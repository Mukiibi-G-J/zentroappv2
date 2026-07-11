# Generated manually for Resource Unit of Measure

import django.db.models.deletion
import utils.utils
import uuid
from django.db import migrations, models


BASE_UNIT_DISPLAY = {"HOUR": "Hour", "MINUTE": "Minute", "DAY": "Day", "SESSION": "Session"}


def backfill_resource_units_of_measure(apps, schema_editor):
    """Create ResourceUnitOfMeasure for each existing Resource from its base_unit."""
    Resource = apps.get_model("resources", "Resource")
    ResourceUnitOfMeasure = apps.get_model("resources", "ResourceUnitOfMeasure")
    UnitOfMeasure = apps.get_model("items", "UnitOfMeasure")
    for resource in Resource.objects.all():
        if not resource.base_unit:
            continue
        desc = BASE_UNIT_DISPLAY.get(resource.base_unit, resource.base_unit)
        uom, _ = UnitOfMeasure.objects.get_or_create(
            code=resource.base_unit,
            defaults={"description": desc},
        )
        ResourceUnitOfMeasure.objects.get_or_create(
            resource=resource,
            unit_of_measure=uom,
            defaults={"quantity_per_unit": 1, "default": True},
        )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("items", "0001_initial"),
        ("resources", "0002_remove_resource_resources_r_dimensi_a67461_idx_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="ResourceUnitOfMeasure",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="Created At")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Updated At")),
                ("system_id", utils.utils.UUIField(db_index=True, default=uuid.uuid4, editable=False, max_length=36, unique=True, verbose_name="System ID")),
                ("quantity_per_unit", models.PositiveIntegerField(default=1, help_text="Quantity per unit (1 for base unit).", verbose_name="Quantity per Unit")),
                ("default", models.BooleanField(default=False, help_text="Default unit of measure for this resource (typically the base unit).", verbose_name="Default")),
                ("resource", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="resource_units_of_measure", to="resources.resource", verbose_name="Resource")),
                ("unit_of_measure", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="resource_unit_of_measure_set", to="items.unitofmeasure", verbose_name="Unit of Measure")),
            ],
            options={
                "verbose_name": "Resource Unit of Measure",
                "verbose_name_plural": "Resource Units of Measure",
                "ordering": ["resource", "-default", "unit_of_measure__code"],
                "unique_together": {("resource", "unit_of_measure")},
            },
        ),
        migrations.RunPython(backfill_resource_units_of_measure, noop_reverse),
    ]
