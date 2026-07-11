"""
Utility functions for Production BOM processing.
Handles service sale processing, inventory deduction, and resource utilization tracking.
"""

from django.db import transaction
from django.core.exceptions import ValidationError
from decimal import Decimal


def process_service_sale(sale_line):
    """
    Process a service sale by applying the Production BOM:
    - Deduct inventory items based on BOM lines
    - Log resource utilization
    - Calculate and set costs on the sale line

    Args:
        sale_line: SalesInvoiceLine instance

    Returns:
        dict: Processing result with status and details

    Raises:
        ValidationError: If insufficient inventory or inactive resources
    """

    if not sale_line.is_service_sale():
        return {
            "status": "skipped",
            "message": "Not a service sale, no BOM processing needed",
        }

    # Check if service item has a production BOM
    if (
        not hasattr(sale_line.item, "production_bom")
        or not sale_line.item.production_bom
    ):
        return {
            "status": "skipped",
            "message": "Service has no production BOM defined",
        }

    bom = sale_line.item.production_bom

    if not bom.is_active:
        raise ValidationError(f"Production BOM {bom.bom_code} is not active")

    # Use transaction to ensure all-or-nothing processing
    with transaction.atomic():
        inventory_deductions = []
        resource_utilizations = []
        total_cost = Decimal("0.00")

        # Process each BOM line
        for bom_line in bom.lines.all():
            if bom_line.line_type == "item":
                # Process item deduction
                result = _process_inventory_line(bom_line, sale_line.quantity)
                inventory_deductions.append(result)
                total_cost += Decimal(str(bom_line.total_cost)) * sale_line.quantity

            elif bom_line.line_type == "production_bom":
                # Process production BOM (nested BOM)
                result = _process_production_bom_line(
                    bom_line, sale_line.quantity, sale_line.assigned_resource
                )
                resource_utilizations.append(result)
                total_cost += Decimal(str(bom_line.total_cost)) * sale_line.quantity

        # Update sale line costs
        sale_line.unit_cost = (
            total_cost / sale_line.quantity if sale_line.quantity > 0 else 0
        )
        sale_line.total_cost = total_cost
        sale_line.save(update_fields=["unit_cost", "total_cost"])

        return {
            "status": "success",
            "message": "BOM processed successfully",
            "total_cost": float(total_cost),
            "inventory_deductions": inventory_deductions,
            "resource_utilizations": resource_utilizations,
        }


def _process_inventory_line(bom_line, sale_quantity):
    """
    Process an inventory BOM line by deducting stock.

    Args:
        bom_line: BOMLine instance with line_type='inventory'
        sale_quantity: Quantity of service being sold

    Returns:
        dict: Deduction details

    Raises:
        ValidationError: If insufficient inventory
    """

    if not bom_line.item:
        raise ValidationError(f"BOM line {bom_line.line_number} has no item")

    inventory_item = bom_line.item
    required_quantity = float(bom_line.quantity_per) * sale_quantity

    # Check if item type is Inventory (actual stock items)
    if inventory_item.type == "Inventory":
        # Get current quantity from ItemLedgerEntries
        from items.models import ItemLedgerEntries

        # Calculate available quantity
        ledger_entries = ItemLedgerEntries.objects.filter(item=inventory_item)
        available_quantity = sum(
            float(entry.remaining_quantity) for entry in ledger_entries
        )

        if available_quantity < required_quantity:
            raise ValidationError(
                f"Insufficient inventory for {inventory_item.item_name}. "
                f"Required: {required_quantity}, Available: {available_quantity}"
            )

        # Deduct inventory (FIFO method)
        _deduct_inventory_fifo(inventory_item, required_quantity)

        return {
            "item": inventory_item.item_name,
            "quantity_deducted": required_quantity,
            "remaining_quantity": available_quantity - required_quantity,
        }
    else:
        # For Service or Non-Inventory items, just log the usage
        return {
            "item": inventory_item.item_name,
            "quantity_used": required_quantity,
            "note": "Non-inventory item, no stock deduction",
        }


def _deduct_inventory_fifo(inventory_item, quantity_to_deduct):
    """
    Deduct inventory using FIFO (First In, First Out) method.

    Args:
        inventory_item: Item instance
        quantity_to_deduct: Quantity to deduct
    """

    from items.models import ItemLedgerEntries

    # Get oldest entries first (FIFO)
    ledger_entries = ItemLedgerEntries.objects.filter(
        item=inventory_item,
        remaining_quantity__gt=0,
    ).order_by("created_at")

    remaining_to_deduct = quantity_to_deduct

    for entry in ledger_entries:
        if remaining_to_deduct <= 0:
            break

        entry_quantity = float(entry.remaining_quantity)

        if entry_quantity >= remaining_to_deduct:
            # This entry has enough to cover the remaining deduction
            entry.remaining_quantity = Decimal(
                str(entry_quantity - remaining_to_deduct)
            )
            entry.save(update_fields=["remaining_quantity"])
            remaining_to_deduct = 0
        else:
            # Use all of this entry and continue to next
            entry.remaining_quantity = Decimal("0")
            entry.save(update_fields=["remaining_quantity"])
            remaining_to_deduct -= entry_quantity

    if remaining_to_deduct > 0:
        raise ValidationError(
            f"Could not deduct full quantity. Remaining: {remaining_to_deduct}"
        )


