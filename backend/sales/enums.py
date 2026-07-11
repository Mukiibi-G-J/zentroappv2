from enum import Enum
from django.db import models
from django.utils.translation import gettext_lazy as _


class SalesInvoiceStatus(Enum):
    DRAFT = "Draft"
    OPEN = "Open"
    POSTED = "Posted"
    CANCELLED = "Cancelled"

    @classmethod
    def choices(cls):
        return [(status.value, status.value) for status in cls]


class SalesOrderStatus(Enum):
    OPEN = "Open"
    PARTIALLY_DELIVERED = "Partially Delivered"
    COMPLETED = "Completed"
    CONVERTED_TO_INVOICE = "Converted to Invoice"

    @classmethod
    def choices(cls):
        return [(status.value, status.value) for status in cls]


class CustomerType(Enum):
    Individual = "Individual"
    General = "General"

    @classmethod
    def choices(cls):
        return [(tag.name, tag.value) for tag in cls]


class CustomerDocumentType(models.TextChoices):
    PAYMENT = "PAYMENT", _("Payment")
    INVOICE = "INVOICE", _("Invoice")
    CREDIT_MEMO = "CREDIT_MEMO", _("Credit Memo")
    FINANCE_CHARGE_MEMO = "FINANCE_CHARGE_MEMO", _("Finance Charge Memo")
    REMINDER = "REMINDER", _("Reminder")
    REFUND = "REFUND", _("Refund")
