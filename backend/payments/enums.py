from enum import Enum
from django.utils.translation import gettext_lazy as _


class DocumentType(Enum):
    """Document types for payment journal entries"""

    PAYMENT = "Payment"
    INVOICE = "Invoice"
    CREDIT_MEMO = "Credit Memo"
    FINANCE_CHARGE_MEMO = "Finance Charge Memo"
    REMINDER = "Reminder"
    REFUND = "Refund"

    @classmethod
    def choices(cls):
        """Return choices for Django model field"""
        return [(tag.value, _(tag.value)) for tag in cls]


class AccountType(Enum):
    """Account types for payment journal entries"""

    CUSTOMER = "Customer"
    VENDOR = "Vendor"
    GL = "G/L Account"

    @classmethod
    def choices(cls):
        """Return choices for Django model field with blank option"""
        choices = [("", _("-- Select Account Type --"))]
        choices.extend([(tag.value, _(tag.value)) for tag in cls])
        return choices


class PaymentStatus(Enum):
    """Payment status options"""

    OPEN = "Open"
    POSTED = "Posted"
    VOID = "Void"
    CANCELLED = "Cancelled"

    @classmethod
    def choices(cls):
        """Return choices for Django model field"""
        return [(tag.value, _(tag.value)) for tag in cls]


class ApplicationStatus(Enum):
    """Application status for payment journal entries"""

    APPLIED = "Applied"
    UNAPPLIED = "Unapplied"
    PARTIALLY_APPLIED = "Partially Applied"

    @classmethod
    def choices(cls):
        """Return choices for Django model field"""
        return [(tag.value, _(tag.value)) for tag in cls]
