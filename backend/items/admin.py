import uuid

from django.utils import timezone
from django.contrib import admin
from django.db import transaction, models
from django.contrib import messages
from mptt.admin import MPTTModelAdmin
from django.urls import path, reverse
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.template.response import TemplateResponse
from django.contrib.admin import helpers
from django.contrib.humanize.templatetags.humanize import intcomma
from django.core.exceptions import ValidationError

from authentication.models import CustomUser as User, UserSetup


from sales.models import Customer, CustomerLedgerEntry
from financials.models import PaymentMethod
from items.models import (
    Item,
    ItemAttribute,
    ItemAttributeEntry,
    ItemAttributeValue,
    UnitOfMeasure,
    ItemCategory,
    ItemImages,
    ItemJournal,
    ItemLedgerEntries,
    ValueEntry,
    ItemUnitOfMeasure,
    ItemTrackingCodes,
    TrackingSpecification,
    Location,
    ItemJournalTemplate,
    ItemJournalBatch,
    PhysInventoryLedgerEntry,
)
from postings.models import (
    GeneralPostingSetup,
    InventoryPostingSetup,
    InventoryPostingGroup,
    GeneralProductPostingGroup,
)
from financials.models import GeneralLedgerEntry, G_LAccount
from dimension.admin_mixin import DefaultDimensionAdminMixin

from financials.enums import BalacingAccountType, GeneralPostingType
from items.enums import EntryType
from items.enums import CostingMethod
from common.enums import Status
from financials.enums import DOCUMENT_TYPE
from sales.enums import CustomerType
from items.forms import ItemJournalForm
from items.posting import ItemJournalFinalPoster


class ItemJournalProccess:
    def __init__(self, journalentry, request, receipt_no=None):
        self.journalentry = journalentry
        self.request = request
        self.receipt_no = receipt_no
        self.entry_processors = {
            EntryType.Purchase.name: self._process_purchase,
            EntryType.Sales.name: self._process_sales,
            EntryType.PositiveAdjustment.name: self._process_positive_adjustment,
            EntryType.NegativeAdjustment.name: self._process_negative_adjustment,
        }

    def process(self):
        print("journal entry type")
        print(self.journalentry.entry_type)
        print(self.entry_processors)
        processor = self.entry_processors.get(self.journalentry.entry_type)
        if processor:
            processor()
        self._delete_journal_entry()

    def _create_ledger_entry(self, **additional_fields):
        base_fields = {
            "item": self.journalentry.item,
            "entry_type": self.journalentry.entry_type,
            "document_no": self.journalentry.document_no,
            "description": self.journalentry.description,
            "unit_of_measure": self.journalentry.unit_of_measure,
            "unit_cost": self.journalentry.unit_cost,
            "date": self.journalentry.date,
            "posting_date": self.journalentry.date,
            "user": self.journalentry.user,
            "receipt_no": self.receipt_no,
        }
        base_fields.update(**additional_fields)
        return ItemLedgerEntries.objects.create(**base_fields)

    def _process_positive_adjustment(self):
        """Handle positive adjustment entries."""
        self._create_ledger_entry(
            quantity=self.journalentry.quantity,
            remaining_quantity=self.journalentry.quantity,
            total=self.journalentry.total,
        )

    def _process_negative_adjustment(self):
        self._create_ledger_entry(
            quantity=-self.journalentry.quantity,
            remaining_quantity=0,
            total=-self.journalentry.total,
        )
        self._reduce_inventory(self.journalentry.quantity, self.journalentry.entry_type)

    def _process_sales(self):
        pass

    def _process_purchase(self):
        pass

    def _reduce_inventory(self, quantity_to_reduce, entry_type):
        """Reduce inventory based on FIFO method (First In, First Out)"""

        # Initialize how much we need to reduce
        remaining = quantity_to_reduce
        entries = ItemLedgerEntries.objects.filter(
            item=self.journalentry.item, remaining_quantity__gt=0
        ).order_by("created_at")

        # Process each inventory entry
        for entry in entries:
            if remaining <= 0:
                break
            # Example:
            # Entry has 10 items remaining
            # We need to reduce 3 items
            # reduction = min(10, 3) = 3
            reduction = min(entry.remaining_quantity, remaining)
            entry.remaining_quantity -= reduction
            entry.save()

            # update how much more we stil need to reduce
            remaining -= reduction

        # If we still have quantity to reduce but no more inventory
        if remaining > 0:
            messages.warning(
                self.request,
                f"Warning: Not enough inventory to fulfill the {entry_type} for {self.item.item}",
            )

    def _validate_sales_entry(self):
        """Validate required fields for sales entries."""
        if self.item.unit_amount is None or self.item.amount is None:
            messages.error(
                self.request, "Unit amount and amount are required for sales entries"
            )
            return False
        return True

    def _delete_journal_entry(self):
        ItemJournal.objects.filter(id=self.journalentry.id).delete()


