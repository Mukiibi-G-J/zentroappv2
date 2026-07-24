from rest_framework import serializers
from django.db.models import Sum
from .models import (
    SalesInvoice,
    SalesInvoiceLine,
    SalesReceivable,
    Customer,
    CustomerLedgerEntry,
    SalesOrder,
    SalesOrderLine,
    SalesFavoriteSlot,
)
from financials.models import PaymentMethod
from authentication.models import CustomUser


class CustomerSerializer(serializers.ModelSerializer):
    payment_method_name = serializers.CharField(
        source="payment_method.description", read_only=True
    )
    general_business_posting_group_name = serializers.CharField(
        source="general_business_posting_group.description", read_only=True
    )
    customer_posting_group_name = serializers.CharField(
        source="customer_posting_group.description", read_only=True
    )
    user_name = serializers.CharField(source="user.full_name", read_only=True)
    balance = serializers.SerializerMethodField()

    def get_balance(self, obj):
        """
        Calculate balance from open customer ledger entries, filtered by branch
        when multi-branch is enabled. Matches the branch filter used in the
        drill-down (ledger_entries) so balance and drill-down stay consistent.
        """
        qs = CustomerLedgerEntry.objects.filter(customer=obj, open=True)

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
            total_amount += entry.remaining_amount
        return abs(total_amount)

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
            "general_business_posting_group",
            "general_business_posting_group_name",
            "vat_business_posting_group",
            "customer_posting_group",
            "customer_posting_group_name",
            "customer_type",
            "payment_method",
            "payment_method_name",
            "user",
            "user_name",
            "balance",
        ]


class SalesInvoiceLineSerializer(serializers.ModelSerializer):
    item_name = serializers.SerializerMethodField()
    item_no = serializers.SerializerMethodField()
    resource_name = serializers.SerializerMethodField()
    resource_code = serializers.SerializerMethodField()
    base_unit = serializers.SerializerMethodField()
    uom_options = serializers.SerializerMethodField()
    unit_of_measure = serializers.SerializerMethodField()
    dimensions_display = serializers.SerializerMethodField()

    class Meta:
        model = SalesInvoiceLine
        fields = [
            "id",
            "system_id",
            "sales_invoice",
            "type",
            "item",
            "item_name",
            "item_no",
            "resource",
            "resource_name",
            "resource_code",
            "base_unit",
            "quantity",
            "unit_price",
            "line_discount_amount",
            "location_code",
            "line_amount",
            "total_amount",
            "vat_percent",
            "vat_amount",
            "description",
            "unit_of_measure",
            "tracking_code",
            "uom_options",
            "item_unit_of_measure",
            "global_dimension_1",
            "dimension_set",
            "dimensions_display",
            "base_unit_price",
        ]
        read_only_fields = [
            "system_id",
            "total_amount",
            "vat_amount",
            "location_code",
        ]
        extra_kwargs = {
            "sales_invoice": {"required": False},
            "item": {"required": False, "allow_null": True},
            "resource": {"required": False, "allow_null": True},
        }

    def get_item_name(self, obj):
        return obj.item.item_name if obj.item else None

    def get_item_no(self, obj):
        return obj.item.no if obj.item else None

    def get_resource_name(self, obj):
        return obj.resource.name if obj.resource else None

    def get_resource_code(self, obj):
        return obj.resource.code if obj.resource else None

    def get_base_unit(self, obj):
        """For resource lines, unit is resource's base_unit (e.g. HOUR, DAY)."""
        if obj.type == "resource" and obj.resource and obj.resource.base_unit:
            return obj.resource.base_unit.code
        return None

    def get_unit_of_measure(self, obj):
        """Return UOM code for display (item and resource lines)."""
        if obj.unit_of_measure_id:
            return obj.unit_of_measure.code
        if obj.type == "resource" and obj.resource and obj.resource.base_unit:
            return obj.resource.base_unit.code
        if obj.item_unit_of_measure_id:
            return obj.item_unit_of_measure.unit_of_measure.code
        return None

    def get_uom_options(self, obj):
        if obj.type == "resource" and obj.resource:
            uoms = getattr(obj.resource, "get_available_uoms", None)
            if uoms:
                return uoms
            if obj.resource.base_unit:
                return [{"code": obj.resource.base_unit.code, "description": obj.resource.base_unit.description, "default": True, "quantity_per_unit": 1}]
        if obj.item:
            return obj.item.get_available_uoms
        return []

    def get_base_unit_price(self, obj):
        return float(obj.base_unit_price)

    def get_dimensions_display(self, obj):
        """
        Return human-readable dimension values for frontend display.
        Format: [{"dimension_code": "BRANCH", "dimension_value_code": "kyanja"}, ...]
        """
        result = []
        if obj.dimension_set_id:
            from dimension.models import expand_dimension_set_to_dict
            d = expand_dimension_set_to_dict(obj.dimension_set)
            for dim, val in d.items():
                if dim and val:
                    result.append({
                        "dimension_code": dim.code,
                        "dimension_value_code": val.code,
                    })
        elif obj.global_dimension_1_id:
            gd1 = obj.global_dimension_1
            if gd1 and gd1.dimension_code:
                result.append({
                    "dimension_code": gd1.dimension_code.code,
                    "dimension_value_code": gd1.code,
                })
        return result

    def validate(self, attrs):
        line_type = attrs.get("type", getattr(self.instance, "type", "item"))
        item = attrs.get("item") if "item" in attrs else getattr(self.instance, "item", None)
        resource = attrs.get("resource") if "resource" in attrs else getattr(self.instance, "resource", None)
        if line_type == "item":
            if not item:
                raise serializers.ValidationError({"item": "Item is required when line type is Item."})
            if resource:
                raise serializers.ValidationError({"resource": "Resource must be empty when line type is Item."})
        elif line_type == "resource":
            if not resource:
                raise serializers.ValidationError({"resource": "Resource is required when line type is Resource."})
            if item:
                raise serializers.ValidationError({"item": "Item must be empty when line type is Resource."})
        return attrs

    def update(self, instance, validated_data):
        if "unit_of_measure" in validated_data:
            pass  # Handled by model
        return super().update(instance, validated_data)


