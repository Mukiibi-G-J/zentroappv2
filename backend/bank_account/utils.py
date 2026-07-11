"""
Utility functions for Bank Account posting operations
"""

from decimal import Decimal
from django.core.exceptions import ValidationError
from financials.enums import BalacingAccountType
from bank_account.enums import BankAccountDocumentType
from bank_account.models import BankAccount, BankAccountLedgerEntry


def create_bank_account_posting_entries(
    bank_account,
    posting_date,
    document_type,
    document_no,
    description,
    amount,
    bal_account_type,
    bal_account_no,
    user,
    global_dimension_1=None,
    dimension_set=None,
    transaction_no=None,
    document_date=None,
):
    """
    Create Bank Account Ledger Entry and return G/L account for G/L entry creation.

    This function handles the posting logic when a payment method uses a Bank Account
    as its balancing account. It creates the Bank Account Ledger Entry and returns
    the corresponding G/L account that should be used for the G/L entry.

    Args:
        bank_account: BankAccount instance
        posting_date: Date when the entry is posted
        document_type: Type of document (Payment, Invoice, etc.) - should be BankAccountDocumentType enum name
        document_no: Document number
        description: Transaction description
        amount: Transaction amount (positive for debit/money in, negative for credit/money out)
        bal_account_type: Type of balancing account (Customer, Vendor, G/L Account) - enum name
        bal_account_no: Account number of the balancing account (string representation)
        user: User who created the entry (required)
        global_dimension_1: Optional dimension value
        dimension_set: Optional dimension set for ledger entry
        transaction_no: Optional transaction number for grouping
        document_date: Optional document date (defaults to posting_date)

    Returns:
        dict with:
            - 'gl_account': G/L Account from bank account posting group (for G/L entry creation)
            - 'bank_account_entry': Created BankAccountLedgerEntry instance
            - 'success': Boolean indicating success

    Raises:
        ValidationError: If bank account doesn't have posting group or G/L account not configured
    """
    # Validate bank account has posting group
    if not bank_account.bank_account_posting_group:
        raise ValidationError(
            f"Bank Account {bank_account.no} does not have a posting group assigned. "
            "Please assign a posting group to the bank account."
        )

    posting_group = bank_account.bank_account_posting_group

    # Additional safety check
    if not posting_group:
        bank_account_name = getattr(
            bank_account, "no", getattr(bank_account, "name", "Unknown")
        )
        raise ValidationError(
            f"Bank Account '{bank_account_name}' has an invalid Bank Account Posting Group reference. "
            "Please update the bank account with a valid posting group."
        )

    posting_group_code = (
        getattr(posting_group, "code", "Unknown") if posting_group else "Unknown"
    )

    # Get G/L account from posting group
    if not posting_group.bank_account:
        raise ValidationError(
            f"Bank Account Posting Group '{posting_group_code}' does not have a G/L account assigned. "
            f"Please configure the G/L account in the posting group settings for '{posting_group_code}'."
        )

    gl_account = posting_group.bank_account

    # Use posting_date as document_date if not provided
    if document_date is None:
        document_date = posting_date

    # Convert document_type to enum name if it's a value
    if isinstance(document_type, str):
        # Check if it's already an enum name
        doc_type_names = [dt.name for dt in BankAccountDocumentType]
        if document_type not in doc_type_names:
            # Try to find by value
            for dt in BankAccountDocumentType:
                if dt.value == document_type:
                    document_type = dt.name
                    break

    # Convert bal_account_type to enum value if needed
    if isinstance(bal_account_type, str):
        # Check if it's an enum name or value
        if bal_account_type not in [t.name for t in BalacingAccountType]:
            # It might be a value, try to find the name
            for t in BalacingAccountType:
                if t.value == bal_account_type:
                    bal_account_type = t.name
                    break

    # Create Bank Account Ledger Entry
    bank_account_entry = BankAccountLedgerEntry.objects.create(
        bank_account_no=bank_account,
        posting_date=posting_date,
        document_type=document_type,
        document_date=document_date,
        document_no=document_no,
        description=description,
        amount=Decimal(str(amount)),
        remaining_amount=Decimal(str(amount)),
        bank_account_posting_group=posting_group,
        bal_account_type=bal_account_type,
        bal_account_no=str(bal_account_no) if bal_account_no else None,
        global_dimension_1=global_dimension_1,
        dimension_set=dimension_set,
        user=user,
    )

    return {
        "gl_account": gl_account,
        "bank_account_entry": bank_account_entry,
        "success": True,
    }


def get_bank_account_gl_account(bank_account):
    """
    Get the G/L account associated with a bank account through its posting group.

    Args:
        bank_account: BankAccount instance

    Returns:
        G_LAccount instance or None

    Raises:
        ValidationError: If bank account doesn't have posting group or G/L account
    """
    if not bank_account:
        raise ValidationError("Bank Account is required but was not provided.")

    if not bank_account.bank_account_posting_group:
        bank_account_name = getattr(
            bank_account, "no", getattr(bank_account, "name", "Unknown")
        )
        raise ValidationError(
            f"Bank Account '{bank_account_name}' does not have a Bank Account Posting Group assigned. "
            "Please assign a posting group to this bank account."
        )

    posting_group = bank_account.bank_account_posting_group

    # Additional safety check in case posting_group becomes None after assignment
    if not posting_group:
        bank_account_name = getattr(
            bank_account, "no", getattr(bank_account, "name", "Unknown")
        )
        raise ValidationError(
            f"Bank Account '{bank_account_name}' has an invalid Bank Account Posting Group reference. "
            "Please update the bank account with a valid posting group."
        )

    posting_group_code = (
        getattr(posting_group, "code", "Unknown") if posting_group else "Unknown"
    )

    if not posting_group.bank_account:
        raise ValidationError(
            f"Bank Account Posting Group '{posting_group_code}' does not have a G/L account assigned. "
            f"Please configure the G/L account in the posting group settings for '{posting_group_code}'."
        )

    return posting_group.bank_account
