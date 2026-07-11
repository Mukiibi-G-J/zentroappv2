from enum import Enum
from django.utils.translation import gettext_lazy as _


class BankAccountDocumentType(Enum):
    """Document types for Bank Account Ledger Entries"""

    Payment = "Payment"
    Invoice = "Invoice"
    Credit_Memo = "Credit Memo"
    Finance_Charge_Memo = "Finance Charge Memo"
    Reminder = "Reminder"
    Refund = "Refund"

    @classmethod
    def choices(cls):
        return [(tag.name, tag.value) for tag in cls]


class BankAccountStatementStatus(Enum):
    """Statement status for Bank Account Ledger Entries"""

    Open = "Open"
    Closed = "Closed"
    Bank_Acc_Entry_Applied = "Bank Acc. Entry Applied"
    Check_Entry_Applied = "Check Entry Applied"

    @classmethod
    def choices(cls):
        return [(tag.name, tag.value) for tag in cls]
