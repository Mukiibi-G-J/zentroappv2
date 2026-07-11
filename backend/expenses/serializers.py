from rest_framework import serializers
from django.utils import timezone
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from .models import (
    Expense,
    ExpenseType as ExpenseTypeModel,
    ExpenseCategory as ExpenseCategoryModel,
)
from financials.models import G_LAccount, PaymentMethod
from .enums import ExpenseDocumentType, ExpenseStatus


class ExpenseSerializer(serializers.ModelSerializer):
    """Serializer for Expense model"""

    gl_account_name = serializers.CharField(source="gl_account.name", read_only=True)
    balancing_account_name = serializers.CharField(
        source="balancing_account.name", read_only=True
    )
    payment_method_name = serializers.CharField(
        source="payment_method.description", read_only=True
    )
    posted_by_name = serializers.CharField(source="posted_by.full_name", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    expense_type_display = serializers.SerializerMethodField()
    expense_type_name = serializers.CharField(
        source="expense_type.name", read_only=True
    )
    expense_category_id = serializers.IntegerField(
        source="expense_type.category.id", read_only=True
    )
    expense_category_name = serializers.CharField(
        source="expense_type.category.name", read_only=True
    )
    expense_category_code = serializers.CharField(
        source="expense_type.category.code", read_only=True
    )

    class Meta:
        model = Expense
        fields = [
            "id",
            "document_no",
            "posting_date",
            "document_type",
            "external_document_no",
            "expense_type",
            "expense_type_display",
            "expense_type_name",
            "expense_category_id",
            "expense_category_name",
            "expense_category_code",
            "description",
            "amount",
            "payment_method",
            "payment_method_name",
            "status",
            "status_display",
            "gl_account",
            "gl_account_name",
            "balancing_account",
            "balancing_account_name",
            "posted_at",
            "posted_by",
            "posted_by_name",
            "global_dimension_1",
            "global_dimension_2",
            "dimension_set",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "document_no",
            "document_type",
            "external_document_no",
            "gl_account",
            "balancing_account",
            "posted_at",
            "posted_by",
        ]
        extra_kwargs = {
            # Built server-side from request branch (X-Branch-Id / user) on create/update.
            "dimension_set": {"required": False, "allow_null": True},
            "global_dimension_1": {"required": False, "allow_null": True},
            "global_dimension_2": {"required": False, "allow_null": True},
        }

    def get_expense_type_display(self, obj):
        if obj.expense_type:
            return obj.expense_type.name
        return ""

    def validate(self, data):
        """Validate expense data"""
        # Validate expense type is selected
        if not data.get("expense_type"):
            raise serializers.ValidationError("Expense type is required")

        # Validate amount is positive
        if data.get("amount") and data["amount"] <= 0:
            raise serializers.ValidationError("Amount must be greater than zero")

        # Payment method is required only when posting the expense
        # Allow creation without payment method for draft expenses
        status = data.get("status", "Open")
        if status == "Posted" and not data.get("payment_method"):
            raise serializers.ValidationError(
                "Payment method is required when posting expense"
            )

        return data

    def _stamp_header_dimensions(self, validated_data):
        """Stamp branch + dimension_set from request context when omitted (BC-style)."""
        request = self.context.get("request")

        if validated_data.get("global_dimension_1") is None and request:
            from dimension.branch_filter import get_branch_for_request
            from dimension.utils import get_first_branch_dimension_value

            branch = get_branch_for_request(request)
            if not branch and getattr(request, "user", None):
                branch = getattr(request.user, "global_dimension_1", None)
            if not branch:
                branch = get_first_branch_dimension_value()
            if branch:
                validated_data["global_dimension_1"] = branch

        if validated_data.get("dimension_set") is None:
            from financials.models import GeneralLedgerSetup
            from dimension.models import get_posting_dimension_payload

            gl_setup = GeneralLedgerSetup.objects.first()
            payload = get_posting_dimension_payload(
                global_dimension_1=validated_data.get("global_dimension_1"),
                global_dimension_2=validated_data.get("global_dimension_2"),
                dimension_set=None,
                gl_setup=gl_setup,
            )
            validated_data["dimension_set"] = payload.get("dimension_set")
            if payload.get("global_dimension_1") is not None:
                validated_data["global_dimension_1"] = payload["global_dimension_1"]
            if payload.get("global_dimension_2") is not None:
                validated_data["global_dimension_2"] = payload["global_dimension_2"]

        return validated_data

    def create(self, validated_data):
        """Create expense with auto-generated document number, G/L accounts, and branch dimensions."""
        try:
            validated_data.setdefault(
                "document_type", ExpenseDocumentType.EXPENSE.value
            )
            validated_data = self._stamp_header_dimensions(validated_data)
            if not validated_data.get("global_dimension_1") or not validated_data.get(
                "dimension_set"
            ):
                raise serializers.ValidationError(
                    {
                        "non_field_errors": [
                            "Branch dimension is required. Configure Global Dimension 1 "
                            "in General Ledger Setup or select a branch."
                        ]
                    }
                )
            return super().create(validated_data)
        except serializers.ValidationError:
            raise
        except Exception as e:
            raise serializers.ValidationError(
                {
                    "non_field_errors": [
                        f"Configuration Error: {str(e)}. "
                        "Please contact your administrator to set up branch dimensions."
                    ]
                }
            )

    def update(self, instance, validated_data):
        """Keep dimension_set in sync when branch shortcut changes."""
        if "global_dimension_1" in validated_data:
            from dimension.models import validate_shortcut_dimension_value

            validate_shortcut_dimension_value(
                instance, 1, validated_data["global_dimension_1"]
            )
            validated_data["dimension_set"] = instance.dimension_set
            validated_data["global_dimension_1"] = instance.global_dimension_1
        elif not instance.dimension_set_id or not instance.global_dimension_1_id:
            validated_data = self._stamp_header_dimensions(validated_data)
        return super().update(instance, validated_data)


class ExpensePreviewSerializer(serializers.Serializer):
    """Serializer for expense posting preview"""

    expense_id = serializers.IntegerField()
    document_no = serializers.CharField()
    posting_date = serializers.DateField()
    description = serializers.CharField()
    amount = serializers.IntegerField()
    expense_type = serializers.CharField()
    payment_method = serializers.CharField()

    # Preview entries
    debit_entry = serializers.DictField()
    credit_entry = serializers.DictField()

    def to_representation(self, instance):
        """Generate preview representation"""
        if isinstance(instance, Expense):
            expense = instance
        else:
            expense = Expense.objects.get(id=instance["expense_id"])

        # Get posting preview
        preview_entries = expense.get_posting_preview()

        if not preview_entries:
            raise serializers.ValidationError(
                "Cannot generate preview - missing G/L accounts"
            )

        debit_entry = preview_entries[0]
        credit_entry = preview_entries[1]

        return {
            "expense_id": expense.id,
            "document_no": expense.document_no,
            "posting_date": expense.posting_date,
            "description": expense.description,
            "amount": expense.amount,
            "expense_type": expense.expense_type,
            "payment_method": (
                expense.payment_method.description if expense.payment_method else ""
            ),
            "debit_entry": {
                "gl_account": debit_entry["gl_account"].no,
                "gl_account_name": debit_entry["gl_account"].name,
                "description": debit_entry["description"],
                "amount": debit_entry["amount"],
                "type": debit_entry["type"],
            },
            "credit_entry": {
                "gl_account": credit_entry["gl_account"].no,
                "gl_account_name": credit_entry["gl_account"].name,
                "description": credit_entry["description"],
                "amount": credit_entry["amount"],
                "type": credit_entry["type"],
            },
        }


class ExpensePostingSerializer(serializers.Serializer):
    """Serializer for posting expenses"""

    expense_id = serializers.IntegerField()
    success = serializers.BooleanField()
    message = serializers.CharField()
    posted_entries = serializers.ListField(required=False)

    def validate_expense_id(self, value):
        """Validate expense exists and can be posted"""
        try:
            expense = Expense.objects.get(id=value)
        except Expense.DoesNotExist:
            raise serializers.ValidationError("Expense not found")

        if expense.status != ExpenseStatus.OPEN.value:
            raise serializers.ValidationError("Only open expenses can be posted")

        if not expense.gl_account or not expense.balancing_account:
            raise serializers.ValidationError("G/L accounts must be set before posting")

        return value

    def create(self, validated_data):
        """Post the expense"""
        expense_id = validated_data["expense_id"]
        expense = Expense.objects.get(id=expense_id)
        user = self.context["request"].user

        try:
            posted_entries = expense.post_expense(user)

            return {
                "expense_id": expense_id,
                "success": True,
                "message": f"Expense {expense.document_no} posted successfully",
                "posted_entries": [
                    {
                        "id": entry.id,
                        "gl_account": entry.gl_account.no,
                        "gl_account_name": entry.gl_account.name,
                        "amount": entry.amount,
                        "description": entry.description,
                    }
                    for entry in posted_entries
                ],
            }

        except Exception as e:
            return {
                "expense_id": expense_id,
                "success": False,
                "message": f"Failed to post expense: {str(e)}",
                "posted_entries": [],
            }


class ExpenseCategorySerializer(serializers.ModelSerializer):
    """Serializer for ExpenseCategory model"""

    default_gl_account_name = serializers.CharField(
        source="default_gl_account.name", read_only=True
    )

    class Meta:
        model = ExpenseCategoryModel
        fields = [
            "id",
            "code",
            "name",
            "description",
            "icon",
            "default_gl_account",
            "default_gl_account_name",
            "is_active",
            "is_system",
        ]
        read_only_fields = ["id", "is_system", "created_at", "updated_at", "system_id"]


class ExpenseTypeSerializer(serializers.ModelSerializer):
    """Serializer for ExpenseType model"""

    gl_account_name = serializers.CharField(source="gl_account.name", read_only=True)
    category_detail = ExpenseCategorySerializer(source="category", read_only=True)
    category_name = serializers.CharField(source="category.name", read_only=True)
    category_code = serializers.CharField(source="category.code", read_only=True)
    category = serializers.PrimaryKeyRelatedField(
        queryset=ExpenseCategoryModel.objects.filter(is_active=True),
        required=False,
        allow_null=True,
    )
    name = serializers.CharField(required=False, allow_blank=False)
    code = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    class Meta:
        model = ExpenseTypeModel
        fields = [
            "id",
            "code",
            "name",
            "description",
            "category",
            "category_name",
            "category_code",
            "category_detail",
            "gl_account",
            "gl_account_name",
            "is_active",
            "is_user_defined",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
            "system_id",
            "is_user_defined",
        ]

    def validate(self, attrs):
        """Ensure we have a code; auto-generate from the name when omitted."""
        code = attrs.get("code")
        name = attrs.get("name")
        
        # For updates, use existing instance values if not provided
        if self.instance:
            name = attrs.get("name") or self.instance.name
            code = attrs.get("code") or self.instance.code
        
        # Auto-generate code from name if code is missing and name exists
        if not code and name:
            generated = slugify(name or "").replace("-", "")
            if not generated:
                generated = (name or "").replace(" ", "")
            attrs["code"] = (generated[:10] or "EXP-TYPE").upper()
        
        # For creates, name is required
        if not self.instance and not name:
            raise serializers.ValidationError({"name": _("Name is required for new expense types.")})
        
        # Category is now optional - no validation required
        return attrs

    def create(self, validated_data):
        validated_data.setdefault("is_user_defined", True)
        validated_data = self._apply_gl_account_fallback(validated_data)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        # Prevent clients from toggling system flags directly
        validated_data.pop("is_user_defined", None)
        validated_data = self._apply_gl_account_fallback(
            validated_data, instance=instance
        )
        return super().update(instance, validated_data)

    def _apply_gl_account_fallback(self, attrs, instance=None):
        """Ensure a GL account is always set based on the selected category."""
        category = attrs.get("category") or (instance.category if instance else None)
        # If clients explicitly send null to reset, drop the key so we can inherit again
        if "gl_account" in attrs and attrs["gl_account"] is None:
            attrs.pop("gl_account")
        if not attrs.get("gl_account") and category and category.default_gl_account:
            attrs["gl_account"] = category.default_gl_account
        return attrs
