from rest_framework import serializers
import os
from dimension.models import (
    update_global_dim_from_dimension_set,
    validate_shortcut_dimension_value,
    update_all_line_dim,
)
from .models import (
    PurchaseInvoice,
    PurchaseInvoiceLine,
    Vendor,
    VendorLedger,
    PurchasePayable,
    DocumentAttachment,
)
from authentication.models import CustomUser


# Allowed MIME types and max size (15 MB) for document attachments
ALLOWED_ATTACHMENT_CONTENT_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
    "application/msword",  # .doc
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # .docx
}
MAX_ATTACHMENT_SIZE_BYTES = 15 * 1024 * 1024  # 15 MB


class DocumentAttachmentSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()
    display_name = serializers.SerializerMethodField()

    class Meta:
        model = DocumentAttachment
        fields = ["id", "purchase_invoice", "file", "name", "display_name", "file_url", "created_at"]
        read_only_fields = ["created_at", "display_name"]

    def get_file_url(self, obj):
        if not obj.file:
            return None
        request = self.context.get("request")
        if request:
            return request.build_absolute_uri(obj.file.url)
        return obj.file.url

    def get_display_name(self, obj):
        """Fallback to filename when name is blank (e.g. older rows or edge cases)."""
        if obj.name:
            return obj.name
        if obj.file and obj.file.name:
            return os.path.basename(obj.file.name)
        return ""

    def validate_file(self, value):
        if value.content_type not in ALLOWED_ATTACHMENT_CONTENT_TYPES:
            raise serializers.ValidationError(
                f"File type not allowed. Allowed: PDF, images, Word documents."
            )
        if value.size > MAX_ATTACHMENT_SIZE_BYTES:
            raise serializers.ValidationError(
                f"File too large. Maximum size is {MAX_ATTACHMENT_SIZE_BYTES // (1024 * 1024)} MB."
            )
        return value

    def create(self, validated_data):
        if not validated_data.get("name") and validated_data.get("file"):
            validated_data["name"] = validated_data["file"].name
        return super().create(validated_data)


class VendorSerializer(serializers.ModelSerializer):
    balance = serializers.SerializerMethodField()

    def get_balance(self, obj):
        """
        Calculate balance from open vendor ledger entries, filtered by branch
        when multi-branch is enabled. Matches the branch filter used in the
        drill-down (ledger_entries) so balance and drill-down stay consistent.
        """
        from purchases.models import VendorLedger

        qs = VendorLedger.objects.filter(vendor=obj, open=True)

        # Apply same branch filter as drill-down (filter_queryset_by_branch)
        request = self.context.get("request")
        if request:
            try:
                from financials.models import GeneralLedgerSetup
                from dimension.branch_filter import get_branch_for_request

                gl_setup = GeneralLedgerSetup.objects.first()
                if gl_setup and getattr(gl_setup, "enable_multiple_branches", False):
                    branch = get_branch_for_request(request)
                    if branch:
                        qs = qs.filter(global_dimension_1_id=branch.id)
            except ImportError:
                pass

        total_amount = 0
        for entry in qs:
            total_amount += entry.remaining_amount or 0
        return total_amount

    class Meta:
        model = Vendor
        fields = [
            "system_id",
            "id",
            "no",
            "name",
            "blocked",
            "balance",
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


class PurchaseInvoiceLineSerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source="item.item_name", read_only=True)
    item_no = serializers.CharField(source="item.no", read_only=True)
    # unit_of_measure = serializers.CharField(source=".unit_of_measure")
    uom_options = serializers.SerializerMethodField()
    base_unit_price = serializers.SerializerMethodField()
    # Explicitly define unit_cost as DecimalField to ensure proper handling
    unit_cost = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False
    )

    class Meta:
        model = PurchaseInvoiceLine
        fields = [
            "id",
            "system_id",
            "item",
            "item_name",
            "item_no",
            "quantity",
            "unit_cost",
            "location_code",
            "total_amount",
            "vat_percent",
            "vat_amount",
            "description",
            "unit_of_measure",
            "uom_options",
            "base_unit_price",
            "global_dimension_1",
            "dimension_set",
        ]
        read_only_fields = ["system_id", "total_amount", "vat_amount", "location_code"]

    def get_uom_options(self, obj):
        if obj.item:
            return obj.item.get_available_uoms
        return []

    def get_base_unit_price(self, obj):
        """Return base unit cost from item card (cost per base UOM)."""
        return float(obj.base_unit_price)

    def update(self, instance, validated_data):
        print("validated_data", validated_data)
        if "unit_of_measure" in validated_data:
            print(validated_data["unit_of_measure"])


