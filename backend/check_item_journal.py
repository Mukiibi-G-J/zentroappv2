#!/usr/bin/env python
import os
import django

# Setup Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from django_tenants.utils import tenant_context
from items.models import ItemJournal
from company.models import Company


def check_item_journal_entries():
    try:
        # Get the EKK tenant
        tenant = Company.objects.get(schema_name="ekk")
        print(f"Tenant: {tenant.name}")

        with tenant_context(tenant):
            total_entries = ItemJournal.objects.count()
            unposted_entries = ItemJournal.objects.filter(status="Open").count()
            posted_entries = ItemJournal.objects.filter(status="Posted").count()

            print(f"Total ItemJournal entries: {total_entries}")
            print(f"Unposted entries: {unposted_entries}")
            print(f"Posted entries: {posted_entries}")

            # Show some sample entries
            if unposted_entries > 0:
                print("\nSample unposted entries:")
                sample_entries = ItemJournal.objects.filter(status="Open")[:5]
                for entry in sample_entries:
                    print(
                        f"  - {entry.document_no}: {entry.item.item_name} ({entry.entry_type}) - Qty: {entry.quantity}"
                    )

            return total_entries, unposted_entries, posted_entries

    except Company.DoesNotExist:
        print("EKK tenant not found")
        return 0, 0, 0
    except Exception as e:
        print(f"Error: {e}")
        return 0, 0, 0


if __name__ == "__main__":
    check_item_journal_entries()
