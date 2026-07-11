# Migration: source_id -> source_template (FK to ItemJournalTemplate)
# source_batch_name -> source_batch (FK to ItemJournalBatch)

from django.db import migrations, models
import django.db.models.deletion


def migrate_source_fields(apps, schema_editor):
    """Migrate source_id -> source_batch_new, add source_template from batch's template."""
    TrackingSpecification = apps.get_model("items", "TrackingSpecification")
    for spec in TrackingSpecification.objects.select_related(
        "source_id", "source_id__journal_template"
    ):
        if spec.source_id:  # old FK to ItemJournalBatch
            spec.source_batch_new_id = spec.source_id_id
            if spec.source_id.journal_template_id:
                spec.source_template_id = spec.source_id.journal_template_id
            spec.save()


def reverse_migrate(apps, schema_editor):
    """Reverse: copy source_batch back to source_id (old field restored in reverse)."""
    pass  # Complex - would need to restore old columns; skip for simplicity


class Migration(migrations.Migration):

    dependencies = [
        ("items", "0018_remove_itemjournalbatch_default_and_more"),
    ]

    operations = [
        # Add new fields (nullable)
        migrations.AddField(
            model_name="trackingspecification",
            name="source_template",
            field=models.ForeignKey(
                blank=True,
                help_text="Journal template (e.g. PHYS. INV., ITEM)",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="tracking_specifications",
                to="items.itemjournaltemplate",
                verbose_name="Source ID",
            ),
        ),
        migrations.AddField(
            model_name="trackingspecification",
            name="source_batch_new",
            field=models.ForeignKey(
                blank=True,
                help_text="Journal batch (e.g. DEFAULT)",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to="items.itemjournalbatch",
                verbose_name="Source Batch Name",
            ),
        ),
        # Migrate data
        migrations.RunPython(migrate_source_fields, reverse_migrate),
        # Remove old source_id and source_batch_name, rename source_batch_new -> source_batch
        migrations.RemoveField(
            model_name="trackingspecification",
            name="source_id",
        ),
        migrations.RemoveField(
            model_name="trackingspecification",
            name="source_batch_name",
        ),
        migrations.RenameField(
            model_name="trackingspecification",
            old_name="source_batch_new",
            new_name="source_batch",
        ),
        migrations.AlterField(
            model_name="trackingspecification",
            name="source_batch",
            field=models.ForeignKey(
                blank=True,
                help_text="Journal batch (e.g. DEFAULT)",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="tracking_specifications",
                to="items.itemjournalbatch",
                verbose_name="Source Batch Name",
            ),
        ),
    ]
