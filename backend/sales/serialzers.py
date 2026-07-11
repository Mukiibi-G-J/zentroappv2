from rest_framework.exceptions import ValidationError as DRFValidationError
from django.core.exceptions import ValidationError

from rest_framework import serializers
from financials.models import GeneralLedgerEntry, G_LAccount
from items.models import Item, ItemLedgerEntries, ItemJournal


class SalesSerializer(serializers.ModelSerializer):
    class Meta:
        model = GeneralLedgerEntry
        fields = "__all__"


class CreateSalesSerializer(serializers.ModelSerializer):
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())
    document_no = serializers.CharField(read_only=True)

    def create(self, validated_data):
        try:
            validated_data["unit_cost"] = Item.objects.get(
                id=validated_data["item"].id
            ).unit_cost
            return super().create(validated_data)
        except ValidationError as e:
            error_dict = {"errors": []}
            if hasattr(e, "message_dict"):
                for field, messages in e.message_dict.items():
                    error_dict["errors"].append(
                        {
                            "field": field,
                            "message": messages[0] if messages else "Unknown error",
                        }
                    )
            else:
                error_dict["errors"].append(
                    {"field": "non_field_errors", "message": str(e)}
                )
            raise DRFValidationError(error_dict)
    class Meta:
        model = ItemJournal
        fields = [
            "id",
            "document_no",
            "item",
            "entry_type",
            "description",
            "quantity",
            "total",
            "unit_amount",
            "unit_cost",
            "date",
            "user",
            "system_id",
            # "item_name",
        ]
