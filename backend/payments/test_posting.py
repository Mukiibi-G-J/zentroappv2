"""
Test file for payment journal posting functionality
"""

from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from payments.models import PaymentJournal
from payments.admin import PaymentJournalPostingProcessor
from financials.models import PaymentMethod, G_LAccount
from sales.models import Customer
from purchases.models import Vendor, VendorPostingGroup

User = get_user_model()


class PaymentJournalPostingTest(TestCase):
    def setUp(self):
        """Set up test data"""
        # Create a user
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )

        # Create a payment method
        self.payment_method = PaymentMethod.objects.create(
            code="CASH", description="Cash Payment", bal_account_type="G/L Account"
        )

        # Create GL accounts
        self.cash_account = G_LAccount.objects.create(
            no="1000",
            name="Cash Account",
            accounttype="Posting",
            accountcategory="Assets",
        )

        self.payables_account = G_LAccount.objects.create(
            no="2000",
            name="Accounts Payable",
            accounttype="Posting",
            accountcategory="Liabilities",
        )

        # Create a vendor posting group
        self.vendor_posting_group = VendorPostingGroup.objects.create(
            code="VPG001",
            description="Test Vendor Posting Group",
            payables_account=self.payables_account,
        )

        # Create a vendor
        self.vendor = Vendor.objects.create(
            name="Test Vendor",
            address="123 Vendor St",
            city="Vendor City",
            vendor_posting_group=self.vendor_posting_group,
        )

        # Create a customer
        self.customer = Customer.objects.create(
            name="Test Customer", address="456 Customer St", city="Customer City"
        )

        # Get content types
        self.vendor_content_type = ContentType.objects.get_for_model(Vendor)
        self.customer_content_type = ContentType.objects.get_for_model(Customer)
        self.gl_content_type = ContentType.objects.get_for_model(G_LAccount)

        # Create request factory
        self.factory = RequestFactory()

    def test_vendor_payment_posting(self):
        """Test posting a vendor payment"""
        # Create a payment journal entry for vendor payment
        payment_journal = PaymentJournal.objects.create(
            posting_date=timezone.now().date(),
            document_type="Payment",
            account_type="Vendor",
            account_content_type=self.vendor_content_type,
            account_object_id=self.vendor.id,
            payment_method=self.payment_method,
            amount=1000,  # $10.00
            bal_account_type="G/L Account",
            bal_account_content_type=self.gl_content_type,
            bal_account_object_id=self.cash_account.no,
            description="Test vendor payment",
            status="Open",
        )

        # Create a request
        request = self.factory.get("/")
        request.user = self.user

        # Create receipt number
        receipt_no = f"RCP-{timezone.now().strftime('%Y%m%d')}-TEST01"

        # Test the posting processor
        processor = PaymentJournalPostingProcessor(payment_journal, request, receipt_no)
        result = processor.post()

        # Check if posting was successful
        self.assertTrue(
            result["success"],
            f"Posting failed: {result.get('message', 'Unknown error')}",
        )

        # Check that the payment journal status was updated
        payment_journal.refresh_from_db()
        self.assertEqual(payment_journal.status, "Posted")

        # Check that GL entries were created
        from financials.models import GeneralLedgerEntry

        gl_entries = GeneralLedgerEntry.objects.filter(
            document_no=payment_journal.document_no
        )
        self.assertEqual(gl_entries.count(), 2)  # Debit and credit entries

        # Check that vendor ledger entry was created
        from purchases.models import VendorLedger

        vendor_entries = VendorLedger.objects.filter(
            document_no=payment_journal.document_no
        )
        self.assertEqual(vendor_entries.count(), 1)

        # Check that detailed vendor ledger entries were created
        from purchases.models import DetailedVendorLedgerEntry

        detailed_vendor_entries = DetailedVendorLedgerEntry.objects.filter(
            document_no=payment_journal.document_no
        )
        self.assertEqual(
            detailed_vendor_entries.count(), 1
        )  # Initial entry only when not applied

    def test_customer_payment_posting(self):
        """Test posting a customer payment"""
        # Create a payment journal entry for customer payment
        payment_journal = PaymentJournal.objects.create(
            posting_date=timezone.now().date(),
            document_type="Payment",
            account_type="Customer",
            account_content_type=self.customer_content_type,
            account_object_id=self.customer.id,
            payment_method=self.payment_method,
            amount=1500,  # $15.00
            bal_account_type="G/L Account",
            bal_account_content_type=self.gl_content_type,
            bal_account_object_id=self.cash_account.no,
            description="Test customer payment",
            status="Open",
        )

        # Create a request
        request = self.factory.get("/")
        request.user = self.user

        # Create receipt number
        receipt_no = f"RCP-{timezone.now().strftime('%Y%m%d')}-TEST02"

        # Test the posting processor
        processor = PaymentJournalPostingProcessor(payment_journal, request, receipt_no)
        result = processor.post()

        # Check if posting was successful
        self.assertTrue(
            result["success"],
            f"Posting failed: {result.get('message', 'Unknown error')}",
        )

        # Check that the payment journal status was updated
        payment_journal.refresh_from_db()
        self.assertEqual(payment_journal.status, "Posted")

        # Check that GL entries were created
        from financials.models import GeneralLedgerEntry

        gl_entries = GeneralLedgerEntry.objects.filter(
            document_no=payment_journal.document_no
        )
        self.assertEqual(gl_entries.count(), 2)  # Debit and credit entries

        # Check that customer ledger entry was created
        from sales.models import CustomerLedgerEntry

        customer_entries = CustomerLedgerEntry.objects.filter(
            document_no=payment_journal.document_no
        )
        self.assertEqual(customer_entries.count(), 1)

        # Check that detailed customer ledger entry was created
        from sales.models import DetailedCustomerLedgerEntry

        detailed_customer_entries = DetailedCustomerLedgerEntry.objects.filter(
            document_no=payment_journal.document_no
        )
        self.assertEqual(detailed_customer_entries.count(), 1)  # Initial entry
