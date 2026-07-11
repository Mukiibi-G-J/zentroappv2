# Migration: Resource.base_unit from CharField to FK to items.UnitOfMeasure (same model as items)

import django.db.models.deletion
from django.db import migrations, models


BASE_UNIT_DISPLAY = {"HOUR": "Hour", "MINUTE": "Minute", "DAY": "Day", "SESSION": "Session"}


def ensure_resource_uom_codes(apps, schema_editor):
    """Ensure HOUR, MINUTE, DAY, SESSION exist in items.UnitOfMeasure."""
    UnitOfMeasure = apps.get_model("items", "UnitOfMeasure")
    for code, desc in BASE_UNIT_DISPLAY.items():
        UnitOfMeasure.objects.get_or_create(
            code=code,
            defaults={"description": desc},
        )


def migrate_base_unit_to_fk(apps, schema_editor):
    """Set Resource.base_unit (FK) from old base_unit (char) code."""
    Resource = apps.get_model("resources", "Resource")
    UnitOfMeasure = apps.get_model("items", "UnitOfMeasure")
    for resource in Resource.objects.all():
        old_code = getattr(resource, "base_unit_old", None)
        if not old_code:
            continue
        try:
            uom = UnitOfMeasure.objects.get(code=old_code)
            resource.base_unit = uom
            resource.save(update_fields=["base_unit"])
        except UnitOfMeasure.DoesNotExist:
            pass


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("items", "0001_initial"),
        ("resources", "0003_resourceunitofmeasure"),
    ]

    operations = [
        migrations.RunPython(ensure_resource_uom_codes, noop_reverse),
        migrations.RenameField(
            model_name="resource",
            old_name="base_unit",
            new_name="base_unit_old",
        ),
        migrations.AddField(
            model_name="resource",
            name="base_unit",
            field=models.ForeignKey(
                blank=True,
                help_text="Unit of measurement for this resource (same model as items)",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="resources_using_as_base",
                to="items.unitofmeasure",
                to_field="code",
                verbose_name="Base Unit",
            ),
        ),
        migrations.RunPython(migrate_base_unit_to_fk, noop_reverse),
        migrations.RemoveField(
            model_name="resource",
            name="base_unit_old",
        ),
    ]