def _process_production_bom_line(bom_line, sale_quantity, assigned_resource=None):
    """
    Process a production BOM line by processing the nested BOM.

    Args:
        bom_line: BOMLine instance with line_type='production_bom'
        sale_quantity: Quantity of service being sold
        assigned_resource: Resource instance that performed the service (optional)

    Returns:
        dict: Production BOM processing details

    Raises:
        ValidationError: If item doesn't have a production BOM
    """

    if not bom_line.item:
        raise ValidationError(f"BOM line {bom_line.line_number} has no item")

    if not hasattr(bom_line.item, "production_bom") or not bom_line.item.production_bom:
        raise ValidationError(
            f"BOM line {bom_line.line_number} item {bom_line.item.item_name} has no production BOM"
        )

    production_bom = bom_line.item.production_bom

    # Calculate required quantity
    required_quantity = float(bom_line.quantity_per) * sale_quantity

    # Process the nested BOM recursively
    # This will process all lines in the nested BOM
    nested_result = process_service_sale(
        type("obj", (object,), {
            "item": bom_line.item,
            "quantity": required_quantity,
            "assigned_resource": assigned_resource
        })()
    )

    return {
        "item": bom_line.item.item_name,
        "item_no": bom_line.item.no,
        "production_bom": production_bom.bom_code,
        "quantity_used": required_quantity,
        "nested_processing": nested_result,
        "note": "Production BOM processed",
    }


def validate_service_sale(sale_line):
    """
    Validate a service sale before processing.

    Args:
        sale_line: SalesInvoiceLine instance

    Returns:
        tuple: (is_valid, error_messages)
    """

    errors = []

    if not sale_line.is_service_sale():
        return True, []

    # Check if service has BOM
    if (
        not hasattr(sale_line.item, "production_bom")
        or not sale_line.item.production_bom
    ):
        # Service without BOM is allowed, but no processing will happen
        return True, []

    bom = sale_line.item.production_bom

    # Check if BOM is active
    if not bom.is_active:
        errors.append(f"Production BOM {bom.bom_code} is not active")

    # Check inventory availability for item lines
    for bom_line in bom.lines.filter(line_type="item"):
        if bom_line.item and bom_line.item.type == "Inventory":
            from items.models import ItemLedgerEntries

            required_quantity = float(bom_line.quantity_per) * sale_line.quantity
            ledger_entries = ItemLedgerEntries.objects.filter(
                item=bom_line.item
            )
            available_quantity = sum(
                float(entry.remaining_quantity) for entry in ledger_entries
            )

            if available_quantity < required_quantity:
                errors.append(
                    f"Insufficient inventory: {bom_line.item.item_name} "
                    f"(Required: {required_quantity}, Available: {available_quantity})"
                )

    # Check production BOM lines have valid production BOMs
    for bom_line in bom.lines.filter(line_type="production_bom"):
        if bom_line.item:
            if not hasattr(bom_line.item, "production_bom") or not bom_line.item.production_bom:
                errors.append(
                    f"Item {bom_line.item.item_name} does not have a Production BOM"
                )
            elif not bom_line.item.production_bom.is_active:
                errors.append(
                    f"Production BOM {bom_line.item.production_bom.bom_code} is not active"
                )

    return len(errors) == 0, errors


def get_service_cost_breakdown(service_item):
    """
    Get detailed cost breakdown for a service item based on its BOM.

    Args:
        service_item: Item instance with type='Service'

    Returns:
        dict: Cost breakdown details
    """

    if not hasattr(service_item, "production_bom") or not service_item.production_bom:
        return {
            "has_bom": False,
            "total_cost": 0,
            "resource_cost": 0,
            "inventory_cost": 0,
            "profit_margin": 0,
            "breakdown": [],
        }

    bom = service_item.production_bom
    breakdown = []
    resource_cost = Decimal("0.00")
    inventory_cost = Decimal("0.00")

    for line in bom.lines.all():
        line_detail = {
            "line_number": line.line_number,
            "line_type": line.line_type,
            "component": None,
            "quantity": 0,
            "unit": None,
            "unit_cost": float(line.unit_cost),
            "total_cost": float(line.total_cost),
        }

        if line.line_type == "production_bom" and line.item:
            line_detail["component"] = line.item.item_name
            line_detail["quantity"] = float(line.quantity_per)
            if hasattr(line.item, "production_bom") and line.item.production_bom:
                line_detail["unit"] = "BOM"
                line_detail["production_bom_code"] = line.item.production_bom.bom_code
            resource_cost += Decimal(str(line.total_cost))
        elif line.line_type == "item" and line.item:
            line_detail["component"] = line.item.item_name
            line_detail["quantity"] = float(line.quantity_per)
            line_detail["unit"] = line.item.unit_of_measure.code if line.item.unit_of_measure else "units"
            inventory_cost += Decimal(str(line.total_cost))

        breakdown.append(line_detail)

    total_cost = resource_cost + inventory_cost
    service_price = (
        Decimal(str(service_item.unit_price))
        if service_item.unit_price
        else Decimal("0")
    )

    profit_margin = 0
    if service_price > 0:
        profit_margin = float(((service_price - total_cost) / service_price) * 100)

    return {
        "has_bom": True,
        "bom_code": bom.bom_code,
        "bom_name": bom.name,
        "total_cost": float(total_cost),
        "resource_cost": float(resource_cost),
        "inventory_cost": float(inventory_cost),
        "service_price": float(service_price),
        "profit": float(service_price - total_cost),
        "profit_margin": profit_margin,
        "breakdown": breakdown,
    }


