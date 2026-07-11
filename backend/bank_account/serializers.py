from rest_framework import serializers
from django.db.models import Sum, Case, When, DecimalField, Value
from .models import BankAccount, BankAccountLedgerEntry, BankAccountPostingGroup
from financials.models import G_LAccount


class BankAccountPostingGroupSerializer(serializers.ModelSerializer):
    """Serializer for Bank Account Posting Group"""

    gl_account_no = serializers.SerializerMethodField()

    class Meta:
        model = BankAccountPostingGroup
        fields = [
            "code",
            "gl_account_no",
            "bank_account",
            "created_at",
            "updated_at",
            "system_id",
        ]
        read_only_fields = ["created_at", "updated_at", "system_id", "gl_account_no"]

    def get_gl_account_no(self, obj):
        """Return G/L Account No. in format: No. - Name"""
        if obj.bank_account:
            return f"{obj.bank_account.no} - {obj.bank_account.name}"
        return None


class BankAccountSerializer(serializers.ModelSerializer):
    """Serializer for Bank Account"""

    bank_account_posting_group_name = serializers.CharField(
        source="bank_account_posting_group.description", read_only=True
    )
    bank_account_posting_group_code = serializers.CharField(
        source="bank_account_posting_group.code", read_only=True
    )
    debit_amount = serializers.SerializerMethodField()
    credit_amount = serializers.SerializerMethodField()
    balance = serializers.SerializerMethodField()

    def _get_branch_filtered_entries(self, obj):
        """Return ledger entries queryset filtered by branch when multi-branch is enabled."""
        qs = BankAccountLedgerEntry.objects.filter(
            bank_account_no=obj.no,
            reversed=False,
        )
        request = self.context.get("request")
        if request:
            from dimension.branch_filter import filter_queryset_by_branch
            qs = filter_queryset_by_branch(qs, request.user, request=request)
        return qs

    def get_debit_amount(self, obj):
        if not obj.no:
            return 0.00
        return (
            self._get_branch_filtered_entries(obj).aggregate(
                total=Sum(
                    Case(
                        When(amount__gt=0, then="amount"),
                        default=Value(0),
                        output_field=DecimalField(max_digits=15, decimal_places=2),
                    )
                )
            )["total"]
            or 0.00
        )

    def get_credit_amount(self, obj):
        if not obj.no:
            return 0.00
        return abs(
            self._get_branch_filtered_entries(obj).aggregate(
                total=Sum(
                    Case(
                        When(amount__lt=0, then="amount"),
                        default=Value(0),
                        output_field=DecimalField(max_digits=15, decimal_places=2),
                    )
                )
            )["total"]
            or 0.00
        )

    def get_balance(self, obj):
        if not obj.no:
            return 0.00
        return float(self.get_debit_amount(obj)) - float(self.get_credit_amount(obj))

    class Meta:
        model = BankAccount
        fields = [
            "system_id",
            "no",
            "name",
            "address",
            "contact",
            "bank_account_no",
            "bank_branch_no",
            "min_balance",
            "bank_account_posting_group",
            "bank_account_posting_group_name",
            "bank_account_posting_group_code",
            "debit_amount",
            "credit_amount",
            "balance",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "system_id",
            "no",
            "created_at",
            "updated_at",
            "debit_amount",
            "credit_amount",
            "balance",
        ]


class BankAccountLedgerEntrySerializer(serializers.ModelSerializer):
    """Serializer for Bank Account Ledger Entry"""

    bank_account_no = serializers.CharField(source="bank_account_no.no", read_only=True)
    bank_account_name = serializers.CharField(
        source="bank_account_no.name", read_only=True
    )
    bank_account_posting_group_name = serializers.CharField(
        source="bank_account_posting_group.description", read_only=True
    )
    debit_amount = serializers.DecimalField(
        max_digits=15, decimal_places=2, read_only=True
    )
    credit_amount = serializers.DecimalField(
        max_digits=15, decimal_places=2, read_only=True
    )
    user_name = serializers.CharField(source="user.full_name", read_only=True)
    global_dimension_1_name = serializers.CharField(
        source="global_dimension_1.description", read_only=True
    )

    class Meta:
        model = BankAccountLedgerEntry
        fields = [
            "entry_no",
            "bank_account_no",
            "bank_account_name",
            "posting_date",
            "document_type",
            "document_date",
            "document_no",
            "description",
            "amount",
            "remaining_amount",
            "bank_account_posting_group",
            "bank_account_posting_group_name",
            "bal_account_type",
            "bal_account_no",
            "statement_status",
            "statement_no",
            "statement_line_no",
            "debit_amount",
            "credit_amount",
            "global_dimension_1",
            "global_dimension_1_name",
            "user",
            "user_name",
            "reversed",
            "reversed_by_entry_no",
            "reversed_entry_no",
            "reversed_by_user",
            "reversed_date",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "entry_no",
            "debit_amount",
            "credit_amount",
            "created_at",
            "updated_at",
            "reversed",
            "reversed_by_entry_no",
            "reversed_entry_no",
            "reversed_by_user",
            "reversed_date",
        ]
