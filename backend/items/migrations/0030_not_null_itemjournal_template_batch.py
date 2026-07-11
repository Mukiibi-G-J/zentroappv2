import django.db.models.deletion
from django.db import migrations, models


def backfill_itemjournal_template_and_batch(apps, schema_editor):
    """
    Ensure every ItemJournal row has:
    - journal_template (ITEM vs PHYS. INV.)
    - journal_batch (DEFAULT for that template)

    This runs before enforcing NOT NULL so existing tenants with legacy data
    won't fail the migration.
    """
    ItemJournal = apps.get_model("items", "ItemJournal")
    ItemJournalTemplate = apps.get_model("items", "ItemJournalTemplate")
    ItemJournalBatch = apps.get_model("items", "ItemJournalBatch")

    item_template, _ = ItemJournalTemplate.objects.get_or_create(
        name="ITEM",
        defaults={"description": "Item Journal", "type": "item"},
    )
    item_batch, _ = ItemJournalBatch.objects.get_or_create(
        journal_template=item_template,
        name="DEFAULT",
        defaults={"description": "Default Journal"},
    )

    phys_template, _ = ItemJournalTemplate.objects.get_or_create(
        name="PHYS. INV.",
        defaults={"description": "Physical Inventory", "type": "phys_inventory"},
    )
    phys_batch, _ = ItemJournalBatch.objects.get_or_create(
        journal_template=phys_template,
        name="DEFAULT",
        defaults={"description": "Default Journal"},
    )

    # Backfill rows in chunks, best-effort.
    qs = ItemJournal.objects.all().only(
        "pk",
        "journal_template_id",
        "journal_batch_id",
        "physical_quantity",
        "calculated_quantity",
    )
    for j in qs.iterator(chunk_size=500):
        is_stock_taking = j.physical_quantity is not None or j.calculated_quantity is not None
        target_template = phys_template if is_stock_taking else item_template
        target_batch = phys_batch if target_template == phys_template else item_batch

        update_fields = []
        if j.journal_template_id != target_template.id:
            j.journal_template_id = target_template.id
            update_fields.append("journal_template")
        if j.journal_batch_id != target_batch.id:
            j.journal_batch_id = target_batch.id
            update_fields.append("journal_batch")
        if update_fields:
            j.save(update_fields=update_fields)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    atomic = False
    dependencies = [
        ("items", "0029_itemjournal_dimensions"),
    ]

    operations = [
        migrations.RunPython(backfill_itemjournal_template_and_batch, noop_reverse),
        migrations.AlterField(
            model_name="itemjournal",
            name="journal_template",
            field=models.ForeignKey(
                help_text="Item journal template",
                on_delete=django.db.models.deletion.PROTECT,
                related_name="item_journals",
                to="items.itemjournaltemplate",
                verbose_name="Journal Template",
            ),
        ),
        migrations.AlterField(
            model_name="itemjournal",
            name="journal_batch",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="item_journals",
                to="items.itemjournalbatch",
                verbose_name="Journal Batch",
            ),
        ),
    ]

