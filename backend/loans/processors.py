from django.db import transaction
from django.utils import timezone
from financials.models import GeneralLedgerEntry
from financials.enums import BalacingAccountType
from common.enums import DocumentType
from bank_account.models import BankAccount
from bank_account.utils import (
    get_bank_account_gl_account,
    create_bank_account_posting_entries,
)
from financials.models import PaymentMethod


class LoanPostingProcessor:
    """
    Processor for generating preview entries for loan registration posting.
    """

    def __init__(self, loan, request, receipt_no):
        self.loan = loan
        self.user = request.user
        self.receipt_no = receipt_no
        self.request = request

        # Resolve branch: document -> X-Branch-Id header -> user global_dimension_1 -> first branch
        from dimension.branch_filter import get_branch_for_request
        from dimension.utils import get_first_branch_dimension_value

        branch = getattr(loan, "global_dimension_1", None)
        if not branch:
            branch = get_branch_for_request(request) if request else None
        if not branch and request and request.user:
            branch = getattr(request.user, "global_dimension_1", None)
        if not branch:
            branch = get_first_branch_dimension_value()
        self.global_dimension_1_value = branch

        self.gl_entries = []
        self.bank_account_entries = []

    def _validate_loan(self):
        """Validate the loan entry"""
        if not self.loan.loan_no:
            raise Exception("Loan must have a loan number")

        if not self.loan.disbursement_date:
            raise Exception("Loan must have a disbursement date")

        if not self.loan.loan_amount:
            raise Exception("Loan must have a loan amount")

        if not self.loan.repayment_account:
            raise Exception("Loan must have a repayment account specified")

        return True

    def process(self):
        """Process the loan and generate preview entries"""
        try:
            # Validate the loan
            if not self._validate_loan():
                return {
                    "success": False,
                    "message": "Loan validation failed",
                    "entries": {},
                }

            # Generate transaction number
            transaction_no = (
                f"LOAN{self.loan.loan_no}-"
                f"{self.loan.disbursement_date.strftime('%Y%m%d')}-{self.loan.id}"
            )

            # Generate GL entries
            self._generate_gl_entries(transaction_no)

            return {
                "gl_entries": self.gl_entries,
                "bank_account_entries": self.bank_account_entries,
            }

        except Exception as e:
            return {
                "success": False,
                "message": f"Error processing loan: {e}",
                "entries": {},
            }

    def _generate_gl_entries(self, transaction_no):
        """Generate general ledger entries for loan registration"""
        from bank_account.enums import BankAccountDocumentType
        from financials.enums import BalacingAccountType as BalAccountType

        # Get loan payable account (Long Term or Short Term)
        loan_payable_account = self.loan.get_loan_payable_account()

        # If repayment_account is "Bank/Mobile Money", create bank ledger entry and get GL account from posting group
        if self.loan.repayment_account == "Bank/Mobile Money":
            if not self.loan.bank_account:
                raise Exception(
                    "Bank account is required when Repayment Account is 'Bank/Mobile Money'"
                )

            # Get GL account from bank posting group
            bank_gl_account = get_bank_account_gl_account(self.loan.bank_account)

            # Create bank account ledger entry for preview
            # For loan disbursement: money comes IN to bank (positive amount)
            self.bank_account_entries.append(
                {
                    "bank_account": self.loan.bank_account,
                    "posting_date": self.loan.disbursement_date,
                    "document_type": BankAccountDocumentType.Payment.name,
                    "document_no": self.loan.loan_no,
                    "description": f"Loan Disbursement {self.loan.loan_no} - {self.loan.lender_name}",
                    "amount": float(self.loan.loan_amount),  # Positive for money IN
                    "bal_account_type": BalAccountType.GLAccount.name,
                    "bal_account_no": loan_payable_account.no,
                    "global_dimension_1": self.global_dimension_1_value,
                    "transaction_no": transaction_no,
                    "document_date": self.loan.disbursement_date,
                    "user": self.user,
                }
            )

            # Debit: Bank GL Account (from posting group)
            self.gl_entries.append(
                {
                    "posting_date": self.loan.disbursement_date,
                    "document_type": DocumentType.Payment.value,
                    "document_no": self.loan.loan_no,
                    "gl_account": bank_gl_account,
                    "description": f"Loan {self.loan.loan_no} - {self.loan.lender_name}",
                    "department_code": (
                        self.global_dimension_1_value.code if self.global_dimension_1_value else None
                    ),
                    "amount": self.loan.loan_amount,
                    "gen_posting_type": "Loan",
                    "global_dimension_1": self.global_dimension_1_value,
                    "balance_account_type": BalacingAccountType.GLAccount.value,
                    "user": self.user,
                    "transaction_no": transaction_no,
                }
            )
        else:
            # For Cash: Get cash account from payment method or default
            cash_bank_account = self._get_cash_bank_account()

            # Debit: Cash Account
            self.gl_entries.append(
                {
                    "posting_date": self.loan.disbursement_date,
                    "document_type": DocumentType.Payment.value,
                    "document_no": self.loan.loan_no,
                    "gl_account": cash_bank_account,
                    "description": f"Loan {self.loan.loan_no} - {self.loan.lender_name}",
                    "department_code": (
                        self.global_dimension_1_value.code if self.global_dimension_1_value else None
                    ),
                    "amount": self.loan.loan_amount,
                    "gen_posting_type": "Loan",
                    "global_dimension_1": self.global_dimension_1_value,
                    "balance_account_type": BalacingAccountType.GLAccount.value,
                    "user": self.user,
                    "transaction_no": transaction_no,
                }
            )

        # Credit: Loan Payable Account
        self.gl_entries.append(
            {
                "posting_date": self.loan.disbursement_date,
                "document_type": DocumentType.Payment.value,
                "document_no": self.loan.loan_no,
                "gl_account": loan_payable_account,
                "description": f"Loan {self.loan.loan_no} - {self.loan.lender_name}",
                "department_code": (
                    self.global_dimension_1_value.code if self.global_dimension_1_value else None
                ),
                "amount": -self.loan.loan_amount,
                "gen_posting_type": "Loan",
                "global_dimension_1": self.global_dimension_1_value,
                "balance_account_type": BalacingAccountType.GLAccount.value,
                "user": self.user,
                "transaction_no": transaction_no,
            }
        )

    def _get_cash_bank_account(self):
        """Get the GL account for cash/bank based on repayment_account field"""
        from financials.models import G_LAccount

        try:
            # If repayment_account is "Bank/Mobile Money", use the selected bank account's GL account
            if self.loan.repayment_account == "Bank/Mobile Money":
                if not self.loan.bank_account:
                    raise Exception(
                        "Bank account is required when Repayment Account is 'Bank/Mobile Money'"
                    )

                # Get the GL account from the bank account
                bank_gl_account = get_bank_account_gl_account(self.loan.bank_account)
                if bank_gl_account:
                    return bank_gl_account
                else:
                    raise Exception(
                        f"GL account not found for bank account {self.loan.bank_account.no}"
                    )

            # If repayment_account is "Cash", get cash account from payment method or default
            elif self.loan.repayment_account == "Cash":
                # Try to get cash account from payment methods
                cash_payment_method = PaymentMethod.objects.filter(
                    code__icontains="cash"
                ).first()
                if cash_payment_method and hasattr(cash_payment_method, "gl_account"):
                    return cash_payment_method.gl_account

                # Default: try to get account 1100 (Cash) or similar
                cash_account = G_LAccount.objects.filter(no="1100").first()
                if cash_account:
                    return cash_account

                raise Exception(
                    "Cash GL account not found. Please configure cash payment method or GL account 1100."
                )

            else:
                raise Exception(
                    f"Invalid repayment account type: {self.loan.repayment_account}"
                )

        except Exception as e:
            raise Exception(
                f"Error getting cash/bank account: {str(e)}. "
                "Please ensure payment methods or bank accounts are configured."
            )


