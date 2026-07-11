from decimal import Decimal
from typing import List

from django.db import ProgrammingError
from django.db.utils import ProgrammingError as DjangoProgrammingError
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from items.models import Item, ItemUnitOfMeasure, UnitOfMeasure
from prepayment.models import (
    Preayment,
    PreaymentLine,
    PreaymentInstallmentHistory,
)
from sales.enums import CustomerType
from sales.models import (
    CustomerLedgerEntry,
    DetailedCustomerLedgerEntry,
    PostedSalesInvoice,
)
from sales.serializers import CustomerLedgerSerializer


class PreaymentLineSerializer(serializers.ModelSerializer):
    """
    Line serializer for document-level prepayments.
    Lines only contain item, quantity, unit_price, amount, and UOM.
    All deposit-related fields are removed (moved to document header).
    """

    item_name = serializers.CharField(source="item.item_name", read_only=True)
    item_no = serializers.CharField(source="item.no", read_only=True)
    is_deleted = serializers.BooleanField(write_only=True, required=False)
    unit_of_measure = serializers.SerializerMethodField()
    uom_options = serializers.SerializerMethodField()
    base_unit_price = serializers.SerializerMethodField()

    class Meta:
        model = PreaymentLine
        fields = [
            "id",
            "document",
            "item",
            "item_name",
            "item_no",
            "item_unit_of_measure",
            "unit_of_measure",
            "tracking_code",
            "description",
            "quantity",
            "unit_price",
            "amount",
            "is_deleted",
            "uom_options",
            "base_unit_price",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "document",
            "amount",
            "item_unit_of_measure",
            "unit_of_measure",
            "uom_options",
            "created_at",
            "updated_at",
        ]

    def get_unit_of_measure(self, obj):
        """Return unit_of_measure code from item_unit_of_measure (like purchase lines)."""
        if obj.item_unit_of_measure and obj.item_unit_of_measure.unit_of_measure:
            return obj.item_unit_of_measure.unit_of_measure.code
        elif obj.unit_of_measure:
            return obj.unit_of_measure.code
        return None

    def get_uom_options(self, obj):
        """Return available UOM options for the item (like purchase and sales lines)."""
        print(f"[DEBUG] get_uom_options called for line {obj.id}")
        print(f"[DEBUG] obj.item: {obj.item}")
        if obj.item:
            uoms = obj.item.get_available_uoms
            print(f"[DEBUG] uom_options from item: {uoms}")
            print(
                f"[DEBUG] uom_options type: {type(uoms)}, length: {len(uoms) if hasattr(uoms, '__len__') else 'N/A'}"
            )
            return uoms
        print(f"[DEBUG] No item found, returning empty list")
        return []

    def get_base_unit_price(self, obj):
        """Return base unit price from item card (price per base UOM)."""
        return float(obj.base_unit_price)

    def validate(self, attrs):
        # No deposit validation needed - deposits are at document level
        # Note: quantity_per_unit is stored in ItemUnitOfMeasure model
        # The amount calculation uses quantity_per_unit from item_unit_of_measure
        return attrs


class PostedSalesInvoiceSerializer(serializers.ModelSerializer):
    total_amount = serializers.SerializerMethodField()

    class Meta:
        model = PostedSalesInvoice
        fields = [
            "id",
            "no",
            "customer_invoice_no",
            "posting_date",
            "document_date",
            "status",
            "total_amount",
        ]

    def get_total_amount(self, obj):
        try:
            return sum(line.amount for line in obj.posted_sales_invoice_lines.all())
        except Exception:
            return 0


class DetailedCustomerLedgerEntrySerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="customer.name", read_only=True)

    class Meta:
        model = DetailedCustomerLedgerEntry
        fields = [
            "entry_no",
            "posting_date",
            "entry_type",
            "document_type",
            "document_no",
            "customer_name",
            "amount",
            "debit_amount",
            "credit_amount",
            "initial_entry_due_date",
            "initial_document_type",
            "applied_customer_ledger_entry_no",
            "unapplied_by_entry_no",
            "unapplied",
            "transaction_no",
        ]


class PreaymentListSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="customer.name", read_only=True)
    remaining_prepayment = serializers.DecimalField(
        max_digits=15, decimal_places=2, read_only=True
    )
    is_final_invoiced = serializers.BooleanField(read_only=True)
    collected_prepayment_fully_invoiced = serializers.BooleanField(read_only=True)

    class Meta:
        model = Preayment
        fields = [
            "id",
            "document_no",
            "customer",
            "customer_name",
            "status",
            "total_amount",
            "total_prepayment",
            "total_prepayment_invoiced",
            "total_prepayment_deducted",
            "remaining_prepayment",
            "is_final_invoiced",
            "collected_prepayment_fully_invoiced",
            "posted_at",
            "posted_transaction_no",
            "posting_date",
            "updated_at",
        ]


class PreaymentInstallmentHistorySerializer(serializers.ModelSerializer):
    applied_by_name = serializers.CharField(
        source="applied_by.full_name", read_only=True
    )

    class Meta:
        model = PreaymentInstallmentHistory
        fields = [
            "id",
            "amount",
            "transaction_no",
            "applied_by",
            "applied_by_name",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class PreaymentDetailSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="customer.name", read_only=True)
    customer_no = serializers.CharField(source="customer.no", read_only=True)
    customer_payment_method = serializers.CharField(
        source="customer.payment_method.description", read_only=True
    )
    posted_by_name = serializers.CharField(source="posted_by.full_name", read_only=True)
    remaining_prepayment = serializers.DecimalField(
        max_digits=15, decimal_places=2, read_only=True
    )
    is_final_invoiced = serializers.BooleanField(read_only=True)
    collected_prepayment_fully_invoiced = serializers.BooleanField(read_only=True)
    preview_deposit_total = serializers.SerializerMethodField()
    total_prepayment_to_deduct = serializers.SerializerMethodField()
    deposit_percent = serializers.SerializerMethodField()
    installment_draft_amount = serializers.SerializerMethodField()
    installment_history = serializers.SerializerMethodField()
    lines = PreaymentLineSerializer(many=True, required=False)
    posted_invoices = serializers.SerializerMethodField()
    customer_ledger_entries = serializers.SerializerMethodField()
    detailed_customer_ledger_entries = serializers.SerializerMethodField()

    class Meta:
        model = Preayment
        fields = [
            "id",
            "document_no",
            "customer",
            "customer_name",
            "customer_no",
            "customer_payment_method",
            "contact_person",
            "document_date",
            "posting_date",
            "due_date",
            "description",
            "status",
            "total_amount",
            "total_prepayment",
            "total_prepayment_invoiced",
            "total_prepayment_deducted",
            "total_prepayment_to_deduct",
            "deposit_percent",
            "preview_deposit_total",
            "remaining_prepayment",
            "is_final_invoiced",
            "collected_prepayment_fully_invoiced",
            "installment_draft_amount",
            "installment_history",
            "posted_at",
            "posted_by_name",
            "posted_transaction_no",
            "global_dimension_1",
            "global_dimension_2",
            "dimension_set",
            "lines",
            "posted_invoices",
            "customer_ledger_entries",
            "detailed_customer_ledger_entries",
            "created_at",
            "updated_at",
        ]

        extra_kwargs = {
            "global_dimension_1": {"required": False, "allow_null": True},
            "global_dimension_2": {"required": False, "allow_null": True},
            "dimension_set": {"required": False, "allow_null": True},
        }

    def _ensure_header_dimensions(self, validated_data: dict) -> None:
        """Stamp branch + dimension_set on new prepayment headers (POS omits these)."""
        if validated_data.get("global_dimension_1") is None:
            request = self.context.get("request")
            from dimension.branch_filter import get_branch_for_request
            from dimension.utils import get_first_branch_dimension_value

            branch = get_branch_for_request(request) if request else None
            if not branch and request and request.user:
                branch = getattr(request.user, "global_dimension_1", None)
            if not branch:
                branch = get_first_branch_dimension_value()
            if branch:
                validated_data["global_dimension_1"] = branch

        if validated_data.get("dimension_set") is None and validated_data.get(
            "global_dimension_1"
        ):
            try:
                from financials.models import GeneralLedgerSetup
                from dimension.models import get_or_create_dimension_set

                gl_setup = GeneralLedgerSetup.objects.first()
                if gl_setup and getattr(gl_setup, "global_dimension_1_id", None):
                    validated_data["dimension_set"] = get_or_create_dimension_set(
                        {
                            gl_setup.global_dimension_1: validated_data[
                                "global_dimension_1"
                            ]
                        }
                    )
            except Exception:
                pass

        if validated_data.get("dimension_set") is None:
            from dimension.utils import resolve_default_branch_for_tenant

            branch, dim_set, _err = resolve_default_branch_for_tenant(
                allow_multiple_branch_values=True
            )
            if branch and validated_data.get("global_dimension_1") is None:
                validated_data["global_dimension_1"] = branch
            if dim_set:
                validated_data["dimension_set"] = dim_set

        if not validated_data.get("global_dimension_1") or not validated_data.get(
            "dimension_set"
        ):
            raise serializers.ValidationError(
                {
                    "non_field_errors": [
                        "Branch dimensions are not configured for this tenant. "
                        "Set up General Ledger Setup with a branch dimension first."
                    ]
                }
            )

    def _apply_line_dimensions(
        self,
        document: Preayment,
        raw_line_data: dict,
        normalized: dict,
    ) -> dict:
        from dimension.branch_filter import get_branch_for_request
        from dimension.models import get_merged_line_dimensions

        request = self.context.get("request")
        request_user = request.user if request else None
        branch = get_branch_for_request(request) if request else None
        if not branch and request_user:
            branch = getattr(request_user, "global_dimension_1", None)
        if not branch:
            branch = document.global_dimension_1

        line_data_for_dims = dict(raw_line_data or {})
        if branch:
            line_data_for_dims["global_dimension_1"] = branch

        customer_no = (
            getattr(document.customer, "no", None) if document.customer else None
        )
        dims = get_merged_line_dimensions(
            customer_no=customer_no,
            item=normalized.get("item"),
            request_user=request_user,
            line_data=line_data_for_dims,
            header_dimensions=document,
        )
        normalized["global_dimension_1"] = (
            dims.get("global_dimension_1") or document.global_dimension_1
        )
        normalized["dimension_set"] = (
            dims.get("dimension_set") or document.dimension_set
        )
        return normalized

    def validate_customer(self, value):
        if value is not None and value.customer_type == CustomerType.General.name:
            raise serializers.ValidationError(
                "Prepayments cannot be recorded for the general/walk-in customer. "
                "Select a named customer."
            )
        return value

    def get_total_prepayment_to_deduct(self, obj):
        """Get total prepayment to deduct, handling missing/deferred database column."""
        # Check if field is in deferred fields set
        if hasattr(obj, "get_deferred_fields"):
            deferred = obj.get_deferred_fields()
            if "total_prepayment_to_deduct" in deferred:
                return Decimal("0.00")

        try:
            # Try to get the value, but catch any database errors
            value = obj.total_prepayment_to_deduct
            return value if value is not None else Decimal("0.00")
        except (
            ProgrammingError,
            DjangoProgrammingError,
            AttributeError,
            ValueError,
        ) as e:
            # Field doesn't exist in DB or is deferred - return default
            return Decimal("0.00")
        except Exception:
            # Catch any other exceptions (including database refresh errors)
            return Decimal("0.00")

    def get_deposit_percent(self, obj):
        """Get deposit percent, handling missing/deferred database column."""
        # Check if field is in deferred fields set
        if hasattr(obj, "get_deferred_fields"):
            deferred = obj.get_deferred_fields()
            if "deposit_percent" in deferred:
                return Decimal("0.00")

        try:
            # Try to get the value, but catch any database errors
            value = obj.deposit_percent
            return value if value is not None else Decimal("0.00")
        except (
            ProgrammingError,
            DjangoProgrammingError,
            AttributeError,
            ValueError,
        ) as e:
            # Field doesn't exist in DB or is deferred - return default
            return Decimal("0.00")
        except Exception:
            # Catch any other exceptions (including database refresh errors)
            return Decimal("0.00")

    def get_preview_deposit_total(self, obj):
        """Get preview deposit total, handling missing/deferred database column."""
        try:
            # Check if field is deferred (not loaded from DB)
            if hasattr(obj, "_deferred") and obj._deferred:
                # Use fallback calculation for deferred fields
                pass
            else:
                # Try to get the property value
                try:
                    return obj.preview_deposit_total
                except (AttributeError, ValueError):
                    pass
        except Exception:
            pass

        # Fallback calculation if property doesn't exist or field is deferred
        try:
            total_prepayment = getattr(
                obj, "total_prepayment", Decimal("0.00")
            ) or Decimal("0.00")
            draft_amount = Decimal("0.00")
            try:
                if hasattr(obj, "installment_draft") and obj.installment_draft:
                    draft_amount = obj.installment_draft.amount or Decimal("0.00")
            except Exception:
                pass
            return total_prepayment + draft_amount
        except Exception:
            return Decimal("0.00")

    def get_installment_draft_amount(self, obj):
        """Get draft installment amount from document-level draft."""
        try:
            if hasattr(obj, "installment_draft") and obj.installment_draft:
                return obj.installment_draft.amount
        except Exception:
            pass
        return Decimal("0.00")

    def get_installment_history(self, obj):
        """Get installment history for this document."""
        try:
            history = obj.installment_history.all()
            return PreaymentInstallmentHistorySerializer(history, many=True).data
        except Exception:
            return []

    def get_posted_invoices(self, obj):
        invoices = obj.posted_sales_invoices.all().prefetch_related(
            "posted_sales_invoice_lines"
        )
        return PostedSalesInvoiceSerializer(invoices, many=True).data

    def get_customer_ledger_entries(self, obj):
        queryset = CustomerLedgerEntry.objects.filter(
            external_document_no=obj.document_no
        ).order_by("-posting_date")
        return CustomerLedgerSerializer(queryset, many=True).data

    def get_detailed_customer_ledger_entries(self, obj):
        transaction_no = obj.posted_transaction_no
        if not transaction_no:
            return []
        queryset = DetailedCustomerLedgerEntry.objects.filter(
            transaction_no=transaction_no
        ).order_by("-posting_date", "-entry_no")
        return DetailedCustomerLedgerEntrySerializer(queryset, many=True).data

    def create(self, validated_data):
        # Use raw initial_data for lines so we can process read-only/alias fields (e.g., unitOfMeasure)
        raw_lines = self.initial_data.get("lines", [])
        # Remove 'lines' from validated_data if DRF placed anything there
        validated_data.pop("lines", None)
        # Remove read-only calculated fields that aren't part of the model
        validated_data.pop("preview_deposit_total", None)
        validated_data.pop("installment_draft_amount", None)
        validated_data.pop("installment_history", None)
        # Ensure required fields have default values since they're required in DB
        # These will be recalculated in recalculate_totals() after lines are created
        from decimal import Decimal

        validated_data["deposit_percent"] = Decimal("0.00")
        validated_data["total_prepayment_to_deduct"] = Decimal("0.00")
        self._ensure_header_dimensions(validated_data)
        document = Preayment.objects.create(**validated_data)
        for line_data in raw_lines:
            normalized = self._normalize_line_payload(dict(line_data or {}))
            normalized = self._apply_line_dimensions(document, line_data, normalized)
            PreaymentLine.objects.create(document=document, **normalized)
        document.recalculate_totals()
        return document

    def update(self, instance, validated_data):
        # Pull raw lines from initial_data to preserve fields that may be marked
        # read_only in the nested serializer (e.g., unit_of_measure, item_unit_of_measure)
        lines_data = self.initial_data.get("lines", None)
        # Ensure we don't pass lines down to default ModelSerializer.update
        validated_data.pop("lines", None)
        # Remove new fields that don't exist in DB yet (until migrations are run)
        # These are read-only calculated fields anyway
        validated_data.pop("total_prepayment_to_deduct", None)
        validated_data.pop("deposit_percent", None)
        validated_data.pop("preview_deposit_total", None)
        validated_data.pop("installment_draft_amount", None)
        validated_data.pop("installment_history", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if lines_data is not None:
            # Work with a shallow copy to avoid mutating self.initial_data
            self._update_lines(instance, [dict(ld or {}) for ld in lines_data])
            instance.recalculate_totals()

        return instance

    def _update_lines(self, instance: Preayment, lines_data: List[dict]):
        existing_lines = {line.id: line for line in instance.lines.all()}
        for payload in lines_data:
            line_id = payload.get("id")
            # Normalize id type (frontend may send stringified ids or with spaces)
            try:
                if isinstance(line_id, str):
                    line_id = int(line_id.strip())
                elif isinstance(line_id, (int,)):
                    line_id = int(line_id)
                else:
                    line_id = None if line_id is None else int(line_id)
            except (TypeError, ValueError):
                line_id = None
            # If an id is present, ALWAYS treat this as an update-or-delete for an existing row.
            # Do NOT create when an id is provided but not found.
            if line_id:
                line = (
                    existing_lines.get(line_id)
                    or instance.lines.filter(id=line_id).first()
                )
                if not line:
                    # Unknown id → skip instead of creating a new row
                    continue
                if payload.get("is_deleted"):
                    line.delete()
                    continue
                # Direct numeric updates first (bypass normalization pitfalls)
                # Note: Installments are now at document level, not line level
                qty_in = payload.get("quantity", None)
                # Accept camelCase from frontend as well
                up_in = payload.get("unit_price", None)
                if up_in is None:
                    up_in = payload.get("unitPrice", None)
                numeric_updated = False
                try:
                    if qty_in is not None:
                        line.quantity = Decimal(str(qty_in))
                        numeric_updated = True
                except Exception:
                    pass
                try:
                    if up_in is not None:
                        unit_price = Decimal(str(up_in))
                        # Strict: reject values that need more than 2 decimals.
                        quant = Decimal("0.01")
                        if unit_price != unit_price.quantize(quant):
                            raise serializers.ValidationError(
                                {
                                    "unit_price": "Only up to 2 decimal places are allowed for unit_price."
                                }
                            )

                        line.unit_price = unit_price
                        numeric_updated = True
                except serializers.ValidationError:
                    raise
                except Exception:
                    pass
                if numeric_updated:
                    try:
                        q = line.quantity or Decimal("0")
                        p = line.unit_price or Decimal("0")
                        line.amount = q * p
                    except Exception:
                        # keep previous amount on failure
                        pass
                # Normalize remaining attributes (item, uom, description, etc.)
                normalized = self._normalize_line_payload(
                    payload, fallback_item=line.item
                )
                for attr, value in normalized.items():
                    if (
                        attr
                        in (
                            "id",
                            "document",
                            "is_deleted",
                            # Skip deposit-related fields (moved to document level)
                            "deposit_amount",
                            "deposit_percent",
                            "prepayment_amount_invoiced",
                            "prepayment_amount_to_deduct",
                            "prepayment_amount_deducted",
                            "installment_amount",
                            "installment_draft_amount",
                            "preview_deposit_total",
                        )
                        or value is None
                    ):
                        continue
                    setattr(line, attr, value)
                # Persist with minimal writes
                line.save()
            else:
                # If request intended deletion but id didn't match, skip creating a blank line
                if payload.get("is_deleted"):
                    continue
                payload.pop("is_deleted", None)
                normalized = self._normalize_line_payload(payload)
                # Guard: only create if we have a meaningful line (has item or non-empty description)
                meaningful_description = (normalized.get("description") or "").strip()
                if not normalized.get("item") and not meaningful_description:
                    # Skip accidental creates (e.g., blur updates without id)
                    continue
                normalized = self._apply_line_dimensions(instance, payload, normalized)
                PreaymentLine.objects.create(document=instance, **normalized)

    def _normalize_line_payload(
        self, payload: dict, fallback_item: Item | None = None
    ) -> dict:
        item_value = payload.get("item")
        item_obj = fallback_item
        if isinstance(item_value, Item):
            item_obj = item_value
        elif isinstance(item_value, int):
            try:
                item_obj = Item.objects.get(pk=item_value)
            except Item.DoesNotExist:
                item_obj = fallback_item
        elif isinstance(item_value, str) and item_value:
            try:
                item_obj = Item.objects.get(no=item_value)
            except Item.DoesNotExist:
                try:
                    item_obj = Item.objects.get(item_name=item_value)
                except Item.DoesNotExist:
                    item_obj = fallback_item
        if item_obj:
            payload["item"] = item_obj

        # Accept camelCase aliases from UI
        # Note: Installments are now at document level, not line level
        if "unit_of_measure" not in payload and "unitOfMeasure" in payload:
            payload["unit_of_measure"] = payload.get("unitOfMeasure")
        if "unit_price" not in payload and "unitPrice" in payload:
            payload["unit_price"] = payload.get("unitPrice")

        uom_value = payload.get("unit_of_measure")
        if uom_value:
            uom_obj = None
            # Accept code string directly
            if isinstance(uom_value, str):
                code = uom_value
                if code:
                    uom_obj, _ = UnitOfMeasure.objects.get_or_create(
                        code=code, defaults={"description": code}
                    )
            # Accept integer id
            elif isinstance(uom_value, int):
                try:
                    uom_obj = UnitOfMeasure.objects.get(pk=uom_value)
                except UnitOfMeasure.DoesNotExist:
                    uom_obj = None
            # Accept dict-like objects with code or id
            else:
                code = getattr(uom_value, "code", None)
                if not code and isinstance(uom_value, dict):
                    code = uom_value.get("code")
                if code:
                    uom_obj, _ = UnitOfMeasure.objects.get_or_create(
                        code=code, defaults={"description": code}
                    )
                elif isinstance(uom_value, dict):
                    uom_id = uom_value.get("id") or uom_value.get("pk")
                    if uom_id:
                        try:
                            uom_obj = UnitOfMeasure.objects.get(pk=uom_id)
                        except UnitOfMeasure.DoesNotExist:
                            uom_obj = None

            if uom_obj:
                payload["unit_of_measure"] = uom_obj
                if item_obj:
                    item_uom, _ = ItemUnitOfMeasure.objects.get_or_create(
                        item=item_obj,
                        unit_of_measure=uom_obj,
                        defaults={"quantity_per_unit": Decimal("1.00")},
                    )
                    payload["item_unit_of_measure"] = item_uom
        return payload


class GLPreviewEntrySerializer(serializers.Serializer):
    account_no = serializers.CharField()
    account_name = serializers.CharField()
    description = serializers.CharField()
    document_type = serializers.CharField()
    amount = serializers.DecimalField(max_digits=15, decimal_places=2)
    balance_account_type = serializers.CharField(allow_null=True)
    global_dimension_1 = serializers.CharField(allow_null=True)


class CustomerPreviewEntrySerializer(serializers.Serializer):
    document_type = serializers.CharField()
    document_no = serializers.CharField()
    description = serializers.CharField()
    amount = serializers.DecimalField(max_digits=15, decimal_places=2)
    open = serializers.BooleanField()
    due_date = serializers.DateField()


class DetailedPreviewEntrySerializer(serializers.Serializer):
    entry_type = serializers.CharField()
    document_type = serializers.CharField()
    amount = serializers.DecimalField(max_digits=15, decimal_places=2)
    debit_amount = serializers.DecimalField(max_digits=15, decimal_places=2)
    credit_amount = serializers.DecimalField(max_digits=15, decimal_places=2)


class LinePreviewContextSerializer(serializers.Serializer):
    line_id = serializers.IntegerField()
    label = serializers.CharField()
    amount = serializers.DecimalField(max_digits=15, decimal_places=2)
    collected_amount = serializers.DecimalField(max_digits=15, decimal_places=2)
    invoiced_amount = serializers.DecimalField(max_digits=15, decimal_places=2)
    target_total = serializers.DecimalField(max_digits=15, decimal_places=2)
    prepayment_account_no = serializers.CharField()
    prepayment_account_name = serializers.CharField()


class PrepaymentPreviewSerializer(serializers.Serializer):
    transaction_no = serializers.CharField()
    total_deposit = serializers.DecimalField(max_digits=15, decimal_places=2)
    has_cash_payment = serializers.BooleanField()
    gl_entries = GLPreviewEntrySerializer(many=True)
    customer_entries = CustomerPreviewEntrySerializer(many=True)
    detailed_customer_entries = DetailedPreviewEntrySerializer(many=True)
    line_context = LinePreviewContextSerializer(many=True)
