# Migrate GeneralLedgerEntry from dimension_1/dimension_2 to dimension_set + global_dimension_1/2

import hashlib
import django.db.models.deletion
from django.db import migrations, models


def _signature_from_ids(pairs):
    """Compute signature from (dim_id, val_id) pairs."""
    pairs = sorted((int(d), int(v)) for d, v in pairs if d and v)
    content = "|".join(f"{d}:{v}" for d, v in pairs)
    return hashlib.sha256(content.encode()).hexdigest()


def migrate_dimensions_to_dimension_set(apps, schema_editor):
    """
    For each GeneralLedgerEntry with dimension_1 or dimension_2:
    - Create or reuse DimensionSet from legacy values (using GeneralLedgerSetup mapping)
    - Assign dimension_set_id
    - Copy dimension_1 -> global_dimension_1, dimension_2 -> global_dimension_2
    """
    GeneralLedgerEntry = apps.get_model("financials", "GeneralLedgerEntry")
    GeneralLedgerSetup = apps.get_model("financials", "GeneralLedgerSetup")
    DimensionSet = apps.get_model("dimension", "DimensionSet")
    DimensionSetEntry = apps.get_model("dimension", "DimensionSetEntry")
    Dimension = apps.get_model("dimension", "Dimension")

    gl_setup = GeneralLedgerSetup.objects.first()
    branch_dim = Dimension.objects.filter(code="BRANCH").first()

    # Cache: signature -> dimension_set_id for coalescing
    seen = {}

    for entry in GeneralLedgerEntry.objects.select_related("dimension_1", "dimension_2").iterator():
        if not entry.dimension_1_id and not entry.dimension_2_id:
            continue
        dim_pairs = []
        dim_objs = {}
        if gl_setup and gl_setup.global_dimension_1_id and entry.dimension_1_id:
            dim_objs[gl_setup.global_dimension_1] = entry.dimension_1
            dim_pairs.append((gl_setup.global_dimension_1_id, entry.dimension_1_id))
        elif branch_dim and entry.dimension_1_id:
            dim_objs[branch_dim] = entry.dimension_1
            dim_pairs.append((branch_dim.id, entry.dimension_1_id))
        if gl_setup and gl_setup.global_dimension_2_id and entry.dimension_2_id:
            dim_objs[gl_setup.global_dimension_2] = entry.dimension_2
            dim_pairs.append((gl_setup.global_dimension_2_id, entry.dimension_2_id))
        if not dim_objs:
            continue
        sig = _signature_from_ids(dim_pairs)
        if sig in seen:
            dim_set_id = seen[sig]
        else:
            dim_set = DimensionSet.objects.create(signature=sig)
            for dim, val in dim_objs.items():
                DimensionSetEntry.objects.create(
                    dimension_set=dim_set,
                    dimension_code=dim,
                    dimension_value=val,
                )
            seen[sig] = dim_set.id
            dim_set_id = dim_set.id
        entry.dimension_set_id = dim_set_id
        entry.global_dimension_1_id = entry.dimension_1_id
        entry.global_dimension_2_id = entry.dimension_2_id
        entry.save(update_fields=["dimension_set_id", "global_dimension_1_id", "global_dimension_2_id"])


def reverse_migrate(apps, schema_editor):
    """Reverse: copy global_dim back to dimension_1/2, clear dimension_set."""
    GeneralLedgerEntry = apps.get_model("financials", "GeneralLedgerEntry")
    for entry in GeneralLedgerEntry.objects.iterator():
        entry.dimension_1_id = entry.global_dimension_1_id
        entry.dimension_2_id = entry.global_dimension_2_id
        entry.dimension_set_id = None
        entry.save(update_fields=["dimension_1_id", "dimension_2_id", "dimension_set_id"])


class Migration(migrations.Migration):

    dependencies = [
        ("dimension", "0004_add_dimension_set_models"),
        ("financials", "0005_change_dimension_2_to_dimension_value"),
    ]

    operations = [
        migrations.AddField(
            model_name="generalledgerentry",
            name="dimension_set",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="general_ledger_entries",
                to="dimension.dimensionset",
            ),
        ),
        migrations.AddField(
            model_name="generalledgerentry",
            name="global_dimension_1",
            field=models.ForeignKey(
                blank=True,
                null=True,
                db_index=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="general_ledger_entries_global_dim_1",
                to="dimension.dimensionvalue",
            ),
        ),
        migrations.AddField(
            model_name="generalledgerentry",
            name="global_dimension_2",
            field=models.ForeignKey(
                blank=True,
                null=True,
                db_index=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="general_ledger_entries_global_dim_2",
                to="dimension.dimensionvalue",
            ),
        ),
        migrations.RunPython(migrate_dimensions_to_dimension_set, reverse_migrate),
        migrations.RemoveField(
            model_name="generalledgerentry",
            name="dimension_1",
        ),
        migrations.RemoveField(
            model_name="generalledgerentry",
            name="dimension_2",
        ),
    ]