class LoanPostingFinalPoster:
    """
    Final poster for actually creating GL entries for loan registration.
    """

    def __init__(self, preview_data, loan, user, receipt_no=None):
        self.preview_data = preview_data
        self.loan = loan
        self.user = user
        self.receipt_no = receipt_no

    def post_to_tables(self):
        """Actually create GeneralLedgerEntry records"""
        try:
            with transaction.atomic():
                # Create Bank Account Ledger Entries (if any)
                for bank_entry_info in self.preview_data.get(
                    "bank_account_entries", []
                ):
                    try:
                        result = create_bank_account_posting_entries(
                            bank_account=bank_entry_info["bank_account"],
                            posting_date=bank_entry_info["posting_date"],
                            document_type=bank_entry_info["document_type"],
                            document_no=bank_entry_info["document_no"],
                            description=bank_entry_info["description"],
                            amount=bank_entry_info["amount"],
                            bal_account_type=bank_entry_info["bal_account_type"],
                            bal_account_no=bank_entry_info["bal_account_no"],
                            user=bank_entry_info.get("user", self.user),
                            global_dimension_1=bank_entry_info.get("global_dimension_1"),
                            transaction_no=bank_entry_info.get("transaction_no"),
                            document_date=bank_entry_info.get("document_date"),
                        )
                    except Exception as e:
                        raise Exception(
                            f"Failed to create bank account ledger entry: {str(e)}"
                        )

                # Create GL Entries
                from dimension.models import get_posting_dimension_payload

                for gl_entry in self.preview_data["gl_entries"]:
                    dim_payload = get_posting_dimension_payload(
                        global_dimension_1=gl_entry.get("global_dimension_1"),
                        dimension_set=gl_entry.get("dimension_set"),
                    )
                    general_ledger = GeneralLedgerEntry.objects.create(
                        posting_date=gl_entry["posting_date"],
                        document_type=gl_entry["document_type"],
                        document_no=gl_entry["document_no"],
                        gl_account=gl_entry["gl_account"],
                        description=gl_entry["description"],
                        amount=float(gl_entry["amount"]),
                        general_posting_type=gl_entry["gen_posting_type"],
                        dimension_set=dim_payload["dimension_set"],
                        global_dimension_1=dim_payload["global_dimension_1"],
                        global_dimension_2=dim_payload["global_dimension_2"],
                        balancing_account_type=gl_entry["balance_account_type"],
                        user=gl_entry["user"],
                        receipt_no=self.receipt_no,
                        transaction_no=gl_entry["transaction_no"],
                    )

            return {
                "success": True,
                "message": f"Successfully posted loan {self.loan.loan_no}",
                "entries_created": {
                    "gl_entries": len(self.preview_data["gl_entries"]),
                },
            }

        except Exception as e:
            return {
                "success": False,
                "message": f"Error posting loan: {str(e)}",
                "error_type": "PostingError",
                "error_details": str(e),
            }