class ItemJournalProccessRefactor:
    """Handles the processing of item journal entries with support for different entry types.

    This class manages the creation of ledger entries, value entries, and inventory adjustments
    for various types of item transactions.
    """

    def __init__(self, journal_entry, request, receipt_no=None):
        """Initialize the processor with required parameters.

        Args:
            journal_entry: The journal entry to process
            request: The current HTTP request
            receipt_no: Optional receipt number for the transaction
        """
        self.journal_entry = journal_entry
        self.request = request
        self.receipt_no = receipt_no
        self.global_dimension_1_value = getattr(request.user, "global_dimension_1", None)
        self.entry_processors = {
            EntryType.PositiveAdjustment.name: self._process_positive_adjustment,
            EntryType.NegativeAdjustment.name: self._process_negative_adjustment,
            EntryType.Sales.name: self._process_sales,
            EntryType.Purchase.name: self._process_purchase,
        }

    def _validate(self):
        """
        if item has item tracking code, then it should have tracking specification
        """
        item = self.journal_entry.item
        item_tracking_specification_count = TrackingSpecification.objects.filter(
            item_journal=self.journal_entry.id,
            item=item,
        ).count()

        # if item_tracking_specification_count > 0:
        #     if item_tracking_specification_count != self.journal_entry.quantity:
        #         messages.error(
        #             self.request,
        #             f"Item tracking code count {item_tracking_specification_count} is not equal to the quantity {self.journal_entry.quantity}",
        #         )
        #         return False
        """
           check if. item jouranl unit of measeure (quantity per unit) * quantity is shoulde be equal to the count of  item tracking specification
        """
        try:
            item_unit_of_measure = ItemUnitOfMeasure.objects.get(
                id=self.journal_entry.item_unit_of_measure.id
            )
        except ItemUnitOfMeasure.DoesNotExist:
            messages.error(
                self.request,
                f"Unit of measure not found for document {self.journal_entry.document_no}",
            )
            return False

        if self.journal_entry.entry_type == EntryType.Purchase.name:
            if (
                int(item_unit_of_measure.quantity_per_unit)
                * int(self.journal_entry.quantity)
            ) != item_tracking_specification_count:
                messages.error(
                    self.request,
                    f"Item tracking specification  for document {self.journal_entry.document_no} has count {item_tracking_specification_count} is not equal to the quantity { int(self.journal_entry.quantity)  * int(item_unit_of_measure.quantity_per_unit) }",
                )
                return False

        if self.journal_entry.unit_amount == 0 or self.journal_entry.quantity == 0:
            messages.error(
                self.request,
                f"Unit amount and quantity cannot be zero for document {self.journal_entry.document_no}",
            )
            return False

        print(self.journal_entry.description)
        print(len(self.journal_entry.description))
        if len(self.journal_entry.description) == 0:
            print("description is empty")
            messages.error(
                self.request,
                f"Description is required for document {self.journal_entry.document_no}",
            )
            return False

        return True

    def process(self):
        """Process the journal entry based on its type."""

        processor = self.entry_processors.get(self.journal_entry.entry_type)
        if processor:
            if not self._validate():
                print("not validasdfaaaaaaaaaaaaaaaaaaaaaaaaaa")
                return
            processor()
        # self._delete_journal_entry()

    def _process_positive_adjustment(self):
        """Handle positive adjustment entries by creating necessary ledger and value entries."""
        self._create_general_ledger_entries()
        item_ledger_entries = self._create_item_ledger_entries()
        # Create value entries for each ledger entry
        for item_ledger_entry in item_ledger_entries:
            self._create_value_entries(item_ledger_entry_no=item_ledger_entry)

    def _process_negative_adjustment(self):
        """Handle negative adjustment entries by creating necessary ledger and value entries."""
        self._create_general_ledger_entries()
        item_ledger_entries = self._create_item_ledger_entries(
            quantity=-self.journal_entry.quantity,
            remaining_quantity=0,
            total=-self.journal_entry.total,
        )
        self._reduce_inventory(
            self.journal_entry.quantity, self.journal_entry.entry_type
        )
        # Create value entries for each ledger entry
        for item_ledger_entry in item_ledger_entries:
            self._create_value_entries(item_ledger_entry_no=item_ledger_entry)

    def _process_sales(self):
        self._create_general_ledger_entries()

        item_ledger_entries = self._create_item_ledger_entries(
            quantity=-self.journal_entry.quantity,
            remaining_quantity=0,
            total=-self.journal_entry.total,
        )
        self._reduce_inventory(
            self.journal_entry.quantity, self.journal_entry.entry_type
        )
        # Create value entries for each ledger entry
        for item_ledger_entry in item_ledger_entries:
            self._create_value_entries(item_ledger_entry_no=item_ledger_entry)

    def _process_purchase(self):
        """Handle purchase entries by creating necessary ledger and value entries.
        Also including item tracking specification
        """
        self._create_general_ledger_entries()
        # item_ledger_entry = self._create_item_ledger_entries()
        # self._create_value_entries(item_ledger_entry_no=item_ledger_entry)

    def _create_item_ledger_entries(self, **additional_fields):
        """Create item ledger entries and update inventory.
        Returns:
            list: List of created ItemLedgerEntries
        """
        item = self.journal_entry.item
        created_entries = []

        # Check if item has tracking code
        if item.tracking_code:
            # Get tracking specifications for this journal entry
            tracking_specifications = TrackingSpecification.objects.filter(
                item_journal=self.journal_entry.id, item=item
            )

            from items.services.item_journal_reversal import (
                build_tracked_line_quantity_and_total,
                merge_tracked_ledger_additional_fields,
            )

            # Create separate ledger entry for each tracking specification
            for spec in tracking_specifications:
                spec_quantity = int(spec.quantity_base or 0)
                if spec_quantity <= 0:
                    continue
                line_qty, line_total = build_tracked_line_quantity_and_total(
                    spec_quantity,
                    int(self.journal_entry.quantity or 0),
                    float(self.journal_entry.total or 0),
                    additional_fields,
                )
                line_remaining = (
                    additional_fields.get("remaining_quantity", spec_quantity)
                    if additional_fields.get("quantity", 0) < 0
                    else spec_quantity
                )

                base_fields = {
                    "quantity": line_qty,
                    "remaining_quantity": line_remaining,
                    "total": line_total,
                    "lot_no": spec.lot_no,
                    "expiry_date": spec.expiry_date,
                    "serial_no": spec.serial_no,
                }
                merge_tracked_ledger_additional_fields(base_fields, additional_fields)

                item_ledger_entry = self._create_ledger_entry(**base_fields)
                created_entries.append(item_ledger_entry)
        else:
            # No tracking required - create single ledger entry
            base_fields = {
                "quantity": self.journal_entry.quantity,
                "remaining_quantity": self.journal_entry.quantity,
                "total": self.journal_entry.total,
            }
            base_fields.update(**additional_fields)
            item_ledger_entry = self._create_ledger_entry(**base_fields)
            created_entries.append(item_ledger_entry)

        return created_entries

    def _create_general_ledger_entries(self):
        """Create general ledger entries for FIFO costing method."""
        item = self.journal_entry.item
        customer = Customer.objects.get(customer_type=CustomerType.General.name)

        if item.costing_method != CostingMethod.FIFO.name:
            return

        if not self._validate_posting_groups(item):
            return

        posting_groups = self._get_posting_groups(item, customer)
        self._create_gl_entries(posting_groups, customer, item)
        print("running 3")

    def _validate_posting_groups(self, item):
        """Validate that required posting groups are set on the item and customer (for sales).

        Args:
            item: The item to validate

        Returns:
            bool: True if all required posting groups are set, False otherwise
        """
        if not self._validate_item_posting_groups(item):
            return False

        if self.journal_entry.entry_type == EntryType.Sales.name:
            if not self._validate_customer_posting_groups():
                return False

        return True

    def _validate_item_posting_groups(self, item):
        """Validate that required posting groups are set on the item.

        Args:
            item: The item to validate

        Returns:
            bool: True if item posting groups are valid, False otherwise
        """
        if (
            item.general_product_posting_group is None
            or item.inventory_posting_group is None
        ):
            missing_group = (
                "General product posting group"
                if item.general_product_posting_group is None
                else "Inventory posting group"
            )
            messages.error(
                self.request,
                f"Cannot process item '{item.item_name}' (ID: {item.no}): {missing_group} is required",
            )
            return False
        return True

    def _validate_customer_posting_groups(self):
        """Validate that required posting groups are set on the general customer for sales entries.

        Returns:
            bool: True if customer posting groups are valid, False otherwise
        """
        try:
            customer = Customer.objects.get(customer_type=CustomerType.General.name)

        except Customer.DoesNotExist:
            messages.error(
                self.request,
                "Cannot process sales entry: Please create a general customer first. "
                "Go to Customers > Add Customer and set the customer type as 'General'",
            )
            return False

        if (
            customer.general_business_posting_group is None
            or customer.customer_posting_group is None
        ):
            missing_group = (
                "General business posting group"
                if customer.general_business_posting_group is None
                else "Customer posting group"
            )
            messages.error(
                self.request,
                f"Cannot process sales entry: General customer missing {missing_group}",
            )
            return False

        return True

    def _create_gl_entries(self, posting_groups, customer, item):
        """Create the debit and credit GL entries.

        Args:
            posting_groups: Tuple of (general_posting_setup, inventory_posting_setup)
        """
        general_posting_setup, inventory_posting_setup = posting_groups

        # inventory acccount got from the item through the inventory posting group
        inventory_account = inventory_posting_setup.inventory_account

        # Determine which account to use based on adjustment_type
        # Default to operational if not set (backward compatibility)
        adjustment_type = getattr(self.journal_entry, "adjustment_type", "operational")

        if adjustment_type == "opening_balance":
            # Use hardcoded Opening Balance account (9999)
            try:
                balancing_account = G_LAccount.objects.get(no="9999")
            except G_LAccount.DoesNotExist:
                # Fallback to inventory adjustment account if 9999 doesn't exist
                balancing_account = general_posting_setup.inventory_adjustment_account
        else:
            # Use operational adjustment account from General Posting Setup
            balancing_account = general_posting_setup.inventory_adjustment_account

        # Determine if this is a negative adjustment
        is_negative_adjustment = (
            self.journal_entry.entry_type == EntryType.NegativeAdjustment.name
        )

        from dimension.models import get_posting_dimension_payload

        dim_payload = get_posting_dimension_payload(
            global_dimension_1=self.global_dimension_1_value,
        )

        # For negative adjustments, we swap the accounts and amounts
        if is_negative_adjustment:
            # Create debit entry (Balancing Account - Inventory Adjustment or Opening Balance)
            GeneralLedgerEntry.objects.create(
                posting_date=self.journal_entry.date,
                document_no=self.journal_entry.document_no,
                gl_account=balancing_account,
                description=f"Negative Adjustment on {self.journal_entry.date}",
                amount=abs(self.journal_entry.total),  # Use absolute value
                balancing_account_type=BalacingAccountType.GL_Account.name,
                user=self.request.user,
                dimension_set=dim_payload["dimension_set"],
                global_dimension_1=dim_payload["global_dimension_1"],
                global_dimension_2=dim_payload["global_dimension_2"],
            )

            # Create credit entry (Inventory Account)
            GeneralLedgerEntry.objects.create(
                posting_date=self.journal_entry.date,
                document_no=self.journal_entry.document_no,
                gl_account=inventory_account,
                description=f"Negative Adjustment on {self.journal_entry.date}",
                amount=-abs(self.journal_entry.total),  # Use negative absolute value
                balancing_account_type=BalacingAccountType.GL_Account.name,
                user=self.request.user,
                dimension_set=dim_payload["dimension_set"],
                global_dimension_1=dim_payload["global_dimension_1"],
                global_dimension_2=dim_payload["global_dimension_2"],
            )
        elif EntryType.PositiveAdjustment.name == self.journal_entry.entry_type:
            # Positive adjustment
            # Create debit entry (Inventory Account)
            GeneralLedgerEntry.objects.create(
                posting_date=self.journal_entry.date,
                document_no=self.journal_entry.document_no,
                gl_account=inventory_account,
                description=f"Positive Adjustment on {self.journal_entry.date}",
                amount=self.journal_entry.total,
                balancing_account_type=BalacingAccountType.GL_Account.name,
                user=self.request.user,
                dimension_set=dim_payload["dimension_set"],
                global_dimension_1=dim_payload["global_dimension_1"],
                global_dimension_2=dim_payload["global_dimension_2"],
            )

            # Create credit entry (Balancing Account - Inventory Adjustment or Opening Balance)
            GeneralLedgerEntry.objects.create(
                posting_date=self.journal_entry.date,
                document_no=self.journal_entry.document_no,
                gl_account=balancing_account,
                description=f"Positive Adjustment on {self.journal_entry.date}",
                amount=-self.journal_entry.total,
                balancing_account_type=BalacingAccountType.GL_Account.name,
                user=self.request.user,
                dimension_set=dim_payload["dimension_set"],
                global_dimension_1=dim_payload["global_dimension_1"],
                global_dimension_2=dim_payload["global_dimension_2"],
            )

        elif EntryType.Sales.name == self.journal_entry.entry_type:
            print("sales++++++++++++++++++++++++++++++++")
            general_posting_setup = general_posting_setup
            cogs_account = general_posting_setup.cogs_account
            # debet cost of goods sold and credit   inventory

            # debit of cost of goods sold
            GeneralLedgerEntry.objects.create(
                posting_date=self.journal_entry.date,
                document_no=self.journal_entry.document_no,
                gl_account=cogs_account,
                description=f"Cost of Goods Sold on {self.journal_entry.document_no} {self.journal_entry.date}",
                amount=self.journal_entry.total,
                balancing_account_type=BalacingAccountType.GL_Account.name,
                user=self.request.user,
                receipt_no=self.receipt_no,
                dimension_set=dim_payload["dimension_set"],
                global_dimension_1=dim_payload["global_dimension_1"],
                global_dimension_2=dim_payload["global_dimension_2"],
            )
            # credit of inventory
            GeneralLedgerEntry.objects.create(
                posting_date=self.journal_entry.date,
                document_no=self.journal_entry.document_no,
                gl_account=inventory_account,
                description=f"Cost of Goods Sold on {self.journal_entry.document_no} {self.journal_entry.date}",
                amount=-self.journal_entry.total,
                balancing_account_type=BalacingAccountType.GL_Account.name,
                user=self.request.user,
                receipt_no=self.receipt_no,
                dimension_set=dim_payload["dimension_set"],
                global_dimension_1=dim_payload["global_dimension_1"],
                global_dimension_2=dim_payload["global_dimension_2"],
            )
            customer_posting_group = customer.customer_posting_group.code
            item_posting_group = item.inventory_posting_group.code
            receivables_account = customer.customer_posting_group.receivables_account

            # create invoice
            # debit of receivables account
            GeneralLedgerEntry.objects.create(
                posting_date=self.journal_entry.date,
                document_type=DOCUMENT_TYPE.Invoice.name,
                document_no=self.journal_entry.document_no,
                gl_account=receivables_account,
                description=f"Invoice on {self.journal_entry.document_no} {self.journal_entry.date}",
                amount=self.journal_entry.amount,
                balancing_account_type=BalacingAccountType.GL_Account.name,
                user=self.request.user,
                receipt_no=self.receipt_no,
                dimension_set=dim_payload["dimension_set"],
                global_dimension_1=dim_payload["global_dimension_1"],
                global_dimension_2=dim_payload["global_dimension_2"],
            )

            # credit of revenue account
            revenue_account = general_posting_setup.sales_account
            GeneralLedgerEntry.objects.create(
                posting_date=self.journal_entry.date,
                document_type=DOCUMENT_TYPE.Invoice.name,
                document_no=self.journal_entry.document_no,
                gl_account=revenue_account,
                description=f"Invoice on {self.journal_entry.document_no} {self.journal_entry.date}",
                amount=-self.journal_entry.amount,
                balancing_account_type=BalacingAccountType.GL_Account.name,
                user=self.request.user,
                general_posting_type=GeneralPostingType.Sales.name,
                general_business_posting_group=general_posting_setup.general_business_posting_group,
                general_product_posting_group=general_posting_setup.general_product_posting_group,
                receipt_no=self.receipt_no,
                dimension_set=dim_payload["dimension_set"],
                global_dimension_1=dim_payload["global_dimension_1"],
                global_dimension_2=dim_payload["global_dimension_2"],
            )
            print("customer", customer.pk)
            print(
                "---------------------------------------------------------------------------"
            )

            # Invoice Customer Ledger Entry
            CustomerLedgerEntry.objects.create(
                posting_date=self.journal_entry.date,
                document_date=self.journal_entry.date,
                document_type=DOCUMENT_TYPE.Invoice.name,
                document_no=self.journal_entry.document_no,
                customer=customer,
                description=f"Invoice on {self.journal_entry.document_no} {self.journal_entry.date}",
                amount=self.journal_entry.amount,
                remaining_amount=self.journal_entry.amount,
                due_date=self.journal_entry.date,
                payment_method=PaymentMethod.objects.get(
                    code=customer.payment_method.code
                ),
                open=False,
                user=self.request.user,
                receipt_no=self.receipt_no,
                dimension_set=dim_payload["dimension_set"],
                global_dimension_1=dim_payload["global_dimension_1"],
                global_dimension_2=dim_payload["global_dimension_2"],
            )

            # create payment

            # debit of cash account
            cash_account = customer.payment_method.bal_account_no
            GeneralLedgerEntry.objects.create(
                posting_date=self.journal_entry.date,
                document_type=DOCUMENT_TYPE.Payment.name,
                document_no=self.journal_entry.document_no,
                gl_account=cash_account,
                description=f"Payment on {self.journal_entry.document_no} {self.journal_entry.date}",
                amount=self.journal_entry.amount,
                balancing_account_type=BalacingAccountType.GL_Account.name,
                user=self.request.user,
                receipt_no=self.receipt_no,
                dimension_set=dim_payload["dimension_set"],
                global_dimension_1=dim_payload["global_dimension_1"],
                global_dimension_2=dim_payload["global_dimension_2"],
            )
            # credit of receivables account
            GeneralLedgerEntry.objects.create(
                posting_date=self.journal_entry.date,
                document_type=DOCUMENT_TYPE.Payment.name,
                document_no=self.journal_entry.document_no,
                gl_account=receivables_account,
                description=f"Payment on {self.journal_entry.document_no} {self.journal_entry.date}",
                amount=-self.journal_entry.amount,
                balancing_account_type=BalacingAccountType.GL_Account.name,
                user=self.request.user,
                receipt_no=self.receipt_no,
                dimension_set=dim_payload["dimension_set"],
                global_dimension_1=dim_payload["global_dimension_1"],
                global_dimension_2=dim_payload["global_dimension_2"],
            )

            # create Customer Payment Ledger Entry
            CustomerLedgerEntry.objects.create(
                posting_date=self.journal_entry.date,
                document_date=self.journal_entry.date,
                document_type=DOCUMENT_TYPE.Payment.name,
                document_no=self.journal_entry.document_no,
                customer=customer,
                description=f"Payment on {self.journal_entry.document_no} {self.journal_entry.date}",
                amount=-self.journal_entry.amount,
                remaining_amount=-self.journal_entry.amount,
                due_date=self.journal_entry.date,
                payment_method=PaymentMethod.objects.get(
                    code=customer.payment_method.code
                ),
                user=self.request.user,
                open=False,
                receipt_no=self.receipt_no,
                dimension_set=dim_payload["dimension_set"],
                global_dimension_1=dim_payload["global_dimension_1"],
                global_dimension_2=dim_payload["global_dimension_2"],
            )
        elif EntryType.Purchase.name == self.journal_entry.entry_type:

            # Get unit of measure on the journal entry
            item = self.journal_entry.item

            # Get the UnitOfMeasure instance from the ItemUnitOfMeasure
            journal_uom = self.journal_entry.item_unit_of_measure
            unit_of_measure = (
                journal_uom.unit_of_measure
            )  # Get the actual UnitOfMeasure

            # Get the ItemUnitOfMeasure
            item_unit_of_measure = ItemUnitOfMeasure.objects.get(
                item=item, unit_of_measure=unit_of_measure
            )

            quantity_per_entry, number_of_entries = self._calculate_base_quantities(
                item, unit_of_measure
            )

            total_base_units = (
                number_of_entries  # Total number of pieces (e.g., 4 pieces in a box)
            )
            unit_cost_per_base = (
                self.journal_entry.unit_cost / total_base_units
            )  # Cost per piece

            # Create entries for each base unit
            for i in range(number_of_entries):
                # Create debit entry (Inventory Account)
                GeneralLedgerEntry.objects.create(
                    posting_date=self.journal_entry.date,
                    document_no=self.journal_entry.document_no,
                    gl_account=inventory_account,
                    description=f"Direct Cost on {self.journal_entry.document_no} {self.journal_entry.date}",
                    amount=unit_cost_per_base,
                    balancing_account_type=BalacingAccountType.GL_Account.name,
                    user=self.request.user,
                    receipt_no=self.receipt_no,
                    dimension_set=dim_payload["dimension_set"],
                    global_dimension_1=dim_payload["global_dimension_1"],
                    global_dimension_2=dim_payload["global_dimension_2"],
                )

                # Create credit entry (Direct cost applied account)
                GeneralLedgerEntry.objects.create(
                    posting_date=self.journal_entry.date,
                    document_no=self.journal_entry.document_no,
                    gl_account=inventory_account,
                    description=f"Direct Cost on {self.journal_entry.document_no} {self.journal_entry.date}",
                    amount=-unit_cost_per_base,
                    balancing_account_type=BalacingAccountType.GL_Account.name,
                    user=self.request.user,
                    receipt_no=self.receipt_no,
                    dimension_set=dim_payload["dimension_set"],
                    global_dimension_1=dim_payload["global_dimension_1"],
                    global_dimension_2=dim_payload["global_dimension_2"],
                )

    def _create_ledger_entry(self, **additional_fields):
        """Create a ledger entry with base and additional fields.

        Args:
            **additional_fields: Additional fields to be included in the ledger entry

        Returns:
            ItemLedgerEntries: The created ledger entry
        """
        base_fields = {
            "item": self.journal_entry.item,
            "entry_type": self.journal_entry.entry_type,
            "document_no": self.journal_entry.document_no,
            "description": self.journal_entry.description,
            "unit_of_measure": self.journal_entry.item_unit_of_measure,
            "unit_cost": self.journal_entry.unit_cost,
            "date": self.journal_entry.date,
            "posting_date": self.journal_entry.date,
            "user": self.journal_entry.user,
            "receipt_no": self.receipt_no,
            "global_dimension_1": self.global_dimension_1_value,
        }
        base_fields.update(**additional_fields)
        return ItemLedgerEntries.objects.create(**base_fields)

    def _create_value_entries(self, **additional_fields):
        """Create value entries for the journal entry.

        Args:
            **additional_fields: Additional fields to be included in the value entry

        Returns:
            ValueEntry: The created value entry

        Raises:
            Item.DoesNotExist: If the referenced item doesn't exist
            GeneralPostingSetup.DoesNotExist: If posting setup is missing
            InventoryPostingSetup.DoesNotExist: If inventory setup is missing
        """
        item = self.journal_entry.item

        # Get posting groups and setups
        posting_groups = self._get_value_entry_posting_groups(item)
        if not posting_groups:
            return None

        general_product_posting_group, inventory_posting_group = posting_groups

        # Get the item ledger entry from additional fields
        item_ledger_entry = additional_fields.get("item_ledger_entry_no")

        # Quantities/costs from item ledger (already signed) or journal line
        if item_ledger_entry:
            quantity = item_ledger_entry.quantity
            total = item_ledger_entry.total
        else:
            quantity = self.journal_entry.quantity
            total = self.journal_entry.total

        from dimension.models import get_posting_dimension_payload
        from items.value_entry_posting import bc_normalize_value_entry_fields

        sales_amount = "0"
        if self.journal_entry.entry_type == EntryType.Sales.name:
            sales_amount = str(self.journal_entry.amount or total or 0)

        dim_payload = get_posting_dimension_payload(
            global_dimension_1=self.global_dimension_1_value,
        )

        ve_signs = bc_normalize_value_entry_fields(
            self.journal_entry.entry_type,
            quantity,
            total,
            cost_per_unit=self.journal_entry.unit_cost,
        )

        base_fields = {
            "posting_date": self.journal_entry.date,
            "entry_type": self.journal_entry.entry_type,
            "document_no": self.journal_entry.document_no,
            "description": self.journal_entry.description or "",
            "sales_amount": sales_amount,
            "item": item,
            "general_product_posting_group": general_product_posting_group,
            "inventory_posting_group": inventory_posting_group,
            "global_dimension_1": dim_payload["global_dimension_1"],
            "dimension_set": dim_payload["dimension_set"],
            **ve_signs,
        }

        base_fields.update(additional_fields)

        return ValueEntry.objects.create(**base_fields)

    def _get_value_entry_posting_groups(self, item):
        """Get posting groups for value entries.

        Args:
            item: The item for which to get posting groups

        Returns:
            tuple: (general_product_posting_group, inventory_posting_group) or None if validation fails

        Raises:
            GeneralPostingSetup.DoesNotExist: If posting setup is missing
            InventoryPostingSetup.DoesNotExist: If inventory setup is missing
        """
        try:

            customer = Customer.objects.get(customer_type=CustomerType.General.name)
            # Get general posting setup and group
            if (
                EntryType.PositiveAdjustment.name == self.journal_entry.entry_type
                or EntryType.NegativeAdjustment.name == self.journal_entry.entry_type
            ):
                general_posting_setup = GeneralPostingSetup.objects.get(
                    general_product_posting_group=item.general_product_posting_group,
                    general_business_posting_group__isnull=True,
                )

            elif EntryType.Sales.name == self.journal_entry.entry_type:
                general_posting_setup = GeneralPostingSetup.objects.get(
                    general_business_posting_group=customer.general_business_posting_group,
                    general_product_posting_group=item.general_product_posting_group,
                )
            general_product_posting_group = GeneralProductPostingGroup.objects.get(
                id=general_posting_setup.general_product_posting_group.id
            )

            # Get inventory posting setup and group (location-aware when configured).
            inventory_posting_setup = self._resolve_inventory_posting_setup(item)
            inventory_posting_group = InventoryPostingGroup.objects.get(
                id=inventory_posting_setup.inventory_posting_group.id
            )

            return general_product_posting_group, inventory_posting_group

        except (
            GeneralPostingSetup.DoesNotExist,
            InventoryPostingSetup.DoesNotExist,
        ) as e:
            messages.error(
                self.request,
                f"Error creating value entry: Missing posting setup for item '{item.item_name}' - {str(e)}",
            )
            return None

    def _resolve_inventory_posting_setup(self, item):
        """
        Resolve InventoryPostingSetup deterministically.

        Rules:
        - If journal has a Location, prefer an exact (location, inventory_posting_group) match.
          If missing, fall back to (location IS NULL, inventory_posting_group) as company default.
        - If journal has no Location, prefer (location IS NULL, inventory_posting_group).
          If none exists, only accept a single setup for that inventory_posting_group; otherwise error.
        """
        inv_group = item.inventory_posting_group
        loc = getattr(self.journal_entry, "location_code", None)

        # 1) Exact location match (if a location exists on the journal).
        if loc:
            exact = InventoryPostingSetup.objects.filter(
                location=loc, inventory_posting_group=inv_group
            )
            if exact.count() == 1:
                return exact.first()
            if exact.count() > 1:
                raise ValidationError(
                    f"Multiple InventoryPostingSetup records match Location '{loc}' and "
                    f"Inventory Posting Group '{inv_group}'. Please keep only one."
                )

        # 2) Company default (location is NULL).
        default_qs = InventoryPostingSetup.objects.filter(
            location__isnull=True, inventory_posting_group=inv_group
        )
        if default_qs.count() == 1:
            return default_qs.first()
        if default_qs.count() > 1:
            raise ValidationError(
                f"Multiple default InventoryPostingSetup records found for Inventory Posting Group "
                f"'{inv_group}' (Location is blank). Please keep only one."
            )

        # 3) Last resort: if there is exactly one setup for this inv group, use it.
        any_qs = InventoryPostingSetup.objects.filter(inventory_posting_group=inv_group)
        if any_qs.count() == 1:
            return any_qs.first()
        if any_qs.count() == 0:
            raise InventoryPostingSetup.DoesNotExist(
                f"No InventoryPostingSetup found for Inventory Posting Group '{inv_group}'."
            )
        raise ValidationError(
            f"InventoryPostingSetup is ambiguous for Inventory Posting Group '{inv_group}'. "
            f"Add a default (blank Location) setup or specify a unique setup per Location."
        )

    def _get_posting_groups(self, item, customer):
        """Get the posting groups for the item.

        Args:
            item: The item to get posting groups for

        Returns:
            tuple: (general_posting_setup, inventory_posting_setup)
        """

        # Resolve inventory posting setup deterministically (location-aware + default fallback).
        inventory_posting_setup = self._resolve_inventory_posting_setup(item)

        # * Get general posting setup based on entry type
        if (
            EntryType.PositiveAdjustment.name == self.journal_entry.entry_type
            or EntryType.NegativeAdjustment.name == self.journal_entry.entry_type
            or EntryType.Purchase.name == self.journal_entry.entry_type
        ):
            general_posting_setup = GeneralPostingSetup.objects.get(
                general_product_posting_group=item.general_product_posting_group,
                general_business_posting_group__isnull=True,
            )

        if EntryType.Sales.name == self.journal_entry.entry_type:
            general_posting_setup = GeneralPostingSetup.objects.get(
                general_business_posting_group=customer.general_business_posting_group,
                general_product_posting_group=item.general_product_posting_group,
            )

        return general_posting_setup, inventory_posting_setup

    def _reduce_inventory(self, quantity_to_reduce, entry_type):
        """Reduce inventory based on FIFO method (First In, First Out).

        Args:
            quantity_to_reduce: The quantity to reduce from inventory
            entry_type: The type of entry being processed
        """
        remaining = quantity_to_reduce
        # For items with tracking (lot numbers), order by expiry date first (FEFO - First Expired, First Out)
        # For items without tracking, use FIFO (First In, First Out) based on created_at
        if self.journal_entry.item.tracking_code:
            # Items with tracking: order by expiry_date (earliest first), then by created_at
            entries = ItemLedgerEntries.objects.filter(
                item=self.journal_entry.item, remaining_quantity__gt=0
            ).order_by(
                models.F("expiry_date").asc(
                    nulls_last=True
                ),  # Items without expiry date go last
                "created_at",
            )
        else:
            # Items without tracking: use FIFO based on created_at
            entries = ItemLedgerEntries.objects.filter(
                item=self.journal_entry.item, remaining_quantity__gt=0
            ).order_by("created_at")

        for entry in entries:
            if remaining <= 0:
                break

            reduction = min(entry.remaining_quantity, remaining)
            entry.remaining_quantity -= reduction
            entry.save()
            remaining -= reduction

        if remaining > 0:
            messages.warning(
                self.request,
                f"Warning: Not enough inventory to fulfill the {entry_type} for {self.journal_entry.item.item}",
            )

    def _calculate_base_quantities(self, item, journal_unit_of_measure):
        """
        Calculate quantities in base unit of measure

        Args:
            item: Item object with base unit of measure
            journal_unit_of_measure: Unit of measure selected in journal

        Returns:
            tuple: (base_quantity_per_unit, number_of_entries)
        """
        # Get the conversion rate from journal UOM to base UOM
        journal_uom_conversion = ItemUnitOfMeasure.objects.get(
            item=item, unit_of_measure=journal_unit_of_measure
        )

        # Calculate total quantity in base units
        base_quantity = int(journal_uom_conversion.quantity_per_unit) * int(
            self.journal_entry.quantity
        )

        # For tracked items, each entry represents one base unit
        if item.tracking_code:
            number_of_entries = base_quantity
            quantity_per_entry = 1  # Each entry is one base unit
        else:
            number_of_entries = 1
            quantity_per_entry = base_quantity

        return quantity_per_entry, number_of_entries

    # def _delete_journal_entry(self):
    #     ItemJournal.objects.filter(id=self.journal_entry.id).delete()


