#  def _create_general_ledger_entries(self):
    #     item = Item.objects.get(id=self.journalentry.item.id)
    #     print(item.costing_method)
    #     print(item.costing_method == CostingMethod.FIFO.name)
    #     if item.costing_method == CostingMethod.FIFO.name:
    #         print("entringe")
    #         if (
    #             item.general_product_posting_group is None
    #             or item.inventory_posting_group is None
    #         ):
    #             messages.error(
    #                 self.request,
    #                 f"Cannot process item '{item.item_name}' (ID: {item.id}): "
    #                 + (
    #                     "General product posting group is required"
    #                     if item.general_product_posting_group is None
    #                     else "Inventory posting group is required"
    #                 ),
    #             )
    #             return
    #         else:
    #             print("i ame running---------------------------------")
    #             general_product_posting_group = GeneralPostingSetup.objects.get(
    #                 general_product_posting_group=item.general_product_posting_group
    #             )
    #             inventory_posting_group = InventoryPostingSetup.objects.get(
    #                 inventory_posting_group=item.inventory_posting_group
    #             )

    #             inventory_account_balaning_account = (
    #                 general_product_posting_group.inventory_adjustment_account
    #             )
    #             inventory_account = inventory_posting_group.inventory_account
    #             print(inventory_account_balaning_account)
    #             print(inventory_account)
    #             print(BalacingAccountType.GL_Account.name)
    #             # debit
    #             gl_entries_debit = GeneralLedgerEntry.objects.create(
    #                 posting_date=self.journalentry.date,
    #                 document_no=self.journalentry.document_no,
    #                 gl_account=inventory_account,
    #                 description=f"Direct Cost applied on {self.journalentry.date}",
    #                 amount=self.journalentry.total,
    #                 balancing_account_type=BalacingAccountType.GL_Account.name,
    #                 user=self.request.user,
    #             )
    #             # credit
    #             gl_entries_credit = GeneralLedgerEntry.objects.create(
    #                 posting_date=self.journalentry.date,
    #                 document_no=self.journalentry.document_no,
    #                 gl_account=inventory_account_balaning_account,
    #                 description=f"Direct Cost applied on {self.journalentry.date}",
    #                 amount=self.journalentry.total * -1,
    #                 balancing_account_type=BalacingAccountType.GL_Account.name,
    #                 user=self.request.user,
    #             )
                # item_ledger_entry = GeneralLedgerEntries.objects.create(
                #     inventory_account_balancing_account=inventory_account_balancing_account,
                #     inventory_account=inventory_account,
                #     quantity=self.journalentry.quantity,
                #     unit_cost=self.journalentry.unit_cost,
                #     total=self.journalentry.total,
                # )

        # pass

    # def _create_ledger_entry(self, **additional_fields):
    #     base_fields = {
    #         "item": self.journalentry.item,
    #         "entry_type": self.journalentry.entry_type,
    #         "document_no": self.journalentry.document_no,
    #         "description": self.journalentry.description,
    #         "unit_of_measure": self.journalentry.unit_of_measure,
    #         "unit_cost": self.journalentry.unit_cost,
    #         "date": self.journalentry.date,
    #         "user": self.journalentry.user,
    #         "receipt_no": self.receipt_no,
    #     }
    #     base_fields.update(**additional_fields)
    #     return ItemLedgerEntries.objects.create(**base_fields)

    # def _create_value_entries(self, **additional_fields):
    #     item = Item.objects.get(id=self.journalentry.item.id)
    #     general_product_posting_setup = GeneralPostingSetup.objects.get(
    #         general_product_posting_group=item.general_product_posting_group
    #     )

    #     general_product_posting_group = GeneralProductPostingGroup.objects.get(
    #         id=general_product_posting_setup.general_product_posting_group.id
    #     )

    #     inventory_posting_setup = InventoryPostingSetup.objects.get(
    #         inventory_posting_group=item.inventory_posting_group
    #     )
    #     inventory_posting_group = InventoryPostingGroup.objects.get(
    #         id=inventory_posting_setup.inventory_posting_group.id
    #     )
    #     print("========================")
    #     print(general_product_posting_group)
    #     print(inventory_posting_group)
    #     print("========================")
    #     bases_fields = {
    #         "posting_date": self.journalentry.date,
    #         "entry_type": self.journalentry.entry_type,
    #         "document_no": self.journalentry.document_no,
    #         "cost_amount": self.journalentry.total,
    #         "cost_per_unit": self.journalentry.unit_cost,
    #         "item_ledger_entry_quantity": self.journalentry.quantity,
    #         "invoiced_quantity": self.journalentry.quantity,
    #         "item": self.journalentry.item,
    #         "general_product_posting_group": general_product_posting_group,
    #         "inventory_posting_group": inventory_posting_group
    #         # "item_ledger_entry_no"
    #     }

    #     bases_fields.update(**additional_fields)

    #     return ValueEntry.objects.create(**bases_fields)