class LoanRepaymentPostingProcessor:
    """
    Processor for generating preview entries for loan repayment posting.
    """

    def __init__(self, repayment, request, receipt_no):
        self.repayment = repayment
        self.user = request.user
        self.receipt_no = receipt_no

        # Resolve branch: repayment/loan -> X-Branch-Id header -> user global_dimension_1 -> first branch
        from dimension.branch_filter import get_branch_for_request
        from dimension.utils import get_first_branch_dimension_value

        branch = getattr(repayment, "global_dimension_1", None)
        if not branch and repayment.loan:
            branch = getattr(repayment.loan, "global_dimension_1", None)
        if not branch:
            branch = get_branch_for_request(request) if request else None
        if not branch and request and request.user:
            branch = getattr(request.user, "global_dimension_1", None)
        if not branch:
            branch = get_first_branch_dimension_value()
        self.global_dimension_1_value = branch

        self.gl_entries = []
        self.bank_account_entries = []

    def _validate_repayment(self):
        """Validate the repayment entry"""
        if not self.repayment.repayment_no:
            raise Exception("Repayment must have a repayment number")

        if not self.repayment.payment_date:
            raise Exception("Repayment must have a payment date")

        if not self.repayment.amount_paid:
            raise Exception("Repayment must have an amount paid")

        if not self.repayment.loan:
            raise Exception("Repayment must be linked to a loan")

        return True

    def process(self):
        """Process the repayment and generate preview entries"""
        try:
            # Validate the repayment
            if not self._validate_repayment():
                return {
                    "success": False,
                    "message": "Repayment validation failed",
                    "entries": {},
                }

            # Generate transaction number
            transaction_no = (
                f"LOANREP{self.repayment.repayment_no}-"
                f"{self.repayment.payment_date.strftime('%Y%m%d')}-{self.repayment.id}"
            )

            # Generate GL entries
            self._generate_gl_entries(transaction_no)

            return {
                "gl_entries": self.gl_entries,
                "bank_account_entries": self.bank_account_entries,
            }

        except Exception as e:
            return {
                "success": False,
                "message": f"Error processing repayment: {e}",
                "entries": {},
            }

    def _calculate_principal_interest_split(self):
        """Calculate principal and interest split during posting"""
        from decimal import Decimal
        
        if not self.repayment.amount_paid or not self.repayment.loan:
            self.repayment.principal_amount = 0
            self.repayment.interest_amount = 0
            return

        # Get remaining principal (only from posted repayments)
        remaining_principal = self.repayment.loan.get_remaining_principal()

        # Calculate interest for this payment period
        # Simple interest: Interest = (Principal * Rate) / (100 * 12) for monthly
        principal_decimal = Decimal(remaining_principal)
        rate = Decimal(self.repayment.loan.interest_rate) / Decimal(100)

        # Calculate monthly interest
        monthly_interest = (principal_decimal * rate) / Decimal(12)
        interest_amount = int(monthly_interest)

        # Interest is calculated first, then remainder goes to principal
        # If payment is less than or equal to interest, all goes to interest
        if self.repayment.amount_paid <= interest_amount:
            self.repayment.interest_amount = self.repayment.amount_paid
            self.repayment.principal_amount = 0
        else:
            # Interest portion first
            self.repayment.interest_amount = interest_amount
            # Remaining goes to principal
            principal_amount = self.repayment.amount_paid - interest_amount
            
            # Ensure principal doesn't exceed remaining principal
            if principal_amount > remaining_principal:
                self.repayment.principal_amount = remaining_principal
                # Adjust interest if needed (shouldn't happen, but safety check)
                self.repayment.interest_amount = self.repayment.amount_paid - remaining_principal
            else:
                self.repayment.principal_amount = principal_amount

    def _generate_gl_entries(self, transaction_no):
        """Generate general ledger entries for loan repayment"""
        from bank_account.enums import BankAccountDocumentType
        from financials.enums import BalacingAccountType as BalAccountType
        
        # Calculate principal and interest split first (interest first, then principal)
        self._calculate_principal_interest_split()
        
        # Get loan payable account (Long Term or Short Term)
        loan_payable_account = self.repayment.loan.get_loan_payable_account()

        # Get interest expense account
        try:
            from financials.models import G_LAccount

            interest_expense_account = G_LAccount.objects.get(no="8615")
        except G_LAccount.DoesNotExist:
            raise Exception(
                "Interest Expense GL account (8615) not found. "
                "Please run seed_loan_accounts command."
            )

        # Debit: Loan Payable (principal amount)
        if self.repayment.principal_amount > 0:
            self.gl_entries.append(
                {
                    "posting_date": self.repayment.payment_date,
                    "document_type": DocumentType.Payment.value,
                    "document_no": self.repayment.repayment_no,
                    "gl_account": loan_payable_account,
                    "description": f"Loan Repayment {self.repayment.repayment_no} - Principal",
                    "department_code": (
                        self.global_dimension_1_value.code if self.global_dimension_1_value else None
                    ),
                    "amount": self.repayment.principal_amount,
                    "gen_posting_type": "Loan Repayment",
                    "global_dimension_1": self.global_dimension_1_value,
                    "balance_account_type": BalacingAccountType.GLAccount.value,
                    "user": self.user,
                    "transaction_no": transaction_no,
                }
            )

        # Debit: Interest Expense (interest amount)
        if self.repayment.interest_amount > 0:
            self.gl_entries.append(
                {
                    "posting_date": self.repayment.payment_date,
                    "document_type": DocumentType.Payment.value,
                    "document_no": self.repayment.repayment_no,
                    "gl_account": interest_expense_account,
                    "description": f"Loan Repayment {self.repayment.repayment_no} - Interest",
                    "department_code": (
                        self.global_dimension_1_value.code if self.global_dimension_1_value else None
                    ),
                    "amount": self.repayment.interest_amount,
                    "gen_posting_type": "Loan Repayment",
                    "global_dimension_1": self.global_dimension_1_value,
                    "balance_account_type": BalacingAccountType.GLAccount.value,
                    "user": self.user,
                    "transaction_no": transaction_no,
                }
            )

        # Credit: Cash/Bank Account (total payment amount)
        # If payment_method is "Bank/Mobile Money", create bank ledger entry and get GL account from posting group
        if self.repayment.payment_method == "Bank/Mobile Money":
            if not self.repayment.bank_account:
                raise Exception(
                    "Bank account is required when Payment Method is 'Bank/Mobile Money'"
                )

            # Get GL account from bank posting group
            bank_gl_account = get_bank_account_gl_account(self.repayment.bank_account)

            # Create bank account ledger entry for preview
            # For loan repayment: money goes OUT from bank (negative amount)
            self.bank_account_entries.append(
                {
                    "bank_account": self.repayment.bank_account,
                    "posting_date": self.repayment.payment_date,
                    "document_type": BankAccountDocumentType.Payment.name,
                    "document_no": self.repayment.repayment_no,
                    "description": f"Loan Repayment {self.repayment.repayment_no} - {self.repayment.loan.lender_name}",
                    "amount": -float(
                        self.repayment.amount_paid
                    ),  # Negative for money OUT
                    "bal_account_type": BalAccountType.GLAccount.name,
                    "bal_account_no": loan_payable_account.no,
                    "global_dimension_1": self.global_dimension_1_value,
                    "transaction_no": transaction_no,
                    "document_date": self.repayment.payment_date,
                    "user": self.user,
                }
            )

            # Credit: Bank GL Account (from posting group)
            self.gl_entries.append(
                {
                    "posting_date": self.repayment.payment_date,
                    "document_type": DocumentType.Payment.value,
                    "document_no": self.repayment.repayment_no,
                    "gl_account": bank_gl_account,
                    "description": f"Loan Repayment {self.repayment.repayment_no}",
                    "department_code": (
                        self.global_dimension_1_value.code if self.global_dimension_1_value else None
                    ),
                    "amount": -self.repayment.amount_paid,
                    "gen_posting_type": "Loan Repayment",
                    "global_dimension_1": self.global_dimension_1_value,
                    "balance_account_type": BalacingAccountType.GLAccount.value,
                    "user": self.user,
                    "transaction_no": transaction_no,
                }
            )
        else:
            # For Cash: Get cash account from payment method or default
            cash_bank_account = self._get_cash_bank_account()

            # Credit: Cash Account
            self.gl_entries.append(
                {
                    "posting_date": self.repayment.payment_date,
                    "document_type": DocumentType.Payment.value,
                    "document_no": self.repayment.repayment_no,
                    "gl_account": cash_bank_account,
                    "description": f"Loan Repayment {self.repayment.repayment_no}",
                    "department_code": (
                        self.global_dimension_1_value.code if self.global_dimension_1_value else None
                    ),
                    "amount": -self.repayment.amount_paid,
                    "gen_posting_type": "Loan Repayment",
                    "global_dimension_1": self.global_dimension_1_value,
                    "balance_account_type": BalacingAccountType.GLAccount.value,
                    "user": self.user,
                    "transaction_no": transaction_no,
                }
            )

    def _get_cash_bank_account(self):
        """Get the GL account for cash/bank based on payment_method field"""
        from financials.models import G_LAccount

        try:
            # If payment_method is "Bank/Mobile Money", use the selected bank account's GL account
            if self.repayment.payment_method == "Bank/Mobile Money":
                if not self.repayment.bank_account:
                    raise Exception(
                        "Bank account is required when Payment Method is 'Bank/Mobile Money'"
                    )

                # Get the GL account from the bank account
                bank_gl_account = get_bank_account_gl_account(
                    self.repayment.bank_account
                )
                if bank_gl_account:
                    return bank_gl_account
                else:
                    raise Exception(
                        f"GL account not found for bank account {self.repayment.bank_account.no}"
                    )

            # If payment_method is "Cash", get cash account from payment method or default
            elif self.repayment.payment_method == "Cash":
                # Try to get cash account from payment methods
                cash_payment_method = PaymentMethod.objects.filter(
                    code__icontains="cash"
                ).first()
                if cash_payment_method and hasattr(cash_payment_method, "gl_account"):
                    return cash_payment_method.gl_account

                # Default: try to get account 1100 (Cash) or similar
                cash_account = G_LAccount.objects.filter(no="1100").first()
                if cash_account:
                    return cash_account

                raise Exception(
                    "Cash GL account not found. Please configure cash payment method or GL account 1100."
                )

            else:
                raise Exception(
                    f"Invalid payment method: {self.repayment.payment_method}"
                )

        except Exception as e:
            raise Exception(
                f"Error getting cash/bank account: {str(e)}. "
                "Please ensure payment methods or bank accounts are configured."
            )


