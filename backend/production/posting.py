"""
Production Order Posting Service.

Posts ItemJournal records (Consumption and Output) for a ProductionOrder,
creating G/L entries, Item Ledger Entries, Value Entries, and Capacity Ledger Entries.

Flow: Preview builds posting data → User confirms → Post uses that preview data
to create DB records. This ensures consistency between what is shown and what is posted.
"""

import json
import uuid
from decimal import Decimal
from django.db import transaction

from items.models import Item, ItemJournal, ItemLedgerEntries, ValueEntry
from items.enums import EntryType
from common.enums import Status
from financials.models import GeneralLedgerEntry, G_LAccount
from postings.models import InventoryPostingSetup, GeneralPostingSetup
from production.models import CapacityLedgerEntry


class ProductionOrderPostingError(Exception):
    """Raised when production order posting fails validation or execution."""

    pass


def production_order_all_journals_posted(production_order):
    """
    True when this order has at least one item journal and every journal status is Posted.
    Used to finish the order without running manufacturing posting again (already done).
    """
    statuses = set(
        ItemJournal.objects.filter(production_order=production_order).values_list(
            "status", flat=True
        )
    )
    return bool(statuses) and statuses == {Status.Posted.value}


def build_production_posting_preview(production_order):
    """
    Build JSON-serializable preview data for production order posting.
    Used by both the preview page and as input to the poster.
    Returns (preview_data, errors).
    """
    from items.models import ItemJournal

    item_journals = ItemJournal.objects.filter(
        production_order=production_order,
        status=Status.Open.value,
    ).select_related(
        "item",
        "item__inventory_posting_group",
        "item__general_product_posting_group",
        "location_code",
        "journal_template",
        "item_unit_of_measure",
        "item_unit_of_measure__unit_of_measure",
    )

    if not item_journals.exists():
        any_journals = ItemJournal.objects.filter(
            production_order=production_order
        ).exists()
        if any_journals:
            return None, [
                "No open item journals for this order. If journals were already posted, "
                "the production finish step cannot run again. Refresh from BOM to recreate "
                "open journals only if appropriate."
            ]
        return None, [
            "No item journals found. Run 'Update Production Order' (refresh from BOM) first."
        ]

    preview_data = {
        "document_no": production_order.no,
        "gl_entries": [],
        "item_ledger_entries": [],
        "value_entries": [],
        "capacity_ledger_entries": [],
        "inventory_reductions": [],
    }
    errors = []

    for journal in item_journals:
        item = journal.item
        entry_type = journal.entry_type

        if not item.inventory_posting_group or not item.general_product_posting_group:
            errors.append(f"Item '{item.item_name}' is missing required posting groups.")
            continue

        if journal.location_code:
            inventory_posting_setup = InventoryPostingSetup.objects.filter(
                location=journal.location_code,
                inventory_posting_group=item.inventory_posting_group,
            ).first()
        else:
            inventory_posting_setup = InventoryPostingSetup.objects.filter(
                inventory_posting_group=item.inventory_posting_group,
                location__isnull=True,
            ).first()

        if not inventory_posting_setup:
            loc = journal.location_code.code if journal.location_code else "default"
            errors.append(
                f"Inventory Posting Setup not found for location '{loc}' "
                f"and posting group '{item.inventory_posting_group.code}'"
            )
            continue

        if not inventory_posting_setup.wip_account:
            errors.append(
                f"WIP Account not set for Inventory Posting Setup (Group: {item.inventory_posting_group.code})"
            )
            continue

        posting_date = (journal.date or production_order.created_at.date()).isoformat()
        quantity = float(journal.quantity or 0)
        unit_cost = float(journal.unit_cost or 0)
        total_cost = quantity * unit_cost
        uom_code = "PCS"
        qty_per_uom = "1"
        if journal.item_unit_of_measure:
            uom = journal.item_unit_of_measure.unit_of_measure
            uom_code = uom.code if uom else "PCS"
            qty_per_uom = str(journal.item_unit_of_measure.quantity_per_unit or 1)
        description = journal.description or f"{entry_type} for {item.item_name} - {production_order.no}"
        location_id = journal.location_code_id
        item_uom_id = journal.item_unit_of_measure_id
        inv_pg_id = item.inventory_posting_group_id
        gen_pg_id = item.general_product_posting_group_id
        location_code_str = (
            journal.location_code.code if journal.location_code else None
        )

        if entry_type == EntryType.Consumption.name:
            inv_acc = inventory_posting_setup.inventory_account
            wip_acc = inventory_posting_setup.wip_account
            preview_data["gl_entries"].extend([
                {
                    "document_no": production_order.no,
                    "gl_account_no": inv_acc.no,
                    "gl_account": inv_acc.name,
                    "amount": -total_cost,
                    "description": f"Consumption for {item.item_name} - {production_order.no}",
                    "posting_date": posting_date,
                    "entry_type": "Credit",
                    "location_code": location_code_str,
                },
                {
                    "document_no": production_order.no,
                    "gl_account_no": wip_acc.no,
                    "gl_account": wip_acc.name,
                    "amount": total_cost,
                    "description": f"Direct Cost for {item.item_name} - {production_order.no}",
                    "posting_date": posting_date,
                    "entry_type": "Debit",
                    "location_code": location_code_str,
                },
            ])
            preview_data["item_ledger_entries"].append({
                "item_id": item.pk,
                "item_no": item.no,
                "item_name": item.item_name,
                "entry_type": entry_type,
                "quantity": -int(quantity),
                "remaining_quantity": 0,
                "total": -total_cost,
                "unit_cost": unit_cost,
                "cost_amount": -total_cost,
                "unit_of_measure": uom_code,
                "quantity_per_unit_of_measure": qty_per_uom,
                "item_unit_of_measure_id": item_uom_id,
                "location_id": location_id,
                "posting_date": posting_date,
                "description": description,
                "document_no": production_order.no,
            })
            preview_data["value_entries"].append({
                "item_id": item.pk,
                "item_no": item.no,
                "item_name": item.item_name,
                "entry_type": "Direct Cost",
                "item_ledger_entry_quantity": -int(quantity),
                "valued_quantity": -int(quantity),
                "invoiced_quantity": 0,
                "cost_per_unit": unit_cost,
                "cost_amount_actual": -total_cost,
                "cost_amount_expected": -total_cost,
                "posting_date": posting_date,
                "document_no": production_order.no,
                "inventory_posting_group_id": inv_pg_id,
                "general_product_posting_group_id": gen_pg_id,
                "location_id": location_id,
            })
            preview_data["inventory_reductions"].append({
                "item_id": item.pk,
                "quantity": int(quantity),
            })
        elif entry_type == EntryType.Output.name:
            inv_acc = inventory_posting_setup.inventory_account
            wip_acc = inventory_posting_setup.wip_account
            preview_data["gl_entries"].extend([
                {
                    "document_no": production_order.no,
                    "gl_account_no": inv_acc.no,
                    "gl_account": inv_acc.name,
                    "amount": total_cost,
                    "description": f"Output for {item.item_name} - {production_order.no}",
                    "posting_date": posting_date,
                    "entry_type": "Debit",
                    "location_code": location_code_str,
                },
                {
                    "document_no": production_order.no,
                    "gl_account_no": wip_acc.no,
                    "gl_account": wip_acc.name,
                    "amount": -total_cost,
                    "description": f"Output for {item.item_name} - {production_order.no}",
                    "posting_date": posting_date,
                    "entry_type": "Credit",
                    "location_code": location_code_str,
                },
            ])
            preview_data["item_ledger_entries"].append({
                "item_id": item.pk,
                "item_no": item.no,
                "item_name": item.item_name,
                "entry_type": entry_type,
                "quantity": int(quantity),
                "remaining_quantity": int(quantity),
                "total": total_cost,
                "unit_cost": unit_cost,
                "cost_amount": total_cost,
                "unit_of_measure": uom_code,
                "quantity_per_unit_of_measure": qty_per_uom,
                "item_unit_of_measure_id": item_uom_id,
                "location_id": location_id,
                "posting_date": posting_date,
                "description": description,
                "document_no": production_order.no,
            })
            preview_data["value_entries"].append({
                "item_id": item.pk,
                "item_no": item.no,
                "item_name": item.item_name,
                "entry_type": "Direct Cost",
                "item_ledger_entry_quantity": int(quantity),
                "valued_quantity": int(quantity),
                "invoiced_quantity": 0,
                "cost_per_unit": unit_cost,
                "cost_amount_actual": total_cost,
                "cost_amount_expected": total_cost,
                "posting_date": posting_date,
                "document_no": production_order.no,
                "inventory_posting_group_id": inv_pg_id,
                "general_product_posting_group_id": gen_pg_id,
                "location_id": location_id,
            })
            if journal.type == "work_center":
                from production.models import WorkCenter

                cap_uom_id = None
                cap_uom_code = None
                if journal.item_unit_of_measure and journal.item_unit_of_measure.unit_of_measure:
                    cap_uom_id = journal.item_unit_of_measure.unit_of_measure_id
                    cap_uom_code = journal.item_unit_of_measure.unit_of_measure.code
                # CapacityLedgerEntry requires work_center when type=work_center; use first active
                default_wc = WorkCenter.objects.filter(is_active=True).first()
                work_center_id = default_wc.pk if default_wc else None
                preview_data["capacity_ledger_entries"].append({
                    "item_id": item.pk,
                    "item_no": item.no,
                    "item_name": item.item_name,
                    "posting_date": posting_date,
                    "type": "work_center",
                    "no": default_wc.code if default_wc else "N/A",
                    "document_no": production_order.no,
                    "description": f"Output for Production Order {production_order.no} - {item.item_name}",
                    "work_center_id": work_center_id,
                    "work_center": default_wc.name if default_wc else "N/A",
                    "quantity": quantity,
                    "output_quantity": quantity,
                    "cap_unit_of_measure_id": cap_uom_id,
                    "cap_unit_of_measure_code": cap_uom_code,
                    "order_no": production_order.no,
                })

    return preview_data, errors


