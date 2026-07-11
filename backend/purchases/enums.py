from enum import Enum


class PurchaseInvoiceStatus(Enum):
    OPEN = "Open"
    POSTED = "Posted"
    CANCELLED = "Cancelled"

    @classmethod
    def choices(cls):
        return [(status.value, status.value) for status in cls]


class PurchaseCreditMemoStatus(Enum):
    OPEN = "Open"
    POSTED = "Posted"
    CANCELLED = "Cancelled"

    @classmethod
    def choices(cls):
        return [(status.value, status.value) for status in cls]