class SalesInvoiceSerializer(serializers.ModelSerializer):
    lines = SalesInvoiceLineSerializer(many=True, required=False)
    customer_name = serializers.CharField(source="customer.name", read_only=True)
    payment_method_name = serializers.CharField(
        source="payment_method.description", read_only=True
    )
    payment_method_details = serializers.SerializerMethodField()
    user_name = serializers.SerializerMethodField()
    total_amount = serializers.SerializerMethodField()
    payment_status = serializers.CharField(read_only=True)
    branch_code = serializers.SerializerMethodField()
    reversed = serializers.SerializerMethodField()
    reversed_by = serializers.SerializerMethodField()
    reversed_date = serializers.SerializerMethodField()
    reversed_by_user = serializers.SerializerMethodField()
    global_dimension_1_display = serializers.SerializerMethodField()

    class Meta:
        model = SalesInvoice
        fields = [
            "id",
            "system_id",
            "invoice_no",
            "customer",
            "customer_name",
            "contact_person",
            "document_date",
            "posting_date",
            "vat_date",
            "due_date",
            "customer_invoice_no",
            "total_amount",
            "status",
            "amount_received",
            "change_amount",
            "payment_method",
            "payment_method_name",
            "payment_method_details",
            "payment_status",
            "user_name",
            "branch_code",
            "reversed",
            "reversed_by",
            "reversed_date",
            "reversed_by_user",
            "invoice_discount_type",
            "invoice_discount_amount",
            "invoice_discount_percentage",
            "prices_including_vat",
            "total_vat_amount",
            "global_dimension_1",
            "global_dimension_2",
            "global_dimension_1_display",
            "dimension_set",
            "created_at",
            "updated_at",
            "lines",
        ]
        read_only_fields = [
            "system_id",
            "invoice_no",
            "customer_invoice_no",
            "total_vat_amount",
            "created_at",
            "updated_at",
        ]
        extra_kwargs = {
            # On create, these are resolved from request context (X-Branch-Id / user branch)
            # and dimension rules; the client should not be forced to provide them.
            "global_dimension_1": {"required": False, "allow_null": True},
            "global_dimension_2": {"required": False, "allow_null": True},
            "dimension_set": {"required": False, "allow_null": True},
        }

    def get_total_amount(self, obj):
        from decimal import Decimal

        # Calculate subtotal from lines (after line discounts)
        subtotal = sum(line.total_amount for line in obj.lines.all())
        # Subtract invoice discount
        invoice_discount = Decimal(obj.invoice_discount_value)
        return float(subtotal - invoice_discount)

    def get_branch_code(self, obj):
        """Return the single branch code for receipt display (from invoice's global_dimension_1)."""
        if obj.global_dimension_1_id:
            return obj.global_dimension_1.code
        return None

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

    def get_user_name(self, obj):
        """Get the user name from the related customer ledger entries"""
        try:
            # Get the most recent customer ledger entry for this invoice
            ledger_entry = obj.customer.sales_ledger_entries.filter(
                document_no=obj.invoice_no
            ).first()
            if ledger_entry and ledger_entry.user:
                return ledger_entry.user.full_name
            return None
        except:
            return None

    def get_reversed(self, obj):
        """Check if this invoice has been reversed by a posted credit memo"""
        from .models import PostedSalesInvoice, SalesCreditMemo

        if obj.status != "Posted":
            return False

        # Find the PostedSalesInvoice for this SalesInvoice
        # Match by customer_invoice_no (both have the same customer_invoice_no)
        try:
            posted_invoice = PostedSalesInvoice.objects.get(
                customer_invoice_no=obj.customer_invoice_no,
                customer=obj.customer,
            )
            # Check if the posted invoice has been reversed
            return posted_invoice.reversed
        except (
            PostedSalesInvoice.DoesNotExist,
            PostedSalesInvoice.MultipleObjectsReturned,
        ):
            # Fallback: check by original_invoice_no matching invoice_no
            # This handles cases where the relationship might be different
            return SalesCreditMemo.objects.filter(
                original_invoice_no=obj.invoice_no,
                status="Posted",
            ).exists()

    def get_reversed_by(self, obj):
        """Get the credit memo number that reversed this invoice"""
        from .models import PostedSalesInvoice, SalesCreditMemo

        if obj.status != "Posted":
            return None

        # Find the PostedSalesInvoice for this SalesInvoice
        try:
            posted_invoice = PostedSalesInvoice.objects.get(
                customer_invoice_no=obj.customer_invoice_no,
                customer=obj.customer,
            )
            # Get the reversed_by field from PostedSalesInvoice
            if posted_invoice.reversed and posted_invoice.reversed_by:
                return posted_invoice.reversed_by
        except (
            PostedSalesInvoice.DoesNotExist,
            PostedSalesInvoice.MultipleObjectsReturned,
        ):
            pass

        # Fallback: check by original_invoice_no
        credit_memo = SalesCreditMemo.objects.filter(
            original_invoice_no=obj.invoice_no,
            status="Posted",
        ).first()

        if credit_memo:
            return credit_memo.credit_memo_no
        return None

    def get_reversed_date(self, obj):
        """Get the datetime when this invoice was reversed (returns datetime for proper timezone handling)"""
        from .models import PostedSalesInvoice, SalesCreditMemo

        if obj.status != "Posted":
            return None

        # First, try to get the credit memo which has the actual creation datetime
        credit_memo = SalesCreditMemo.objects.filter(
            original_invoice_no=obj.invoice_no,
            status="Posted",
        ).first()

        if credit_memo and credit_memo.created_at:
            # Return the full datetime from credit memo creation (this preserves timezone)
            return credit_memo.created_at

        # Fallback: check PostedSalesInvoice
        try:
            posted_invoice = PostedSalesInvoice.objects.get(
                customer_invoice_no=obj.customer_invoice_no,
                customer=obj.customer,
            )
            # If reversed, try to use created_at from a related credit memo
            if posted_invoice.reversed:
                # Try to find credit memo by original_invoice relationship
                related_credit_memo = SalesCreditMemo.objects.filter(
                    original_invoice=posted_invoice,
                    status="Posted",
                ).first()

                if related_credit_memo and related_credit_memo.created_at:
                    return related_credit_memo.created_at

                # Last resort: use PostedSalesInvoice's created_at if it was recently reversed
                # This is less accurate but better than a date-only field
                if posted_invoice.created_at:
                    return posted_invoice.created_at
        except (
            PostedSalesInvoice.DoesNotExist,
            PostedSalesInvoice.MultipleObjectsReturned,
        ):
            pass

        return None

    def get_reversed_by_user(self, obj):
        """Get the user who reversed this invoice"""
        from .models import PostedSalesInvoice, SalesCreditMemo

        if obj.status != "Posted":
            return None

        # Find the PostedSalesInvoice for this SalesInvoice
        try:
            posted_invoice = PostedSalesInvoice.objects.get(
                customer_invoice_no=obj.customer_invoice_no,
                customer=obj.customer,
            )
            # Get the credit memo that reversed this posted invoice
            credit_memo = SalesCreditMemo.objects.filter(
                original_invoice=posted_invoice,
                status="Posted",
            ).first()

            if credit_memo and credit_memo.reversed_by_user:
                return credit_memo.reversed_by_user.full_name
        except (
            PostedSalesInvoice.DoesNotExist,
            PostedSalesInvoice.MultipleObjectsReturned,
        ):
            pass

        # Fallback: check by original_invoice_no
        credit_memo = SalesCreditMemo.objects.filter(
            original_invoice_no=obj.invoice_no,
            status="Posted",
        ).first()

        if credit_memo and credit_memo.reversed_by_user:
            return credit_memo.reversed_by_user.full_name
        return None

    def to_internal_value(self, data):
        """Extract lines before DRF validation to preserve discount values"""
        # Create a mutable copy of data
        if not isinstance(data, dict):
            if hasattr(data, "_mutable"):
                # QueryDict - make mutable copy
                data_copy = data.copy()
            else:
                data_copy = dict(data)
        else:
            data_copy = dict(data)

        # Extract and store raw lines data before validation
        # This preserves the discount field which might be lost during nested serializer validation
        lines_data = data_copy.pop("lines", None)

        # Store raw lines for later use in create method
        if lines_data is not None:
            self._raw_lines_data = lines_data

        # Now validate without lines field
        if "lines" in data_copy:
            del data_copy["lines"]

        validated_data = super().to_internal_value(data_copy)
        # Ensure lines didn't sneak into validated_data
        validated_data.pop("lines", None)
        return validated_data

    def validate(self, attrs):
        """Validate invoice discount doesn't exceed subtotal"""
        from decimal import Decimal

        # Get invoice discount values
        discount_type = attrs.get("invoice_discount_type")
        discount_amount = attrs.get("invoice_discount_amount", Decimal("0"))
        discount_percentage = attrs.get("invoice_discount_percentage", Decimal("0"))

        # Check if invoice discounts are enabled
        if (discount_amount and Decimal(str(discount_amount)) > 0) or (
            discount_percentage and Decimal(str(discount_percentage)) > 0
        ):
            from .models import SalesReceivable

            sales_setup = SalesReceivable.objects.first()
            if not sales_setup or not sales_setup.enable_invoice_discounts:
                raise serializers.ValidationError(
                    "Invoice discounts are disabled in Sales & Receivables Setup"
                )

        # Validate percentage is between 0 and 100
        if discount_percentage:
            percentage = Decimal(str(discount_percentage))
            if percentage < 0 or percentage > 100:
                raise serializers.ValidationError(
                    {
                        "invoice_discount_percentage": "Invoice discount percentage must be between 0 and 100"
                    }
                )

        # Validate amount is non-negative
        if discount_amount:
            amount = Decimal(str(discount_amount))
            if amount < 0:
                raise serializers.ValidationError(
                    {
                        "invoice_discount_amount": "Invoice discount amount cannot be negative"
                    }
                )

        # For updates, validate discount doesn't exceed subtotal
        if self.instance and self.instance.pk:
            subtotal = Decimal("0")
            for line in self.instance.lines.all():
                subtotal += Decimal(str(line.total_amount))

            # Calculate discount value
            discount_value = Decimal("0")
            if discount_type == "amount":
                discount_value = Decimal(str(discount_amount or 0))
            elif discount_type == "percentage":
                percentage = Decimal(str(discount_percentage or 0))
                discount_value = (subtotal * percentage) / Decimal("100")

            if discount_value > subtotal:
                raise serializers.ValidationError(
                    "Invoice discount cannot exceed invoice subtotal"
                )

        return attrs

    def validate_lines(self, value):
        """Custom validation for lines that doesn't require sales_invoice during creation"""
        if not value:
            return value

        # For creation, we don't validate sales_invoice field
        # For updates, we can validate it
        for line_data in value:
            if isinstance(line_data, dict):
                # Remove sales_invoice from validation during creation
                line_data.pop("sales_invoice", None)

        return value

    def create(self, validated_data):
        from django.db import transaction
        from django.db.utils import IntegrityError
        from django.core.exceptions import ValidationError as DjangoValidationError

        try:
            with transaction.atomic():
                return self._create_invoice_with_lines(validated_data)
        except serializers.ValidationError:
            raise
        except DjangoValidationError as e:
            if hasattr(e, "message_dict"):
                raise serializers.ValidationError(e.message_dict)
            raise serializers.ValidationError(
                e.messages if hasattr(e, "messages") else {"non_field_errors": [str(e)]}
            )
        except IntegrityError as e:
            msg = str(e)
            if "serial_no" in msg.lower():
                raise serializers.ValidationError(
                    {
                        "serial_nos": (
                            "One or more serial numbers cannot be reserved on this sale "
                            "(already tracked elsewhere). Apply outstanding migrations or "
                            "pick different serials."
                        )
                    }
                )
            raise serializers.ValidationError({"non_field_errors": [msg]})
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

    def _create_invoice_with_lines(self, validated_data):
        # Use raw lines data if available (from to_internal_value), otherwise use validated data
        # This ensures we get the original discount values before nested serializer validation
        lines_data = getattr(self, "_raw_lines_data", None)
        if lines_data is None:
            lines_data = validated_data.pop("lines", [])
        else:
            # Clear the stored raw data after using it
            delattr(self, "_raw_lines_data")

        # Stamp header dimensions if not provided
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

        # Ensure header has a dimension_set consistent with global dimensions.
        # This keeps posting processors and downstream ledgers consistent even if the client omits it.
        if validated_data.get("dimension_set") is None and validated_data.get(
            "global_dimension_1"
        ) is not None:
            branch_val = validated_data["global_dimension_1"]
            try:
                from dimension.models import get_or_create_dimension_set

                # Prefer the dimension the branch value actually belongs to
                # (GL setup dim can differ from the value's dimension → empty set → null).
                dim = getattr(branch_val, "dimension_code", None)
                if dim is not None:
                    validated_data["dimension_set"] = get_or_create_dimension_set(
                        {dim: branch_val}
                    )

                if validated_data.get("dimension_set") is None:
                    from financials.models import GeneralLedgerSetup

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
                raise serializers.ValidationError(
                    {
                        "dimension_set": (
                            "Could not resolve a dimension set for the selected branch. "
                            "Check Global Dimension 1 setup and branch dimension values."
                        )
                    }
                )

        print("DEBUG: Creating sales invoice with data:", validated_data)
        print("DEBUG: Status in validated_data:", validated_data.get("status"))
        print("DEBUG: Lines data:", lines_data)

        # Handle invoice discount fields - convert to Decimal if needed
        from decimal import Decimal

        # Handle invoice_discount_amount
        if "invoice_discount_amount" in validated_data:
            discount_amount = validated_data.get("invoice_discount_amount")
            if isinstance(discount_amount, str):
                validated_data["invoice_discount_amount"] = Decimal(discount_amount)
            elif isinstance(discount_amount, (int, float)):
                validated_data["invoice_discount_amount"] = Decimal(
                    str(discount_amount)
                )
            elif discount_amount is None:
                validated_data["invoice_discount_amount"] = Decimal("0")

        # Handle invoice_discount_percentage
        if "invoice_discount_percentage" in validated_data:
            discount_percentage = validated_data.get("invoice_discount_percentage")
            if isinstance(discount_percentage, str):
                validated_data["invoice_discount_percentage"] = Decimal(
                    discount_percentage
                )
            elif isinstance(discount_percentage, (int, float)):
                validated_data["invoice_discount_percentage"] = Decimal(
                    str(discount_percentage)
                )
            elif discount_percentage is None:
                validated_data["invoice_discount_percentage"] = Decimal("0")

        # Create the sales invoice
        sales_invoice = super().create(validated_data)

        # Create the sales invoice lines
        from items.models import (
            Item,
            Location,
            UnitOfMeasure,
            ItemUnitOfMeasure,
        )
        from resources.models import Resource

        for i, line_data in enumerate(lines_data):
            line_type = line_data.get("type", "item")
            line_data["type"] = line_type

            if line_type == "resource":
                # Resource line: resolve resource, clear item-only fields
                resource_val = line_data.get("resource")
                if not resource_val:
                    raise serializers.ValidationError(
                        {"lines": f"Line {i+1}: Resource is required when type is Resource."}
                    )
                if isinstance(resource_val, int):
                    try:
                        resource = Resource.objects.get(pk=resource_val)
                    except Resource.DoesNotExist:
                        raise serializers.ValidationError(
                            {"lines": f"Line {i+1}: Resource with id {resource_val} not found."}
                        )
                elif isinstance(resource_val, str):
                    try:
                        resource = Resource.objects.get(code=resource_val)
                    except Resource.DoesNotExist:
                        raise serializers.ValidationError(
                            {"lines": f"Line {i+1}: Resource with code {resource_val} not found."}
                        )
                else:
                    resource = resource_val
                line_data["resource"] = resource
                line_data["item"] = None
                line_data["location_code"] = None
                line_data["item_unit_of_measure"] = None
                # Resolve unit_of_measure for resource line (UOM code from frontend)
                uom_code = line_data.get("unit_of_measure")
                if uom_code and isinstance(uom_code, str):
                    uom, _ = UnitOfMeasure.objects.get_or_create(
                        code=uom_code, defaults={"description": uom_code}
                    )
                    line_data["unit_of_measure"] = uom
                else:
                    line_data["unit_of_measure"] = getattr(resource, "base_unit", None)
                line_data["tracking_code"] = None
            else:
                # Item line: resolve item and location, handle UOM
                if not line_data.get("item"):
                    raise serializers.ValidationError(
                        {"lines": f"Line {i+1}: Item is required when type is Item."}
                    )
                if isinstance(line_data["item"], str):
                    try:
                        item = Item.objects.get(no=line_data["item"])
                        line_data["item"] = item
                    except Item.DoesNotExist:
                        try:
                            item = Item.objects.get(item_name=line_data["item"])
                            line_data["item"] = item
                        except Item.DoesNotExist:
                            raise serializers.ValidationError(
                                {"lines": f"Line {i+1}: Item {line_data['item']} not found."}
                            )
                elif isinstance(line_data["item"], int):
                    try:
                        item = Item.objects.get(pk=line_data["item"])
                        line_data["item"] = item
                    except Item.DoesNotExist:
                        raise serializers.ValidationError(
                            {"lines": f"Line {i+1}: Item with id {line_data['item']} not found."}
                        )
                else:
                    item = line_data["item"]

                if "location_code" not in line_data or line_data["location_code"] is None:
                    # Prefer a location that matches the effective branch (X-Branch-Id / user branch)
                    # so POS sales always post stock movements to the correct branch location.
                    from dimension.branch_filter import get_branch_for_request

                    request = self.context.get("request")
                    branch = get_branch_for_request(request) if request else None
                    if not branch and request and getattr(request, "user", None):
                        branch = getattr(request.user, "global_dimension_1", None)

                    default_location = None
                    if branch and getattr(branch, "code", None):
                        default_location = Location.objects.filter(code=branch.code).first()
                    if not default_location:
                        default_location = Location.objects.first()
                    if not default_location:
                        raise serializers.ValidationError(
                            "No location found. Please create a location first."
                        )
                    line_data["location_code"] = default_location

                if "unit_of_measure" in line_data and line_data["unit_of_measure"]:
                    try:
                        uom, _ = UnitOfMeasure.objects.get_or_create(
                            code=line_data["unit_of_measure"],
                            defaults={"description": line_data["unit_of_measure"]},
                        )
                        line_data["unit_of_measure"] = uom
                        item_uom, _ = ItemUnitOfMeasure.objects.get_or_create(
                            item=item,
                            unit_of_measure=uom,
                            defaults={"quantity_per_unit": 1},
                        )
                        line_data["item_unit_of_measure"] = item_uom
                    except Exception:
                        line_data.pop("unit_of_measure", None)
                        line_data.pop("item_unit_of_measure", None)

            # Convert quantity and unit_price
            if "quantity" in line_data:
                line_data["quantity"] = int(float(line_data["quantity"]))
            if "unit_price" in line_data:
                unit_price_val = line_data["unit_price"]
                if isinstance(unit_price_val, str):
                    line_data["unit_price"] = Decimal(unit_price_val)
                elif isinstance(unit_price_val, (int, float)):
                    line_data["unit_price"] = Decimal(str(unit_price_val))

                # Strict: reject values that need more than 2 decimals.
                unit_price = line_data["unit_price"]
                if unit_price is not None:
                    quant = Decimal("0.01")
                    if unit_price != unit_price.quantize(quant):
                        raise serializers.ValidationError(
                            {
                                "unit_price": "Only up to 2 decimal places are allowed for unit_price."
                            }
                        )

                from sales.price_permissions import validate_sales_line_unit_price

                request = self.context.get("request")
                try:
                    line_data["unit_price"] = validate_sales_line_unit_price(
                        getattr(request, "user", None) if request else None,
                        unit_price=line_data["unit_price"],
                        item=line_data.get("item"),
                        resource=line_data.get("resource"),
                        line_label=f"line {i + 1}",
                    )
                except Exception as exc:
                    # Django ValidationError → DRF ValidationError
                    from django.core.exceptions import ValidationError as DjangoValidationError

                    if isinstance(exc, DjangoValidationError):
                        raise serializers.ValidationError(exc.message_dict if hasattr(exc, "message_dict") else exc.messages)
                    raise

            discount_input = line_data.pop("line_discount_amount", None) or line_data.pop("lineDiscountAmount", None)
            try:
                if discount_input is None or discount_input == "":
                    line_data["line_discount_amount"] = Decimal("0")
                elif isinstance(discount_input, str):
                    line_data["line_discount_amount"] = Decimal(discount_input.strip()) if discount_input.strip() else Decimal("0")
                elif isinstance(discount_input, (int, float)):
                    line_data["line_discount_amount"] = Decimal(str(discount_input))
                else:
                    line_data["line_discount_amount"] = discount_input if isinstance(discount_input, Decimal) else Decimal("0")
            except (TypeError, ValueError):
                line_data["line_discount_amount"] = Decimal("0")

            # POS payload fields that are not SalesInvoiceLine columns
            serial_nos = line_data.pop("serial_nos", None) or line_data.pop(
                "serial_numbers", None
            )
            line_data.pop("id", None)
            line_data.pop("item_name", None)
            line_data.pop("item_no", None)
            line_data.pop("total_amount", None)
            line_data.pop("resource_name", None)
            line_data.pop("resource_code", None)
            line_data.pop("base_unit", None)
            line_data.pop("uom_options", None)
            line_data.pop("line_amount", None)
            line_data.pop("client_id", None)
            line_data.pop("clientId", None)

            tracking_raw = line_data.get("tracking_code")
            if tracking_raw is not None and str(tracking_raw).strip() == "":
                line_data["tracking_code"] = None

            # Merge default dimensions (Customer, Item/Resource) with user and explicit
            from dimension.models import get_merged_line_dimensions
            from dimension.branch_filter import get_branch_for_request

            request = self.context.get("request")
            request_user = request.user if request else None

            # Prefer X-Branch-Id (selected branch) over user.global_dimension_1
            branch = get_branch_for_request(request) if request else None
            if not branch and request_user:
                branch = getattr(request_user, "global_dimension_1", None)
            line_data_for_dims = dict(line_data)
            if branch:
                line_data_for_dims["global_dimension_1"] = branch

            customer_no = (
                getattr(sales_invoice.customer, "no", None)
                if sales_invoice.customer
                else None
            )
            item = line_data.get("item")
            resource = line_data.get("resource")
            dims = get_merged_line_dimensions(
                customer_no=customer_no,
                item=item,
                resource=resource,
                request_user=request_user,
                line_data=line_data_for_dims,
                header_dimensions=sales_invoice,
            )
            line_data["dimension_set"] = dims.get("dimension_set")
            line_data["global_dimension_1"] = dims.get("global_dimension_1")

            # POS often sends description=''; use item/resource name for sales history lines
            if not str(line_data.get("description") or "").strip():
                if item is not None:
                    line_data["description"] = getattr(item, "item_name", "") or ""
                elif resource is not None:
                    line_data["description"] = getattr(resource, "name", "") or ""

            line = SalesInvoiceLine.objects.create(
                sales_invoice=sales_invoice, **line_data
            )

            # POS: attach serial tracking specs (one SN per unit). Lot uses tracking_code.
            if serial_nos and line_data.get("type", "item") == "item" and line.item_id:
                from items.models import TrackingSpecification, ItemLedgerEntries

                if not isinstance(serial_nos, (list, tuple)):
                    serial_nos = [serial_nos]
                cleaned = [str(s).strip() for s in serial_nos if str(s).strip()]
                if cleaned:
                    TrackingSpecification.objects.filter(
                        sales_invoice_line=line
                    ).delete()
                    for sn in cleaned:
                        # Match stock location for this serial (POS default location
                        # may differ from where the SN was received).
                        ledger = (
                            ItemLedgerEntries.objects.filter(
                                item=line.item,
                                serial_no__iexact=sn,
                                remaining_quantity__gt=0,
                            )
                            .select_related("location")
                            .first()
                        )
                        sn_location = (
                            ledger.location
                            if ledger and ledger.location_id
                            else line.location_code
                        )
                        if (
                            sn_location
                            and line.location_code_id
                            and sn_location.pk != line.location_code_id
                        ):
                            line.location_code = sn_location
                            line.save(update_fields=["location_code"])
                        TrackingSpecification(
                            sales_invoice=sales_invoice,
                            sales_invoice_line=line,
                            item=line.item,
                            serial_no=sn,
                            quantity_base=1,
                            description="",
                            location_code=sn_location,
                            user=(
                                request_user
                                if request_user
                                and getattr(request_user, "is_authenticated", False)
                                else None
                            ),
                        ).save()
                    line.tracking_code = None
                    line.save(update_fields=["tracking_code"])

        return sales_invoice

    def update(self, instance, validated_data):
        print("Sales Invoice Update - validated_data:", validated_data)

        # Update the instance fields
        for attr, value in validated_data.items():
            if attr != "lines":  # Skip lines as they're handled separately
                setattr(instance, attr, value)

        try:
            instance.save()
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


class SalesHistoryListSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="customer.name", read_only=True)
    payment_method_name = serializers.CharField(
        source="payment_method.description", read_only=True, allow_null=True
    )
    payment_status = serializers.CharField(read_only=True)
    total_amount = serializers.DecimalField(
        max_digits=18, decimal_places=2, source="computed_total_amount", read_only=True
    )
    reversed = serializers.BooleanField(read_only=True)
    reversed_by_user = serializers.CharField(read_only=True, allow_null=True)
    reversed_date = serializers.DateTimeField(read_only=True, allow_null=True)

    class Meta:
        model = SalesInvoice
        fields = [
            "id",
            "system_id",
            "invoice_no",
            "customer",
            "customer_name",
            "document_date",
            "status",
            "total_amount",
            "payment_method_name",
            "payment_status",
            "reversed",
            "reversed_by_user",
            "reversed_date",
        ]


class SalesOrderLineSerializer(serializers.ModelSerializer):
    item_name = serializers.SerializerMethodField()
    item_no = serializers.SerializerMethodField()
    resource_name = serializers.SerializerMethodField()
    resource_code = serializers.SerializerMethodField()
    base_unit = serializers.SerializerMethodField()
    uom_options = serializers.SerializerMethodField()
    dimensions_display = serializers.SerializerMethodField()

    class Meta:
        model = SalesOrderLine
        fields = [
            "id",
            "system_id",
            "sales_order",
            "type",
            "item",
            "item_name",
            "item_no",
            "resource",
            "resource_name",
            "resource_code",
            "base_unit",
            "quantity",
            "unit_price",
            "location_code",
            "line_amount",
            "total_amount",
            "description",
            "unit_of_measure",
            "uom_options",
            "item_unit_of_measure",
            "global_dimension_1",
            "dimension_set",
            "dimensions_display",
            "amount",
            "line_discount_amount",
        ]
        read_only_fields = [
            "system_id",
            "total_amount",
            "location_code",
            "amount",
        ]
        extra_kwargs = {
            "sales_order": {"required": False},
            "item": {"required": False, "allow_null": True},
            "resource": {"required": False, "allow_null": True},
        }

    def get_item_name(self, obj):
        return obj.item.item_name if obj.item else None

    def get_item_no(self, obj):
        return obj.item.no if obj.item else None

    def get_resource_name(self, obj):
        return obj.resource.name if obj.resource else None

    def get_resource_code(self, obj):
        return obj.resource.code if obj.resource else None

    def get_base_unit(self, obj):
        if obj.type == "resource" and obj.resource:
            return obj.resource.base_unit
        return None

    def get_uom_options(self, obj):
        if obj.type == "resource" and obj.resource:
            uoms = getattr(obj.resource, "get_available_uoms", None)
            if uoms:
                return uoms
            return [{"code": obj.resource.base_unit, "description": obj.resource.get_base_unit_display(), "default": True, "quantity_per_unit": 1}]
        if obj.item:
            return obj.item.get_available_uoms
        return []

    def get_dimensions_display(self, obj):
        """Return human-readable dimension values for frontend (tracking codes/values)."""
        result = []
        if obj.dimension_set_id:
            from dimension.models import expand_dimension_set_to_dict
            d = expand_dimension_set_to_dict(obj.dimension_set)
            for dim, val in d.items():
                if dim and val:
                    result.append({"dimension_code": dim.code, "dimension_value_code": val.code})
        elif obj.global_dimension_1_id:
            gd1 = obj.global_dimension_1
            if gd1 and gd1.dimension_code:
                result.append({"dimension_code": gd1.dimension_code.code, "dimension_value_code": gd1.code})
        return result

    def validate(self, attrs):
        line_type = attrs.get("type", getattr(self.instance, "type", "item"))
        item = attrs.get("item") if "item" in attrs else getattr(self.instance, "item", None)
        resource = attrs.get("resource") if "resource" in attrs else getattr(self.instance, "resource", None)
        if line_type == "item":
            if not item:
                raise serializers.ValidationError({"item": "Item is required when line type is Item."})
            if resource:
                raise serializers.ValidationError({"resource": "Resource must be empty when line type is Item."})
        elif line_type == "resource":
            if not resource:
                raise serializers.ValidationError({"resource": "Resource is required when line type is Resource."})
            if item:
                raise serializers.ValidationError({"item": "Item must be empty when line type is Resource."})
        return attrs

    def create(self, validated_data):
        return SalesOrderLine.objects.create(**validated_data)


