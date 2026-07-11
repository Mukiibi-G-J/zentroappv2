# Generated manually for backfilling TrackingSpecification source fields

from django.db import migrations
from django.db.models import Q


def backfill_source_defaults(apps, schema_editor):
    """
    Backfill source_id and source_batch_name for existing TrackingSpecification
    records that have null/empty values. Uses item_journal's batch when present,
    otherwise ITEM - DEFAULT as fallback.
    """
    TrackingSpecification = apps.get_model("items", "TrackingSpecification")
    ItemJournalBatch = apps.get_model("items", "ItemJournalBatch")
    ItemJournal = apps.get_model("items", "ItemJournal")

    try:
        item_default_batch = ItemJournalBatch.objects.get(
            journal_template__name="ITEM", name="DEFAULT"
        )
    except ItemJournalBatch.DoesNotExist:
        item_default_batch = None

    specs_to_update = TrackingSpecification.objects.filter(
        source_id__isnull=True
    ).select_related(
        "item_journal",
        "item_journal__journal_batch",
        "item_journal__journal_template",
    )
    for spec in specs_to_update:
        if (
            spec.item_journal_id
            and spec.item_journal
            and spec.item_journal.journal_batch_id
        ):
            batch = spec.item_journal.journal_batch
            spec.source_id = batch
            spec.source_batch_name = (
                f"{batch.journal_template.name} - {batch.name}"
            )
        elif item_default_batch:
            spec.source_id = item_default_batch
            spec.source_batch_name = (
                f"{item_default_batch.journal_template.name} - "
                f"{item_default_batch.name}"
            )
        else:
            continue
        spec.save()


def reverse_backfill(apps, schema_editor):
    """Reverse: set source_id and source_batch_name back to null/empty
    for specs that may have been backfilled (ITEM or PHYS. INV. DEFAULT)."""
    TrackingSpecification = apps.get_model("items", "TrackingSpecification")
    TrackingSpecification.objects.filter(
        Q(
            source_id__journal_template__name="ITEM",
            source_id__name="DEFAULT",
        )
        | Q(
            source_id__journal_template__name="PHYS. INV.",
            source_id__name="DEFAULT",
        )
    ).update(source_id=None, source_batch_name="")


class Migration(migrations.Migration):

    dependencies = [
        ("items", "0016_add_item_journal_batch_default"),
    ]

    operations = [
        migrations.RunPython(backfill_source_defaults, reverse_backfill),
    ]
