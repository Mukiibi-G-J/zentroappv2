from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q
from django_tenants.utils import schema_context
from items.models import ItemJournal, ItemJournalTemplate, ItemJournalBatch


@transaction.atomic
def update_item_journal_templates() -> dict:
    """
    Update all existing ItemJournal records to have correct journal_template and journal_batch.
    
    Returns:
        dict: Summary with updated counts
    """
    # Get or create "ITEM" template and "DEFAULT" batch
    item_template, _ = ItemJournalTemplate.objects.get_or_create(
        name="ITEM",
        defaults={
            "description": "Item Journal",
            "type": "item",
        },
    )
    
    item_batch, _ = ItemJournalBatch.objects.get_or_create(
        journal_template=item_template,
        name="DEFAULT",
        defaults={"description": "Default Journal"},
    )

    # Get or create "PHYS. INV." template and "DEFAULT" batch (stock taking)
    phys_template, _ = ItemJournalTemplate.objects.get_or_create(
        name="PHYS. INV.",
        defaults={"description": "Physical Inventory", "type": "phys_inventory"},
    )
    phys_batch, _ = ItemJournalBatch.objects.get_or_create(
        journal_template=phys_template,
        name="DEFAULT",
        defaults={"description": "Default Journal"},
    )
    
    summary = {
        "updated_to_item": 0,
        "updated_to_phys": 0,
        "updated_batch_only": 0,
        "already_correct": 0,
        "errors": 0,
        "error_details": [],
    }
    
    # Fill missing template/batch only (do not convert existing PHYS. INV. stock taking rows)
    # Use bulk UPDATEs (safe + fast).
    try:
        # 1) Missing template: decide by presence of physical/calculated quantity
        missing_template = ItemJournal.objects.filter(journal_template__isnull=True)
        summary["updated_to_phys"] += missing_template.filter(
            physical_quantity__isnull=False
        ).update(journal_template=phys_template, journal_batch=phys_batch)
        summary["updated_to_phys"] += missing_template.filter(
            calculated_quantity__isnull=False
        ).update(journal_template=phys_template, journal_batch=phys_batch)
        summary["updated_to_item"] += missing_template.filter(
            physical_quantity__isnull=True, calculated_quantity__isnull=True
        ).update(journal_template=item_template, journal_batch=item_batch)
    except Exception:
        # With NOT NULL enforced, this likely won't run; keep for legacy tenants.
        pass

    try:
        # 2) Missing batch: set DEFAULT matching the template
        summary["updated_batch_only"] += ItemJournal.objects.filter(
            journal_template=phys_template, journal_batch__isnull=True
        ).update(journal_batch=phys_batch)
        summary["updated_batch_only"] += ItemJournal.objects.filter(
            journal_template=item_template, journal_batch__isnull=True
        ).update(journal_batch=item_batch)
    except Exception:
        pass

    # 3) Ensure correct DEFAULT batch when template exists but batch doesn't match template
    try:
        summary["updated_batch_only"] += ItemJournal.objects.filter(
            journal_template=phys_template
        ).exclude(journal_batch__journal_template=phys_template).update(
            journal_batch=phys_batch
        )
        summary["updated_batch_only"] += ItemJournal.objects.filter(
            journal_template=item_template
        ).exclude(journal_batch__journal_template=item_template).update(
            journal_batch=item_batch
        )
    except Exception:
        pass

    try:
        summary["already_correct"] = ItemJournal.objects.filter(
            Q(journal_template=item_template, journal_batch=item_batch)
            | Q(journal_template=phys_template, journal_batch=phys_batch)
        ).count()
    except Exception:
        summary["already_correct"] = 0
    
    # Update TrackingSpecification source_template/source_batch away from PHYS. INV. if present
    try:
        updated = TrackingSpecification.objects.filter(
            source_template__name="PHYS. INV."
        ).update(source_template=item_template)
        updated2 = TrackingSpecification.objects.filter(
            source_batch__journal_template__name="PHYS. INV."
        ).update(source_batch=item_batch)
        summary["updated_tracking_specs"] = int(updated or 0) + int(updated2 or 0)
    except Exception:
        pass

    # Delete PHYS. INV. batches/templates if they exist (after reassignment)
    try:
        phys_batches = ItemJournalBatch.objects.filter(journal_template__name="PHYS. INV.")
        summary["deleted_phys_batches"] = phys_batches.count()
        phys_batches.delete()
    except Exception:
        pass
    try:
        phys_templates = ItemJournalTemplate.objects.filter(name="PHYS. INV.")
        summary["deleted_phys_templates"] = phys_templates.count()
        phys_templates.delete()
    except Exception:
        pass

    return summary


class Command(BaseCommand):
    help = "Update all existing ItemJournal records to have correct journal_template and journal_batch"

    def add_arguments(self, parser):
        parser.add_argument(
            "--tenant",
            type=str,
            help="Tenant schema name (optional, defaults to current schema)",
        )

    def handle(self, *args, **options):
        tenant_schema = options.get("tenant")

        def update_journals():
            summary = update_item_journal_templates()
            
            # Display summary
            self.stdout.write("\n" + "=" * 80)
            self.stdout.write(self.style.SUCCESS("UPDATE SUMMARY"))
            self.stdout.write("=" * 80)
            self.stdout.write(f"  OK Updated to ITEM template: {summary['updated_to_item']} journals")
            self.stdout.write(f"  OK Updated to PHYS. INV. template: {summary['updated_to_phys']} journals")
            self.stdout.write(f"  OK Updated batch only: {summary['updated_batch_only']} journals")
            self.stdout.write(f"  OK Already correct: {summary['already_correct']} journals")
            
            if summary["errors"] > 0:
                self.stdout.write(
                    self.style.ERROR(f"  X Errors: {summary['errors']} journals")
                )
                self.stdout.write("\n  Error Details:")
                for error in summary["error_details"]:
                    self.stdout.write(
                        self.style.ERROR(
                            f"    - Journal {error['journal_id']} ({error['document_no']}): {error['error']}"
                        )
                    )
            
            total_processed = (
                summary["updated_to_item"]
                + summary["updated_to_phys"]
                + summary["updated_batch_only"]
                + summary["already_correct"]
                + summary["errors"]
            )
            self.stdout.write(f"\n  Total Processed: {total_processed} journals")

        try:
            if tenant_schema:
                with schema_context(tenant_schema):
                    update_journals()
            else:
                update_journals()
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"X Error updating journals: {str(e)}")
            )
            raise

        self.stdout.write("\n" + "=" * 80)
        self.stdout.write(self.style.SUCCESS("ITEM JOURNAL TEMPLATE UPDATE COMPLETED"))
        self.stdout.write("=" * 80 + "\n")

