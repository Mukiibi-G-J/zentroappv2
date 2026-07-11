from enum import Enum
from django.utils.translation import gettext_lazy as _


class LoanType(Enum):
    """Loan type options"""

    BANK = "Bank"
    SACCO = "SACCO"
    INDIVIDUAL = "Individual"

    @classmethod
    def choices(cls):
        """Return choices for Django model field"""
        return [(tag.value, _(tag.value)) for tag in cls]


class LoanStatus(Enum):
    """Loan status options"""

    OPEN = "Open"
    POSTED = "Posted"
    CLOSED = "Closed"
    CANCELLED = "Cancelled"

    @classmethod
    def choices(cls):
        """Return choices for Django model field"""
        return [(tag.value, _(tag.value)) for tag in cls]


class RepaymentStatus(Enum):
    """Loan repayment status options"""

    OPEN = "Open"
    POSTED = "Posted"
    CANCELLED = "Cancelled"

    @classmethod
    def choices(cls):
        """Return choices for Django model field"""
        return [(tag.value, _(tag.value)) for tag in cls]


class RepaymentAccountType(Enum):
    """Repayment account type options"""

    BANK = "Bank/Mobile Money"
    CASH = "Cash"

    @classmethod
    def choices(cls):
        """Return choices for Django model field"""
        return [(tag.value, _(tag.value)) for tag in cls]

