from rest_framework import serializers

from receipt_templates.models import ReceiptTemplate, ReceiptTemplateAssignment


class ReceiptTemplateSerializer(serializers.ModelSerializer):
    receipt_type = serializers.CharField()
    layout_preset = serializers.CharField()

    class Meta:
        model = ReceiptTemplate
        fields = [
            "id",
            "code",
            "name",
            "receipt_type",
            "layout_preset",
            "paper_profile",
            "sections",
            "editor_mode",
            "format_string",
            "is_system",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "is_system", "created_at", "updated_at"]

    def validate(self, attrs):
        if self.instance and self.instance.is_system:
            # System templates: only sections, paper_profile, name editable
            locked = {"code", "receipt_type", "layout_preset"}
            for field in locked:
                if field in attrs and getattr(self.instance, field) != attrs[field]:
                    raise serializers.ValidationError(
                        {field: "System templates cannot change this field."}
                    )
        return attrs


class ReceiptTemplateAssignmentSerializer(serializers.ModelSerializer):
    template_code = serializers.CharField(source="template.code", read_only=True)
    template_name = serializers.CharField(source="template.name", read_only=True)

    class Meta:
        model = ReceiptTemplateAssignment
        fields = [
            "id",
            "template",
            "template_code",
            "template_name",
            "device_type",
            "printer_type",
            "process",
            "branch",
            "priority",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