class SalesOrderSerializer(serializers.ModelSerializer):
    # Don't use nested serializer - handle lines manually to avoid DRF validation issues
    # lines = SalesOrderLineSerializer(many=True, required=False, read_only=True)
    customer_name = serializers.CharField(source="customer.name", read_only=True)
    total_amount = serializers.IntegerField(read_only=True)

    def to_representation(self, instance):
        """Add lines when serializing for response"""
        representation = super().to_representation(instance)
        # Add lines using the line serializer
        if hasattr(instance, "lines"):
            representation["lines"] = SalesOrderLineSerializer(
                instance.lines.all(), many=True
            ).data
        return representation

    class Meta:
        model = SalesOrder
        fields = [
            "id",
            "system_id",
            "order_no",
            "customer",
            "customer_name",
            "contact_person",
            "order_date",
            "expected_delivery_date",
            "notes",
            "status",
            "total_amount",
            "created_at",
            "updated_at",
            # "lines",  # Handled manually in to_representation
        ]
        read_only_fields = [
            "system_id",
            "order_no",
            "total_amount",
            "created_at",
            "updated_at",
        ]

    def to_internal_value(self, data):
        # Extract lines before DRF tries to validate nested serializer
        # This prevents DRF from trying to use the wrong serializer
        # Create a mutable copy of data
        if not isinstance(data, dict):
            if hasattr(data, "_mutable"):
                # QueryDict - make mutable copy
                data_copy = data.copy()
            else:
                data_copy = dict(data)
        else:
            data_copy = dict(data)

        # Extract and remove lines completely before validation
        lines_data = data_copy.pop("lines", None)

        # Store lines for later use in update method
        if lines_data is not None:
            self._lines_data = lines_data

        # Now validate without lines field - ensure it's completely removed
        if "lines" in data_copy:
            del data_copy["lines"]

        validated_data = super().to_internal_value(data_copy)
        # Double-check lines didn't sneak into validated_data
        validated_data.pop("lines", None)
        return validated_data

    def validate(self, attrs):
        # Ensure lines are not in attrs (they're handled separately)
        # This should never happen since we remove it in to_internal_value, but just in case
        if "lines" in attrs:
            del attrs["lines"]
        return attrs

    def create(self, validated_data):
        from decimal import Decimal
        from items.models import Item, Location, UnitOfMeasure, ItemUnitOfMeasure
        from resources.models import Resource

        lines_data = validated_data.pop("lines", [])
        order = SalesOrder.objects.create(**validated_data)

        for line_data in lines_data:
            line_type = line_data.get("type", "item")
            line_data["type"] = line_type

            if line_type == "resource":
                resource_val = line_data.get("resource")
                if not resource_val:
                    raise serializers.ValidationError(
                        "Resource is required when line type is Resource."
                    )
                if isinstance(resource_val, int):
                    resource = Resource.objects.filter(pk=resource_val).first()
                elif isinstance(resource_val, str):
                    resource = Resource.objects.filter(code=resource_val).first()
                else:
                    resource = resource_val
                if not resource:
                    raise serializers.ValidationError(
                        f"Resource {resource_val} not found."
                    )
                line_data["resource"] = resource
                line_data["item"] = None
                line_data["location_code"] = None
                line_data["item_unit_of_measure"] = None
                uom_code = line_data.get("unit_of_measure")
                if uom_code and isinstance(uom_code, str):
                    uom, _ = UnitOfMeasure.objects.get_or_create(
                        code=uom_code, defaults={"description": uom_code}
                    )
                    line_data["unit_of_measure"] = uom
                else:
                    line_data["unit_of_measure"] = getattr(resource, "base_unit", None)
            else:
                item_value = line_data.get("item")
                if not item_value:
                    raise serializers.ValidationError(
                        "Item is required when line type is Item."
                    )
                if isinstance(item_value, str):
                    item = Item.objects.filter(no=item_value).first()
                    if not item:
                        item = Item.objects.filter(item_name=item_value).first()
                    if not item:
                        raise serializers.ValidationError(
                            f"Item with number/name {item_value} not found"
                        )
                    line_data["item"] = item
                if "location_code" not in line_data or not line_data.get("location_code"):
                    # Same rule as SalesInvoice: default to location matching effective branch.
                    from dimension.branch_filter import get_branch_for_request

                    request = self.context.get("request")
                    branch = get_branch_for_request(request) if request else None
                    if not branch and request and getattr(request, "user", None):
                        branch = getattr(request.user, "global_dimension_1", None)

                    default_location = None
                    if branch and getattr(branch, "code", None):
                        default_location = Location.objects.filter(code=branch.code).first()
                    if not default_location:
                        default_location = Location.objects.first()
                    if not default_location:
                        raise serializers.ValidationError(
                            "No location found. Please create a location first."
                        )
                    line_data["location_code"] = default_location
                uom_code = line_data.get("unit_of_measure")
                if uom_code:
                    uom, _ = UnitOfMeasure.objects.get_or_create(
                        code=uom_code, defaults={"description": uom_code}
                    )
                    line_data["unit_of_measure"] = uom
                    item = line_data["item"]
                    item_uom, _ = ItemUnitOfMeasure.objects.get_or_create(
                        item=item,
                        unit_of_measure=uom,
                        defaults={"quantity_per_unit": 1},
                    )
                    line_data["item_unit_of_measure"] = item_uom

            if "quantity" in line_data:
                line_data["quantity"] = int(float(line_data["quantity"]))
            if "unit_price" in line_data:
                unit_price_val = line_data["unit_price"]
                if isinstance(unit_price_val, str):
                    line_data["unit_price"] = Decimal(unit_price_val)
                elif isinstance(unit_price_val, (int, float)):
                    line_data["unit_price"] = Decimal(str(unit_price_val))

                # Strict: reject values that need more than 2 decimals.
                unit_price = line_data["unit_price"]
                if unit_price is not None:
                    quant = Decimal("0.01")
                    if unit_price != unit_price.quantize(quant):
                        raise serializers.ValidationError(
                            {
                                "unit_price": "Only up to 2 decimal places are allowed for unit_price."
                            }
                        )

            line_data.pop("id", None)
            line_data.pop("item_name", None)
            line_data.pop("item_no", None)
            line_data.pop("total_amount", None)
            line_data.pop("resource_name", None)
            line_data.pop("resource_code", None)
            line_data.pop("base_unit", None)
            line_data.pop("uom_options", None)
            line_data.pop("line_amount", None)

            SalesOrderLine.objects.create(sales_order=order, **line_data)

        order.recalculate_totals()
        return order

    def update(self, instance, validated_data):
        # Pull raw lines from _lines_data (set manually in view) or from initial_data
        # This follows the Prepayment pattern to avoid DRF nested serializer validation issues
        lines_data = getattr(self, "_lines_data", None)
        if lines_data is None:
            # Fallback to initial_data if _lines_data not set
            lines_data = getattr(self, "initial_data", {}).get("lines", None)

        # Ensure we don't pass lines down to default ModelSerializer.update
        validated_data.pop("lines", None)

        # Update instance fields (excluding lines)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        try:
            instance.save()
        except Exception as e:
            raise serializers.ValidationError(
                {
                    "non_field_errors": [
                        f"Configuration Error: {str(e)}. "
                        "Please contact your administrator to set up the required configuration."
                    ]
                }
            )

        # Handle lines update if provided - work with shallow copy to avoid mutating initial_data
        if lines_data is not None:
            self._update_lines(instance, [dict(ld or {}) for ld in lines_data])
            instance.recalculate_totals()

        return instance

    def _merge_line_dimensions(self, instance, line_data, prepared_data, item, resource):
        """Merge default dimensions (Customer, Item/Resource) with user and explicit payload."""
        from dimension.models import get_merged_line_dimensions

        customer_no = (
            getattr(instance.customer, "no", None)
            if hasattr(instance, "customer") and instance.customer
            else None
        )
        request_user = None
        if self.context.get("request") and hasattr(self.context["request"], "user"):
            request_user = self.context["request"].user
        dims = get_merged_line_dimensions(
            customer_no=customer_no,
            item=item,
            resource=resource,
            request_user=request_user,
            line_data=line_data,
        )
        prepared_data["dimension_set"] = dims.get("dimension_set")
        prepared_data["global_dimension_1"] = dims.get("global_dimension_1")

    def _update_lines(self, instance, lines_data):
        """Update sales order lines - supports both item and resource lines (BC-style)."""
        from decimal import Decimal
        from items.models import Item, Location, UnitOfMeasure, ItemUnitOfMeasure
        from resources.models import Resource
        from sales.models import SalesOrderLine, SalesOrder

        existing_lines = {line.id: line for line in instance.lines.all()}

        for line_data in lines_data:
            line_id = line_data.get("id")
            line_type = line_data.get("type", "item")

            if line_data.get("deleted"):
                if line_id and line_id in existing_lines:
                    existing_lines[line_id].delete()
                continue

            line_data.pop("total_amount", None)
            line_data.pop("amount", None)
            line_data.pop("item_name", None)
            line_data.pop("item_no", None)
            line_data.pop("resource_name", None)
            line_data.pop("resource_code", None)
            line_data.pop("base_unit", None)
            line_data.pop("uom_options", None)

            unit_price_val = line_data.get("unit_price", 0)
            if isinstance(unit_price_val, str):
                unit_price = Decimal(unit_price_val)
            elif isinstance(unit_price_val, (int, float)):
                unit_price = Decimal(str(unit_price_val))
            else:
                unit_price = Decimal("0")
            quantity = int(float(line_data.get("quantity", 0)))
            description = line_data.get("description", "")

            if line_type == "resource":
                resource_val = line_data.get("resource")
                if not resource_val:
                    continue
                if isinstance(resource_val, int):
                    resource = Resource.objects.filter(pk=resource_val).first()
                elif isinstance(resource_val, str):
                    resource = Resource.objects.filter(code=resource_val).first()
                else:
                    resource = resource_val
                if not resource:
                    continue
                uom_code = line_data.get("unit_of_measure")
                if uom_code and isinstance(uom_code, str):
                    unit_of_measure, _ = UnitOfMeasure.objects.get_or_create(
                        code=uom_code, defaults={"description": uom_code}
                    )
                else:
                    unit_of_measure = getattr(resource, "base_unit", None)
                prepared_data = {
                    "type": "resource",
                    "resource": resource,
                    "item": None,
                    "quantity": quantity,
                    "unit_price": unit_price,
                    "description": description or resource.name,
                    "item_unit_of_measure": None,
                    "unit_of_measure": unit_of_measure,
                    "location_code": None,
                }
                self._merge_line_dimensions(instance, line_data, prepared_data, None, resource)
            else:
                item = None
                item_value = line_data.get("item") or line_data.get("item_system_id")
                item_no = line_data.get("item_no")
                item_name = line_data.get("item_name")
                if isinstance(item_value, str):
                    item = Item.objects.filter(system_id=item_value).first()
                    if not item:
                        item = Item.objects.filter(no=item_value).first()
                    if not item:
                        item = Item.objects.filter(item_name=item_value).first()
                elif isinstance(item_value, int):
                    item = Item.objects.filter(pk=item_value).first()
                elif hasattr(item_value, "no"):
                    item = item_value
                if not item and item_no:
                    item = Item.objects.filter(no=item_no).first()
                if not item and item_name:
                    item = Item.objects.filter(item_name=item_name).first()
                if not item:
                    continue

                location = Location.objects.first()
                if hasattr(instance, "customer") and getattr(instance.customer, "global_dimension_1", None):
                    try:
                        location = Location.objects.get(code=instance.customer.global_dimension_1.code)
                    except Exception:
                        pass
                unit_of_measure_code = line_data.get("unit_of_measure", "PCS")
                if isinstance(unit_of_measure_code, str):
                    unit_of_measure, _ = UnitOfMeasure.objects.get_or_create(
                        code=unit_of_measure_code,
                        defaults={"description": unit_of_measure_code},
                    )
                else:
                    unit_of_measure = unit_of_measure_code
                item_unit_of_measure, _ = ItemUnitOfMeasure.objects.get_or_create(
                    unit_of_measure=unit_of_measure,
                    item=item,
                    defaults={"quantity_per_unit": 1},
                )
                prepared_data = {
                    "type": "item",
                    "item": item,
                    "resource": None,
                    "quantity": quantity,
                    "unit_price": unit_price,
                    "description": description or (item.item_name if item else ""),
                    "item_unit_of_measure": item_unit_of_measure,
                    "unit_of_measure": unit_of_measure,
                    "location_code": location,
                }
                self._merge_line_dimensions(instance, line_data, prepared_data, item, None)

            if line_data.get("line_discount_amount") is not None:
                try:
                    prepared_data["line_discount_amount"] = Decimal(str(line_data["line_discount_amount"]))
                except (TypeError, ValueError):
                    pass

            if line_id and line_id in existing_lines:
                line = existing_lines[line_id]
                for field, value in prepared_data.items():
                    setattr(line, field, value)
                line.save()
            else:
                if not isinstance(instance, SalesOrder):
                    raise ValueError(f"Instance must be SalesOrder, got {type(instance)}")
                SalesOrderLine.objects.create(sales_order=instance, **prepared_data)


class CustomerLedgerSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="customer.name", read_only=True)
    payment_method_name = serializers.CharField(
        source="payment_method.description", read_only=True
    )
    days_overdue = serializers.IntegerField(read_only=True)
    # Mirror vendor presentation: show invoices as negative amounts
    amount = serializers.SerializerMethodField()
    original_amount = serializers.SerializerMethodField()
    remaining_amount = serializers.SerializerMethodField()

    def get_amount(self, obj):
        try:
            return (
                abs(obj.amount) if str(obj.document_type) == "Invoice" else obj.amount
            )
        except Exception:
            return obj.amount

    def get_original_amount(self, obj):
        try:
            return (
                abs(obj.original_amount)
                if str(obj.document_type) == "Invoice"
                else obj.original_amount
            )
        except Exception:
            return obj.original_amount

    def get_remaining_amount(self, obj):
        try:
            # Use the property method which computes from detailed entries
            return abs(obj.remaining_amount)
        except Exception:
            return 0

    class Meta:
        model = CustomerLedgerEntry
        fields = [
            "id",
            "system_id",
            "posting_date",
            "document_date",
            "document_type",
            "document_no",
            "external_document_no",
            "customer",
            "customer_name",
            "description",
            "receipt_no",
            "payment_method",
            "payment_method_name",
            "amount",
            "remaining_amount",
            "sales",
            "original_amount",
            "due_date",
            "open",
            "global_dimension_1",
            "dimension_set",
            "transaction_no",
            "user",
            "days_overdue",
        ]


