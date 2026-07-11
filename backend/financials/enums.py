from enum import Enum


class DOCUMENT_TYPE(Enum):
    default = ""
    Invoice = "Invoice"
    Payment = "Payment"
    Expense = "Expense"
    ExpenseReversal = "Expense Reversal"

    @classmethod
    def choices(cls):
        return [(tag.name, tag.value) for tag in cls]


class G_L_Account_Category(Enum):
    Assets = "Assets"
    Liabilities = "Liabilities"
    Equity = "Equity"
    Income = "Income"
    Cost_of_Goods_Sold = "Cost of Goods Sold"
    Expense = "Expense"


class INCOME_BALANCE(Enum):
    Income = "Income Statement"
    Balance = "Balance Sheet"


class G_L_Account_Type(Enum):
    Posting = "Posting"
    Heading = "Heading"
    Total = "Total"
    Begin_Total = "Begin-Total"
    End_Total = "End-Total"


class DEBIT_CREDIT(Enum):
    Both = "Both"
    Debit = "Debit"
    Credit = "Credit"


class FinancialReportPeriodType(Enum):
    Day = "Day"
    Week = "Week"
    Month = "Month"
    Quarter = "Quarter"
    Year = "Year"
    Accounting_Period = "Accounting Period"

    @classmethod
    def choices(cls):
        return [(tag.value, tag.value) for tag in cls]


class FinancialReportRowType(Enum):
    Header = "Header"
    Posting = "Posting"
    Total = "Total"
    Begin_Total = "Begin-Total"
    End_Total = "End-Total"

    @classmethod
    def choices(cls):
        return [(tag.value, tag.value) for tag in cls]


class FinancialReportTotalingType(Enum):
    Posting_Accounts = "Posting Accounts"
    Total_Accounts = "Total Accounts"
    Formula = "Formula"
    Set_Base_For_Percent = "Set Base For Percent"
    Cash_Flow_Accounts = "Cash Flow Accounts"
    Cost_Type = "Cost Type"
    Cost_Object = "Cost Object"

    @classmethod
    def choices(cls):
        return [(tag.value, tag.value) for tag in cls]


class FinancialReportAmountType(Enum):
    Net_Amount = "Net Amount"
    Debits = "Debits"
    Credits = "Credits"
    Debits_Minus_Credits = "Debits Minus Credits"
    Credits_Minus_Debits = "Credits Minus Debits"

    @classmethod
    def choices(cls):
        return [(tag.value, tag.value) for tag in cls]


class FinancialReportShowLine(Enum):
    Yes = "Yes"
    No = "No"
    If_Amount_Not_Zero = "If Amount Not Zero"
    If_Any_Column_Not_Zero = "If Any Column Not Zero"
    When_Positive_Balance = "When Positive Balance"
    When_Negative_Balance = "When Negative Balance"

    @classmethod
    def choices(cls):
        return [(tag.value, tag.value) for tag in cls]


class FinancialReportColumnType(Enum):
    Net_Change = "Net Change"
    Balance_at_Date = "Balance at Date"
    Beginning_Balance = "Beginning Balance"

    @classmethod
    def choices(cls):
        return [(tag.value, tag.value) for tag in cls]


class BalacingAccountType(Enum):
    GL_Account = ""
    GLAccount = "G/L Account"
    Customer = "Customer"
    Vendor = "Vendor"
    Bank_Account = "Bank Account"

    @classmethod
    def choices(cls):
        return [(tag.name, tag.value) for tag in cls]


def coerce_balancing_account_type(value):
    """
    Normalize balancing account type to the CharField choice key (enum member name).

    Posting previews often carry BalacingAccountType.*.value (e.g. "G/L Account");
    GeneralLedgerEntry.balancing_account_type must store the choice key (e.g. "GLAccount").
    """
    if value is None or value == "":
        return None
    if isinstance(value, BalacingAccountType):
        return value.name
    for tag in BalacingAccountType:
        if value == tag.name or value == tag.value:
            return tag.name
    return value


class GeneralPostingType(Enum):
    default = ""
    Sales = "Sales"
    Purchase = "Purchase"

    @classmethod
    def choices(cls):
        return [(tag.name, tag.value) for tag in cls]


class PaymentStatus(Enum):
    default = ""
    Open = "Open"
    Posted = "Posted"

    @classmethod
    def choices(cls):
        return [(tag.name, tag.value) for tag in cls]