class ProductionOrderPostingFromPreviewService:
    """
    Posts production order using preview data from the preview page.
    Creates DB records exactly as shown in the preview.
    """

    def __init__(self, production_order, user, preview_data):
        self.production_order = production_order
        self.user = user
        self.preview_data = preview_data
        self.transaction_no = str(uuid.uuid4())
        self.document_no = preview_data["document_no"]

    def post(self):
        """Create G/L, Item Ledger, Value, and Capacity entries from preview data."""
        from items.models import ItemUnitOfMeasure, Location
        from postings.models import InventoryPostingGroup, GeneralProductPostingGroup

        with transaction.atomic():
            # 1. G/L entries
            from dimension.models import (
                DimensionValue,
                get_posting_dimension_payload,
            )

            for e in self.preview_data["gl_entries"]:
                loc_code = e.get("location_code")
                loc_dim = None
                if loc_code:
                    loc_dim = DimensionValue.objects.filter(code=loc_code).first()
                dim_payload = get_posting_dimension_payload(
                    global_dimension_1=loc_dim
                    or getattr(self.user, "global_dimension_1", None)
                )
                gl_account = G_LAccount.objects.get(no=e["gl_account_no"])
                GeneralLedgerEntry.objects.create(
                    gl_account=gl_account,
                    posting_date=e["posting_date"],
                    document_no=self.document_no,
                    description=e["description"],
                    amount=float(e["amount"]),
                    user=self.user,
                    transaction_no=self.transaction_no,
                    dimension_set=dim_payload["dimension_set"],
                    global_dimension_1=dim_payload["global_dimension_1"],
                    global_dimension_2=dim_payload["global_dimension_2"],
                )

            # 2. Item Ledger Entries + Value Entries (paired)
            ile_list = self.preview_data["item_ledger_entries"]
            ve_list = self.preview_data["value_entries"]
            for ile_data, ve_data in zip(ile_list, ve_list):
                item = Item.objects.get(pk=ile_data["item_id"])
                loc = None
                if ile_data.get("location_id"):
                    loc = Location.objects.filter(pk=ile_data["location_id"]).first()
                item_uom = None
                if ile_data.get("item_unit_of_measure_id"):
                    item_uom = ItemUnitOfMeasure.objects.filter(
                        pk=ile_data["item_unit_of_measure_id"]
                    ).first()

                loc_dim = None
                if loc:
                    loc_dim = DimensionValue.objects.filter(code=loc.code).first()
                dim_payload = get_posting_dimension_payload(
                    global_dimension_1=loc_dim
                    or getattr(self.user, "global_dimension_1", None)
                )

                ile = ItemLedgerEntries.objects.create(
                    item=item,
                    entry_type=ile_data["entry_type"],
                    document_no=ile_data["document_no"],
                    description=ile_data["description"],
                    quantity=ile_data["quantity"],
                    remaining_quantity=ile_data["remaining_quantity"],
                    total=float(ile_data["total"]),
                    unit_of_measure=ile_data["unit_of_measure"],
                    quantity_per_unit_of_measure=ile_data["quantity_per_unit_of_measure"],
                    unit_of_measure_code=item_uom,
                    date=ile_data["posting_date"],
                    user=self.user,
                    location=loc,
                    transaction_no=self.transaction_no,
                    posting_date=ile_data["posting_date"],
                    dimension_set=dim_payload["dimension_set"],
                    global_dimension_1=dim_payload["global_dimension_1"],
                    global_dimension_2=dim_payload["global_dimension_2"],
                )

                inv_pg = InventoryPostingGroup.objects.get(pk=ve_data["inventory_posting_group_id"])
                gen_pg = GeneralProductPostingGroup.objects.get(pk=ve_data["general_product_posting_group_id"])
                ve_loc = None
                if ve_data.get("location_id"):
                    ve_loc = Location.objects.filter(pk=ve_data["location_id"]).first()

                ValueEntry.objects.create(
                    item=item,
                    entry_type=ve_data["entry_type"],
                    document_no=ve_data["document_no"],
                    description=ile.description,
                    item_ledger_entry_no=ile,
                    cost_amount=str(int(ve_data["cost_amount_actual"])),
                    sales_amount="0",
                    cost_per_unit=round(float(ve_data["cost_per_unit"]), 2),
                    item_ledger_entry_quantity=ve_data["item_ledger_entry_quantity"],
                    valued_quantity=ve_data["valued_quantity"],
                    invoiced_quantity=ve_data.get("invoiced_quantity", 0),
                    inventory_posting_group=inv_pg,
                    general_product_posting_group=gen_pg,
                    posting_date=ve_data["posting_date"],
                    location_code=ve_loc,
                    transaction_no=self.transaction_no,
                    dimension_set=dim_payload["dimension_set"],
                    global_dimension_1=dim_payload["global_dimension_1"],
                    global_dimension_2=dim_payload["global_dimension_2"],
                )

            # 3. Inventory reduction (FIFO) for consumption
            for red in self.preview_data.get("inventory_reductions", []):
                self._reduce_inventory(
                    Item.objects.get(pk=red["item_id"]),
                    red["quantity"],
                )

            # 4. Capacity Ledger Entries (optional: only when an active Work Center exists)
            from production.models import WorkCenter

            default_work_center = WorkCenter.objects.filter(is_active=True).first()

            for cap in self.preview_data.get("capacity_ledger_entries", []):
                work_center = None
                wc_id = cap.get("work_center_id")
                if wc_id is not None and wc_id != "":
                    try:
                        pk = int(wc_id) if not isinstance(wc_id, int) else wc_id
                        work_center = WorkCenter.objects.filter(pk=pk).first()
                    except (TypeError, ValueError):
                        pass
                if not work_center:
                    work_center = default_work_center
                if not work_center:
                    # No active Work Center: skip capacity entry; posting still succeeds
                    continue

                item = Item.objects.get(pk=cap["item_id"])
                cap_uom = None
                if cap.get("cap_unit_of_measure_id"):
                    from items.models import UnitOfMeasure
                    cap_uom = UnitOfMeasure.objects.filter(
                        pk=cap["cap_unit_of_measure_id"]
                    ).first()
                CapacityLedgerEntry.objects.create(
                    no=work_center.code,
                    posting_date=cap["posting_date"],
                    type="work_center",
                    document_no=cap["document_no"],
                    description=cap["description"],
                    work_center=work_center,
                    quantity=Decimal(str(cap["quantity"])),
                    setup_time=Decimal("0"),
                    run_time=Decimal("0"),
                    stop_time=Decimal("0"),
                    output_quantity=Decimal(str(cap["output_quantity"])),
                    cap_unit_of_measure_code=cap_uom,
                    item_no=item,
                    order_type="production",
                    order_no=self.production_order,
                )

            # 5. Mark journals as posted
            ItemJournal.objects.filter(
                production_order=self.production_order
            ).update(status=Status.Posted.value)

    def _reduce_inventory(self, item, quantity_to_reduce):
        remaining = int(quantity_to_reduce)
        if remaining <= 0:
            return
        entries = ItemLedgerEntries.objects.filter(
            item=item,
            remaining_quantity__gt=0,
        ).order_by("created_at")
        for entry in entries:
            if remaining <= 0:
                break
            reduction = min(entry.remaining_quantity, remaining)
            entry.remaining_quantity -= reduction
            entry.save(update_fields=["remaining_quantity"])
            remaining -= reduction
        if remaining > 0:
            raise ProductionOrderPostingError(
                f"Not enough inventory for item '{item.item_name}'. Still need {remaining} more units."
            )


