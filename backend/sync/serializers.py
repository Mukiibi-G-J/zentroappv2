from rest_framework import serializers

from purchases.models import Vendor
from sales.models import Customer


class CustomerSyncSerializer(serializers.ModelSerializer):
    """Offline pull payload — no per-customer balance (avoids slow ledger scans)."""

    class Meta:
        model = Customer
        fields = [
            "id",
            "system_id",
            "no",
            "name",
            "address",
            "address_2",
            "city",
            "contact",
            "phone_number",
            "credit_limit",
            "customer_type",
            "payment_method",
        ]


class VendorSyncSerializer(serializers.ModelSerializer):
    """Lightweight vendor payload for offline pull (no per-vendor balance queries)."""

    class Meta:
        model = Vendor
        fields = [
            "system_id",
            "id",
            "no",
            "name",
            "blocked",
            "address",
            "address_2",
            "country",
            "city",
            "state",
            "post_code",
            "phone",
            "mobile",
            "email",
            "website",
            "payment_method",
            "vendor_posting_group",
            "business_posting_group",
            "vat_business_posting_group",
        ]
