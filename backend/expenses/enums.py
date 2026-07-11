from enum import Enum
from django.utils.translation import gettext_lazy as _


class ExpenseDocumentType(Enum):
    """Document types for expense entries"""

    EXPENSE = "Expense"
    REFUND = "Refund"
    ADJUSTMENT = "Adjustment"

    @classmethod
    def choices(cls):
        """Return choices for Django model field"""
        return [(tag.value, _(tag.value)) for tag in cls]


class ExpenseStatus(Enum):
    """Expense status options"""

    OPEN = "Open"
    POSTED = "Posted"
    REVERSED = "Reversed"

    @classmethod
    def choices(cls):
        """Return choices for Django model field"""
        return [(tag.value, _(tag.value)) for tag in cls]


class ExpenseType(Enum):
    """Expense types that map to specific G/L accounts"""

    OFFICE_SUPPLIES = "Office Supplies"
    UTILITIES = "Utilities"
    RENT = "Rent"
    SALARY = "Salary"
    ADVERTISING = "Advertising"
    TRAVEL = "Travel"
    MEALS = "Meals"
    INSURANCE = "Insurance"
    MAINTENANCE = "Maintenance"
    LEGAL_FEES = "Legal Fees"
    ACCOUNTING_FEES = "Accounting Fees"
    BANK_CHARGES = "Bank Charges"
    INTEREST = "Interest"
    DEPRECIATION = "Depreciation"
    OTHER = "Other"

    @classmethod
    def choices(cls):
        """Return choices for Django model field with blank option"""
        choices = [("", _("-- Select Expense Type --"))]
        choices.extend([(tag.value, _(tag.value)) for tag in cls])
        return choices

    @classmethod
    def get_gl_account_mapping(cls):
        """Return mapping of expense types to G/L account numbers"""
        return {
            cls.OFFICE_SUPPLIES.value: "6100",  # Office Supplies
            cls.UTILITIES.value: "6101",  # Utilities
            cls.RENT.value: "6102",  # Rent Expense
            cls.SALARY.value: "6103",  # Salaries and Wages
            cls.ADVERTISING.value: "6104",  # Advertising
            cls.TRAVEL.value: "6105",  # Travel Expense
            cls.MEALS.value: "6106",  # Meals and Entertainment
            cls.INSURANCE.value: "6107",  # Insurance
            cls.MAINTENANCE.value: "6108",  # Maintenance and Repairs
            cls.LEGAL_FEES.value: "6109",  # Legal Fees
            cls.ACCOUNTING_FEES.value: "6112",  # Accounting Fees
            cls.BANK_CHARGES.value: "6113",  # Bank Charges
            cls.INTEREST.value: "6114",  # Interest Expense
            cls.DEPRECIATION.value: "6115",  # Depreciation
            cls.OTHER.value: "6116",  # Other Expenses
        }