class ProductionOrderPostingService:
    """
    Posts all item journals for a production order.
    Creates G/L entries, Item Ledger Entries, Value Entries, and Capacity Ledger Entries.
    """

    def __init__(self, production_order, user):
        self.production_order = production_order
        self.user = user
        self.transaction_no = str(uuid.uuid4())
        self.document_no = production_order.no

    def post(self):
        """
        Post all item journals for the production order.
        Raises ProductionOrderPostingError on validation failure.
        """
        item_journals = ItemJournal.objects.filter(
            production_order=self.production_order
        ).select_related(
            "item",
            "item__inventory_posting_group",
            "item__general_product_posting_group",
            "location_code",
            "journal_template",
            "item_unit_of_measure",
        )

        if not item_journals.exists():
            raise ProductionOrderPostingError(
                "No item journals found. Please run 'Update Production Details' first."
            )

        with transaction.atomic():
            for journal in item_journals:
                self._post_journal(journal)

            # Mark all journals as posted
            item_journals.update(status=Status.Posted.value)

    def _post_journal(self, journal):
        """Post a single item journal (Consumption or Output)."""
        item = journal.item
        entry_type = journal.entry_type

        if not item.inventory_posting_group or not item.general_product_posting_group:
            raise ProductionOrderPostingError(
                f"Item '{item.item_name}' is missing required posting groups."
            )

        inventory_posting_setup = self._get_inventory_posting_setup(journal, item)
        if not inventory_posting_setup:
            location_info = (
                journal.location_code.code if journal.location_code else "default"
            )
            raise ProductionOrderPostingError(
                f"Inventory Posting Setup not found for location '{location_info}' "
                f"and posting group '{item.inventory_posting_group.code}'"
            )

        general_posting_setup = GeneralPostingSetup.objects.filter(
            general_product_posting_group=item.general_product_posting_group,
        ).first()
        if not general_posting_setup:
            raise ProductionOrderPostingError(
                f"General Posting Setup not found for "
                f"'{item.general_product_posting_group.code}'"
            )

        quantity = int(journal.quantity or 0)
        unit_cost = float(journal.unit_cost or 0)
        total_cost = quantity * unit_cost
        posting_date = journal.date or self.production_order.created_at.date()

        if entry_type == EntryType.Consumption.name:
            self._post_consumption(
                journal,
                item,
                inventory_posting_setup,
                quantity,
                unit_cost,
                total_cost,
                posting_date,
            )
        elif entry_type == EntryType.Output.name:
            self._post_output(
                journal,
                item,
                inventory_posting_setup,
                quantity,
                unit_cost,
                total_cost,
                posting_date,
            )
        else:
            raise ProductionOrderPostingError(f"Unsupported entry type: {entry_type}")

    def _get_inventory_posting_setup(self, journal, item):
        """Get InventoryPostingSetup for the journal's location and item."""
        if journal.location_code:
            return InventoryPostingSetup.objects.filter(
                location=journal.location_code,
                inventory_posting_group=item.inventory_posting_group,
            ).first()
        return InventoryPostingSetup.objects.filter(
            inventory_posting_group=item.inventory_posting_group,
            location__isnull=True,
        ).first()

    def _dim_payload_for_journal(self, journal):
        from dimension.models import DimensionValue, get_posting_dimension_payload

        loc_dim = None
        if journal and journal.location_code_id:
            loc_dim = DimensionValue.objects.filter(
                code=journal.location_code.code
            ).first()
        return get_posting_dimension_payload(
            global_dimension_1=loc_dim
            or getattr(self.user, "global_dimension_1", None)
        )

    def _post_consumption(
        self,
        journal,
        item,
        inventory_posting_setup,
        quantity,
        unit_cost,
        total_cost,
        posting_date,
    ):
        """Post consumption: Credit Inventory, Debit WIP."""
        inventory_account = inventory_posting_setup.inventory_account
        wip_account = inventory_posting_setup.wip_account
        if not wip_account:
            raise ProductionOrderPostingError(
                "WIP Account not set for Inventory Posting Setup."
            )

        # G/L: Credit Inventory
        self._create_gl_entry(
            gl_account_no=inventory_account.no,
            amount=-total_cost,
            description=f"Consumption for {item.item_name} - {self.document_no}",
            posting_date=posting_date,
            journal=journal,
        )
        # G/L: Debit WIP
        self._create_gl_entry(
            gl_account_no=wip_account.no,
            amount=total_cost,
            description=f"Direct Cost for {item.item_name} - {self.document_no}",
            posting_date=posting_date,
            journal=journal,
        )

        # Item Ledger Entry (negative)
        qty_int = -quantity
        remaining = 0
        total = -total_cost
        ile = self._create_item_ledger_entry(
            journal,
            item,
            EntryType.Consumption.name,
            qty_int,
            remaining,
            total,
            posting_date,
        )

        # Value Entry
        self._create_value_entry(
            journal,
            item,
            ile,
            "Direct Cost",
            -quantity,
            -total_cost,
            unit_cost,
            posting_date,
        )

        # Reduce inventory (FIFO)
        self._reduce_inventory(item, quantity)

    def _post_output(
        self,
        journal,
        item,
        inventory_posting_setup,
        quantity,
        unit_cost,
        total_cost,
        posting_date,
    ):
        """Post output: Debit Inventory, Credit WIP."""
        inventory_account = inventory_posting_setup.inventory_account
        wip_account = inventory_posting_setup.wip_account
        if not wip_account:
            raise ProductionOrderPostingError(
                "WIP Account not set for Inventory Posting Setup."
            )

        # G/L: Debit Inventory
        self._create_gl_entry(
            gl_account_no=inventory_account.no,
            amount=total_cost,
            description=f"Output for {item.item_name} - {self.document_no}",
            posting_date=posting_date,
            journal=journal,
        )
        # G/L: Credit WIP
        self._create_gl_entry(
            gl_account_no=wip_account.no,
            amount=-total_cost,
            description=f"Output for {item.item_name} - {self.document_no}",
            posting_date=posting_date,
            journal=journal,
        )

        # Item Ledger Entry (positive)
        remaining = quantity
        total = total_cost
        ile = self._create_item_ledger_entry(
            journal,
            item,
            EntryType.Output.name,
            quantity,
            remaining,
            total,
            posting_date,
        )

        # Value Entry
        self._create_value_entry(
            journal,
            item,
            ile,
            "Direct Cost",
            quantity,
            total_cost,
            unit_cost,
            posting_date,
        )

        # Capacity Ledger Entry (for work_center output)
        if journal.type == "work_center":
            self._create_capacity_ledger_entry(journal, item, quantity, posting_date)

    def _create_gl_entry(
        self, gl_account_no, amount, description, posting_date, journal=None
    ):
        """Create a General Ledger Entry."""
        from dimension.models import DimensionValue, get_posting_dimension_payload

        loc_dim = None
        if journal and journal.location_code_id:
            loc_dim = DimensionValue.objects.filter(
                code=journal.location_code.code
            ).first()
        dim_payload = get_posting_dimension_payload(
            global_dimension_1=loc_dim
            or getattr(self.user, "global_dimension_1", None)
        )
        gl_account = G_LAccount.objects.get(no=gl_account_no)
        GeneralLedgerEntry.objects.create(
            gl_account=gl_account,
            posting_date=posting_date,
            document_no=self.document_no,
            description=description,
            amount=float(amount),
            user=self.user,
            transaction_no=self.transaction_no,
            dimension_set=dim_payload["dimension_set"],
            global_dimension_1=dim_payload["global_dimension_1"],
            global_dimension_2=dim_payload["global_dimension_2"],
        )

    def _create_item_ledger_entry(
        self,
        journal,
        item,
        entry_type,
        quantity,
        remaining_quantity,
        total,
        posting_date,
    ):
        """Create an Item Ledger Entry. Returns the created instance."""
        unit_of_measure = "PCS"
        quantity_per_unit = "1"
        if journal.item_unit_of_measure:
            unit_of_measure = journal.item_unit_of_measure.unit_of_measure.code
            quantity_per_unit = str(journal.item_unit_of_measure.quantity_per_unit or 1)

        description = (
            journal.description
            or f"{entry_type} for {item.item_name} - {self.document_no}"
        )

        dim_payload = self._dim_payload_for_journal(journal)
        return ItemLedgerEntries.objects.create(
            item=item,
            entry_type=entry_type,
            document_no=self.document_no,
            description=description,
            quantity=int(quantity),
            remaining_quantity=max(0, int(remaining_quantity)),
            total=float(total),
            unit_of_measure=unit_of_measure,
            quantity_per_unit_of_measure=quantity_per_unit,
            unit_of_measure_code=journal.item_unit_of_measure,
            date=posting_date,
            user=self.user,
            location=journal.location_code,
            transaction_no=self.transaction_no,
            posting_date=posting_date,
            dimension_set=dim_payload["dimension_set"],
            global_dimension_1=dim_payload["global_dimension_1"],
            global_dimension_2=dim_payload["global_dimension_2"],
        )

    def _create_value_entry(
        self,
        journal,
        item,
        item_ledger_entry,
        entry_type,
        item_ledger_entry_quantity,
        cost_amount,
        cost_per_unit,
        posting_date,
    ):
        """Create a Value Entry."""
        inv_pg = item.inventory_posting_group
        gen_pg = item.general_product_posting_group

        cost_per_unit_value = round(float(cost_per_unit), 2) if cost_per_unit else 0.0
        qty_int = int(item_ledger_entry_quantity)

        dim_payload = self._dim_payload_for_journal(journal)
        ValueEntry.objects.create(
            item=item,
            entry_type=entry_type,
            document_no=self.document_no,
            description=item_ledger_entry.description,
            item_ledger_entry_no=item_ledger_entry,
            cost_amount=str(cost_amount),
            sales_amount="0",
            cost_per_unit=cost_per_unit_value,
            item_ledger_entry_quantity=qty_int,
            valued_quantity=qty_int,
            invoiced_quantity=0,
            inventory_posting_group=inv_pg,
            general_product_posting_group=gen_pg,
            posting_date=posting_date,
            location_code=journal.location_code,
            transaction_no=self.transaction_no,
            dimension_set=dim_payload["dimension_set"],
            global_dimension_1=dim_payload["global_dimension_1"],
            global_dimension_2=dim_payload["global_dimension_2"],
        )

    def _create_capacity_ledger_entry(self, journal, item, quantity, posting_date):
        """Create a Capacity Ledger Entry for output when an active Work Center exists; otherwise skip."""
        from production.models import WorkCenter

        work_center = WorkCenter.objects.filter(is_active=True).first()
        if not work_center:
            return

        cap_uom = None
        if (
            journal.item_unit_of_measure
            and journal.item_unit_of_measure.unit_of_measure
        ):
            cap_uom = journal.item_unit_of_measure.unit_of_measure

        CapacityLedgerEntry.objects.create(
            no=work_center.code,
            posting_date=posting_date,
            type="work_center",
            document_no=self.document_no,
            description=f"Output for Production Order {self.document_no} - {item.item_name}",
            work_center=work_center,
            quantity=Decimal(str(quantity)),
            setup_time=Decimal("0"),
            run_time=Decimal("0"),
            stop_time=Decimal("0"),
            output_quantity=Decimal(str(quantity)),
            cap_unit_of_measure_code=cap_uom,
            item_no=item,
            order_type="production",
            order_no=self.production_order,
        )

    def _reduce_inventory(self, item, quantity_to_reduce):
        """
        Reduce inventory using FIFO (First In, First Out).
        Decreases remaining_quantity on existing positive entries.
        """
        from items.models import ItemLedgerEntries

        remaining = int(quantity_to_reduce)
        if remaining <= 0:
            return

        entries = ItemLedgerEntries.objects.filter(
            item=item,
            remaining_quantity__gt=0,
        ).order_by("created_at")

        for entry in entries:
            if remaining <= 0:
                break
            reduction = min(entry.remaining_quantity, remaining)
            entry.remaining_quantity -= reduction
            entry.save(update_fields=["remaining_quantity"])
            remaining -= reduction

        if remaining > 0:
            raise ProductionOrderPostingError(
                f"Not enough inventory for item '{item.item_name}'. "
                f"Still need {remaining} more units."
            )
