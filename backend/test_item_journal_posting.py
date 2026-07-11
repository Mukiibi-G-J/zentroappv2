#!/usr/bin/env python
import os
import django
import time
from datetime import datetime

# Setup Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from django_tenants.utils import tenant_context
from django.contrib.auth import get_user_model
from items.models import ItemJournal
from company.models import Company
from items.admin import postItemJournalReFactor
from django.contrib import messages
from django.test import RequestFactory

User = get_user_model()


def test_item_journal_posting():
    try:
        # Get the EKK tenant
        tenant = Company.objects.get(schema_name="ekk")
        print(f"Testing ItemJournal posting for tenant: {tenant.name}")

        with tenant_context(tenant):
            # Get unposted entries
            unposted_entries = ItemJournal.objects.filter(status="Open")
            total_unposted = unposted_entries.count()

            print(f"Found {total_unposted} unposted entries")

            if total_unposted == 0:
                print("No unposted entries found to test")
                return

            # Get a user for the request
            user = User.objects.first()
            if not user:
                print("No user found")
                return

            print(f"Using user: {user.username}")

            # Create a mock request
            factory = RequestFactory()
            request = factory.post("/admin/items/itemjournal/")
            request.user = user

            # Test with first 10 entries first
            test_entries = unposted_entries[:10]
            print(f"\nTesting with first {len(test_entries)} entries...")

            start_time = time.time()

            # Call the posting function
            postItemJournalReFactor(None, request, test_entries)

            end_time = time.time()
            processing_time = end_time - start_time

            print(f"\nPosting completed in {processing_time:.2f} seconds")
            print(
                f"Average time per entry: {processing_time/len(test_entries):.2f} seconds"
            )

            # Check results
            posted_count = ItemJournal.objects.filter(status="Posted").count()
            remaining_unposted = ItemJournal.objects.filter(status="Open").count()

            print(f"\nResults:")
            print(f"  - Entries posted: {posted_count}")
            print(f"  - Remaining unposted: {remaining_unposted}")

            # Now test with more entries if available
            if remaining_unposted >= 50:
                print(f"\nTesting with 50 more entries...")
                more_entries = ItemJournal.objects.filter(status="Open")[:50]

                start_time = time.time()
                postItemJournalReFactor(None, request, more_entries)
                end_time = time.time()

                processing_time = end_time - start_time
                print(f"Posting 50 entries completed in {processing_time:.2f} seconds")
                print(f"Average time per entry: {processing_time/50:.2f} seconds")

                # Final results
                final_posted = ItemJournal.objects.filter(status="Posted").count()
                final_unposted = ItemJournal.objects.filter(status="Open").count()

                print(f"\nFinal Results:")
                print(f"  - Total posted: {final_posted}")
                print(f"  - Total unposted: {final_unposted}")

    except Company.DoesNotExist:
        print("EKK tenant not found")
    except Exception as e:
        print(f"Error during testing: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    test_item_journal_posting()
