from rest_framework import serializers
from .models import G_LAccount, GeneralLedgerEntry, PaymentMethod, Payment, PaymentBatch


class G_LAccountSerializer(serializers.ModelSerializer):
    balance = serializers.SerializerMethodField()

    class Meta:
        model = G_LAccount
        fields = [
            "no",
            "name",
            "indentation",
            "income_balance",
            "accountcategory",
            "debit_credit",
            "accounttype",
            "totaling",
            "balance",
            "direct_posting",
            "blocked",
        ]
        read_only_fields = ["balance"]

    def validate_no(self, value):
        """
        Validate that the account number is unique
        """
        if G_LAccount.objects.filter(no=value).exists():
            if self.instance and self.instance.no == value:
                return value
            raise serializers.ValidationError(
                "An account with this number already exists."
            )
        return value

    def get_balance(self, obj):
        # Prefer annotated values when Filter totals by is applied
        if hasattr(obj, "balance_at_date"):
            return obj.balance_at_date or 0.0
        if hasattr(obj, "balance_range"):
            return obj.balance_range or 0.0
        if hasattr(obj, "balance_filtered"):
            return obj.balance_filtered or 0.0
        return obj.balance

    def validate(self, data):
        """
        Custom validation for the entire object
        """
        if data.get("direct_posting") and data.get("totaling"):
            raise serializers.ValidationError(
                "An account cannot have both direct posting and totaling enabled."
            )
        return data


class GeneralLedgerEntrySerializer(serializers.ModelSerializer):
    user = serializers.SerializerMethodField()
    global_dimension_1_code = serializers.SerializerMethodField()
    global_dimension_2_code = serializers.SerializerMethodField()

    class Meta:
        model = GeneralLedgerEntry
        fields = [
            "id",
            "gl_account",
            "posting_date",
            "document_type",
            "document_no",
            "description",
            "amount",
            "created_at",
            "updated_at",
            "transaction_no",
            "user",
            "global_dimension_1_code",
            "global_dimension_2_code",
        ]
        read_only_fields = ["user", "global_dimension_1_code", "global_dimension_2_code"]

    def get_user(self, obj):
        return obj.user.username

    def get_global_dimension_1_code(self, obj):
        if obj.global_dimension_1:
            return (
                f"{obj.global_dimension_1.code}"
                + (
                    f" - {obj.global_dimension_1.description}"
                    if obj.global_dimension_1.description
                    else ""
                )
            )
        return None

    def get_global_dimension_2_code(self, obj):
        if obj.global_dimension_2:
            return (
                f"{obj.global_dimension_2.code}"
                + (
                    f" - {obj.global_dimension_2.description}"
                    if obj.global_dimension_2.description
                    else ""
                )
            )
        return None


class PaymentMethodSerializer(serializers.ModelSerializer):
    # Nested account details for display (read-only)
    bal_account_no_no = serializers.CharField(
        source="bal_account_no.no", read_only=True, required=False
    )
    bal_account_no_name = serializers.CharField(
        source="bal_account_no.name", read_only=True, required=False
    )
    # Nested bank account details for display (read-only)
    bal_bank_account_no_no = serializers.CharField(
        source="bal_bank_account_no.no", read_only=True, required=False
    )
    bal_bank_account_no_name = serializers.CharField(
        source="bal_bank_account_no.name", read_only=True, required=False
    )
    
    class Meta:
        model = PaymentMethod
        fields = [
            "id",
            "code",
            "description",
            "bal_account_type",
            "bal_account_no",
            "bal_account_no_no",
            "bal_account_no_name",
            "bal_bank_account_no",
            "bal_bank_account_no_no",
            "bal_bank_account_no_name",
            "system_id",
            "requires_amount_received",
        ]
        read_only_fields = ["bal_account_no_no", "bal_account_no_name", "bal_bank_account_no_no", "bal_bank_account_no_name"]


class PaymentBatchSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentBatch
        fields = [
            "id",
            "name",
            "bal_account_type",
            "bal_account_no",
            "no_series",
            "system_id",
        ]


class PaymentSerializer(serializers.ModelSerializer):
    payment_batch_details = PaymentBatchSerializer(
        source="payment_batch", read_only=True
    )
    payment_method_details = PaymentMethodSerializer(
        source="payment_method", read_only=True
    )
    gl_account_details = G_LAccountSerializer(source="gl_account", read_only=True)
    gl_balancing_account_details = G_LAccountSerializer(
        source="gl_balancing_account", read_only=True
    )

    class Meta:
        model = Payment
        fields = [
            "id",
            "system_id",
            "payment_batch",
            "payment_batch_details",
            "payment_method",
            "payment_method_details",
            "payment_date",
            "document_type",
            "document_no",
            "external_document_no",
            "account_type",
            "gl_account",
            "gl_account_details",
            "vendor_account",
            "customer_account",
            "message_to_recipient",
            "description",
            "bal_account_type",
            "gl_balancing_account",
            "gl_balancing_account_details",
            "amount",
            "status",
        ]
        read_only_fields = ["document_no", "system_id"]

    def validate(self, data):
        """
        Custom validation for payment data
        """
        # Validate that only one account is set based on account_type
        account_fields = {
            "G/L Account": data.get("gl_account"),
            "Vendor": data.get("vendor_account"),
            "Customer": data.get("customer_account"),
        }

        account_type = data.get("account_type")
        if not account_type:
            raise serializers.ValidationError("Account type is required")

        if not account_fields.get(account_type):
            raise serializers.ValidationError(
                f"Account number is required for account type {account_type}"
            )

        # Check that only one account field is set
        set_fields = [field for field in account_fields.values() if field is not None]
        if len(set_fields) > 1:
            raise serializers.ValidationError("Only one account field should be set")

        return data