class SalesReceivableSerializer(serializers.ModelSerializer):
    class Meta:
        model = SalesReceivable
        fields = [
            "id",
            "customer_no",
            "sales_no",
            "invoice_no",
            "posted_invoice_no",
            "credit_memo_no",
            "posted_credit_memo_no",
            "posted_prepayment_invoice_no",
            "posted_prepayment_credit_memo_no",
            "sales_order_no",
            "prevent_price_below_original",
            "disable_price_editing",
            "enable_line_discounts",
        ]


# Additional serializers for API compatibility
class SalesSerializer(serializers.Serializer):
    """Serializer for sales dashboard and reporting"""

    total_sales = serializers.DecimalField(
        max_digits=15, decimal_places=2, read_only=True
    )
    total_invoices = serializers.IntegerField(read_only=True)
    total_customers = serializers.IntegerField(read_only=True)
    average_invoice_amount = serializers.DecimalField(
        max_digits=15, decimal_places=2, read_only=True
    )
    recent_sales = serializers.ListField(read_only=True)
    top_customers = serializers.ListField(read_only=True)
    sales_by_month = serializers.ListField(read_only=True)


class CreateSalesSerializer(serializers.Serializer):
    """Serializer for creating sales transactions"""

    customer = serializers.PrimaryKeyRelatedField(queryset=Customer.objects.all())
    contact_person = serializers.CharField(
        max_length=255, required=False, allow_blank=True
    )
    document_date = serializers.DateField(required=False)
    posting_date = serializers.DateField(required=False)
    vat_date = serializers.DateField(required=False)
    due_date = serializers.DateField(required=False)
    customer_invoice_no = serializers.CharField(
        max_length=100, required=False, allow_blank=True
    )
    status = serializers.CharField(max_length=20, required=False)
    amount_received = serializers.IntegerField(required=False, min_value=0)
    change_amount = serializers.IntegerField(required=False, min_value=0)
    payment_method = serializers.PrimaryKeyRelatedField(
        queryset=PaymentMethod.objects.all(), required=False, allow_null=True
    )
    user = serializers.PrimaryKeyRelatedField(
        queryset=CustomUser.objects.all(), required=False, allow_null=True
    )
    lines = serializers.ListField(
        child=serializers.DictField(), required=True, min_length=1
    )


class SalesFavoriteSlotSerializer(serializers.ModelSerializer):
    """Read serializer for POS favorites grid; sort_order mirrors position for reorder APIs."""

    sort_order = serializers.IntegerField(source="position", read_only=True)

    class Meta:
        model = SalesFavoriteSlot
        fields = [
            "system_id",
            "position",
            "sort_order",
            "item_system_id",
            "item_no",
            "item_name",
            "unit_price",
        ]
