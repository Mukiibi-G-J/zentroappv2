"""
Script to clean up duplicate CustomerLedgerEntry records created by the NOT_PAID payment method bug.

This script removes duplicate payment entries that were incorrectly created when posting
invoices with the NOT_PAID payment method.

Usage:
    python manage.py shell < cleanup_duplicate_ledger_entries.py

    Or for a specific tenant:
    python manage.py shell --schema=hardwareworld < cleanup_duplicate_ledger_entries.py
"""

from django.db.models import Count
from sales.models import CustomerLedgerEntry


def cleanup_duplicate_entries():
    """
    Find and remove duplicate CustomerLedgerEntry records.

    The bug created two entries with the same document_no and customer:
    1. An Invoice entry (correct)
    2. A Payment entry (incorrect - should only exist for cash payments)

    This script removes the incorrect Payment entries for NOT_PAID invoices.
    """
    print("🔍 Searching for duplicate CustomerLedgerEntry records...")

    # Find document_no + customer combinations that have duplicates
    duplicates = (
        CustomerLedgerEntry.objects.values("document_no", "customer")
        .annotate(count=Count("id"))
        .filter(count__gt=1)
    )

    total_duplicates = len(duplicates)
    print(f"Found {total_duplicates} sets of duplicate entries")

    if total_duplicates == 0:
        print("✅ No duplicates found. Database is clean!")
        return

    deleted_count = 0

    for dup in duplicates:
        document_no = dup["document_no"]
        customer_id = dup["customer"]
        count = dup["count"]

        print(f"\n📋 Processing document {document_no} (Customer ID: {customer_id})")
        print(f"   Found {count} entries")

        # Get all entries for this document + customer
        entries = CustomerLedgerEntry.objects.filter(
            document_no=document_no, customer_id=customer_id
        ).order_by("id")

        # Display the entries
        for entry in entries:
            print(
                f"   - ID {entry.id}: {entry.document_type} | Amount: {entry.amount} | Open: {entry.open}"
            )

        # Keep the Invoice entry, delete Payment entries
        invoice_entry = entries.filter(document_type="Invoice").first()
        payment_entries = entries.filter(document_type="Payment")

        if invoice_entry and payment_entries.exists():
            print(f"   ✅ Keeping Invoice entry ID {invoice_entry.id}")
            print(f"   ❌ Deleting {payment_entries.count()} Payment entry/entries:")

            for payment in payment_entries:
                print(f"      - Deleting Payment entry ID {payment.id}")
                payment.delete()
                deleted_count += 1
        else:
            print(f"   ⚠️  Skipping - unexpected entry types")

    print(f"\n{'='*60}")
    print(f"✨ Cleanup complete!")
    print(f"   - Total duplicate sets found: {total_duplicates}")
    print(f"   - Entries deleted: {deleted_count}")
    print(f"{'='*60}")


if __name__ == "__main__":
    # Confirmation prompt
    print("=" * 60)
    print("CLEANUP DUPLICATE CUSTOMER LEDGER ENTRIES")
    print("=" * 60)
    print("\nThis script will remove duplicate Payment entries that were")
    print("incorrectly created for invoices with NOT_PAID payment method.")
    print("\nOnly the correct Invoice entries will be kept.")

    confirm = input("\nProceed with cleanup? (yes/no): ").strip().lower()

    if confirm == "yes":
        cleanup_duplicate_entries()
    else:
        print("❌ Cleanup cancelled.")
