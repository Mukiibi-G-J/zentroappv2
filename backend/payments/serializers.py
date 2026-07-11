from rest_framework import serializers
from django.contrib.contenttypes.models import ContentType
from .models import PaymentJournal
from financials.models import PaymentMethod


class PaymentJournalSerializer(serializers.ModelSerializer):
    """Serializer for PaymentJournal model with GenericForeignKey support"""

    # Account information
    account_name = serializers.CharField(read_only=True)
    account_content_type_id = serializers.IntegerField(required=False, allow_null=True)
    account_object_id = serializers.IntegerField(required=False, allow_null=True)

    # Balancing account information
    bal_account_name = serializers.CharField(read_only=True)
    bal_account_content_type_id = serializers.IntegerField(
        required=False, allow_null=True
    )
    bal_account_object_id = serializers.IntegerField(required=False, allow_null=True)

    # Applies to document information
    applies_to_doc_name = serializers.CharField(read_only=True)
    applies_to_content_type_id = serializers.IntegerField(
        required=False, allow_null=True
    )
    applies_to_object_id = serializers.IntegerField(required=False, allow_null=True)

    # Payment method information
    payment_method_name = serializers.CharField(read_only=True)
    payment_method = serializers.PrimaryKeyRelatedField(
        queryset=PaymentMethod.objects.all(),
        required=False,
        allow_null=True,
    )

    class Meta:
        model = PaymentJournal
        fields = [
            "id",
            "system_id",
            "posting_date",
            "document_type",
            "document_no",
            "external_document_no",
            "description",
            "account_type",
            "account_content_type_id",
            "account_object_id",
            "account_name",
            "description",
            "payment_method",
            "payment_method_name",
            "amount",
            "bal_account_type",
            "bal_account_content_type_id",
            "bal_account_object_id",
            "bal_account_name",
            "status",
            "application_status",
            "applies_to_doc_type",
            "applies_to_content_type_id",
            "applies_to_object_id",
            "applies_to_doc_name",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "system_id",
            "account_name",
            "bal_account_name",
            "applies_to_doc_name",
            "payment_method_name",
            "created_at",
            "updated_at",
        ]
        extra_kwargs = {
            "document_no": {"allow_null": True, "allow_blank": True, "required": False},
            "account_type": {
                "allow_null": True,
                "allow_blank": True,
                "required": False,
            },
            "bal_account_type": {
                "allow_null": True,
                "allow_blank": True,
                "required": False,
            },
        }

    def validate(self, data):
        """Custom validation for the PaymentJournal model"""
        # Validate account information - only validate if account_type is provided and not empty
        account_type = data.get("account_type")
        account_content_type_id = data.get("account_content_type_id")
        account_object_id = data.get("account_object_id")

        # Only validate if account_type is a real value (not default/placeholder) and no account is selected
        if (
            account_type
            and account_type.strip()
            and account_type
            not in [
                "",
                "Customer",
                "customer",
                "Vendor",
                "vendor",
                None,
            ]  # Skip validation for empty or default values
            and not (account_content_type_id and account_object_id)
        ):
            raise serializers.ValidationError(
                {
                    "account_content_type_id": "Account content type and object ID are required when account type is specified",
                    "account_object_id": "Account content type and object ID are required when account type is specified",
                }
            )

        # Validate balancing account information - only validate if bal_account_type is provided and not empty
        bal_account_type = data.get("bal_account_type")
        bal_account_content_type_id = data.get("bal_account_content_type_id")
        bal_account_object_id = data.get("bal_account_object_id")

        # Only validate if bal_account_type is a real value (not default/placeholder) and no account is selected
        if (
            bal_account_type
            and bal_account_type.strip()
            and bal_account_type
            not in [
                "",
                "G/L Account",
                "g/l account",
                None,
            ]  # Skip validation for empty or default values
            and not (bal_account_content_type_id and bal_account_object_id)
        ):
            raise serializers.ValidationError(
                {
                    "bal_account_content_type_id": "Balancing account content type and object ID are required when balancing account type is specified",
                    "bal_account_object_id": "Balancing account content type and object ID are required when balancing account type is specified",
                }
            )

        # Validate applies_to fields - only validate if applies_to_doc_type is provided and not empty
        applies_to_doc_type = data.get("applies_to_doc_type")
        applies_to_content_type_id = data.get("applies_to_content_type_id")
        applies_to_object_id = data.get("applies_to_object_id")

        if (
            applies_to_doc_type
            and applies_to_doc_type.strip()
            and not (applies_to_content_type_id and applies_to_object_id)
        ):
            raise serializers.ValidationError(
                {
                    "applies_to_content_type_id": "Applies to content type and object ID are required when applies to document type is specified",
                    "applies_to_object_id": "Applies to content type and object ID are required when applies to document type is specified",
                }
            )

        return data

    def create(self, validated_data):
        """Create a new PaymentJournal instance"""
        # Extract GenericForeignKey data
        account_content_type_id = validated_data.pop("account_content_type_id", None)
        account_object_id = validated_data.pop("account_object_id", None)
        bal_account_content_type_id = validated_data.pop(
            "bal_account_content_type_id", None
        )
        bal_account_object_id = validated_data.pop("bal_account_object_id", None)
        applies_to_content_type_id = validated_data.pop(
            "applies_to_content_type_id", None
        )
        applies_to_object_id = validated_data.pop("applies_to_object_id", None)

        # Auto-populate balancing account fields from payment method
        payment_method = validated_data.get("payment_method")
        if (
            payment_method
            and not bal_account_content_type_id
            and not bal_account_object_id
        ):
            print(
                f"Auto-populating balancing account from payment method: {payment_method}"
            )
            validated_data["bal_account_type"] = payment_method.bal_account_type
            if payment_method.bal_account_no:
                # Get the content type for G_LAccount
                gl_account_content_type = ContentType.objects.get_for_model(
                    PaymentMethod._meta.get_field("bal_account_no").related_model
                )
                validated_data["bal_account_content_type_id"] = (
                    gl_account_content_type.id
                )
                validated_data["bal_account_object_id"] = (
                    payment_method.bal_account_no.no
                )
                print(f"Set bal_account_content_type_id: {gl_account_content_type.id}")
                print(f"Set bal_account_object_id: {payment_method.bal_account_no.no}")

        # Debug logging
        print(
            f"Creating PaymentJournal with account_content_type_id: {account_content_type_id}"
        )
        print(f"Creating PaymentJournal with account_object_id: {account_object_id}")
        print(
            f"Creating PaymentJournal with account_type: {validated_data.get('account_type')}"
        )

        # Set GenericForeignKey fields
        if account_content_type_id and account_object_id:
            validated_data["account_content_type_id"] = account_content_type_id
            validated_data["account_object_id"] = account_object_id
            print(f"Set account_content_type_id: {account_content_type_id}")
            print(f"Set account_object_id: {account_object_id}")
        elif account_object_id and not account_content_type_id:
            print(
                f"WARNING: account_object_id provided ({account_object_id}) but no account_content_type_id"
            )
            # Try to infer content type from account_type
            account_type = validated_data.get("account_type")
            if account_type:
                try:
                    if account_type.lower() == "vendor":
                        content_type = ContentType.objects.get(model="vendor")
                        validated_data["account_content_type_id"] = content_type.id
                        validated_data["account_object_id"] = account_object_id
                        print(f"Inferred vendor content type: {content_type.id}")
                    elif account_type.lower() == "customer":
                        content_type = ContentType.objects.get(model="customer")
                        validated_data["account_content_type_id"] = content_type.id
                        validated_data["account_object_id"] = account_object_id
                        print(f"Inferred customer content type: {content_type.id}")
                except ContentType.DoesNotExist:
                    print(f"ERROR: Could not find content type for {account_type}")

        if bal_account_content_type_id and bal_account_object_id:
            validated_data["bal_account_content_type_id"] = bal_account_content_type_id
            validated_data["bal_account_object_id"] = bal_account_object_id

        if applies_to_content_type_id and applies_to_object_id:
            validated_data["applies_to_content_type_id"] = applies_to_content_type_id
            validated_data["applies_to_object_id"] = applies_to_object_id

        instance = super().create(validated_data)
        print(f"Created PaymentJournal instance: {instance}")
        print(f"Instance account_name: {instance.account_name}")
        print(f"Instance account_no: {instance.account_no}")
        return instance

    def update(self, instance, validated_data):
        """Update an existing PaymentJournal instance"""
        # Extract GenericForeignKey data
        account_content_type_id = validated_data.pop("account_content_type_id", None)
        account_object_id = validated_data.pop("account_object_id", None)
        bal_account_content_type_id = validated_data.pop(
            "bal_account_content_type_id", None
        )
        bal_account_object_id = validated_data.pop("bal_account_object_id", None)
        applies_to_content_type_id = validated_data.pop(
            "applies_to_content_type_id", None
        )
        applies_to_object_id = validated_data.pop("applies_to_object_id", None)

        # Auto-populate balancing account fields from payment method
        payment_method = validated_data.get("payment_method")
        if (
            payment_method
            and not bal_account_content_type_id
            and not bal_account_object_id
        ):
            print(
                f"Auto-populating balancing account from payment method: {payment_method}"
            )
            validated_data["bal_account_type"] = payment_method.bal_account_type
            if payment_method.bal_account_no:
                # Get the content type for G_LAccount
                gl_account_content_type = ContentType.objects.get_for_model(
                    PaymentMethod._meta.get_field("bal_account_no").related_model
                )
                validated_data["bal_account_content_type_id"] = (
                    gl_account_content_type.id
                )
                validated_data["bal_account_object_id"] = (
                    payment_method.bal_account_no.no
                )
                print(f"Set bal_account_content_type_id: {gl_account_content_type.id}")
                print(f"Set bal_account_object_id: {payment_method.bal_account_no.no}")

        # Debug logging
        print(
            f"Updating PaymentJournal with account_content_type_id: {account_content_type_id}"
        )
        print(f"Updating PaymentJournal with account_object_id: {account_object_id}")
        print(
            f"Updating PaymentJournal with account_type: {validated_data.get('account_type')}"
        )

        # Set GenericForeignKey fields
        if account_content_type_id and account_object_id:
            validated_data["account_content_type_id"] = account_content_type_id
            validated_data["account_object_id"] = account_object_id
            print(f"Set account_content_type_id: {account_content_type_id}")
            print(f"Set account_object_id: {account_object_id}")
        elif account_object_id and not account_content_type_id:
            print(
                f"WARNING: account_object_id provided ({account_object_id}) but no account_content_type_id"
            )
            # Try to infer content type from account_type
            account_type = validated_data.get("account_type")
            if account_type:
                try:
                    if account_type.lower() == "vendor":
                        content_type = ContentType.objects.get(model="vendor")
                        validated_data["account_content_type_id"] = content_type.id
                        validated_data["account_object_id"] = account_object_id
                        print(f"Inferred vendor content type: {content_type.id}")
                    elif account_type.lower() == "customer":
                        content_type = ContentType.objects.get(model="customer")
                        validated_data["account_content_type_id"] = content_type.id
                        validated_data["account_object_id"] = account_object_id
                        print(f"Inferred customer content type: {content_type.id}")
                except ContentType.DoesNotExist:
                    print(f"ERROR: Could not find content type for {account_type}")

        if bal_account_content_type_id and bal_account_object_id:
            validated_data["bal_account_content_type_id"] = bal_account_content_type_id
            validated_data["bal_account_object_id"] = bal_account_object_id

        if applies_to_content_type_id and applies_to_object_id:
            validated_data["applies_to_content_type_id"] = applies_to_content_type_id
            validated_data["applies_to_object_id"] = applies_to_object_id

        instance = super().update(instance, validated_data)
        print(f"Updated PaymentJournal instance: {instance}")
        print(f"Instance account_name: {instance.account_name}")
        print(f"Instance account_no: {instance.account_no}")
        return instance


class PaymentJournalListSerializer(serializers.ModelSerializer):
    """Simplified serializer for list views"""

    account_name = serializers.CharField(read_only=True)
    bal_account_name = serializers.CharField(read_only=True)
    applies_to_doc_name = serializers.CharField(read_only=True)
    payment_method_name = serializers.CharField(read_only=True)

    class Meta:
        model = PaymentJournal
        fields = [
            "id",
            "system_id",
            "posting_date",
            "document_type",
            "document_no",
            "external_document_no",
            "description",
            "account_type",
            "account_content_type_id",
            "account_object_id",
            "account_name",
            "payment_method_name",
            "amount",
            "bal_account_type",
            "bal_account_content_type_id",
            "bal_account_object_id",
            "bal_account_name",
            "status",
            "application_status",
            "applies_to_doc_type",
            "applies_to_content_type_id",
            "applies_to_object_id",
            "applies_to_doc_name",
            "created_at",
        ]
