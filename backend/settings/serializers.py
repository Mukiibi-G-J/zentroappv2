import re

from rest_framework import serializers

from settings.models import MobileAppUserSettings


class MobileAppUserSettingsSerializer(serializers.ModelSerializer):
    searchMode = serializers.ChoiceField(
        source="search_mode",
        choices=[
            MobileAppUserSettings.SEARCH_MODE_BARCODE,
            MobileAppUserSettings.SEARCH_MODE_REALTIME,
        ],
        required=False,
    )
    barcodeScannerEnabled = serializers.BooleanField(
        source="barcode_scanner_enabled", required=False
    )
    barcodeBeepEnabled = serializers.BooleanField(
        source="barcode_beep_enabled", required=False
    )
    printer = serializers.DictField(required=False, write_only=True)

    class Meta:
        model = MobileAppUserSettings
        fields = [
            "searchMode",
            "barcodeScannerEnabled",
            "barcodeBeepEnabled",
            "printer",
        ]

    def validate(self, attrs):
        self._validate_strict_boolean(
            incoming_key="barcodeScannerEnabled", model_key="barcode_scanner_enabled"
        )
        self._validate_strict_boolean(
            incoming_key="barcodeBeepEnabled", model_key="barcode_beep_enabled"
        )

        printer_input = self.initial_data.get("printer")
        if printer_input is not None:
            if not isinstance(printer_input, dict):
                raise serializers.ValidationError(
                    {"printer": "printer must be an object."}
                )
            attrs["printer"] = self._validate_printer(printer_input)
        return attrs

    def update(self, instance, validated_data):
        printer_data = validated_data.pop("printer", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        if printer_data is not None:
            instance.printer_type = printer_data["type"]
            instance.printer_device_name = printer_data["deviceName"]
            instance.printer_mac_address = printer_data["macAddress"]
            instance.printer_paper_width = printer_data["paperWidth"]
            instance.printer_copies = printer_data["copies"]

        instance.save()
        return instance

    def _validate_strict_boolean(self, incoming_key, model_key):
        if incoming_key not in self.initial_data:
            return
        if not isinstance(self.initial_data[incoming_key], bool):
            raise serializers.ValidationError({incoming_key: "Must be a boolean."})

    def _validate_printer(self, data):
        allowed_types = {
            MobileAppUserSettings.PRINTER_TYPE_SUNMI,
            MobileAppUserSettings.PRINTER_TYPE_BLUETOOTH,
            MobileAppUserSettings.PRINTER_TYPE_NONE,
        }
        allowed_widths = {
            MobileAppUserSettings.PAPER_WIDTH_58,
            MobileAppUserSettings.PAPER_WIDTH_80,
        }

        printer_type = data.get("type")
        if printer_type not in allowed_types:
            raise serializers.ValidationError(
                {"printer": {"type": "Must be one of sunmi, bluetooth, none."}}
            )

        paper_width = str(data.get("paperWidth", MobileAppUserSettings.PAPER_WIDTH_58))
        if paper_width not in allowed_widths:
            raise serializers.ValidationError(
                {"printer": {"paperWidth": "Must be one of 58 or 80."}}
            )

        copies = data.get("copies", 1)
        if not isinstance(copies, int) or copies < 1:
            raise serializers.ValidationError(
                {"printer": {"copies": "Must be an integer >= 1."}}
            )

        device_name = (data.get("deviceName") or "").strip()
        mac_address = (data.get("macAddress") or "").strip()

        if printer_type == MobileAppUserSettings.PRINTER_TYPE_BLUETOOTH:
            if not device_name:
                raise serializers.ValidationError(
                    {"printer": {"deviceName": "Required for bluetooth printers."}}
                )
            if not self._is_valid_mac(mac_address):
                raise serializers.ValidationError(
                    {"printer": {"macAddress": "Invalid MAC address format."}}
                )

        if printer_type == MobileAppUserSettings.PRINTER_TYPE_NONE:
            device_name = ""
            mac_address = ""

        return {
            "type": printer_type,
            "deviceName": device_name,
            "macAddress": mac_address,
            "paperWidth": paper_width,
            "copies": copies,
        }

    def _is_valid_mac(self, value):
        return bool(re.fullmatch(r"^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$", value))
