from rest_framework import serializers
from django.utils.translation import gettext_lazy as _
from .models import Loan, LoanRepayment
from .enums import LoanType, RepaymentAccountType
from bank_account.models import BankAccount
from financials.models import G_LAccount


class LoanSerializer(serializers.ModelSerializer):
    """Serializer for Loan model with camelCase field names"""

    lenderName = serializers.CharField(source="lender_name", read_only=False, required=False)
    loanNo = serializers.CharField(source="loan_no", read_only=True)
    loanType = serializers.CharField(
        source="loan_type",
        read_only=False,
        required=False,
        allow_blank=True,
        allow_null=True,
    )
    loanAmount = serializers.IntegerField(source="loan_amount", read_only=False, required=False)
    disbursementDate = serializers.DateField(
        source="disbursement_date", read_only=False, required=False, allow_null=True
    )
    interestRate = serializers.DecimalField(
        source="interest_rate", max_digits=5, decimal_places=2, read_only=False, required=False, allow_null=True
    )
    repaymentPeriod = serializers.IntegerField(
        source="repayment_period", read_only=False, required=False
    )
    repaymentAccount = serializers.CharField(
        source="repayment_account",
        read_only=False,
        required=False,
        allow_blank=True,
        allow_null=True,
    )
    bankAccount = serializers.PrimaryKeyRelatedField(
        queryset=BankAccount.objects.all(),
        source="bank_account",
        required=False,
        allow_null=True,
    )
    bankAccountNo = serializers.CharField(
        source="bank_account.no", read_only=True, required=False
    )
    bankAccountName = serializers.CharField(
        source="bank_account.name", read_only=True, required=False
    )
    posted = serializers.BooleanField(read_only=True)
    postedDate = serializers.DateField(source="posted_date", read_only=True)
    postedByName = serializers.CharField(source="posted_by.full_name", read_only=True)
    statusDisplay = serializers.CharField(source="get_status_display", read_only=True)
    monthlyPayment = serializers.SerializerMethodField()
    totalInterest = serializers.SerializerMethodField()
    remainingPrincipal = serializers.SerializerMethodField()
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)

    class Meta:
        model = Loan
        fields = [
            "id",
            "loanNo",
            "loanType",
            "lenderName",
            "loanAmount",
            "disbursementDate",
            "interestRate",
            "repaymentPeriod",
            "repaymentAccount",
            "bankAccount",
            "bankAccountNo",
            "bankAccountName",
            "purpose",
            "status",
            "statusDisplay",
            "posted",
            "postedDate",
            "postedByName",
            "monthlyPayment",
            "totalInterest",
            "remainingPrincipal",
            "createdAt",
            "updatedAt",
        ]
        read_only_fields = [
            "loanNo",
            "posted",
            "postedDate",
            "postedByName",
            "monthlyPayment",
            "totalInterest",
            "remainingPrincipal",
            "createdAt",
            "updatedAt",
        ]

    def get_monthlyPayment(self, obj):
        """Calculate monthly payment amount"""
        return obj.calculate_monthly_payment()

    def get_totalInterest(self, obj):
        """Calculate total interest over loan period"""
        return obj.calculate_total_interest()

    def get_remainingPrincipal(self, obj):
        """Get remaining principal after repayments"""
        return obj.get_remaining_principal()

    def create(self, validated_data):
        """Override create to provide defaults for required database fields when creating with partial data"""
        # Provide temporary defaults for required database fields if not provided or None
        # This allows auto-save to create loans incrementally
        from django.utils.timezone import datetime
        
        # Always ensure required database fields have values (even if 0)
        # These will be updated via PATCH as user fills in the form
        if "loan_amount" not in validated_data:
            validated_data["loan_amount"] = 0
        elif validated_data.get("loan_amount") is None:
            validated_data["loan_amount"] = 0
        
        if "interest_rate" not in validated_data:
            validated_data["interest_rate"] = 0
        elif validated_data.get("interest_rate") is None:
            validated_data["interest_rate"] = 0
        
        if "repayment_period" not in validated_data:
            validated_data["repayment_period"] = 1
        elif validated_data.get("repayment_period") is None or validated_data.get("repayment_period") == 0:
            validated_data["repayment_period"] = 1
        
        if "disbursement_date" not in validated_data or validated_data.get("disbursement_date") is None:
            validated_data["disbursement_date"] = datetime.now().date()

        # Stamp branch dimension if not provided
        if validated_data.get("global_dimension_1") is None:
            from dimension.branch_filter import get_branch_for_request
            from dimension.utils import get_first_branch_dimension_value

            request = self.context.get("request")
            branch = get_branch_for_request(request) if request else None
            if not branch and request and request.user:
                branch = getattr(request.user, "global_dimension_1", None)
            if not branch:
                branch = get_first_branch_dimension_value()
            if branch:
                validated_data["global_dimension_1"] = branch

        return super().create(validated_data)

    def validate_loanType(self, value):
        """Validate loan type against enum choices"""
        # Handle None, empty string, or whitespace-only strings
        if value is None:
            return None
        if isinstance(value, str):
            value = value.strip()
            if not value:
                return None
            # Validate against enum choices
            valid_choices = [choice[0] for choice in LoanType.choices()]
            if value not in valid_choices:
                raise serializers.ValidationError(
                    f"Invalid loan type. Must be one of: {', '.join(valid_choices)}"
                )
        return value

    def validate_repaymentAccount(self, value):
        """Validate repayment account against enum choices"""
        # Handle None, empty string, or whitespace-only strings
        if value is None:
            return None
        if isinstance(value, str):
            value = value.strip()
            if not value:
                return None
            # Validate against enum choices
            valid_choices = [choice[0] for choice in RepaymentAccountType.choices()]
            if value not in valid_choices:
                raise serializers.ValidationError(
                    f"Invalid repayment account. Must be one of: {', '.join(valid_choices)}"
                )
        return value

    def validate(self, data):
        """Validate loan data"""
        # Get the instance if this is an update (partial_update)
        instance = getattr(self, 'instance', None)
        is_partial = self.partial
        
        # For create (not partial), we need at least lender_name to create a loan
        # Other fields can be added later via PATCH
        if not instance and not is_partial:
            # Minimum required: lender_name
            if "lender_name" not in data or not data["lender_name"]:
                raise serializers.ValidationError(
                    {"lenderName": "Lender name is required to create a loan."}
                )
        
        # Validate loan amount is positive (only if provided)
        if data.get("loan_amount") is not None:
            if data["loan_amount"] <= 0:
                raise serializers.ValidationError(
                    {"loanAmount": "Loan amount must be greater than zero"}
                )

        # Validate interest rate is between 0 and 100 (only if provided)
        if data.get("interest_rate") is not None:
            rate = data["interest_rate"]
            if rate < 0 or rate > 100:
                raise serializers.ValidationError(
                    {"interestRate": "Interest rate must be between 0 and 100"}
                )

        # Validate repayment period is positive (only if provided)
        if data.get("repayment_period") is not None:
            if data["repayment_period"] <= 0:
                raise serializers.ValidationError(
                    {"repaymentPeriod": "Repayment period must be greater than zero"}
                )

        # Validate bank account is required when repayment_account is "Bank/Mobile Money"
        repayment_account = data.get("repayment_account")
        # For partial updates, use existing value if not provided
        if is_partial and instance and repayment_account is None:
            repayment_account = instance.repayment_account
            
        bank_account = data.get("bank_account")
        # For partial updates, use existing value if not provided
        if is_partial and instance and bank_account is None:
            bank_account = instance.bank_account

        # For auto-save (partial updates), allow user to select repayment account first,
        # then select bank account later. Only validate bank account requirement for:
        # 1. Full updates/creates (not partial)
        # 2. Partial updates where BOTH repayment_account AND bank_account are being updated
        #    (meaning user is trying to set repayment_account to "Bank/Mobile Money" 
        #     while also removing/clearing the bank_account)
        if repayment_account == "Bank/Mobile Money" and not bank_account:
            # Skip validation for partial updates where only repayment_account is being set
            # This allows auto-save to work incrementally
            if is_partial:
                # Only validate if bank_account is explicitly being cleared (set to None)
                # AND there's no existing bank_account on the instance
                if "bank_account" in data and data["bank_account"] is None:
                    if not (instance and instance.bank_account):
                        raise serializers.ValidationError(
                            {
                                "bankAccount": "Bank account is required when Repayment Account is 'Bank/Mobile Money'"
                            }
                        )
            else:
                # For full updates/creates, always validate
                raise serializers.ValidationError(
                    {
                        "bankAccount": "Bank account is required when Repayment Account is 'Bank/Mobile Money'"
                    }
                )

        return data