class LoanRepaymentPostingFinalPoster:
    """
    Final poster for actually creating GL entries for loan repayment.
    """

    def __init__(self, preview_data, repayment, user, receipt_no=None):
        self.preview_data = preview_data
        self.repayment = repayment
        self.user = user
        self.receipt_no = receipt_no

    def post_to_tables(self):
        """Actually create GeneralLedgerEntry records"""
        try:
            with transaction.atomic():
                # Create Bank Account Ledger Entries (if any)
                for bank_entry_info in self.preview_data.get(
                    "bank_account_entries", []
                ):
                    try:
                        result = create_bank_account_posting_entries(
                            bank_account=bank_entry_info["bank_account"],
                            posting_date=bank_entry_info["posting_date"],
                            document_type=bank_entry_info["document_type"],
                            document_no=bank_entry_info["document_no"],
                            description=bank_entry_info["description"],
                            amount=bank_entry_info["amount"],
                            bal_account_type=bank_entry_info["bal_account_type"],
                            bal_account_no=bank_entry_info["bal_account_no"],
                            user=bank_entry_info.get("user", self.user),
                            global_dimension_1=bank_entry_info.get("global_dimension_1"),
                            transaction_no=bank_entry_info.get("transaction_no"),
                            document_date=bank_entry_info.get("document_date"),
                        )
                    except Exception as e:
                        raise Exception(
                            f"Failed to create bank account ledger entry: {str(e)}"
                        )

                # Create GL Entries
                from dimension.models import get_posting_dimension_payload

                for gl_entry in self.preview_data["gl_entries"]:
                    dim_payload = get_posting_dimension_payload(
                        global_dimension_1=gl_entry.get("global_dimension_1"),
                        dimension_set=gl_entry.get("dimension_set"),
                    )
                    general_ledger = GeneralLedgerEntry.objects.create(
                        posting_date=gl_entry["posting_date"],
                        document_type=gl_entry["document_type"],
                        document_no=gl_entry["document_no"],
                        gl_account=gl_entry["gl_account"],
                        description=gl_entry["description"],
                        amount=float(gl_entry["amount"]),
                        general_posting_type=gl_entry["gen_posting_type"],
                        dimension_set=dim_payload["dimension_set"],
                        global_dimension_1=dim_payload["global_dimension_1"],
                        global_dimension_2=dim_payload["global_dimension_2"],
                        balancing_account_type=gl_entry["balance_account_type"],
                        user=gl_entry["user"],
                        receipt_no=self.receipt_no,
                        transaction_no=gl_entry["transaction_no"],
                    )

            return {
                "success": True,
                "message": f"Successfully posted loan repayment {self.repayment.repayment_no}",
                "entries_created": {
                    "gl_entries": len(self.preview_data["gl_entries"]),
                },
            }

        except Exception as e:
            return {
                "success": False,
                "message": f"Error posting loan repayment: {str(e)}",
                "error_type": "PostingError",
                "error_details": str(e),
            }
