from enum import Enum


class DocumentType(Enum):
    default = ""
    Purchase = "Purchase"
    PurchaseReceipt = "Purchase Receipt"
    Adjustment = "Adjustment"
    Invoice = "Invoice"
    Payment = "Payment"
    CreditMemo = "Credit Memo"
    Refund = "Refund"
    Sales = "Sales"

    @classmethod
    def choices(cls):
        return [(choice.value, choice.name) for choice in cls]


class EntryType(Enum):
    initial = "Initial Entry"
    application = "Application"
    
    # unrealized_loss = "Unrealized Loss"
    # unrealized_gain = "Unrealized Gain"
    # realized_loss = "Realized Loss"
    # realized_gain = "Realized Gain"
    # payment_discount = "Payment Discount"
    # payment_tolerance = "Payment Tolerance"
    # rounding = "Rounding"

    @classmethod
    def choices(cls):
        return [(choice.value, choice.name) for choice in cls]



class Status(Enum):
    Open = "Open"
    Posted = "Posted"

    @classmethod
    def choices(cls):
        return [(choice.value, choice.name) for choice in cls]