class PurchaseInvoiceSerializer(serializers.ModelSerializer):
    lines = PurchaseInvoiceLineSerializer(many=True, required=False)
    vendor_name = serializers.CharField(source="vendor.name", read_only=True)
    payment_method_name = serializers.CharField(
        source="payment_method.description", read_only=True
    )
    payment_method_details = serializers.SerializerMethodField()
    total_amount = serializers.SerializerMethodField()
    reversed = serializers.SerializerMethodField()
    reversed_by = serializers.SerializerMethodField()
    reversed_date = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()
    document_attachments = serializers.SerializerMethodField()
    global_dimension_1_display = serializers.SerializerMethodField()

    class Meta:
        model = PurchaseInvoice
        fields = [
            "id",
            "system_id",
            "invoice_no",
            "vendor",
            "vendor_name",
            "contact_person",
            "document_date",
            "posting_date",
            "vat_date",
            "due_date",
            "vendor_invoice_no",
            "status",
            "payment_method",
            "payment_method_name",
            "payment_method_details",
            "total_amount",
            "prices_including_vat",
            "total_vat_amount",
            "reversed",
            "reversed_by",
            "reversed_date",
            "global_dimension_1",
            "global_dimension_2",
            "global_dimension_1_display",
            "dimension_set",
            "created_at",
            "updated_at",
            "created_by",
            "created_by_name",
            "lines",
            "document_attachments",
        ]
        read_only_fields = [
            "invoice_no",
            "total_vat_amount",
            "created_at",
            "updated_at",
        ]
        extra_kwargs = {
            # `dimension_set` is built server-side from shortcut dimensions (e.g. global_dimension_1)
            # in `create()` / `update()` flows. It must not block initial autosave/creation when omitted.
            "dimension_set": {"required": False, "allow_null": True},
        }

    def get_global_dimension_1_display(self, obj):
        """Return tracking code (branch) for display. BC-style Global Dimension 1."""
        gd1 = getattr(obj, "global_dimension_1", None)
        if not gd1:
            return None
        return {"id": gd1.id, "code": gd1.code, "description": getattr(gd1, "description", "") or ""}

    def get_payment_method_details(self, obj):
        """Get the full payment method details"""
        if obj.payment_method:
            return {
                "id": obj.payment_method.id,
                "code": obj.payment_method.code,
                "description": obj.payment_method.description,
                "requires_amount_received": obj.payment_method.requires_amount_received,
            }
        return None

    def get_total_amount(self, obj):
        return sum(line.total_amount for line in obj.lines.all())

    def get_reversed(self, obj):
        """Check if this invoice has been reversed by a posted credit memo"""
        if obj.status != "Posted":
            return False

        from .models import PostedPurchaseCreditMemo, PostedPurchaseInvoice

        # Find the PostedPurchaseInvoice for this PurchaseInvoice
        # Match by vendor_invoice_no (both have the same vendor_invoice_no)
        try:
            posted_invoice = PostedPurchaseInvoice.objects.get(
                vendor_invoice_no=obj.vendor_invoice_no
            )
            # Check if there's a posted credit memo that reverses this posted invoice
            return PostedPurchaseCreditMemo.objects.filter(
                original_posted_invoice=posted_invoice
            ).exists()
        except (
            PostedPurchaseInvoice.DoesNotExist,
            PostedPurchaseInvoice.MultipleObjectsReturned,
        ):
            # Fallback: check by original_invoice_no matching invoice_no
            # This handles cases where the relationship might be different
            return PostedPurchaseCreditMemo.objects.filter(
                original_invoice_no=obj.invoice_no
            ).exists()

    def get_reversed_by(self, obj):
        """Get the credit memo number that reversed this invoice"""
        if obj.status != "Posted":
            return None

        from .models import PostedPurchaseCreditMemo, PostedPurchaseInvoice

        # Find the PostedPurchaseInvoice for this PurchaseInvoice
        try:
            posted_invoice = PostedPurchaseInvoice.objects.get(
                vendor_invoice_no=obj.vendor_invoice_no
            )
            # Get the credit memo that reverses this posted invoice
            credit_memo = PostedPurchaseCreditMemo.objects.filter(
                original_posted_invoice=posted_invoice
            ).first()

            if credit_memo:
                return credit_memo.no
        except (
            PostedPurchaseInvoice.DoesNotExist,
            PostedPurchaseInvoice.MultipleObjectsReturned,
        ):
            pass

        # Fallback: check by original_invoice_no
        credit_memo = PostedPurchaseCreditMemo.objects.filter(
            original_invoice_no=obj.invoice_no
        ).first()

        if credit_memo:
            return credit_memo.no
        return None

    def get_reversed_date(self, obj):
        """Get the date when this invoice was reversed"""
        if obj.status != "Posted":
            return None

        from .models import PostedPurchaseCreditMemo, PostedPurchaseInvoice

        # Find the PostedPurchaseInvoice for this PurchaseInvoice
        try:
            posted_invoice = PostedPurchaseInvoice.objects.get(
                vendor_invoice_no=obj.vendor_invoice_no
            )
            # Get the credit memo that reverses this posted invoice
            credit_memo = PostedPurchaseCreditMemo.objects.filter(
                original_posted_invoice=posted_invoice
            ).first()

            if credit_memo:
                return credit_memo.posting_date
        except (
            PostedPurchaseInvoice.DoesNotExist,
            PostedPurchaseInvoice.MultipleObjectsReturned,
        ):
            pass

        # Fallback: check by original_invoice_no
        credit_memo = PostedPurchaseCreditMemo.objects.filter(
            original_invoice_no=obj.invoice_no
        ).first()

        if credit_memo:
            return credit_memo.posting_date
        return None

    def get_document_attachments(self, obj):
        """Return list of attachments for the UI (id, name, file_url, created_at)."""
        request = self.context.get("request")
        attachments = obj.document_attachments.all().order_by("-created_at")
        return [
            {
                "id": a.id,
                "name": a.name or (a.file.name.split("/")[-1] if a.file else ""),
                "file_url": request.build_absolute_uri(a.file.url) if request and a.file else (a.file.url if a.file else None),
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in attachments
        ]

    def get_created_by_name(self, obj):
        """Get the name of the user who created this invoice"""
        # First, try to get from created_by field (for new invoices)
        if obj.created_by:
            return obj.created_by.full_name

        # For already-posted invoices that don't have created_by set,
        # try to get the user from ItemLedgerEntries created during posting
        if obj.status == "Posted" and obj.invoice_no:
            try:
                from items.models import ItemLedgerEntries
                from items.enums import DocumentType

                # Get the first ItemLedgerEntry for this invoice
                item_ledger_entry = ItemLedgerEntries.objects.filter(
                    document_no=obj.invoice_no,
                    document_type=DocumentType.PurchaseReceipt.value,
                ).first()

                if item_ledger_entry and item_ledger_entry.user:
                    return item_ledger_entry.user.full_name
            except Exception:
                # If anything fails, just return None
                pass

        return None

    def create(self, validated_data):
        try:
            # Get the user from the request context
            request = self.context.get("request")
            if request and hasattr(request, "user") and request.user.is_authenticated:
                validated_data["created_by"] = request.user
            # Stamp header dimensions if not provided
            if validated_data.get("global_dimension_1") is None:
                from dimension.branch_filter import get_branch_for_request
                from dimension.utils import get_first_branch_dimension_value
                branch = get_branch_for_request(request) if request else None
                if not branch and request and request.user:
                    branch = getattr(request.user, "global_dimension_1", None)
                if not branch:
                    branch = get_first_branch_dimension_value()
                if branch:
                    validated_data["global_dimension_1"] = branch

            # DB constraint: dimension_set_id is NOT NULL for purchases_purchaseinvoice.
            # Build a DimensionSet from shortcut dimensions BEFORE initial insert.
            if validated_data.get("dimension_set") is None:
                from dimension.models import get_posting_dimension_payload

                payload = get_posting_dimension_payload(
                    global_dimension_1=validated_data.get("global_dimension_1"),
                    global_dimension_2=validated_data.get("global_dimension_2"),
                    dimension_set=None,
                )
                validated_data["dimension_set"] = payload.get("dimension_set")
                # Keep globals consistent with the built set (if any defaults were applied)
                if payload.get("global_dimension_1") is not None:
                    validated_data["global_dimension_1"] = payload.get("global_dimension_1")
                if payload.get("global_dimension_2") is not None:
                    validated_data["global_dimension_2"] = payload.get("global_dimension_2")

            instance = super().create(validated_data)
            # Build dimension_set from shortcut dims when set (BC-style)
            if instance.global_dimension_1_id and not instance.dimension_set_id:
                validate_shortcut_dimension_value(instance, 1, instance.global_dimension_1)
            if instance.global_dimension_2_id:
                validate_shortcut_dimension_value(instance, 2, instance.global_dimension_2)
            if instance.dimension_set_id or instance.global_dimension_1_id or instance.global_dimension_2_id:
                instance.save(update_fields=["dimension_set_id", "global_dimension_1_id", "global_dimension_2_id"])
                if instance.lines.exists():
                    update_all_line_dim(instance, instance.dimension_set_id, None)
            return instance
        except Exception as e:
            # Convert ConfigurationError to a user-friendly error
            raise serializers.ValidationError(
                {
                    "non_field_errors": [
                        f"Configuration Error: {str(e)}. "
                        "Please contact your administrator to set up the required configuration."
                    ]
                }
            )

    def update(self, instance, validated_data):
        old_dim_set_id = instance.dimension_set_id

        if "dimension_set" in validated_data:
            instance.dimension_set = validated_data["dimension_set"]
            update_global_dim_from_dimension_set(instance)
        if "global_dimension_1" in validated_data:
            validate_shortcut_dimension_value(instance, 1, validated_data["global_dimension_1"])
        if "global_dimension_2" in validated_data:
            validate_shortcut_dimension_value(instance, 2, validated_data["global_dimension_2"])

        for attr, value in validated_data.items():
            if attr not in ("lines", "dimension_set", "global_dimension_1", "global_dimension_2"):
                setattr(instance, attr, value)

        try:
            instance.save()
            if "prices_including_vat" in validated_data:
                instance.recalculate_vat()
            if instance.dimension_set_id != old_dim_set_id:
                update_all_line_dim(instance, instance.dimension_set_id, old_dim_set_id)
        except Exception as e:
            # Convert ConfigurationError to a user-friendly error
            raise serializers.ValidationError(
                {
                    "non_field_errors": [
                        f"Configuration Error: {str(e)}. "
                        "Please contact your administrator to set up the required configuration."
                    ]
                }
            )

        return instance

    # def create(self, validated_data):
    #     lines_data = validated_data.pop("lines", [])
    #     purchase = super().create(validated_data)

    #     for line_data in lines_data:
    #         PurchaseInvoiceLine.objects.create(purchase_invoice=purchase, **line_data)
    #     return purchase

    # def update(self, instance, validated_data):
    #     lines_data = validated_data.pop("lines", [])
    #     print("lines_data", lines_data)
    #     purchase = super().update(instance, validated_data)

    #     # Clear existing lines and create new ones
    #     instance.lines.all().delete()
    #     for line_data in lines_data:
    #         PurchaseInvoiceLine.objects.create(purchase_invoice=purchase, **line_data)
    #     return purchase


class VendorLedgerSerializer(serializers.ModelSerializer):
    vendor_name = serializers.CharField(source="vendor.name", read_only=True)
    payment_method_name = serializers.CharField(
        source="payment_method.name", read_only=True
    )
    days_overdue = serializers.IntegerField(read_only=True)

    class Meta:
        model = VendorLedger
        fields = [
            "id",
            "posting_date",
            "document_date",
            "document_type",
            "document_no",
            "external_document_no",
            "applies_to_id",
            "vendor",
            "vendor_name",
            "description",
            "payment_method",
            "payment_method_name",
            "original_amount",
            "amount",
            "remaining_amount",
            "open",
            "due_date",
            "days_overdue",
            "global_dimension_1",
            "dimension_set",
        ]