def _user_can_reverse_item_journal(request) -> bool:
    if getattr(request.user, "is_superuser", False):
        return True
    setup = UserSetup.get_or_create_for_user(request.user)
    return bool(setup.can_reverse_item_journal)


def _reverse_item_journal_permission_denied(modeladmin, request):
    modeladmin.message_user(
        request,
        "You do not have permission to reverse posted item journals. "
        "Ask an administrator to enable “Can reverse item journal” in User Setup.",
        level=messages.ERROR,
    )


@admin.action(description="Open selected journal")
def open_selected_item_journal(modeladmin, request, queryset):
    """Redirect to the journal change form (single selection only)."""
    count = queryset.count()
    if count != 1:
        modeladmin.message_user(
            request,
            "Select exactly one item journal to open.",
            level=messages.ERROR,
        )
        return
    journal = queryset.first()
    return HttpResponseRedirect(
        reverse("admin:items_itemjournal_change", args=[journal.pk])
    )


@admin.action(description="Mark selected journals as Open")
def mark_item_journals_open(modeladmin, request, queryset):
    updated = queryset.exclude(status=Status.Open.value).update(
        status=Status.Open.value
    )
    modeladmin.message_user(
        request,
        f"{updated} journal(s) marked as Open.",
        level=messages.SUCCESS if updated else messages.INFO,
    )


@admin.action(description="Mark selected journals as Posted (status only)")
def mark_item_journals_posted_status_only(modeladmin, request, queryset):
    """
    Update the status field only — does not create ledger/G/L entries.
    Use “Post to Journal Refactor” for full posting.
    """
    updated = queryset.exclude(status=Status.Posted.value).update(
        status=Status.Posted.value
    )
    modeladmin.message_user(
        request,
        f"{updated} journal(s) marked as Posted (status field only).",
        level=messages.SUCCESS if updated else messages.INFO,
    )


@admin.action(description="Preview reverse posted journal")
def preview_reverse_posted_journal(modeladmin, request, queryset):
    if not _user_can_reverse_item_journal(request):
        _reverse_item_journal_permission_denied(modeladmin, request)
        return

    if len(queryset) != 1:
        modeladmin.message_user(
            request,
            "Please select a single posted item journal to preview reversal.",
            level=messages.ERROR,
        )
        return

    journal = queryset[0]
    if journal.status != "Posted":
        modeladmin.message_user(
            request,
            f"Only posted journals can be reversed. Current status: {journal.status!r}.",
            level=messages.ERROR,
        )
        return

    from items.services.item_journal_reversal import ItemJournalPostingReversal

    reverser = ItemJournalPostingReversal(journal=journal, user=request.user)
    plan = reverser.dry_run_plan()

    if not plan["can_reverse"]:
        modeladmin.message_user(
            request,
            "This journal has no unreversed ledger rows to reverse "
            "(already fully reversed).",
            level=messages.WARNING,
        )
        return

    preview_data = {
        "steps": [
            "Mark original G/L, item ledger, and value entries as reversed",
            "Create reversing G/L entries (opposite amounts)",
            "Create reversing item ledger entries",
            "Create reversing value entries",
            "Restore FIFO inventory layers (if applicable)",
        ],
        "gl_entries_count": len(plan["gl_entries"]),
        "item_ledger_entries_count": len(plan["item_ledger_entries"]),
        "value_entries_count": len(plan["value_entries"]),
        "fifo_restore_count": len(plan["fifo_restore"]),
        "plan": plan,
    }

    return TemplateResponse(
        request,
        "admin/items/itemjournal/preview_reversal.html",
        context={
            "title": "Preview Item Journal Reversal",
            "journal": journal,
            "preview_data": preview_data,
            "opts": modeladmin.model._meta,
        },
    )


