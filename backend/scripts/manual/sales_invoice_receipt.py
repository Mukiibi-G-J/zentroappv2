#!/usr/bin/env python
"""
Test script to verify sales invoice creation with payment fields
"""
import os
import sys
import django

# Add the project directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Set up Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from sales.models import SalesInvoice, SalesInvoiceLine
from items.models import Item
from customers.models import Customer
from django.contrib.auth import get_user_model


def test_sales_invoice_creation():
    """Test creating a sales invoice with payment fields"""
    try:
        print("Testing sales invoice creation...")

        # Get or create a test customer
        customer, created = Customer.objects.get_or_create(
            name="Test Customer",
            defaults={"phone": "1234567890", "email": "test@example.com"},
        )
        print(f"Customer: {customer.name} (ID: {customer.id})")

        # Get or create a test item
        item, created = Item.objects.get_or_create(
            no="TEST001",
            defaults={"item_name": "Test Item", "unit_price": 1000, "inventory": 100},
        )
        print(f"Item: {item.item_name} (ID: {item.id})")

        # Create a sales invoice
        invoice = SalesInvoice.objects.create(
            customer=customer,
            document_date="2024-01-01",
            status="Open",
            amount_received=1500,
            change_amount=500,
        )
        print(f"Created invoice ID: {invoice.id}")
        print(f"Amount received: {invoice.amount_received}")
        print(f"Change amount: {invoice.change_amount}")

        # Create a line item
        line = SalesInvoiceLine.objects.create(
            sales_invoice=invoice,
            item=item,
            quantity=1,
            unit_price=1000,
            total_amount=1000,
        )
        print(f"Created line item ID: {line.id}")

        # Refresh and check properties
        invoice.refresh_from_db()
        print(f"After refresh - Total amount: {invoice.total_amount}")
        print(f"After refresh - Amount received: {invoice.amount_received}")
        print(f"After refresh - Change amount: {invoice.change_amount}")

        # Test serializer
        from sales.serializers import SalesInvoiceSerializer

        serializer = SalesInvoiceSerializer(invoice)
        data = serializer.data
        print(f"Serialized amount_received: {data.get('amount_received')}")
        print(f"Serialized change_amount: {data.get('change_amount')}")
        print(f"Serialized total_amount: {data.get('total_amount')}")

        print("Test completed successfully!")
        return True

    except Exception as e:
        print(f"Test failed with error: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    test_sales_invoice_creation()
