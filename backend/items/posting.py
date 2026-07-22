from items.models import (
    ItemJournal,
    ItemLedgerEntries,
    ValueEntry,
    Location,
    PhysInventoryLedgerEntry,
    TrackingSpecification,
)
from postings.models import GeneralProductPostingGroup, InventoryPostingGroup
from financials.models import GeneralLedgerEntry, G_LAccount
from sales.models import PaymentMethod, CustomerLedgerEntry, Customer
from items.enums import EntryType
from common.enums import Status


class ItemJournalFinalPoster:
    def __init__(self, preview_data, journal_entry, user):
        self.preview_data = preview_data
        self.journal_entry = journal_entry
        self.user = user

    def post_to_tables(self):
        # 1. Insert General Ledger Entries
        from dimension.models import get_posting_dimension_payload

        for entry in self.preview_data.get("gl_entries", []):
            dim_payload = get_posting_dimension_payload(
                global_dimension_1=entry.get("global_dimension_1"),
                dimension_set=entry.get("dimension_set"),
            )
            GeneralLedgerEntry.objects.create(
                posting_date=entry.get("posting_date"),
                document_type=entry.get("document_type"),
                document_no=entry.get("document_no"),
                gl_account=G_LAccount.objects.get(
                    name=entry.get("gl_account")
                ),  # <-- FIXED
                description=entry.get("description"),
                amount=entry.get("amount"),
                balancing_account_type=entry.get("balancing_account_type"),
                transaction_no=entry.get("transaction_no"),
                dimension_set=dim_payload["dimension_set"],
                global_dimension_1=dim_payload["global_dimension_1"],
                global_dimension_2=dim_payload["global_dimension_2"],
                user=self.user,
                # Add other fields as needed
            )

        # 2. Insert Item Ledger Entries
        ledger_entry_map = {}
        for i, entry in enumerate(self.preview_data.get("item_entries", [])):
            ile_dim = get_posting_dimension_payload(
                global_dimension_1=entry.get("global_dimension_1"),
                dimension_set=entry.get("dimension_set"),
            )
            item_ledger_entry = ItemLedgerEntries.objects.create(
                item=self.journal_entry.item,  # Use FK from journal entry
                entry_type=entry.get("entry_type"),
                posting_date=entry.get("posting_date") or entry.get("date"),
                document_no=entry.get("document_no"),
                description=entry.get("description"),
                quantity=entry.get("quantity"),
                remaining_quantity=entry.get("remaining_quantity"),
                # unit_cost=entry.get("unit_cost"),
                total=entry.get("total"),
                unit_of_measure=self.journal_entry.item_unit_of_measure.unit_of_measure.code,
                transaction_no=entry.get("transaction_no"),
                date=entry.get("date"),
                user=self.user,
                global_dimension_1=ile_dim["global_dimension_1"],
                dimension_set=ile_dim["dimension_set"],
                sales_amount=entry.get("sales_amount"),
                location=self.journal_entry.location_code,
                unit_of_measure_code=self.journal_entry.item_unit_of_measure,
                quantity_per_unit_of_measure=str(
                    self.journal_entry.item_unit_of_measure.quantity_per_unit
                ),
                lot_no=entry.get("lot_no"),
                expiry_date=entry.get("expiry_date"),
                serial_no=entry.get("serial_no"),
                # Add other fields as needed
            )

            # Use simple index-based mapping for consistency with value entries
            map_key = f"{entry['document_no']}_{i}"
            ledger_entry_map[map_key] = item_ledger_entry

        # 3. Insert Physical Inventory Ledger Entries (for phys. inventory journals)
        for entry in self.preview_data.get("phys_inventory_entries", []):
            # Get the corresponding item ledger entry (first one in the map for this document)
            item_ledger_entry = next(
                (ile for ile in ledger_entry_map.values() 
                 if ile.document_no == entry.get("document_no")),
                None
            )
            
            PhysInventoryLedgerEntry.objects.create(
                document_no=entry.get("document_no"),
                posting_date=entry.get("posting_date"),
                item=self.journal_entry.item,
                item_no=self.journal_entry.item.no,
                description=entry.get("description"),
                location_code=self.journal_entry.location_code,
                qty_expected=entry.get("qty_expected"),
                qty_phys_inventory=entry.get("qty_phys_inventory"),
                quantity=entry.get("quantity"),
                entry_type=entry.get("entry_type"),
                unit_of_measure=self.journal_entry.item_unit_of_measure,
                unit_amount=entry.get("unit_amount"),
                unit_cost=entry.get("unit_cost"),
                user=self.user,
                item_ledger_entry=item_ledger_entry,
                journal_batch=self.journal_entry.journal_batch,
            )

        # 4. Insert Value Entries
        for i, entry in enumerate(self.preview_data.get("value_entries", [])):
            # For value entries, we need to match them with item ledger entries by index
            # since they don't have lot_no/expiry_date in their structure
            map_key = f"{entry['document_no']}_{i}"

            item_ledger_entry = ledger_entry_map[map_key]
            ve_dim = get_posting_dimension_payload(
                global_dimension_1=entry.get("global_dimension_1"),
                global_dimension_2=entry.get("global_dimension_2"),
                dimension_set=entry.get("dimension_set"),
            )
            sales_raw = entry.get("sales_amount")
            sales_amount = (
                str(sales_raw) if sales_raw is not None and sales_raw != "" else "0"
            )
            description = (
                entry.get("description")
                or self.journal_entry.description
                or ""
            )
            entry_type = entry.get("entry_type") or ""
            from items.value_entry_posting import bc_normalize_value_entry_fields

            ve_signs = bc_normalize_value_entry_fields(
                entry_type,
                entry.get("item_ledger_entry_quantity"),
                entry.get("cost_amount"),
                cost_per_unit=entry.get("cost_per_unit"),
            )

            ValueEntry.objects.create(
                item=self.journal_entry.item,  # Use FK from journal entry
                entry_type=entry_type,
                document_no=entry.get("document_no"),
                description=description,
                cost_amount=ve_signs["cost_amount"],
                sales_amount=sales_amount,
                cost_per_unit=ve_signs["cost_per_unit"],
                item_ledger_entry_quantity=ve_signs["item_ledger_entry_quantity"],
                invoiced_quantity=ve_signs["invoiced_quantity"],
                general_product_posting_group=GeneralProductPostingGroup.objects.get(
                    code=entry.get("general_product_posting_group")
                ),
                inventory_posting_group=InventoryPostingGroup.objects.get(
                    code=entry.get("inventory_posting_group")
                ),
                transaction_no=entry.get("transaction_no"),
                posting_date=entry.get("posting_date"),
                valued_quantity=ve_signs["valued_quantity"],
                item_ledger_entry_no=item_ledger_entry,
                location_code=self.journal_entry.location_code,
                global_dimension_1=ve_dim["global_dimension_1"],
                dimension_set=ve_dim["dimension_set"],
            )

        # 5. Insert Customer Ledger Entries (if you have this model)
        for entry in self.preview_data.get("customer_entries", []):
            CustomerLedgerEntry.objects.create(
                customer=Customer.objects.get(name=entry.get("customer")),
                document_no=entry.get("document_no"),
                document_type=entry.get("document_type"),
                posting_date=entry.get("posting_date"),
                document_date=entry.get("document_date"),
                description=entry.get("description"),
                amount=entry.get("amount"),
                remaining_amount=entry.get("remaining_amount"),
                due_date=entry.get("due_date"),
                payment_method=PaymentMethod.objects.get(
                    name=entry.get("payment_method")
                ),
                transaction_no=entry.get("transaction_no"),
                user=self.user,
                # Add other fields as needed
            )

        # 6. Reduce inventory for sales, negative adjustments, and production consumption
        if self.journal_entry.entry_type in [
            EntryType.Sales.name,
            EntryType.NegativeAdjustment.name,
            EntryType.Consumption.name,
        ]:
            self._reduce_inventory()

        # 7. Update the status of the journal entry to 'Posted'
        self.journal_entry.status = Status.Posted.value
        self.journal_entry.save(update_fields=["status"])

        return True

    def _reduce_inventory(self):
        """Reduce inventory based on FIFO method (First In, First Out).

        This method reduces the remaining_quantity of existing inventory entries
        for sales and negative adjustment transactions.
        """
        if (
            self.journal_entry.entry_type == EntryType.NegativeAdjustment.name
            and self.journal_entry.item_id
        ):
            tracking_specs = TrackingSpecification.objects.filter(
                item_journal=self.journal_entry
            ).order_by("expiry_date", "id")
            from django.db.models import Q

            has_tracking = tracking_specs.filter(
                (Q(lot_no__isnull=False) & ~Q(lot_no=""))
                | (Q(serial_no__isnull=False) & ~Q(serial_no=""))
            ).exists()
            if has_tracking:
                self._reduce_inventory_from_tracking_specs(tracking_specs)
                return

        self._reduce_inventory_fifo()

    def _reduce_inventory_from_tracking_specs(self, tracking_specs):
        """Reduce remaining qty from selected lots/serials for tracked negative adjustments."""
        total_reduced = 0
        for spec in tracking_specs:
            lot_no = (spec.lot_no or "").strip()
            serial_no = (spec.serial_no or "").strip()
            qty_for_spec = int(spec.quantity_base or 0)
            if qty_for_spec <= 0:
                continue
            if not lot_no and not serial_no:
                continue

            remaining_for_spec = qty_for_spec
            entries = ItemLedgerEntries.objects.filter(
                item=self.journal_entry.item,
                remaining_quantity__gt=0,
            )
            if serial_no:
                entries = entries.filter(serial_no__iexact=serial_no)
            if lot_no:
                entries = entries.filter(lot_no=lot_no)
            if self.journal_entry.location_code_id:
                entries = entries.filter(
                    location_id=self.journal_entry.location_code_id
                )
            if self.journal_entry.global_dimension_1_id:
                entries = entries.filter(
                    global_dimension_1_id=self.journal_entry.global_dimension_1_id
                )
            entries = entries.order_by("expiry_date", "created_at")

            for entry in entries:
                if remaining_for_spec <= 0:
                    break
                reduction = min(entry.remaining_quantity, remaining_for_spec)
                entry.remaining_quantity -= reduction
                entry.save(update_fields=["remaining_quantity", "updated_at"])
                remaining_for_spec -= reduction
                total_reduced += reduction

            if remaining_for_spec > 0:
                label = f"Serial '{serial_no}'" if serial_no else f"Lot '{lot_no}'"
                raise Exception(
                    f"{label} has insufficient inventory for negative adjustment. "
                    f"Missing {remaining_for_spec} base units."
                )

        # Calculate the actual quantity based on unit of measure conversion
        from items.models import ItemUnitOfMeasure

        item_unit_of_measure = ItemUnitOfMeasure.objects.get(
            id=self.journal_entry.item_unit_of_measure.id
        )
        quantity_to_reduce = int(item_unit_of_measure.quantity_per_unit) * int(
            self.journal_entry.quantity
        )
        if total_reduced != quantity_to_reduce:
            raise Exception(
                "Tracking quantities do not match journal quantity for negative adjustment. "
                f"Expected {quantity_to_reduce}, reduced {total_reduced}."
            )

    def _reduce_inventory_fifo(self):
        """Fallback FIFO inventory reduction for non-tracked flows."""
        # Calculate the actual quantity based on unit of measure conversion
        from items.models import ItemUnitOfMeasure

        item_unit_of_measure = ItemUnitOfMeasure.objects.get(
            id=self.journal_entry.item_unit_of_measure.id
        )
        quantity_to_reduce = int(item_unit_of_measure.quantity_per_unit) * int(
            self.journal_entry.quantity
        )

        remaining = quantity_to_reduce
        entries = ItemLedgerEntries.objects.filter(
            item=self.journal_entry.item, remaining_quantity__gt=0
        ).order_by("created_at")

        # Process each inventory entry
        for entry in entries:
            if remaining <= 0:
                break

            # Calculate how much to reduce from this entry
            reduction = min(entry.remaining_quantity, remaining)
            entry.remaining_quantity -= reduction
            entry.save()

            # Update how much more we still need to reduce
            remaining -= reduction

        # If we still have quantity to reduce but no more inventory
        if remaining > 0:
            # You might want to log this warning or raise an exception
            raise Exception(
                f"Warning: Not enough inventory to fulfill the {self.journal_entry.entry_type} "
                f"for {self.journal_entry.item.item_name}. Still need {remaining} more units."
            )