@admin.action(description="Preview Journal Posting")
def preview_journal_posting(modeladmin, request, queryset):
    if len(queryset) != 1:
        modeladmin.message_user(
            request,
            "Please select a single journal entry to preview posting.",
            level="ERROR",
        )
        return

    journal_entry = queryset[0]
    receipt_no = (
        f"RCP-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
    )

    # if unit of measure, amount, unit_cost, totla are empty show error
    if (
        not journal_entry.item_unit_of_measure
        or not journal_entry.amount
        or not journal_entry.unit_cost
        or not journal_entry.total
    ):
        modeladmin.message_user(
            request,
            "Unit of measure, amount, unit cost, and total are required to preview posting.",
            level="ERROR",
        )
        missing_fields = []
        if not journal_entry.item_unit_of_measure:
            missing_fields.append("Unit of measure")
        if not journal_entry.amount:
            missing_fields.append("Amount")
        if not journal_entry.unit_cost:
            missing_fields.append("Unit cost")
        if not journal_entry.total:
            missing_fields.append("Total")
        raise Exception(
            f"Unit of measure, amount, unit cost, and total are required to preview posting. Missing fields: {', '.join(missing_fields)}"
        )

    try:
        # Use the new preview processor
        processor = ItemJournalPreviewProcessor(journal_entry, request, receipt_no)
        preview_entries = processor.process()

        # Check if validation failed (empty preview data)
        if not preview_entries or (
            isinstance(preview_entries, dict) and not any(preview_entries.values())
        ):
            # Validation failed, return without showing preview
            return

        # Create the data structure expected by the template
        preview_data = {
            "journal": f"Journal Entry {journal_entry.id} -> {journal_entry.document_no}",
            "steps": [
                "Posting item ledger entries",
                "Posting general ledger entries",
                "Posting value entries",
                "Posting customer ledger entries (if sales)",
            ],
            "entries": preview_entries,
        }

        return TemplateResponse(
            request,
            "admin/items/itemjournal/preview_posting.html",
            context={
                "title": "Preview Journal Posting",
                "journal_entry": journal_entry,
                "preview_entries": preview_data,
                "opts": modeladmin.model._meta,
            },
        )

    except Customer.DoesNotExist:
        modeladmin.message_user(
            request,
            "Error: General customer not found. Please create a general customer first.",
            level="ERROR",
        )
        return
    except (GeneralPostingSetup.DoesNotExist, InventoryPostingSetup.DoesNotExist) as e:
        modeladmin.message_user(
            request,
            f"Error: Required posting setup not found - {str(e)}",
            level="ERROR",
        )
        return
    except Exception as e:
        modeladmin.message_user(
            request,
            f"Error generating preview: {str(e)}",
            level="ERROR",
        )
        return


@admin.action(description="Post to Journal Refactor")
def postItemJournalReFactor(modeladmin, request, queryset):
    try:
        with transaction.atomic():
            receipt_no = f"RCP-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
            for journalentry in queryset.all():
                # 1. Run the preview logic
                previewer = ItemJournalPreviewProcessor(
                    journalentry, request, receipt_no=receipt_no
                )
                preview_data = previewer.process()  # This returns the preview dict

                # Check if validation failed (empty preview data)
                if not preview_data or (
                    isinstance(preview_data, dict) and not any(preview_data.values())
                ):
                    # Skip this journal entry due to validation failure
                    continue

                # 2. Run the final posting logic
                poster = ItemJournalFinalPoster(
                    preview_data, journalentry, request.user
                )
                poster.post_to_tables()

        messages.success(
            request, "Selected journal entries have been posted successfully."
        )

    except Exception as e:
        messages.error(request, f"Error processing journal entries: {str(e)}")
        return


@admin.register(UnitOfMeasure)
class ItemUnitofMeasureAdmin(admin.ModelAdmin):
    list_display = ("description",)
    search_fields = ["description"]
    # readonly_fields = ("code",)
    model = UnitOfMeasure


@admin.register(ItemUnitOfMeasure)
class ItemUnitOfMeasureAdmin(admin.ModelAdmin):
    list_display = ("item", "unit_of_measure", "quantity_per_unit", "price", "default")
    search_fields = ["item__item_name", "unit_of_measure__code"]


class ItemUnitOfMeasureInline(admin.TabularInline):
    model = ItemUnitOfMeasure
    extra = 1


class ItemImageInline(admin.TabularInline):
    model = ItemImages
    extra = 1


class ItemAttributeEntryInline(admin.StackedInline):
    model = ItemAttributeEntry
    extra = 1
    filter_horizontal = ("selected_values",)
    autocomplete_fields = ("attribute",)


@admin.register(ItemAttributeValue)
class ItemAttributeValueAdmin(admin.ModelAdmin):
    list_display = ("value", "blocked")
    list_filter = ("blocked",)
    search_fields = ("value",)


@admin.register(ItemAttribute)
class ItemAttributeAdmin(admin.ModelAdmin):
    list_display = ("name", "type", "blocked")
    list_filter = ("type", "blocked")
    search_fields = ("name",)
    filter_horizontal = ("values",)


@admin.register(ItemAttributeEntry)
class ItemAttributeEntryAdmin(admin.ModelAdmin):
    list_display = ("item", "attribute", "display_value")
    search_fields = ("item__item_name", "attribute__name")
    autocomplete_fields = ("item", "attribute")
    filter_horizontal = ("selected_values",)


def _items_export_permissions_for_user(user):
    """Match `ItemViewSet.export` / Celery export: respect UserSetup price columns."""
    try:
        user_setup = UserSetup.objects.get(user=user)
        return {
            "can_see_buying_price": user_setup.can_see_buying_price,
            "can_see_profit_margin": user_setup.can_see_profit_margin,
            "can_see_item_cost": user_setup.can_see_item_cost,
        }
    except UserSetup.DoesNotExist:
        return {
            "can_see_buying_price": True,
            "can_see_profit_margin": True,
            "can_see_item_cost": True,
        }


@admin.action(description="Export selected items to PDF (same as Items app)")
def export_selected_items_to_pdf(modeladmin, request, queryset):
    """
    Uses the same ReportLab table as the SPA export (`items.tasks._export_to_pdf`),
    including UserSetup visibility for unit cost and profit columns.
    """
    from items.tasks import _export_to_pdf

    if not queryset.exists():
        modeladmin.message_user(request, "No items selected.", level=messages.WARNING)
        return

    items = list(queryset.select_related("item_category").order_by("item_name")[:500])
    perms = _items_export_permissions_for_user(request.user)

    try:
        file_bytes, filename = _export_to_pdf(items, user_permissions=perms)
    except ImportError as e:
        modeladmin.message_user(
            request,
            f"PDF export unavailable (missing dependency): {e}",
            level=messages.ERROR,
        )
        return
    except Exception as e:
        modeladmin.message_user(
            request,
            f"PDF export failed: {e}",
            level=messages.ERROR,
        )
        return

    response = HttpResponse(file_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@admin.action(description="Export barcode labels PDF (selected items)")
def export_selected_items_barcode_labels_pdf(modeladmin, request, queryset):
    """
    Printable Code128 labels (name + barcode), one page per item — in-memory PDF.
    Items without Bar Code No. are skipped. Complements the tabular SPA-style PDF
    action above (which uses `items.tasks._export_to_pdf`).
    """
    from items.barcode_export import build_barcode_labels_pdf_bytes

    if not queryset.exists():
        modeladmin.message_user(request, "No items selected.", level=messages.WARNING)
        return

    items = list(queryset.order_by("item_name")[:500])
    try:
        file_bytes, filename = build_barcode_labels_pdf_bytes(items)
    except ValueError as e:
        modeladmin.message_user(request, str(e), level=messages.WARNING)
        return
    except ImportError as e:
        modeladmin.message_user(
            request,
            f"Barcode PDF unavailable (missing dependency): {e}",
            level=messages.ERROR,
        )
        return
    except Exception as e:
        modeladmin.message_user(
            request,
            f"Barcode PDF failed: {e}",
            level=messages.ERROR,
        )
        return

    response = HttpResponse(file_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@admin.register(Item)
class ItemAdmin(DefaultDimensionAdminMixin, admin.ModelAdmin):
    related_model = "items.Item"
    no_attr = "no"

    list_display = (
        "no",
        "bar_code_no",
        "item_name",
        "type",
        "blocked",
        "item_category",
        "manufacturing_policy",
        "inventory",
        "costing_method",
        "general_product_posting_group",
        "inventory_posting_group",
        "unit_of_measure",
        "purchase_unit_of_measure",
        "sales_unit_of_measure",
        "unit_price",
        "unit_cost",
        "profit_percentage",
        "tracking_code",
        "created_at",
        "updated_at",
    )
    readonly_fields = ("inventory", "unit_cost", "profit_percentage", "no")
    search_fields = ["item_name", "system_id", "bar_code_no", "no"]

    list_filter = (
        "type",
        "blocked",
        "costing_method",
        "replenishment_system",
        "manufacturing_policy",
        "flushing_method",
        "created_at",
        "updated_at",
    )
    fieldsets = [
        (
            "Item",
            {
                "classes": ["Wide"],
                "fields": [
                    "no",
                    "item_name",
                    "item_category",
                    "type",
                    "blocked",
                    "bar_code_no",
                ],
            },
        ),
        (
            "Inventory",
            {
                "classes": ["Wide"],
                "fields": ["inventory", "minimum_stock", "shelf_no"],
            },
        ),
        (
            "Costing & Posting",
            {
                "classes": ["wide"],
                "fields": [
                    "costing_method",
                    "unit_price",
                    "unit_cost",
                    "profit_percentage",
                    "general_product_posting_group",
                    "vat_product_posting_group",
                    "inventory_posting_group",
                ],
            },
        ),
        (
            "Tracking",
            {
                "classes": ["wide"],
                "fields": [
                    "tracking_code",
                    "unit_of_measure",
                    "purchase_unit_of_measure",
                    "sales_unit_of_measure",
                ],
            },
        ),
        (
            "Production",
            {
                "classes": ["wide"],
                "fields": [
                    "production_bom",
                    "replenishment_system",
                    "manufacturing_policy",
                    "flushing_method",
                ],
            },
        ),
        # (
        #     "Images",
        #     {
        #         "classes": ["wide"],
        #         "fields": ["images"],
        #     },
        # ),
    ]

    inlines = [
        ItemUnitOfMeasureInline,
        ItemImageInline,
        ItemAttributeEntryInline,
    ]
    actions = [
        export_selected_items_to_pdf,
        export_selected_items_barcode_labels_pdf,
    ]


@admin.register(ItemCategory)
class ItemCategoryAdmin(MPTTModelAdmin):
    list_display = (
        "code",
        "description",
    )
    filter_horizontal = ("attributes",)
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "code",
                    "description",
                    "parent",
                    "attributes",
                ),
            },
        ),
    )
    # ordering = ("code",)


class TrackingSpecificationInline(admin.TabularInline):
    model = TrackingSpecification
    extra = 1


class ItemLedgerEntriesInline(admin.TabularInline):
    model = TrackingSpecification
    extra = 1

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "lot_no":
            # Get the current item from the parent form
            if request._obj_ is not None:
                kwargs["queryset"] = ItemLedgerEntries.objects.filter(
                    item=request._obj_.item, lot_no__isnull=False
                ).exclude(lot_no="")
            else:
                kwargs["queryset"] = ItemLedgerEntries.objects.none()
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(ItemJournalBatch)
class ItemJournalBatchAdmin(admin.ModelAdmin):
    list_display = (
        "journal_template",
        "name",
        "description",
        "no_series",
        "created_at",
    )
    list_filter = ("journal_template", "created_at")
    search_fields = ("name", "description", "journal_template__name")
    autocomplete_fields = ["journal_template", "no_series"]
    ordering = ["journal_template", "name"]


class ItemJournalStatusFilter(admin.SimpleListFilter):
    title = "status"
    parameter_name = "status"

    def lookups(self, request, model_admin):
        return (
            (Status.Open.value, Status.Open.value),
            (Status.Posted.value, Status.Posted.value),
        )

    def queryset(self, request, queryset):
        value = self.value()
        if value:
            return queryset.filter(status=value)
        return queryset


