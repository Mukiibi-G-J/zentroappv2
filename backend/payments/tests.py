from django.test import TestCase
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from decimal import Decimal

from .models import PaymentJournal
from .enums import DocumentType, AccountType, PaymentStatus, ApplicationStatus
from financials.models import PaymentMethod, G_LAccount
from sales.models import Customer
from purchases.models import Vendor

# Create your tests here.


class PaymentJournalModelTest(TestCase):
    def setUp(self):
        """Set up test data"""
        # Create a payment method
        self.payment_method = PaymentMethod.objects.create(
            code="CASH", description="Cash Payment", bal_account_type="G/L Account"
        )

        # Create a GL account for balancing
        self.gl_account = G_LAccount.objects.create(
            no="1000",
            name="Cash Account",
            accounttype="Posting",
            accountcategory="Assets",
        )

        # Create a customer
        self.customer = Customer.objects.create(
            name="Test Customer", address="123 Test St", city="Test City"
        )

        # Create a vendor
        self.vendor = Vendor.objects.create(
            name="Test Vendor", address="456 Vendor St", city="Vendor City"
        )

        # Get content types
        self.customer_content_type = ContentType.objects.get_for_model(Customer)
        self.vendor_content_type = ContentType.objects.get_for_model(Vendor)
        self.gl_content_type = ContentType.objects.get_for_model(G_LAccount)

    def test_create_payment_journal_with_customer(self):
        """Test creating a payment journal entry with customer account"""
        payment_journal = PaymentJournal.objects.create(
            posting_date="2024-01-15",
            document_type=DocumentType.PAYMENT.value,
            document_no="PAY-001",
            account_type=AccountType.CUSTOMER.value,
            account_content_type=self.customer_content_type,
            account_object_id=self.customer.id,
            payment_method=self.payment_method,
            amount=Decimal("1000.00"),
            bal_account_type=AccountType.GL.value,
            bal_account_content_type=self.gl_content_type,
            bal_account_object_id=self.gl_account.no,
            description="Payment from customer",
        )

        self.assertEqual(payment_journal.document_no, "PAY-001")
        self.assertEqual(payment_journal.amount, Decimal("1000.00"))
        self.assertEqual(payment_journal.account_no, self.customer)
        self.assertEqual(payment_journal.bal_account_no, self.gl_account)
        self.assertEqual(payment_journal.account_name, self.customer.name)
        self.assertEqual(
            payment_journal.bal_account_name,
            f"{self.gl_account.no} - {self.gl_account.name}",
        )

    def test_create_payment_journal_with_vendor(self):
        """Test creating a payment journal entry with vendor account"""
        payment_journal = PaymentJournal.objects.create(
            posting_date="2024-01-15",
            document_type=PaymentJournal.DocumentType.PAYMENT,
            document_no="PAY-002",
            account_type=PaymentJournal.AccountType.VENDOR,
            account_content_type=self.vendor_content_type,
            account_object_id=self.vendor.id,
            payment_method=self.payment_method,
            amount=Decimal("500.00"),
            bal_account_type=PaymentJournal.AccountType.GL,
            bal_account_content_type=self.gl_content_type,
            bal_account_object_id=self.gl_account.no,
            description="Payment to vendor",
        )

        self.assertEqual(payment_journal.document_no, "PAY-002")
        self.assertEqual(payment_journal.amount, Decimal("500.00"))
        self.assertEqual(payment_journal.account_no, self.vendor)
        self.assertEqual(payment_journal.bal_account_no, self.gl_account)
        self.assertEqual(
            payment_journal.account_name, f"{self.vendor.no} - {self.vendor.name}"
        )

    def test_create_payment_journal_with_gl_account(self):
        """Test creating a payment journal entry with GL account"""
        payment_journal = PaymentJournal.objects.create(
            posting_date="2024-01-15",
            document_type=PaymentJournal.DocumentType.PAYMENT,
            document_no="PAY-003",
            account_type=PaymentJournal.AccountType.GL,
            account_content_type=self.gl_content_type,
            account_object_id=self.gl_account.no,
            payment_method=self.payment_method,
            amount=Decimal("750.00"),
            bal_account_type=PaymentJournal.AccountType.GL,
            bal_account_content_type=self.gl_content_type,
            bal_account_object_id=self.gl_account.no,
            description="Internal transfer",
        )

        self.assertEqual(payment_journal.document_no, "PAY-003")
        self.assertEqual(payment_journal.amount, Decimal("750.00"))
        self.assertEqual(payment_journal.account_no, self.gl_account)
        self.assertEqual(payment_journal.bal_account_no, self.gl_account)

    def test_payment_journal_with_external_document(self):
        """Test creating a payment journal entry with external document number"""
        payment_journal = PaymentJournal.objects.create(
            posting_date="2024-01-15",
            document_type=PaymentJournal.DocumentType.PAYMENT,
            document_no="PAY-004",
            external_document_no="EXT-001",
            account_type=PaymentJournal.AccountType.CUSTOMER,
            account_content_type=self.customer_content_type,
            account_object_id=self.customer.id,
            payment_method=self.payment_method,
            amount=Decimal("1200.00"),
            bal_account_type=PaymentJournal.AccountType.GL,
            bal_account_content_type=self.gl_content_type,
            bal_account_object_id=self.gl_account.no,
            description="Payment with external reference",
        )

        self.assertEqual(payment_journal.external_document_no, "EXT-001")

    def test_payment_journal_with_application(self):
        """Test creating a payment journal entry with application to another document"""
        payment_journal = PaymentJournal.objects.create(
            posting_date="2024-01-15",
            document_type=PaymentJournal.DocumentType.PAYMENT,
            document_no="PAY-005",
            account_type=PaymentJournal.AccountType.CUSTOMER,
            account_content_type=self.customer_content_type,
            account_object_id=self.customer.id,
            payment_method=self.payment_method,
            amount=Decimal("800.00"),
            bal_account_type=PaymentJournal.AccountType.GL,
            bal_account_content_type=self.gl_content_type,
            bal_account_object_id=self.gl_account.no,
            applied=True,
            applies_to_doc_type="Invoice",
            applies_to_content_type=self.customer_content_type,
            applies_to_object_id=self.customer.id,
            description="Payment applied to invoice",
        )

        self.assertTrue(payment_journal.applied)
        self.assertEqual(payment_journal.applies_to_doc_type, "Invoice")
        self.assertEqual(payment_journal.applies_to_doc, self.customer)

    def test_payment_journal_refund(self):
        """Test creating a refund payment journal entry"""
        payment_journal = PaymentJournal.objects.create(
            posting_date="2024-01-15",
            document_type=PaymentJournal.DocumentType.REFUND,
            document_no="REF-001",
            account_type=PaymentJournal.AccountType.CUSTOMER,
            account_content_type=self.customer_content_type,
            account_object_id=self.customer.id,
            payment_method=self.payment_method,
            amount=Decimal("200.00"),
            bal_account_type=PaymentJournal.AccountType.GL,
            bal_account_content_type=self.gl_content_type,
            bal_account_object_id=self.gl_account.no,
            description="Refund to customer",
        )

        self.assertEqual(
            payment_journal.document_type, PaymentJournal.DocumentType.REFUND
        )

    def test_payment_journal_validation_missing_account(self):
        """Test validation when account information is missing"""
        with self.assertRaises(ValidationError):
            payment_journal = PaymentJournal(
                posting_date="2024-01-15",
                document_type=PaymentJournal.DocumentType.PAYMENT,
                document_no="PAY-006",
                account_type=PaymentJournal.AccountType.CUSTOMER,
                # Missing account_content_type and account_object_id
                payment_method=self.payment_method,
                amount=Decimal("100.00"),
                bal_account_type=PaymentJournal.AccountType.GL,
                bal_account_content_type=self.gl_content_type,
                bal_account_object_id=self.gl_account.no,
            )
            payment_journal.full_clean()

    def test_payment_journal_validation_missing_bal_account(self):
        """Test validation when balancing account information is missing"""
        with self.assertRaises(ValidationError):
            payment_journal = PaymentJournal(
                posting_date="2024-01-15",
                document_type=PaymentJournal.DocumentType.PAYMENT,
                document_no="PAY-007",
                account_type=PaymentJournal.AccountType.CUSTOMER,
                account_content_type=self.customer_content_type,
                account_object_id=self.customer.id,
                payment_method=self.payment_method,
                amount=Decimal("100.00"),
                bal_account_type=PaymentJournal.AccountType.GL,
                # Missing bal_account_content_type and bal_account_object_id
            )
            payment_journal.full_clean()

    def test_payment_journal_validation_applies_to_fields(self):
        """Test validation when only one of applies_to fields is provided"""
        with self.assertRaises(ValidationError):
            payment_journal = PaymentJournal(
                posting_date="2024-01-15",
                document_type=PaymentJournal.DocumentType.PAYMENT,
                document_no="PAY-008",
                account_type=PaymentJournal.AccountType.CUSTOMER,
                account_content_type=self.customer_content_type,
                account_object_id=self.customer.id,
                payment_method=self.payment_method,
                amount=Decimal("100.00"),
                bal_account_type=PaymentJournal.AccountType.GL,
                bal_account_content_type=self.gl_content_type,
                bal_account_object_id=self.gl_account.no,
                applies_to_doc_type="Invoice",
                # Missing applies_to_content_type and applies_to_object_id
            )
            payment_journal.full_clean()

    def test_payment_journal_str_representation(self):
        """Test the string representation of PaymentJournal"""
        payment_journal = PaymentJournal.objects.create(
            posting_date="2024-01-15",
            document_type=PaymentJournal.DocumentType.PAYMENT,
            document_no="PAY-009",
            account_type=PaymentJournal.AccountType.CUSTOMER,
            account_content_type=self.customer_content_type,
            account_object_id=self.customer.id,
            payment_method=self.payment_method,
            amount=Decimal("300.00"),
            bal_account_type=PaymentJournal.AccountType.GL,
            bal_account_content_type=self.gl_content_type,
            bal_account_object_id=self.gl_account.no,
        )

        expected_str = f"PAY-009 - 2024-01-15 (300.00)"
        self.assertEqual(str(payment_journal), expected_str)
