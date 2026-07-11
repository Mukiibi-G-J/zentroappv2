# Repair dimension_dimensionsetentry FKs that incorrectly reference public.dimension_*.

from django.db import migrations

from dimension.schema_repair import repair_dimensionsetentry_fks


def _forwards(apps, schema_editor):
    repair_dimensionsetentry_fks(schema_editor)


class Migration(migrations.Migration):
    dependencies = [
        ("dimension", "0009_ensure_expenses_dimension_foreign_keys"),
    ]

    operations = [
        migrations.RunPython(_forwards, migrations.RunPython.noop),
    ]