@admin.register(ItemJournal)
class ItemJournalAdmin(admin.ModelAdmin):
    form = ItemJournalForm  # Use our custom form
    list_display = (
        "journal_template",
        "item",
        "entry_type",
        "type",
        "document_no",
        "quantity",
        "item_unit_of_measure",
        "display_unit_amount",
        "display_amount",
        "display_unit_cost",
        "location_code",
        "item_specification",
        "status",
        "date",
        "user",
        "created_at",
    )
    list_display_links = ("document_no",)
    list_editable = ("status",)

    # autocomplete_fields = ["item"]
    # actions = [postItemJournal]
    actions = [
        open_selected_item_journal,
        mark_item_journals_open,
        mark_item_journals_posted_status_only,
        postItemJournalReFactor,
        preview_journal_posting,
        preview_reverse_posted_journal,
    ]
    readonly_fields = ["document_no"]

    def get_actions(self, request):
        actions = super().get_actions(request)
        if not _user_can_reverse_item_journal(request):
            actions.pop("preview_reverse_posted_journal", None)
        return actions

    def apply_reverse_journal(self, request, journal_id):
        if request.method != "POST":
            return HttpResponseRedirect(
                reverse("admin:items_itemjournal_changelist")
            )

        if not _user_can_reverse_item_journal(request):
            _reverse_item_journal_permission_denied(self, request)
            return HttpResponseRedirect(
                reverse("admin:items_itemjournal_changelist")
            )

        journal = ItemJournal.objects.filter(pk=journal_id).first()
        if not journal:
            self.message_user(request, "Item journal not found.", level=messages.ERROR)
            return HttpResponseRedirect(
                reverse("admin:items_itemjournal_changelist")
            )

        if journal.status != "Posted":
            self.message_user(
                request,
                f"Only posted journals can be reversed. Current status: {journal.status!r}.",
                level=messages.ERROR,
            )
            return HttpResponseRedirect(
                reverse("admin:items_itemjournal_changelist")
            )

        from items.services.item_journal_reversal import ItemJournalPostingReversal

        reverser = ItemJournalPostingReversal(journal=journal, user=request.user)
        try:
            result = reverser.apply(mark_only=False)
        except ValueError as exc:
            self.message_user(request, str(exc), level=messages.ERROR)
            return HttpResponseRedirect(
                reverse("admin:items_itemjournal_changelist")
            )
        except Exception as exc:
            self.message_user(
                request,
                f"Failed to reverse journal: {exc}",
                level=messages.ERROR,
            )
            return HttpResponseRedirect(
                reverse("admin:items_itemjournal_changelist")
            )

        reversal_doc = result.get("reversal_document_no", reverser.reversal_document_no)
        self.message_user(
            request,
            f"Successfully reversed {journal.document_no}. "
            f"Reversing document: {reversal_doc}. "
            f"Created G/L: {len(result.get('created_gl', []))}, "
            f"item ledger: {len(result.get('created_item_ledger', []))}, "
            f"value entries: {len(result.get('created_value_entries', []))}.",
            level=messages.SUCCESS,
        )
        return HttpResponseRedirect(reverse("admin:items_itemjournal_changelist"))

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Filter fields based on context"""
        if db_field.name == "journal_template":
            from items.models import ItemJournalTemplate

            kwargs["queryset"] = ItemJournalTemplate.objects.all().order_by("name")
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    # exclude = ["user"]
    search_fields = [
        "document_no",
        "item__no",
        "item__item_name",
        "item__bar_code_no",
        "item__system_id",
    ]
    autocomplete_fields = ["item", "item_unit_of_measure"]
    list_filter = [
        ItemJournalStatusFilter,
        "journal_template",
        "journal_batch",
        "entry_type",
        "type",
        "location_code",
        "date",
        "created_at",
    ]

    def get_form(self, request, obj=None, **kwargs):
        # Store the object reference for use in formfield_for_foreignkey
        request._obj_ = obj
        return super().get_form(request, obj, **kwargs)

    #  adding item tracking specification
    inlines = [ItemLedgerEntriesInline]

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        form.base_fields["amount"].disabled = True
        return form

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "<int:journal_id>/reverse/apply/",
                self.admin_site.admin_view(self.apply_reverse_journal),
                name="items_itemjournal_reverse_apply",
            ),
            path(
                "get_item_cost/<str:item_no>/",
                self.admin_site.admin_view(self.get_item_cost),
                name="get-item-cost",
            ),
            path(
                "get_item_uom/<str:item_no>/",
                self.admin_site.admin_view(self.get_item_uom),
                name="get-item-uom",
            ),
            path(
                "get_item_uom_by_id/<int:uom_id>/",
                self.admin_site.admin_view(self.get_item_uom_by_id),
                name="get-item-uom-by-id",
            ),
        ]
        return custom_urls + urls

    def get_item_cost(self, request, item_no):
        """Get the unit cost for a specific item.

        Args:
            request: The HTTP request
            item_id: The ID of the item to get the cost for

        Returns:
            JsonResponse with the unit cost or appropriate error message
        """
        try:
            item = Item.objects.get(no=item_no)
            if item is None:
                return JsonResponse(
                    {"error": f"Item with ID {item_no} not found"}, status=404
                )

            # Default to 0 if unit_cost is None or not set
            unit_cost = 0
            if hasattr(item, "unit_cost") and item.unit_cost is not None:
                unit_cost = item.unit_cost

            return JsonResponse({"unit_cost": unit_cost, "success": True})

        except Item.DoesNotExist:
            return JsonResponse(
                {"error": f"Item with ID {item_no} not found"}, status=404
            )
        except Exception as e:
            return JsonResponse({"error": f"An error occurred: {str(e)}"}, status=500)

    def get_item_uom(self, request, item_no):
        try:
            item = Item.objects.get(no=item_no)
            item_uoms = ItemUnitOfMeasure.objects.filter(item=item).select_related(
                "unit_of_measure"
            )

            if not item_uoms.exists():
                return JsonResponse(
                    {
                        "units_of_measure": [],
                        "success": False,
                        "error": "No units of measure defined for this item",
                    }
                )

            uom_data = [
                {
                    "id": uom.id,
                    "code": uom.unit_of_measure.code,
                    "description": uom.unit_of_measure.description,
                    "quantity_per_unit": uom.quantity_per_unit,
                    "is_default": uom.default,
                }
                for uom in item_uoms
            ]

            return JsonResponse({"units_of_measure": uom_data, "success": True})

        except Item.DoesNotExist:
            return JsonResponse(
                {"error": f"Item with ID {item_no} not found", "success": False},
                status=404,
            )
        except Exception as e:
            return JsonResponse({"error": str(e), "success": False}, status=500)

    def get_item_uom_by_id(self, request, uom_id):
        try:
            uom = ItemUnitOfMeasure.objects.select_related("unit_of_measure").get(
                id=uom_id
            )

            uom_data = {
                "id": uom.id,
                "quantity_per_unit": uom.quantity_per_unit,
                "unit_of_measure": uom.unit_of_measure.code,
            }

            return JsonResponse({"units_of_measure": uom_data, "success": True})

        except ItemUnitOfMeasure.DoesNotExist:
            return JsonResponse(
                {
                    "error": f"Unit of Measure with ID {uom_id} not found",
                    "success": False,
                },
                status=404,
            )
        except Exception as e:
            return JsonResponse({"error": str(e), "success": False}, status=500)

    def display_unit_amount(self, obj):
        return intcomma(obj.unit_amount)

    display_unit_amount.short_description = "Unit Amount"
    display_unit_amount.admin_order_field = "unit_amount"

    def display_amount(self, obj):
        return intcomma(obj.amount)

    display_amount.short_description = "Amount"
    display_amount.admin_order_field = "amount"

    def display_unit_cost(self, obj):
        return intcomma(obj.unit_cost)

    display_unit_cost.short_description = "Unit Cost"
    display_unit_cost.admin_order_field = "unit_cost"

    def save_model(self, request, obj, form, change):
        if change and "status" in form.changed_data:
            previous_status = (
                ItemJournal.objects.filter(pk=obj.pk)
                .values_list("status", flat=True)
                .first()
            )
            if (
                previous_status == Status.Posted.value
                and obj.status == Status.Open.value
            ):
                messages.warning(
                    request,
                    f"{obj.document_no}: status set to Open without reversing "
                    "ledger entries. Use “Preview reverse posted journal” for a "
                    "proper reversal.",
                )
        super().save_model(request, obj, form, change)

    class Media:
        css = {"all": ("admin/css/fix_action_buttons.css",)}
        js = ("admin/item_journal.js", "admin/number_format.js")


@admin.register(ItemLedgerEntries)
class ItemLedgerEntriesAdmin(admin.ModelAdmin):
    class EmptyDimensionFieldsFilter(admin.SimpleListFilter):
        title = "Empty dimensions"
        parameter_name = "dimension_empty"

        def lookups(self, request, model_admin):
            return (
                ("no_set", "Missing dimension set"),
                ("no_dim1", "Missing global dimension 1"),
                ("no_dim2", "Missing global dimension 2"),
                ("any", "Missing any (set or global dimensions)"),
            )

        def queryset(self, request, queryset):
            from django.db.models import Q

            v = self.value()
            if v == "no_set":
                return queryset.filter(dimension_set__isnull=True)
            if v == "no_dim1":
                return queryset.filter(global_dimension_1__isnull=True)
            if v == "no_dim2":
                return queryset.filter(global_dimension_2__isnull=True)
            if v == "any":
                return queryset.filter(
                    Q(dimension_set__isnull=True)
                    | Q(global_dimension_1__isnull=True)
                    | Q(global_dimension_2__isnull=True)
                )
            return queryset

    list_display = (
        "item",
        "entry_type",
        "document_no",
        "quantity",
        "remaining_quantity",
        "total",
        "cost_amount",
        "lot_no",
        "expiry_date",
        "unit_of_measure_code",
        "location",
        "dimension_set",
        "global_dimension_1",
        "global_dimension_2",
        "created_at",
        "user",
        "date",
        "transaction_no",
    )
    list_select_related = (
        "item",
        "location",
        "dimension_set",
        "global_dimension_1",
        "global_dimension_2",
        "user",
    )
    list_editable = ("date",)
    readonly_fields = (
        "item",
        "entry_type",
        "document_no",
        "quantity",
        "unit_of_measure_code",
        "total",
        # "unit_cost",
        # "unit_amount",
        # "amount",
        "user",
        "created_at",
    )
    list_filter = ("item", "entry_type", "date", EmptyDimensionFieldsFilter)
    # autocomplete_fields = ["item"]
    search_fields = [
        "document_no",
        "item__item_name",
        "item__bar_code_no",
        "item__system_id",
    ]
    actions = ["find_related_gl_entries"]

    class Media:
        css = {"all": ("admin/css/fix_action_buttons.css",)}

    def get_urls(self):
        from django.urls import path

        urls = super().get_urls()
        custom_urls = [
            path(
                "view-related-gl-entries/",
                self.admin_site.admin_view(self.view_related_gl_entries),
                name="items_itemledgerentries_view_gl_entries",
            ),
        ]
        return custom_urls + urls

    def view_related_gl_entries(self, request):
        """
        View to display related G/L entries in a table format
        """
        from django.shortcuts import render
        from financials.models import GeneralLedgerEntry

        # Get IDs from query string
        item_entry_ids = request.GET.get("ids", "").split(",")

        if not item_entry_ids or item_entry_ids == [""]:
            from django.contrib import messages

            messages.error(request, "No item ledger entries selected")
            return HttpResponseRedirect(
                reverse("admin:items_itemledgerentries_changelist")
            )

        # Get the item ledger entries
        item_entries = ItemLedgerEntries.objects.filter(id__in=item_entry_ids)

        # Get transaction numbers and document numbers
        transaction_nos = list(
            item_entries.exclude(transaction_no__isnull=True)
            .exclude(transaction_no="")
            .values_list("transaction_no", flat=True)
            .distinct()
        )
        document_nos = list(
            item_entries.values_list("document_no", flat=True).distinct()
        )

        # Find matching G/L entries
        gl_entries = GeneralLedgerEntry.objects.none()

        if transaction_nos:
            gl_entries = GeneralLedgerEntry.objects.filter(
                transaction_no__in=transaction_nos
            )

        # If no transaction_nos, try document_nos
        if not gl_entries.exists() and document_nos:
            gl_entries = GeneralLedgerEntry.objects.filter(document_no__in=document_nos)

        # Order entries
        gl_entries = gl_entries.select_related("gl_account", "user").order_by(
            "posting_date", "document_no"
        )

        # Find related Value Entries
        from items.models import ValueEntry

        value_entries = ValueEntry.objects.none()

        # First try by item_ledger_entry_no (most accurate)
        value_entries = ValueEntry.objects.filter(item_ledger_entry_no__in=item_entries)

        # If not found, try by transaction_no
        if not value_entries.exists() and transaction_nos:
            value_entries = ValueEntry.objects.filter(
                transaction_no__in=transaction_nos
            )

        # If still not found, try by document_no
        if not value_entries.exists() and document_nos:
            value_entries = ValueEntry.objects.filter(document_no__in=document_nos)

        value_entries = value_entries.select_related(
            "item", "general_product_posting_group", "inventory_posting_group"
        ).order_by("posting_date", "document_no")

        context = {
            "title": "Related G/L Entries",
            "item_entries": item_entries,
            "gl_entries": gl_entries,
            "value_entries": value_entries,
            "transaction_nos": transaction_nos,
            "document_nos": document_nos,
            "selected_ids": [int(id) for id in item_entry_ids if id],
            "opts": self.model._meta,
        }

        return render(
            request, "admin/items/itemledgerentries/related_gl_entries.html", context
        )

    @admin.action(description="Find Related G/L Entries")
    def find_related_gl_entries(self, request, queryset):
        """
        Find all G/L entries that were created when these item ledger entries were posted.
        Redirects to a dedicated view page showing the entries in table format.
        """
        from django.http import HttpResponseRedirect
        from django.urls import reverse

        # Get IDs of selected entries
        entry_ids = ",".join(str(entry.id) for entry in queryset)

        # Redirect to the view page
        url = reverse("admin:items_itemledgerentries_view_gl_entries")
        return HttpResponseRedirect(f"{url}?ids={entry_ids}")


@admin.register(ValueEntry)
class ValueEntryAdmin(admin.ModelAdmin):
    class EmptyDimensionFieldsFilter(admin.SimpleListFilter):
        title = "Empty dimensions"
        parameter_name = "dimension_empty"

        def lookups(self, request, model_admin):
            return (
                ("no_set", "Missing dimension set"),
                ("no_dim1", "Missing global dimension 1"),
                ("no_dim2", "Missing global dimension 2"),
                ("any", "Missing any (set or global dimensions)"),
            )

        def queryset(self, request, queryset):
            from django.db.models import Q

            v = self.value()
            if v == "no_set":
                return queryset.filter(dimension_set__isnull=True)
            if v == "no_dim1":
                return queryset.filter(global_dimension_1__isnull=True)
            if v == "no_dim2":
                return queryset.filter(global_dimension_2__isnull=True)
            if v == "any":
                return queryset.filter(
                    Q(dimension_set__isnull=True)
                    | Q(global_dimension_1__isnull=True)
                    | Q(global_dimension_2__isnull=True)
                )
            return queryset

    list_display = (
        "item",
        "entry_type",
        "document_no",
        "cost_amount",
        "cost_amount_non_invtbl",
        "cost_per_unit",
        "item_ledger_entry_quantity",
        "invoiced_quantity",
        "general_product_posting_group",
        "inventory_posting_group",
        "dimension_set",
        "global_dimension_1",
        "global_dimension_2",
        "transaction_no",
    )
    search_fields = ["item__item_name", "document_no", "transaction_no"]
    list_select_related = (
        "item",
        "general_product_posting_group",
        "inventory_posting_group",
        "dimension_set",
        "global_dimension_1",
        "global_dimension_2",
    )
    list_filter = (EmptyDimensionFieldsFilter,)


@admin.register(ItemJournalTemplate)
class ItemJournalTemplateAdmin(admin.ModelAdmin):
    """
    Admin interface for Item Journal Template model.
    """

    list_display = ["name", "description", "type", "no_series"]
    list_filter = ["type"]
    search_fields = ["name", "description"]
    readonly_fields = ["created_at", "updated_at", "system_id"]

    fieldsets = (
        (
            "Template Information",
            {
                "fields": (
                    "name",
                    "description",
                    "type",
                    "no_series",
                )
            },
        ),
        (
            "System Information",
            {
                "fields": ("system_id", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Filter fields based on context"""
        if db_field.name == "no_series":
            from setup.models import NoSeries

            kwargs["queryset"] = NoSeries.objects.all().order_by("code")
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(ItemTrackingCodes)
class ItemTrackingCodesAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "description",
        "require_serial_no",
        "require_lot_no",
        "require_expiry_date",
    )
    search_fields = ["code", "description"]


