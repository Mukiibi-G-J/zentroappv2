"""
Example usage of the PaymentJournal model with updated enums and GenericForeignKey.

This file demonstrates how to use the PaymentJournal model with:
1. Updated enum values in title case format
2. GenericForeignKey for applies_to_doc that can reference Customer, Vendor, or any other model
"""

from decimal import Decimal
from django.contrib.contenttypes.models import ContentType
from payments.models import PaymentJournal
from payments.enums import DocumentType, AccountType, PaymentStatus, ApplicationStatus


# Example: Creating a customer payment
def create_customer_payment():
    """Example of creating a customer payment"""

    # You would need to get actual instances from your database
    # customer = Customer.objects.get(id=1)
    # payment_method = PaymentMethod.objects.get(id=1)
    # gl_account = G_LAccount.objects.get(no="1000")

    # Get content types
    # customer_content_type = ContentType.objects.get_for_model(Customer)
    # gl_content_type = ContentType.objects.get_for_model(G_LAccount)

    payment_journal = PaymentJournal.objects.create(
        posting_date="2024-01-15",
        document_type=DocumentType.PAYMENT.value,  # "Payment"
        document_no="PAY-001",
        account_type=AccountType.CUSTOMER.value,  # "Customer"
        # account_content_type=customer_content_type,
        # account_object_id=customer.id,
        # payment_method=payment_method,
        amount=Decimal("1000.00"),
        bal_account_type=AccountType.GL.value,  # "G/L Account"
        # bal_account_content_type=gl_content_type,
        # bal_account_object_id=gl_account.no,
        description="Payment from customer",
    )

    print(f"Created payment: {payment_journal}")
    print(f"Document type: {payment_journal.document_type}")
    print(f"Account type: {payment_journal.account_type}")
    print(f"Status: {payment_journal.status}")

    return payment_journal


# Example: Creating a vendor payment
def create_vendor_payment():
    """Example of creating a vendor payment"""

    payment_journal = PaymentJournal.objects.create(
        posting_date="2024-01-15",
        document_type=DocumentType.PAYMENT.value,  # "Payment"
        document_no="PAY-002",
        account_type=AccountType.VENDOR.value,  # "Vendor"
        # account_content_type=vendor_content_type,
        # account_object_id=vendor.id,
        # payment_method=payment_method,
        amount=Decimal("500.00"),
        bal_account_type=AccountType.GL.value,  # "G/L Account"
        # bal_account_content_type=gl_content_type,
        # bal_account_object_id=gl_account.no,
        description="Payment to vendor",
    )

    print(f"Created vendor payment: {payment_journal}")
    return payment_journal


# Example: Creating a refund
def create_refund():
    """Example of creating a refund"""

    payment_journal = PaymentJournal.objects.create(
        posting_date="2024-01-15",
        document_type=DocumentType.REFUND.value,  # "Refund"
        document_no="REF-001",
        account_type=AccountType.CUSTOMER.value,  # "Customer"
        # account_content_type=customer_content_type,
        # account_object_id=customer.id,
        # payment_method=payment_method,
        amount=Decimal("200.00"),
        bal_account_type=AccountType.GL.value,  # "G/L Account"
        # bal_account_content_type=gl_content_type,
        # bal_account_object_id=gl_account.no,
        description="Refund to customer",
    )

    print(f"Created refund: {payment_journal}")
    return payment_journal


# Example: Applying a payment to a document using GenericForeignKey
def apply_payment_to_document(payment_journal, target_document):
    """Example of applying a payment to a document using GenericForeignKey"""

    # Get content type for the target document
    target_content_type = ContentType.objects.get_for_model(target_document.__class__)

    # Update the payment journal
    payment_journal.application_status = ApplicationStatus.APPLIED.value  # "Applied"
    payment_journal.applies_to_doc_type = "Invoice"  # or whatever document type
    payment_journal.applies_to_content_type = target_content_type
    payment_journal.applies_to_object_id = target_document.id
    payment_journal.save()

    print(f"Applied payment to document: {payment_journal.applies_to_doc}")
    print(f"Applies to document name: {payment_journal.applies_to_doc_name}")

    return payment_journal


# Example: Querying payments by applies_to document
def query_payments_by_applies_to_document(target_document):
    """Example of querying payments that apply to a specific document"""

    target_content_type = ContentType.objects.get_for_model(target_document.__class__)

    payments = PaymentJournal.objects.filter(
        applies_to_content_type=target_content_type,
        applies_to_object_id=target_document.id,
    )

    print(f"Found {payments.count()} payments that apply to {target_document}")
    return payments


# Example: Working with enum values
def demonstrate_enum_values():
    """Demonstrate the new enum values"""

    print("Document Types:")
    for doc_type in DocumentType:
        print(f"  {doc_type.name} = '{doc_type.value}'")

    print("\nAccount Types:")
    for acc_type in AccountType:
        print(f"  {acc_type.name} = '{acc_type.value}'")

    print("\nPayment Statuses:")
    for status in PaymentStatus:
        print(f"  {status.name} = '{status.value}'")

    print("\nApplication Statuses:")
    for app_status in ApplicationStatus:
        print(f"  {app_status.name} = '{app_status.value}'")


if __name__ == "__main__":
    print("PaymentJournal Model Example Usage")
    print("=" * 40)

    # Demonstrate enum values
    demonstrate_enum_values()

    print("\n" + "=" * 40)
    print("Note: Uncomment the actual model references to run these examples")
    print("The examples show the structure but require actual model instances")

    # Uncomment to run examples:
    # create_customer_payment()
    # create_vendor_payment()
    # create_refund()
