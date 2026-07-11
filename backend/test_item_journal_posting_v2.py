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
from items.models import ItemJournal, ItemLedgerEntries, ValueEntry
from financials.models import GeneralLedgerEntry
from company.models import Company
from items.admin import ItemJournalPreviewProcessor, ItemJournalFinalPoster
from django.test import RequestFactory
from django.contrib.messages.storage.fallback import FallbackStorage

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

            # Create a mock request with messages support
            factory = RequestFactory()
            request = factory.post("/admin/items/itemjournal/")
            request.user = user

            # Add messages storage to request
            setattr(request, "session", {})
            messages = FallbackStorage(request)
            setattr(request, "_messages", messages)

            # Test with first 10 entries first
            test_entries = unposted_entries[:10]
            print(f"\nTesting with first {len(test_entries)} entries...")

            # Get initial counts
            initial_ledger_entries = ItemLedgerEntries.objects.count()
            initial_value_entries = ValueEntry.objects.count()
            initial_gl_entries = GeneralLedgerEntry.objects.count()

            print(f"Initial counts:")
            print(f"  - Item Ledger Entries: {initial_ledger_entries}")
            print(f"  - Value Entries: {initial_value_entries}")
            print(f"  - General Ledger Entries: {initial_gl_entries}")

            start_time = time.time()

            # Process each entry individually to track progress
            successful_postings = 0
            failed_postings = 0

            for i, journal_entry in enumerate(test_entries):
                try:
                    print(
                        f"Processing entry {i+1}/{len(test_entries)}: {journal_entry.document_no}"
                    )

                    # Generate receipt number
                    receipt_no = f"RCP-{datetime.now().strftime('%Y%m%d')}-{chr(65+i)}{chr(65+i)}{chr(65+i)}"

                    # Run preview
                    previewer = ItemJournalPreviewProcessor(
                        journal_entry, request, receipt_no
                    )
                    preview_data = previewer.process()

                    if not preview_data or (
                        isinstance(preview_data, dict)
                        and not any(preview_data.values())
                    ):
                        print(f"  - Skipped (validation failed)")
                        failed_postings += 1
                        continue

                    # Run final posting
                    poster = ItemJournalFinalPoster(preview_data, journal_entry, user)
                    poster.post_to_tables()

                    # Update status to Posted
                    journal_entry.status = "Posted"
                    journal_entry.save()

                    successful_postings += 1
                    print(f"  - Posted successfully")

                except Exception as e:
                    print(f"  - Failed: {str(e)}")
                    failed_postings += 1

            end_time = time.time()
            processing_time = end_time - start_time

            # Get final counts
            final_ledger_entries = ItemLedgerEntries.objects.count()
            final_value_entries = ValueEntry.objects.count()
            final_gl_entries = GeneralLedgerEntry.objects.count()

            print(f"\n=== POSTING RESULTS ===")
            print(f"Processing time: {processing_time:.2f} seconds")
            print(
                f"Average time per entry: {processing_time/len(test_entries):.2f} seconds"
            )
            print(f"Successful postings: {successful_postings}")
            print(f"Failed postings: {failed_postings}")

            print(f"\n=== ENTRIES CREATED ===")
            print(
                f"Item Ledger Entries: {final_ledger_entries - initial_ledger_entries} (new)"
            )
            print(f"Value Entries: {final_value_entries - initial_value_entries} (new)")
            print(
                f"General Ledger Entries: {final_gl_entries - initial_gl_entries} (new)"
            )

            # Check final status
            posted_count = ItemJournal.objects.filter(status="Posted").count()
            remaining_unposted = ItemJournal.objects.filter(status="Open").count()

            print(f"\n=== FINAL STATUS ===")
            print(f"Total posted: {posted_count}")
            print(f"Remaining unposted: {remaining_unposted}")

            # Now test with more entries if available
            if remaining_unposted >= 50:
                print(f"\n=== TESTING WITH 50 MORE ENTRIES ===")
                more_entries = ItemJournal.objects.filter(status="Open")[:50]

                # Get counts before second batch
                batch2_initial_ledger = ItemLedgerEntries.objects.count()
                batch2_initial_value = ValueEntry.objects.count()
                batch2_initial_gl = GeneralLedgerEntry.objects.count()

                start_time = time.time()

                successful_batch2 = 0
                failed_batch2 = 0

                for i, journal_entry in enumerate(more_entries):
                    try:
                        receipt_no = f"RCP-{datetime.now().strftime('%Y%m%d')}-{chr(65+i)}{chr(65+i)}{chr(65+i)}"

                        previewer = ItemJournalPreviewProcessor(
                            journal_entry, request, receipt_no
                        )
                        preview_data = previewer.process()

                        if not preview_data or (
                            isinstance(preview_data, dict)
                            and not any(preview_data.values())
                        ):
                            failed_batch2 += 1
                            continue

                        poster = ItemJournalFinalPoster(
                            preview_data, journal_entry, user
                        )
                        poster.post_to_tables()

                        journal_entry.status = "Posted"
                        journal_entry.save()

                        successful_batch2 += 1

                    except Exception as e:
                        failed_batch2 += 1

                end_time = time.time()
                batch2_time = end_time - start_time

                # Final counts
                batch2_final_ledger = ItemLedgerEntries.objects.count()
                batch2_final_value = ValueEntry.objects.count()
                batch2_final_gl = GeneralLedgerEntry.objects.count()

                print(f"Batch 2 Results:")
                print(f"  - Time: {batch2_time:.2f} seconds")
                print(f"  - Average per entry: {batch2_time/50:.2f} seconds")
                print(f"  - Successful: {successful_batch2}")
                print(f"  - Failed: {failed_batch2}")
                print(
                    f"  - New Item Ledger Entries: {batch2_final_ledger - batch2_initial_ledger}"
                )
                print(
                    f"  - New Value Entries: {batch2_final_value - batch2_initial_value}"
                )
                print(f"  - New GL Entries: {batch2_final_gl - batch2_initial_gl}")

                # Overall results
                total_posted = ItemJournal.objects.filter(status="Posted").count()
                total_unposted = ItemJournal.objects.filter(status="Open").count()

                print(f"\n=== OVERALL RESULTS ===")
                print(f"Total posted: {total_posted}")
                print(f"Total unposted: {total_unposted}")
                print(
                    f"Total processing time: {processing_time + batch2_time:.2f} seconds"
                )

    except Company.DoesNotExist:
        print("EKK tenant not found")
    except Exception as e:
        print(f"Error during testing: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    test_item_journal_posting()
 