@admin.register(TrackingSpecification)
class TrackingSpecificationAdmin(admin.ModelAdmin):
    list_display = ("item", "serial_no", "lot_no", "expiry_date")
    search_fields = ["item__item_name", "serial_no", "lot_no"]


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ("code", "description")
    search_fields = ["code", "description"]

    fieldsets = [
        (
            "Location",
            {
                "fields": ("code", "description"),
                "description": (
                    "Changing the code updates inventory/posting setup references. "
                    "To rename a branch, prefer Setup → Branches or "
                    "manage.py tenant_command rename_branch_dimension_value."
                ),
            },
        ),
        (
            "Address",
            {
                "fields": ("address", "city", "phone", "email"),
            },
        ),
    ]

    def save_model(self, request, obj, form, change):
        if not change:
            super().save_model(request, obj, form, change)
            return

        from django.contrib import messages
        from items.location_code_rename import rename_location_code

        old_code = (
            Location.objects.filter(pk=obj.pk).values_list("code", flat=True).first()
        )
        if old_code is None:
            super().save_model(request, obj, form, change)
            return

        if (old_code or "").strip() == (obj.code or "").strip():
            super().save_model(request, obj, form, change)
            return

        try:
            rename_location_code(
                old_code,
                obj.code,
                description=obj.description,
                address=obj.address,
                city=obj.city,
                phone=obj.phone,
                email=obj.email,
            )
        except ValueError as exc:
            messages.error(request, str(exc))
            return
        messages.success(
            request,
            f"Location code renamed from {old_code!r} to {obj.code!r} "
            "(related posting and ledger rows were updated).",
        )