class LoanRepaymentSerializer(serializers.ModelSerializer):
    """Serializer for LoanRepayment model with camelCase field names"""

    loan = serializers.PrimaryKeyRelatedField(
        queryset=Loan.objects.all(),
        required=False,
        allow_null=True
    )
    loanNo = serializers.CharField(source="loan.loan_no", read_only=True)
    lenderName = serializers.CharField(source="loan.lender_name", read_only=True)
    repaymentNo = serializers.CharField(source="repayment_no", read_only=True)
    paymentDate = serializers.DateField(
        source="payment_date",
        read_only=False,
        required=False,
        allow_null=True
    )
    amountPaid = serializers.IntegerField(
        source="amount_paid",
        read_only=False,
        required=False,
        allow_null=True
    )
    principalAmount = serializers.IntegerField(
        source="principal_amount", read_only=True
    )
    interestAmount = serializers.IntegerField(source="interest_amount", read_only=True)
    paymentMethod = serializers.CharField(
        source="payment_method",
        read_only=False,
        required=False,
        allow_blank=True,
        allow_null=True
    )
    bankAccount = serializers.PrimaryKeyRelatedField(
        queryset=BankAccount.objects.all(),
        source="bank_account",
        required=False,
        allow_null=True,
    )
    bankAccountNo = serializers.CharField(
        source="bank_account.no", read_only=True, required=False
    )
    bankAccountName = serializers.CharField(
        source="bank_account.name", read_only=True, required=False
    )
    posted = serializers.BooleanField(read_only=True)
    postedDate = serializers.DateField(source="posted_date", read_only=True)
    postedByName = serializers.CharField(source="posted_by.full_name", read_only=True)
    statusDisplay = serializers.CharField(source="get_status_display", read_only=True)
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)

    class Meta:
        model = LoanRepayment
        fields = [
            "id",
            "loan",
            "loanNo",
            "lenderName",
            "repaymentNo",
            "paymentDate",
            "amountPaid",
            "principalAmount",
            "interestAmount",
            "paymentMethod",
            "bankAccount",
            "bankAccountNo",
            "bankAccountName",
            "status",
            "statusDisplay",
            "posted",
            "postedDate",
            "postedByName",
            "createdAt",
            "updatedAt",
        ]
        read_only_fields = [
            "repaymentNo",
            "principalAmount",
            "interestAmount",
            "posted",
            "postedDate",
            "postedByName",
            "createdAt",
            "updatedAt",
        ]

    def create(self, validated_data):
        """Override create to provide defaults for required database fields when creating with partial data"""
        # Provide temporary defaults for required database fields if not provided or None
        # This allows auto-save to create repayments incrementally
        from django.utils.timezone import datetime
        
        # Always ensure required database fields have values (even if 0)
        # These will be updated via PATCH as user fills in the form
        if "amount_paid" not in validated_data:
            validated_data["amount_paid"] = 0
        elif validated_data.get("amount_paid") is None:
            validated_data["amount_paid"] = 0
        
        if "payment_date" not in validated_data or validated_data.get("payment_date") is None:
            validated_data["payment_date"] = datetime.now().date()
        
        # Payment method can be null initially
        if "payment_method" not in validated_data:
            validated_data["payment_method"] = None

        # Stamp branch dimension: prefer loan's branch, else request context
        if validated_data.get("global_dimension_1") is None:
            loan = validated_data.get("loan")
            if loan and getattr(loan, "global_dimension_1", None):
                validated_data["global_dimension_1"] = loan.global_dimension_1
            else:
                from dimension.branch_filter import get_branch_for_request
                from dimension.utils import get_first_branch_dimension_value

                request = self.context.get("request")
                branch = get_branch_for_request(request) if request else None
                if not branch and request and request.user:
                    branch = getattr(request.user, "global_dimension_1", None)
                if not branch:
                    branch = get_first_branch_dimension_value()
                if branch:
                    validated_data["global_dimension_1"] = branch

        return super().create(validated_data)

    def validate(self, data):
        """Validate repayment data"""
        # Get the instance if this is an update (partial_update)
        instance = getattr(self, 'instance', None)
        is_partial = self.partial
        
        # For create (not partial), we need at least loan to create a repayment
        # Other fields can be added later via PATCH
        if not instance and not is_partial:
            # Minimum required: loan
            if "loan" not in data or not data["loan"]:
                raise serializers.ValidationError(
                    {"loan": "Loan is required to create a repayment."}
                )
        
        # Validate amount paid is positive (only if provided)
        if data.get("amount_paid") is not None:
            if data["amount_paid"] <= 0:
                raise serializers.ValidationError(
                    {"amountPaid": "Amount paid must be greater than zero"}
                )

        # Validate payment date is not before loan disbursement date
        loan = data.get("loan")
        # For partial updates, use existing value if not provided
        if is_partial and instance and loan is None:
            loan = instance.loan
            
        payment_date = data.get("payment_date")
        # For partial updates, use existing value if not provided
        if is_partial and instance and payment_date is None:
            payment_date = instance.payment_date

        if loan and payment_date:
            if payment_date < loan.disbursement_date:
                raise serializers.ValidationError(
                    {
                        "paymentDate": "Payment date cannot be before loan disbursement date"
                    }
                )

        # Validate bank account is required when payment_method is "Bank/Mobile Money"
        payment_method = data.get("payment_method")
        # For partial updates, use existing value if not provided
        if is_partial and instance and payment_method is None:
            payment_method = instance.payment_method
            
        bank_account = data.get("bank_account")
        # For partial updates, use existing value if not provided
        if is_partial and instance and bank_account is None:
            bank_account = instance.bank_account

        # For auto-save (partial updates), allow user to select payment method first,
        # then select bank account later. Only validate bank account requirement for:
        # 1. Full updates/creates (not partial)
        # 2. Partial updates where BOTH payment_method AND bank_account are being updated
        if payment_method == "Bank/Mobile Money" and not bank_account:
            # Skip validation for partial updates where only payment_method is being set
            # This allows auto-save to work incrementally
            if is_partial:
                # Only validate if bank_account is explicitly being cleared (set to None)
                # AND there's no existing bank_account on the instance
                if "bank_account" in data and data["bank_account"] is None:
                    if not (instance and instance.bank_account):
                        raise serializers.ValidationError(
                            {
                                "bankAccount": "Bank account is required when Payment Method is 'Bank/Mobile Money'"
                            }
                        )
            else:
                # For full updates/creates, always validate
                raise serializers.ValidationError(
                    {
                        "bankAccount": "Bank account is required when Payment Method is 'Bank/Mobile Money'"
                    }
                )

        return data
