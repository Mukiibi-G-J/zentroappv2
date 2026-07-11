# Some tenant schemas never received dimension_dimensionset / dimension_dimensionsetentry
# (migration 0004 recorded but tables landed in public). Create them in the tenant schema
# and repair cross-schema FKs when tables exist but point at public.dimension_*.

from django.db import migrations

from dimension.schema_repair import ensure_dimensionset_tables


class Migration(migrations.Migration):
    dependencies = [
        ("dimension", "0010_repair_dimensionsetentry_fks"),
    ]

    operations = [
        migrations.RunPython(
            ensure_dimensionset_tables,
            migrations.RunPython.noop,
        ),
    ]