@admin.register(PhysInventoryLedgerEntry)
class PhysInventoryLedgerEntryAdmin(admin.ModelAdmin):
    """
    Admin interface for Physical Inventory Ledger Entry model.
    Read-only view for audit trail of physical inventory counts.
    """

    list_display = [
        "entry_no",
        "posting_date",
        "document_no",
        "item_no",
        "location_code",
        "qty_expected",
        "qty_phys_inventory",
        "quantity",
        "entry_type",
        "user",
    ]
    list_filter = ["posting_date", "entry_type", "location_code", "user"]
    search_fields = ["document_no", "item_no", "item__item_name", "description"]
    readonly_fields = [
        "entry_no",
        "document_no",
        "posting_date",
        "item",
        "item_no",
        "description",
        "location_code",
        "qty_expected",
        "qty_phys_inventory",
        "quantity",
        "entry_type",
        "unit_of_measure",
        "unit_amount",
        "unit_cost",
        "user",
        "item_ledger_entry",
        "journal_batch",
        "created_at",
        "updated_at",
        "system_id",
        "variance_percentage",
    ]
    date_hierarchy = "posting_date"

    fieldsets = (
        (
            "Document Information",
            {
                "fields": (
                    "entry_no",
                    "document_no",
                    "posting_date",
                    "journal_batch",
                )
            },
        ),
        (
            "Item Information",
            {
                "fields": (
                    "item",
                    "item_no",
                    "description",
                    "location_code",
                )
            },
        ),
        (
            "Count Information (Audit Trail)",
            {
                "fields": (
                    "qty_expected",
                    "qty_phys_inventory",
                    "quantity",
                    "variance_percentage",
                    "entry_type",
                )
            },
        ),
        (
            "Valuation",
            {
                "fields": (
                    "unit_of_measure",
                    "unit_amount",
                    "unit_cost",
                )
            },
        ),
        (
            "Links & Audit",
            {
                "fields": (
                    "user",
                    "item_ledger_entry",
                )
            },
        ),
        (
            "System Information",
            {
                "fields": ("system_id", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    def has_add_permission(self, request):
        """Physical inventory ledger entries cannot be added manually."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Physical inventory ledger entries cannot be deleted (audit trail)."""
        return False

    def has_change_permission(self, request, obj=None):
        """Physical inventory ledger entries cannot be modified (audit trail)."""
        return False


admin.site.register(ItemImages)


class ItemJournalPreviewProcessor:
    """Handles the preview of item journal entries with support for different entry types.

    This class generates preview data for ledger entries, value entries, and inventory adjustments
    for various types of item transactions without creating actual database entries.
    """

    def __init__(self, journal_entry, request, receipt_no=None):
        """Initialize the preview processor with required parameters.

        Args:
            journal_entry: The journal entry to preview
            request: The current HTTP request
            receipt_no: Optional receipt number for the transaction
        """
        self.journal_entry = journal_entry
        self.request = request
        self.receipt_no = receipt_no
        # Branch for ItemLedgerEntries: prefer X-Branch-Id (API), else user.global_dimension_1
        from dimension.branch_filter import get_branch_for_request

        self.global_dimension_1_value = get_branch_for_request(request)
        if not self.global_dimension_1_value:
            self.global_dimension_1_value = getattr(request.user, "global_dimension_1", None)
        self.entry_processors = {
            EntryType.PositiveAdjustment.name: self._preview_positive_adjustment,
            EntryType.NegativeAdjustment.name: self._preview_negative_adjustment,
            EntryType.Sales.name: self._preview_sales,
            EntryType.Purchase.name: self._preview_purchase,
            # Production order item journals (same inventory mechanics as adjustments)
            EntryType.Consumption.name: self._preview_negative_adjustment,
            EntryType.Output.name: self._preview_positive_adjustment,
        }
        self.preview_data = {
            "gl_entries": [],
            "item_entries": [],
            "value_entries": [],
            "customer_entries": [],
            "phys_inventory_entries": [],
        }

    def _validate_quantity_balance(self):
        """
        Validate that the total quantity from tracking specifications equals the expected quantity.
        This function checks if the sum of all tracking specification quantities matches
        the expected quantity based on the journal entry quantity and unit of measure.
        """
        try:
            # Get the item journal and its unit of measure
            item_journal = self.journal_entry
            item_unit_of_measure = ItemUnitOfMeasure.objects.get(
                id=item_journal.item_unit_of_measure.id
            )

            # Calculate expected quantity
            expected_quantity = int(item_journal.quantity) * int(
                item_unit_of_measure.quantity_per_unit
            )

            # Get all tracking specifications for this item journal
            specifications = TrackingSpecification.objects.filter(
                item_journal=item_journal.id, item=item_journal.item
            )

            # Calculate total quantity from specifications
            total_quantity = (
                specifications.aggregate(total=models.Sum("quantity_base"))["total"]
                or 0
            )

            # Only validate quantities if the item has tracking code
            if item_journal.item.tracking_code:
                # Check if quantities match
                if total_quantity != expected_quantity:
                    messages.error(
                        self.request,
                        f"Quantity mismatch for document {item_journal.document_no}: "
                        f"Expected {expected_quantity} (from {item_journal.quantity} × {item_unit_of_measure.quantity_per_unit}), "
                        f"but tracking specifications total {total_quantity}. "
                        f"Please ensure all items have proper tracking specifications.",
                    )
                    return False

            return True

        except ItemUnitOfMeasure.DoesNotExist:
            messages.error(
                self.request,
                f"Unit of measure not found for document {self.journal_entry.document_no}",
            )
            return False
        except Exception as e:
            messages.error(
                self.request,
                f"Error validating quantity balance for document {self.journal_entry.document_no}: {str(e)}",
            )
            return False

    def _validate(self):
        """
        if item has item tracking code, then it should have tracking specification
        """
        item = self.journal_entry.item
        item_tracking_specification_count = TrackingSpecification.objects.filter(
            item_journal=self.journal_entry.id,
            item=item,
        ).count()

        """
           check if. item jouranl unit of measeure (quantity per unit) * quantity is shoulde be equal to the count of  item tracking specification
        """

        if not self.journal_entry.item_unit_of_measure:
            messages.error(
                self.request,
                f"Unit of measure is required for document {self.journal_entry.document_no}",
            )
            return False

        try:
            item_unit_of_measure = ItemUnitOfMeasure.objects.get(
                id=self.journal_entry.item_unit_of_measure.id
            )
        except ItemUnitOfMeasure.DoesNotExist:
            messages.error(
                self.request,
                f"Unit of measure not found for document {self.journal_entry.document_no}",
            )
            return False

        # Check quantity balance for all entry types that require tracking
        if self.journal_entry.entry_type in [
            EntryType.Purchase.name,
            EntryType.Sales.name,
            EntryType.PositiveAdjustment.name,
            EntryType.NegativeAdjustment.name,
            EntryType.Consumption.name,
            EntryType.Output.name,
        ]:
            if not self._validate_quantity_balance():
                return False

        if self.journal_entry.entry_type == EntryType.Purchase.name:
            if (
                int(item_unit_of_measure.quantity_per_unit)
                * int(self.journal_entry.quantity)
            ) != item_tracking_specification_count:
                messages.error(
                    self.request,
                    f"Item tracking specification  for document {self.journal_entry.document_no} has count {item_tracking_specification_count} is not equal to the quantity { int(self.journal_entry.quantity)  * int(item_unit_of_measure.quantity_per_unit) }",
                )
                return False
        # check if the unit amount is not zero and quantity is not zero
        if (
            self.journal_entry.quantity == 0
            or self.journal_entry.unit_amount == 0
            or len(self.journal_entry.description) == 0
        ):
            missing_fields = []
            if self.journal_entry.quantity == 0:
                missing_fields.append("quantity")
            if self.journal_entry.unit_amount == 0:
                missing_fields.append("unit amount")
            if len(self.journal_entry.description) == 0:
                missing_fields.append("description")
            messages.error(
                self.request,
                f"The following fields are required: {', '.join(missing_fields)} for document {self.journal_entry.document_no}",
            )
            return False
        return True

    def process(self):
        """Process the journal entry preview based on its type."""
        processor = self.entry_processors.get(self.journal_entry.entry_type)
        if processor:
            if not self._validate():
                return self.preview_data  # Return empty preview_data instead of None
            processor()
        return self.preview_data

    def _preview_positive_adjustment(self):
        """Preview positive adjustment entries."""
        self._preview_general_ledger_entries()
        item_ledger_entries = self._preview_item_ledger_entries()
        # Create value entries for each ledger entry
        for item_ledger_entry in item_ledger_entries:
            self._preview_value_entries(item_ledger_entry_no=item_ledger_entry)
        # Create physical inventory ledger entry if this is from phys. inventory journal
        if (
            self.journal_entry.journal_template
            and self.journal_entry.journal_template.type == "phys_inventory"
        ):
            self._preview_phys_inventory_ledger_entry()

    def _preview_negative_adjustment(self):
        """Preview negative adjustment entries."""
        # Calculate the actual quantity based on unit of measure conversion
        item_unit_of_measure = ItemUnitOfMeasure.objects.get(
            id=self.journal_entry.item_unit_of_measure.id
        )
        calculated_quantity = int(item_unit_of_measure.quantity_per_unit) * int(
            self.journal_entry.quantity
        )

        self._preview_general_ledger_entries()
        item_ledger_entries = self._preview_item_ledger_entries(
            quantity=-calculated_quantity,
            remaining_quantity=0,
            total=-self.journal_entry.total,
        )
        # Create value entries for each ledger entry
        for item_ledger_entry in item_ledger_entries:
            self._preview_value_entries(item_ledger_entry_no=item_ledger_entry)
        # Add inventory reduction preview
        self._preview_reduce_inventory(
            calculated_quantity, self.journal_entry.entry_type
        )
        # Create physical inventory ledger entry if this is from phys. inventory journal
        if (
            self.journal_entry.journal_template
            and self.journal_entry.journal_template.type == "phys_inventory"
        ):
            self._preview_phys_inventory_ledger_entry()

    def _preview_sales(self):
        """Preview sales entries."""
        # Calculate the actual quantity based on unit of measure conversion
        item_unit_of_measure = ItemUnitOfMeasure.objects.get(
            id=self.journal_entry.item_unit_of_measure.id
        )
        calculated_quantity = int(item_unit_of_measure.quantity_per_unit) * int(
            self.journal_entry.quantity
        )

        self._preview_general_ledger_entries()
        item_ledger_entries = self._preview_item_ledger_entries(
            quantity=-calculated_quantity,
            remaining_quantity=0,
            total=-self.journal_entry.total,
        )
        # Create value entries for each ledger entry
        for item_ledger_entry in item_ledger_entries:
            self._preview_value_entries(item_ledger_entry_no=item_ledger_entry)
        # Add inventory reduction preview
        self._preview_reduce_inventory(
            calculated_quantity, self.journal_entry.entry_type
        )

    def _preview_purchase(self):
        """Preview purchase entries."""
        self._preview_general_ledger_entries()

    def _preview_item_ledger_entries(self, **additional_fields):
        """Preview item ledger entries.

        Returns:
            list: List of preview ledger entries
        """
        item = self.journal_entry.item
        created_entries = []

        # Check if item has tracking code
        if item.tracking_code:
            # Get tracking specifications for this journal entry
            tracking_specifications = TrackingSpecification.objects.filter(
                item_journal=self.journal_entry.id, item=item
            )

            from items.services.item_journal_reversal import (
                build_tracked_line_quantity_and_total,
                merge_tracked_ledger_additional_fields,
            )

            # Create separate ledger entry for each tracking specification
            for spec in tracking_specifications:
                spec_quantity = int(spec.quantity_base or 0)
                if spec_quantity <= 0:
                    continue
                line_qty, line_total = build_tracked_line_quantity_and_total(
                    spec_quantity,
                    int(self.journal_entry.quantity or 0),
                    float(self.journal_entry.total or 0),
                    additional_fields,
                )
                line_remaining = (
                    additional_fields.get("remaining_quantity", spec_quantity)
                    if additional_fields.get("quantity", 0) < 0
                    else spec_quantity
                )

                base_fields = {
                    "posting_date": self.journal_entry.date,
                    "date": self.journal_entry.date,
                    "entry_type": self.journal_entry.entry_type,
                    "document_no": self.journal_entry.document_no,
                    "item": self.journal_entry.item.item_name,
                    "description": self.journal_entry.description,
                    "quantity": line_qty,
                    "remaining_quantity": line_remaining,
                    "unit_cost": self.journal_entry.unit_cost,
                    "total": line_total,
                    "unit_of_measure": self.journal_entry.item_unit_of_measure.unit_of_measure.code,
                    "transaction_no": self.receipt_no,
                    "lot_no": spec.lot_no,
                    "expiry_date": spec.expiry_date,
                    "serial_no": spec.serial_no,
                    "global_dimension_1": self.global_dimension_1_value,
                }
                merge_tracked_ledger_additional_fields(base_fields, additional_fields)

                # Add to preview data
                self.preview_data["item_entries"].append(base_fields)
                created_entries.append(base_fields)
        else:
            # No tracking required - create single ledger entry
            # Calculate the actual quantity based on unit of measure conversion
            item_unit_of_measure = ItemUnitOfMeasure.objects.get(
                id=self.journal_entry.item_unit_of_measure.id
            )
            calculated_quantity = int(item_unit_of_measure.quantity_per_unit) * int(
                self.journal_entry.quantity
            )

            base_fields = {
                "posting_date": self.journal_entry.date,
                "date": self.journal_entry.date,
                "entry_type": self.journal_entry.entry_type,
                "document_no": self.journal_entry.document_no,
                "item": self.journal_entry.item.item_name,
                "description": self.journal_entry.description,
                "quantity": calculated_quantity,
                "remaining_quantity": calculated_quantity,
                "unit_cost": self.journal_entry.unit_cost,
                "total": self.journal_entry.total,
                "unit_of_measure": self.journal_entry.item_unit_of_measure.unit_of_measure.code,
                "transaction_no": self.receipt_no,
                "global_dimension_1": self.global_dimension_1_value,
            }
            base_fields.update(**additional_fields)

            # Add to preview data
            self.preview_data["item_entries"].append(base_fields)
            created_entries.append(base_fields)

        return created_entries

    def _preview_general_ledger_entries(self):
        """Preview general ledger entries for FIFO costing method."""
        item = self.journal_entry.item
        customer = Customer.objects.get(customer_type=CustomerType.General.name)

        if item.costing_method != CostingMethod.FIFO.name:
            return

        if not self._validate_posting_groups(item):
            return

        posting_groups = self._get_posting_groups(item, customer)
        self._preview_gl_entries(posting_groups, customer, item)

    def _validate_posting_groups(self, item):
        """Validate that required posting groups are set on the item and customer (for sales)."""
        if not self._validate_item_posting_groups(item):
            return False

        if self.journal_entry.entry_type == EntryType.Sales.name:
            if not self._validate_customer_posting_groups():
                return False

        return True

    def _validate_item_posting_groups(self, item):
        """Validate that required posting groups are set on the item."""
        if (
            item.general_product_posting_group is None
            or item.inventory_posting_group is None
        ):
            missing_group = (
                "General product posting group"
                if item.general_product_posting_group is None
                else "Inventory posting group"
            )
            messages.error(
                self.request,
                f"Cannot process item '{item.item_name}' (ID: {item.no}): {missing_group} is required",
            )
            return False
        return True

    def _validate_customer_posting_groups(self):
        """Validate that required posting groups are set on the general customer for sales entries."""
        try:
            customer = Customer.objects.get(customer_type=CustomerType.General.name)

        except Customer.DoesNotExist:
            messages.error(
                self.request,
                "Cannot process sales entry: Please create a general customer first. "
                "Go to Customers > Add Customer and set the customer type as 'General'",
            )
            return False

        if (
            customer.general_business_posting_group is None
            or customer.customer_posting_group is None
        ):
            missing_group = (
                "General business posting group"
                if customer.general_business_posting_group is None
                else "Customer posting group"
            )
            messages.error(
                self.request,
                f"Cannot process sales entry: General customer missing {missing_group}",
            )
            return False

        return True

    def _preview_gl_entries(self, posting_groups, customer, item):
        """Preview the debit and credit GL entries."""
        general_posting_setup, inventory_posting_setup = posting_groups

        # inventory acccount got from the item through the inventory posting group
        inventory_account = inventory_posting_setup.inventory_account

        # Determine which account to use based on adjustment_type
        # Default to operational if not set (backward compatibility)
        adjustment_type = getattr(self.journal_entry, "adjustment_type", "operational")

        if adjustment_type == "opening_balance":
            # Use hardcoded Opening Balance account (9999)
            try:
                balancing_account = G_LAccount.objects.get(no="9999")
                balancing_account_name = balancing_account.name
            except G_LAccount.DoesNotExist:
                # Fallback to inventory adjustment account if 9999 doesn't exist
                balancing_account = general_posting_setup.inventory_adjustment_account
                balancing_account_name = balancing_account.name
        else:
            # Use operational adjustment account from General Posting Setup
            balancing_account = general_posting_setup.inventory_adjustment_account
            balancing_account_name = balancing_account.name

        # Inventory-out entries (negative adjustment + production consumption)
        is_negative_adjustment = self.journal_entry.entry_type in (
            EntryType.NegativeAdjustment.name,
            EntryType.Consumption.name,
        )

        # For negative adjustments, we swap the accounts and amounts
        if is_negative_adjustment:
            # Preview debit entry (Balancing Account - Inventory Adjustment or Opening Balance)
            self.preview_data["gl_entries"].append(
                {
                    "posting_date": self.journal_entry.date,
                    "document_type": None,
                    "document_no": self.journal_entry.document_no,
                    "gl_account": balancing_account_name,
                    "description": f"Negative Adjustment on {self.journal_entry.date}",
                    "amount": abs(self.journal_entry.total),
                    "balancing_account_type": BalacingAccountType.GL_Account.name,
                    "transaction_no": self.receipt_no,
                    # Dimensions: keep G/L in the same branch/dimension-set as the journal.
                    "global_dimension_1": self.journal_entry.global_dimension_1
                    or self.global_dimension_1_value,
                    "dimension_set": self.journal_entry.dimension_set,
                }
            )

            # Preview credit entry (Inventory Account)
            self.preview_data["gl_entries"].append(
                {
                    "posting_date": self.journal_entry.date,
                    "document_type": None,
                    "document_no": self.journal_entry.document_no,
                    "gl_account": inventory_account.name,
                    "description": f"Negative Adjustment on {self.journal_entry.date}",
                    "amount": -abs(self.journal_entry.total),
                    "balancing_account_type": BalacingAccountType.GL_Account.name,
                    "transaction_no": self.receipt_no,
                    "global_dimension_1": self.journal_entry.global_dimension_1
                    or self.global_dimension_1_value,
                    "dimension_set": self.journal_entry.dimension_set,
                }
            )

        elif self.journal_entry.entry_type in (
            EntryType.PositiveAdjustment.name,
            EntryType.Output.name,
        ):
            # Positive adjustment / production output (inventory in)
            # Preview debit entry (Inventory Account)
            self.preview_data["gl_entries"].append(
                {
                    "posting_date": self.journal_entry.date,
                    "document_type": None,
                    "document_no": self.journal_entry.document_no,
                    "gl_account": inventory_account.name,
                    "description": f"Positive Adjustment on {self.journal_entry.date}",
                    "amount": self.journal_entry.total,
                    "balancing_account_type": BalacingAccountType.GL_Account.name,
                    "transaction_no": self.receipt_no,
                    "global_dimension_1": self.journal_entry.global_dimension_1
                    or self.global_dimension_1_value,
                    "dimension_set": self.journal_entry.dimension_set,
                }
            )

            # Preview credit entry (Balancing Account - Inventory Adjustment or Opening Balance)
            self.preview_data["gl_entries"].append(
                {
                    "posting_date": self.journal_entry.date,
                    "document_type": None,
                    "document_no": self.journal_entry.document_no,
                    "gl_account": balancing_account_name,
                    "description": f"Positive Adjustment on {self.journal_entry.date}",
                    "amount": -self.journal_entry.total,
                    "balancing_account_type": BalacingAccountType.GL_Account.name,
                    "transaction_no": self.receipt_no,
                    "global_dimension_1": self.journal_entry.global_dimension_1
                    or self.global_dimension_1_value,
                    "dimension_set": self.journal_entry.dimension_set,
                }
            )

        elif EntryType.Sales.name == self.journal_entry.entry_type:
            cogs_account = general_posting_setup.cogs_account

            # Preview debit of cost of goods sold
            self.preview_data["gl_entries"].append(
                {
                    "posting_date": self.journal_entry.date,
                    "document_type": None,
                    "document_no": self.journal_entry.document_no,
                    "gl_account": cogs_account.name,
                    "description": f"Cost of Goods Sold on {self.journal_entry.document_no} {self.journal_entry.date}",
                    "amount": self.journal_entry.total,
                    "balancing_account_type": BalacingAccountType.GL_Account.name,
                    "transaction_no": self.receipt_no,
                    "global_dimension_1": self.journal_entry.global_dimension_1
                    or self.global_dimension_1_value,
                    "dimension_set": self.journal_entry.dimension_set,
                }
            )

            # Preview credit of inventory
            self.preview_data["gl_entries"].append(
                {
                    "posting_date": self.journal_entry.date,
                    "document_type": None,
                    "document_no": self.journal_entry.document_no,
                    "gl_account": inventory_account.name,
                    "description": f"Cost of Goods Sold on {self.journal_entry.document_no} {self.journal_entry.date}",
                    "amount": -self.journal_entry.total,
                    "balancing_account_type": BalacingAccountType.GL_Account.name,
                    "transaction_no": self.receipt_no,
                    "global_dimension_1": self.journal_entry.global_dimension_1
                    or self.global_dimension_1_value,
                    "dimension_set": self.journal_entry.dimension_set,
                }
            )

            receivables_account = customer.customer_posting_group.receivables_account

            # Preview invoice - debit of receivables account
            self.preview_data["gl_entries"].append(
                {
                    "posting_date": self.journal_entry.date,
                    "document_type": DOCUMENT_TYPE.Invoice.name,
                    "document_no": self.journal_entry.document_no,
                    "gl_account": receivables_account.name,
                    "description": f"Invoice on {self.journal_entry.document_no} {self.journal_entry.date}",
                    "amount": self.journal_entry.amount,
                    "balancing_account_type": BalacingAccountType.GL_Account.name,
                    "transaction_no": self.receipt_no,
                    "global_dimension_1": self.journal_entry.global_dimension_1
                    or self.global_dimension_1_value,
                    "dimension_set": self.journal_entry.dimension_set,
                }
            )

            # Preview invoice - credit of revenue account
            revenue_account = general_posting_setup.sales_account
            self.preview_data["gl_entries"].append(
                {
                    "posting_date": self.journal_entry.date,
                    "document_type": DOCUMENT_TYPE.Invoice.name,
                    "document_no": self.journal_entry.document_no,
                    "gl_account": revenue_account.name,
                    "description": f"Invoice on {self.journal_entry.document_no} {self.journal_entry.date}",
                    "amount": -self.journal_entry.amount,
                    "balancing_account_type": BalacingAccountType.GL_Account.name,
                    "transaction_no": self.receipt_no,
                    "global_dimension_1": self.journal_entry.global_dimension_1
                    or self.global_dimension_1_value,
                    "dimension_set": self.journal_entry.dimension_set,
                }
            )

            # Preview Invoice Customer Ledger Entry
            self.preview_data["customer_entries"].append(
                {
                    "posting_date": self.journal_entry.date,
                    "document_date": self.journal_entry.date,
                    "document_type": DOCUMENT_TYPE.Invoice.name,
                    "document_no": self.journal_entry.document_no,
                    "customer": customer.name,
                    "description": f"Invoice on {self.journal_entry.document_no} {self.journal_entry.date}",
                    "amount": self.journal_entry.amount,
                    "remaining_amount": self.journal_entry.amount,
                    "due_date": self.journal_entry.date,
                    "payment_method": customer.payment_method.name,
                    "transaction_no": self.receipt_no,
                }
            )

            # Preview payment - debit of cash account
            cash_account = customer.payment_method.bal_account_no
            self.preview_data["gl_entries"].append(
                {
                    "posting_date": self.journal_entry.date,
                    "document_type": DOCUMENT_TYPE.Payment.name,
                    "document_no": self.journal_entry.document_no,
                    "gl_account": cash_account.name,
                    "description": f"Payment on {self.journal_entry.document_no} {self.journal_entry.date}",
                    "amount": self.journal_entry.amount,
                    "balancing_account_type": BalacingAccountType.GL_Account.name,
                    "transaction_no": self.receipt_no,
                    "global_dimension_1": self.journal_entry.global_dimension_1
                    or self.global_dimension_1_value,
                    "dimension_set": self.journal_entry.dimension_set,
                }
            )

            # Preview payment - credit of receivables account
            self.preview_data["gl_entries"].append(
                {
                    "posting_date": self.journal_entry.date,
                    "document_type": DOCUMENT_TYPE.Payment.name,
                    "document_no": self.journal_entry.document_no,
                    "gl_account": receivables_account.name,
                    "description": f"Payment on {self.journal_entry.document_no} {self.journal_entry.date}",
                    "amount": -self.journal_entry.amount,
                    "balancing_account_type": BalacingAccountType.GL_Account.name,
                    "transaction_no": self.receipt_no,
                    "global_dimension_1": self.journal_entry.global_dimension_1
                    or self.global_dimension_1_value,
                    "dimension_set": self.journal_entry.dimension_set,
                }
            )

            # Preview Customer Payment Ledger Entry
            self.preview_data["customer_entries"].append(
                {
                    "posting_date": self.journal_entry.date,
                    "document_date": self.journal_entry.date,
                    "document_type": DOCUMENT_TYPE.Payment.name,
                    "document_no": self.journal_entry.document_no,
                    "customer": customer.name,
                    "description": f"Payment on {self.journal_entry.document_no} {self.journal_entry.date}",
                    "amount": -self.journal_entry.amount,
                    "remaining_amount": -self.journal_entry.amount,
                    "due_date": self.journal_entry.date,
                    "payment_method": customer.payment_method.name,
                    "transaction_no": self.receipt_no,
                }
            )

        elif EntryType.Purchase.name == self.journal_entry.entry_type:
            # Get unit of measure on the journal entry
            item = self.journal_entry.item
            journal_uom = self.journal_entry.item_unit_of_measure
            unit_of_measure = journal_uom.unit_of_measure

            quantity_per_entry, number_of_entries = self._calculate_base_quantities(
                item, unit_of_measure
            )

            total_base_units = number_of_entries
            unit_cost_per_base = self.journal_entry.unit_cost / total_base_units

            # Preview entries for each base unit
            for i in range(number_of_entries):
                # Preview debit entry (Inventory Account)
                self.preview_data["gl_entries"].append(
                    {
                        "posting_date": self.journal_entry.date,
                        "document_type": None,
                        "document_no": self.journal_entry.document_no,
                        "gl_account": inventory_account.name,
                        "description": f"Direct Cost on {self.journal_entry.document_no} {self.journal_entry.date}",
                        "amount": unit_cost_per_base,
                        "balancing_account_type": BalacingAccountType.GL_Account.name,
                        "transaction_no": self.receipt_no,
                        "global_dimension_1": self.journal_entry.global_dimension_1
                        or self.global_dimension_1_value,
                        "dimension_set": self.journal_entry.dimension_set,
                    }
                )

                # Preview credit entry (Direct cost applied account)
                self.preview_data["gl_entries"].append(
                    {
                        "posting_date": self.journal_entry.date,
                        "document_type": None,
                        "document_no": self.journal_entry.document_no,
                        "gl_account": inventory_account.name,
                        "description": f"Direct Cost on {self.journal_entry.document_no} {self.journal_entry.date}",
                        "amount": -unit_cost_per_base,
                        "balancing_account_type": BalacingAccountType.GL_Account.name,
                        "transaction_no": self.receipt_no,
                        "global_dimension_1": self.journal_entry.global_dimension_1
                        or self.global_dimension_1_value,
                        "dimension_set": self.journal_entry.dimension_set,
                    }
                )

    def _preview_value_entries(self, **additional_fields):
        """Preview value entries for the journal entry."""
        item = self.journal_entry.item

        # Get posting groups and setups
        posting_groups = self._get_value_entry_posting_groups(item)
        if not posting_groups:
            return None

        general_product_posting_group, inventory_posting_group = posting_groups

        # Get the item ledger entry from additional fields
        item_ledger_entry = additional_fields.get("item_ledger_entry_no")

        # Calculate quantities and costs based on the specific ledger entry
        if item_ledger_entry:
            quantity = item_ledger_entry["quantity"]
            total = item_ledger_entry["total"]
            # Calculate cost per unit for this specific ledger entry
            cost_per_unit = (total / quantity) if quantity else 0
        else:
            # Calculate the actual quantity based on unit of measure conversion
            item_unit_of_measure = ItemUnitOfMeasure.objects.get(
                id=self.journal_entry.item_unit_of_measure.id
            )
            calculated_quantity = int(item_unit_of_measure.quantity_per_unit) * int(
                self.journal_entry.quantity
            )
            quantity = calculated_quantity
            total = self.journal_entry.total
            cost_per_unit = self.journal_entry.unit_amount

        sales_amount = "0"
        if self.journal_entry.entry_type == EntryType.Sales.name:
            sales_amount = str(self.journal_entry.amount or total or 0)

        from items.value_entry_posting import bc_normalize_value_entry_fields

        ve_signs = bc_normalize_value_entry_fields(
            self.journal_entry.entry_type,
            quantity,
            total,
            cost_per_unit=cost_per_unit,
        )

        base_fields = {
            "posting_date": self.journal_entry.date,
            "entry_type": self.journal_entry.entry_type,
            "document_no": self.journal_entry.document_no,
            "description": self.journal_entry.description or "",
            "item": item.item_name,
            "general_product_posting_group": general_product_posting_group.code,
            "inventory_posting_group": inventory_posting_group.code,
            "transaction_no": self.receipt_no,
            "sales_amount": sales_amount,
            "global_dimension_1": self.global_dimension_1_value,
            **ve_signs,
        }

        base_fields.update(additional_fields)
        self.preview_data["value_entries"].append(base_fields)

    def _resolve_inventory_posting_setup(self, item):
        """
        Resolve InventoryPostingSetup deterministically for preview posting.

        Rules:
        - If journal has a Location, prefer an exact (location, inventory_posting_group) match.
          If missing, fall back to (location IS NULL, inventory_posting_group) as company default.
        - If journal has no Location, prefer (location IS NULL, inventory_posting_group).
          If none exists, only accept a single setup for that inventory_posting_group; otherwise error.
        """
        inv_group = item.inventory_posting_group
        loc = getattr(self.journal_entry, "location_code", None)

        if loc:
            exact = InventoryPostingSetup.objects.filter(
                location=loc, inventory_posting_group=inv_group
            )
            if exact.count() == 1:
                return exact.first()
            if exact.count() > 1:
                raise ValidationError(
                    f"Multiple InventoryPostingSetup records match Location '{loc}' and "
                    f"Inventory Posting Group '{inv_group}'. Please keep only one."
                )

        default_qs = InventoryPostingSetup.objects.filter(
            location__isnull=True, inventory_posting_group=inv_group
        )
        if default_qs.count() == 1:
            return default_qs.first()
        if default_qs.count() > 1:
            raise ValidationError(
                f"Multiple default InventoryPostingSetup records found for Inventory Posting Group "
                f"'{inv_group}' (Location is blank). Please keep only one."
            )

        any_qs = InventoryPostingSetup.objects.filter(inventory_posting_group=inv_group)
        if any_qs.count() == 1:
            return any_qs.first()
        if any_qs.count() == 0:
            raise InventoryPostingSetup.DoesNotExist(
                f"No InventoryPostingSetup found for Inventory Posting Group '{inv_group}'."
            )
        raise ValidationError(
            f"InventoryPostingSetup is ambiguous for Inventory Posting Group '{inv_group}'. "
            f"Add a default (blank Location) setup or specify a unique setup per Location."
        )

    def _get_value_entry_posting_groups(self, item):
        """Get posting groups for value entries."""
        try:
            customer = Customer.objects.get(customer_type=CustomerType.General.name)

            if self.journal_entry.entry_type in (
                EntryType.PositiveAdjustment.name,
                EntryType.NegativeAdjustment.name,
                EntryType.Consumption.name,
                EntryType.Output.name,
            ):
                general_posting_setup = GeneralPostingSetup.objects.get(
                    general_product_posting_group=item.general_product_posting_group,
                    general_business_posting_group__isnull=True,
                )

            elif EntryType.Sales.name == self.journal_entry.entry_type:
                general_posting_setup = GeneralPostingSetup.objects.get(
                    general_business_posting_group=customer.general_business_posting_group,
                    general_product_posting_group=item.general_product_posting_group,
                )

            general_product_posting_group = GeneralProductPostingGroup.objects.get(
                code=general_posting_setup.general_product_posting_group.code
            )

            inventory_posting_setup = self._resolve_inventory_posting_setup(item)
            inventory_posting_group = InventoryPostingGroup.objects.get(
                code=inventory_posting_setup.inventory_posting_group.code
            )

            return general_product_posting_group, inventory_posting_group

        except (
            GeneralPostingSetup.DoesNotExist,
            InventoryPostingSetup.DoesNotExist,
        ) as e:
            messages.error(
                self.request,
                f"Error creating value entry: Missing posting setup for item '{item.item_name}' - {str(e)}",
            )
            return None

    def _get_posting_groups(self, item, customer):
        """Get the posting groups for the item."""
        inventory_posting_setup = self._resolve_inventory_posting_setup(item)

        # Get general posting setup based on entry type
        if self.journal_entry.entry_type in (
            EntryType.PositiveAdjustment.name,
            EntryType.NegativeAdjustment.name,
            EntryType.Purchase.name,
            EntryType.Consumption.name,
            EntryType.Output.name,
        ):
            general_posting_setup = GeneralPostingSetup.objects.get(
                general_product_posting_group=item.general_product_posting_group,
                general_business_posting_group__isnull=True,
            )

            if EntryType.Sales.name == self.journal_entry.entry_type:
                general_posting_setup = GeneralPostingSetup.objects.get(
                    general_business_posting_group=customer.general_business_posting_group,
                    general_product_posting_group=item.general_product_posting_group,
                )

        return general_posting_setup, inventory_posting_setup

    def _calculate_base_quantities(self, item, journal_unit_of_measure):
        """Calculate quantities in base unit of measure."""
        journal_uom_conversion = ItemUnitOfMeasure.objects.get(
            item=item, unit_of_measure=journal_unit_of_measure
        )

        base_quantity = int(journal_uom_conversion.quantity_per_unit) * int(
            self.journal_entry.quantity
        )

        if item.tracking_code:
            number_of_entries = base_quantity
            quantity_per_entry = 1
        else:
            number_of_entries = 1
            quantity_per_entry = base_quantity

        return quantity_per_entry, number_of_entries

    def _preview_phys_inventory_ledger_entry(self):
        """Preview physical inventory ledger entry for audit trail."""
        # Get expected and physical quantities
        qty_expected = self.journal_entry.calculated_quantity or 0
        qty_phys_inventory = self.journal_entry.physical_quantity or 0
        quantity_variance = qty_phys_inventory - qty_expected

        phys_inventory_entry = {
            "document_no": self.journal_entry.document_no,
            "posting_date": self.journal_entry.date,
            "item_no": self.journal_entry.item.no,
            "description": self.journal_entry.description,
            "location_code": (
                self.journal_entry.location_code.code
                if self.journal_entry.location_code
                else ""
            ),
            "qty_expected": float(qty_expected),
            "qty_phys_inventory": float(qty_phys_inventory),
            "quantity": float(quantity_variance),
            "entry_type": self.journal_entry.entry_type,
            "unit_amount": (
                float(self.journal_entry.unit_amount)
                if self.journal_entry.unit_amount
                else None
            ),
            "unit_cost": float(self.journal_entry.unit_cost),
        }

        self.preview_data["phys_inventory_entries"].append(phys_inventory_entry)

    def _preview_reduce_inventory(self, quantity_to_reduce, entry_type):
        """Preview inventory reduction based on FIFO method (First In, First Out).

        This method shows what inventory entries would be reduced without actually
        modifying the database.

        Args:
            quantity_to_reduce: The quantity to reduce from inventory
            entry_type: The type of entry being processed
        """
        remaining = quantity_to_reduce
        # For items with tracking (lot numbers), order by expiry date first (FEFO - First Expired, First Out)
        # For items without tracking, use FIFO (First In, First Out) based on created_at
        if self.journal_entry.item.tracking_code:
            # Items with tracking: order by expiry_date (earliest first), then by created_at
            entries = ItemLedgerEntries.objects.filter(
                item=self.journal_entry.item, remaining_quantity__gt=0
            ).order_by(
                models.F("expiry_date").asc(
                    nulls_last=True
                ),  # Items without expiry date go last
                "created_at",
            )
        else:
            # Items without tracking: use FIFO based on created_at
            entries = ItemLedgerEntries.objects.filter(
                item=self.journal_entry.item, remaining_quantity__gt=0
            ).order_by("created_at")

        inventory_reductions = []

        for entry in entries:
            if remaining <= 0:
                break

            reduction = min(entry.remaining_quantity, remaining)
            inventory_reductions.append(
                {
                    "entry_id": entry.id,
                    "document_no": entry.document_no,
                    "current_remaining": entry.remaining_quantity,
                    "reduction_amount": reduction,
                    "new_remaining": entry.remaining_quantity - reduction,
                    "entry_date": entry.date,
                    "lot_no": entry.lot_no,
                    "expiry_date": entry.expiry_date,
                }
            )

            remaining -= reduction

        # Add inventory reduction preview to the preview data
        self.preview_data["inventory_reductions"] = {
            "total_quantity_to_reduce": quantity_to_reduce,
            "entry_type": entry_type,
            "reductions": inventory_reductions,
            "remaining_after_reduction": remaining,
            "warning": remaining > 0,
        }

        if remaining > 0:
            # Add warning to preview data
            self.preview_data["warnings"] = self.preview_data.get("warnings", [])
            self.preview_data["warnings"].append(
                f"Warning: Not enough inventory to fulfill the {entry_type} for {self.journal_entry.item.item_name}. "
                f"Still need {remaining} more units."
            )
