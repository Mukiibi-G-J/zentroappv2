"""
Seed script for the page engine.
Run via management command: python manage.py seed_pages
"""
from pages.models import Page, PageControl, PageControlField, PageAction, TableRelation


ACCOUNT_TYPE_RELATIONS = (
    ('Customer', 'Customer'),
    ('Vendor', 'Vendor'),
    ('G/L Account', 'G_LAccount'),
)


GENERAL_JOURNAL_ACCOUNT_TYPE_RELATIONS = (
    ('Customer', 'Customer'),
    ('Vendor', 'Vendor'),
    ('G/L Account', 'G_LAccount'),
    ('Bank Account', 'BankAccount'),
)

PURCHASE_INVOICE_LINE_TYPE_RELATIONS = (
    ('item', 'Item'),
    ('resource', 'Resource'),
    ('gl_account', 'G_LAccount'),
)

# Replaced by unified virtual ``no`` column on purchase invoice line subforms.
PURCHASE_LINE_LEGACY_NO_FIELD_NAMES = ('item', 'resource', 'gl_account')


def seed():
    # ── Card pages first (list pages reference them) ───────────────────────────

    item_card = _seed_item_card()

    cust_card, _ = Page.objects.get_or_create(
        name='CustomerCard',
        defaults={
            'caption': 'Customer Card',
            'source_table': 'Customer',
            'page_type': 'Card',
            'editable': True,
            'insert_allowed': True,
            'delete_allowed': False,
            'modify_allowed': False,
            'title_field': 'name',
        },
    )
    cust_card.delete_allowed = False
    cust_card.modify_allowed = False
    cust_card.save(update_fields=['delete_allowed', 'modify_allowed'])
    cust_card_ctrl, _ = PageControl.objects.get_or_create(
        page=cust_card,
        name='CustomerCardGroup',
        defaults={
            'control_type': 'Group',
            'caption': 'General',
            'source_table': 'Customer',
            'show_caption': True,
            'editable': False,
            'visible': True,
        },
    )
    cust_card_ctrl.show_caption = True
    cust_card_ctrl.editable = False
    cust_card_ctrl.save(update_fields=['show_caption', 'editable'])
    _seed_fields(cust_card_ctrl, cust_card, [
        dict(name='no',           caption='No.',          field_type='Code',    visible=True, editable=False, primary_key=True,  tab_index=0),
        dict(name='name',         caption='Name',         field_type='Text',    visible=True, editable=True,  primary_key=False, tab_index=1),
        dict(name='phone_number', caption='Phone No.',    field_type='Text',    visible=True, editable=True,  primary_key=False, tab_index=2),
        dict(name='address',      caption='Address',      field_type='Text',    visible=True, editable=True,  primary_key=False, tab_index=3),
        dict(name='address_2',    caption='Address 2',    field_type='Text',    visible=True, editable=True,  primary_key=False, tab_index=4),
        dict(name='city',         caption='City',         field_type='Text',    visible=True, editable=True,  primary_key=False, tab_index=5),
        dict(name='contact',      caption='Contact',      field_type='Text',    visible=True, editable=True,  primary_key=False, tab_index=6),
        dict(name='credit_limit', caption='Credit Limit', field_type='Decimal', visible=True, editable=True,  primary_key=False, tab_index=7),
        dict(name='balance',      caption='Balance (LCY)',field_type='Decimal', visible=True, editable=False, primary_key=False, tab_index=8),
        dict(name='blocked',      caption='Blocked',      field_type='Boolean', visible=True, editable=True,  primary_key=False, tab_index=9),
    ])

    vendor_card, _ = Page.objects.get_or_create(
        name='VendorCard',
        defaults={
            'caption': 'Vendor Card',
            'source_table': 'Vendor',
            'page_type': 'Card',
            'editable': True,
            'insert_allowed': True,
            'delete_allowed': True,
            'modify_allowed': True,
            'title_field': 'name',
        },
    )
    vendor_card_ctrl, _ = PageControl.objects.get_or_create(
        page=vendor_card,
        name='VendorCardGroup',
        defaults={
            'control_type': 'Group',
            'caption': 'General',
            'source_table': 'Vendor',
            'show_caption': False,
            'editable': True,
            'visible': True,
        },
    )
    _seed_fields(vendor_card_ctrl, vendor_card, [
        dict(name='no',      caption='No.',     field_type='Code',    visible=True, editable=False, primary_key=True,  tab_index=0),
        dict(name='name',    caption='Name',    field_type='Text',    visible=True, editable=True,  primary_key=False, tab_index=1),
        dict(name='phone',   caption='Phone',   field_type='Text',    visible=True, editable=True,  primary_key=False, tab_index=2),
        dict(name='mobile',  caption='Mobile',  field_type='Text',    visible=True, editable=True,  primary_key=False, tab_index=3),
        dict(name='email',   caption='Email',   field_type='Text',    visible=True, editable=True,  primary_key=False, tab_index=4),
        dict(name='address', caption='Address', field_type='Text',    visible=True, editable=True,  primary_key=False, tab_index=5),
        dict(name='city',    caption='City',    field_type='Text',    visible=True, editable=True,  primary_key=False, tab_index=6),
        dict(name='country', caption='Country', field_type='Text',    visible=True, editable=True,  primary_key=False, tab_index=7),
        dict(name='balance', caption='Balance (LCY)', field_type='Decimal', visible=True, editable=False, primary_key=False, tab_index=8),
        dict(name='blocked', caption='Blocked', field_type='Boolean', visible=True, editable=True,  primary_key=False, tab_index=9),
    ])

    bank_card, _ = Page.objects.get_or_create(
        name='BankAccountCard',
        defaults={
            'caption': 'Bank Account',
            'source_table': 'BankAccount',
            'page_type': 'Card',
            'editable': True,
            'insert_allowed': True,
            'delete_allowed': True,
            'modify_allowed': True,
            'title_field': 'name',
        },
    )
    bank_card_ctrl, _ = PageControl.objects.get_or_create(
        page=bank_card,
        name='BankAccountCardGroup',
        defaults={
            'control_type': 'Group',
            'caption': 'General',
            'source_table': 'BankAccount',
            'show_caption': False,
            'editable': True,
            'visible': True,
        },
    )
    _seed_fields(bank_card_ctrl, bank_card, [
        dict(name='no',                         caption='No.',                    field_type='Code',    visible=True, editable=False, primary_key=True,  tab_index=0),
        dict(name='name',                       caption='Name',                   field_type='Text',    visible=True, editable=True,  primary_key=False, tab_index=1),
        dict(name='bank_account_posting_group', caption='Bank Acc. Posting Group', field_type='Code',    visible=True, editable=True,  primary_key=False, tab_index=2),
        dict(name='bank_account_no',            caption='Account No.',            field_type='Text',    visible=True, editable=True,  primary_key=False, tab_index=3),
        dict(name='bank_branch_no',             caption='Bank Branch No.',        field_type='Text',    visible=True, editable=True,  primary_key=False, tab_index=4),
        dict(name='address',                    caption='Address',                field_type='Text',    visible=True, editable=True,  primary_key=False, tab_index=5),
        dict(name='contact',                    caption='Contact',                field_type='Text',    visible=True, editable=True,  primary_key=False, tab_index=6),
        dict(name='min_balance',                caption='Min. Balance',           field_type='Decimal', visible=True, editable=True,  primary_key=False, tab_index=7),
        dict(name='balance',                    caption='Balance',                field_type='Decimal', visible=True, editable=False, primary_key=False, tab_index=8),
    ])

    # ── List pages — create and link card pages ────────────────────────────────

    items_page, _ = Page.objects.get_or_create(
        name='ItemList',
        defaults={
            'caption': 'Items',
            'source_table': 'Item',
            'page_type': 'List',
            'editable': True,
            'insert_allowed': True,
            'delete_allowed': True,
            'modify_allowed': True,
            'card_page': item_card,
        },
    )
    items_page.card_page = item_card
    items_page.save(update_fields=['card_page'])

    items_ctrl, _ = PageControl.objects.get_or_create(
        page=items_page,
        name='ItemListControl',
        defaults={
            'control_type': 'Repeater',
            'caption': 'Items',
            'source_table': 'Item',
            'show_caption': True,
            'editable': True,
            'visible': True,
        },
    )
    _seed_fields(items_ctrl, items_page, [
        dict(name='no',         caption='No.',        field_type='Code',    visible=True, editable=False, primary_key=True,  tab_index=0),
        dict(name='item_name',  caption='Item Name',  field_type='Text',    visible=True, editable=True,  primary_key=False, tab_index=1),
        dict(name='type',       caption='Type',       field_type='Enum',    visible=True, editable=True,  primary_key=False, tab_index=2),
        dict(
            name='unit_of_measure',
            caption='Unit of Measure',
            field_type='Code',
            visible=True,
            editable=True,
            primary_key=False,
            tab_index=3,
            has_table_relation=True,
            related_table='UnitOfMeasure',
            related_field='code',
            related_display_field='description',
        ),
        dict(name='unit_price', caption='Unit Price', field_type='Decimal', visible=True, editable=True,  primary_key=False, tab_index=4),
        dict(name='inventory',  caption='Inventory',  field_type='Integer', visible=True, editable=False, primary_key=False, tab_index=5),
        dict(name='blocked',    caption='Blocked',    field_type='Boolean', visible=True, editable=True,  primary_key=False, tab_index=6),
    ])
    _ensure_table_relation('Item', 'unit_of_measure', 'UnitOfMeasure')

    cust_page, _ = Page.objects.get_or_create(
        name='CustomerList',
        defaults={
            'caption': 'Customers',
            'source_table': 'Customer',
            'page_type': 'List',
            'editable': True,
            'insert_allowed': True,
            'delete_allowed': True,
            'modify_allowed': True,
            'card_page': cust_card,
        },
    )
    cust_page.card_page = cust_card
    cust_page.save(update_fields=['card_page'])

    cust_ctrl, _ = PageControl.objects.get_or_create(
        page=cust_page,
        name='CustomerListControl',
        defaults={
            'control_type': 'Repeater',
            'caption': 'Customers',
            'source_table': 'Customer',
            'show_caption': True,
            'editable': False,
            'visible': True,
        },
    )
    cust_ctrl.editable = False
    cust_ctrl.save(update_fields=['editable'])
    _seed_fields(cust_ctrl, cust_page, [
        dict(name='no',           caption='No.',      field_type='Code',    visible=True, editable=False, primary_key=True,  tab_index=0),
        dict(name='name',         caption='Name',     field_type='Text',    visible=True, editable=False, primary_key=False, tab_index=1),
        dict(name='phone_number', caption='Phone No.',field_type='Text',    visible=True, editable=False, primary_key=False, tab_index=2),
        dict(name='address',      caption='Address',  field_type='Text',    visible=True, editable=False, primary_key=False, tab_index=3),
        dict(name='balance',      caption='Balance',  field_type='Decimal', visible=True, editable=False, primary_key=False, tab_index=4),
        dict(name='blocked',      caption='Blocked',  field_type='Boolean', visible=True, editable=False, primary_key=False, tab_index=5),
    ])

    vendor_page, _ = Page.objects.get_or_create(
        name='VendorList',
        defaults={
            'caption': 'Vendors',
            'source_table': 'Vendor',
            'page_type': 'List',
            'editable': True,
            'insert_allowed': True,
            'delete_allowed': True,
            'modify_allowed': True,
            'card_page': vendor_card,
        },
    )
    vendor_page.card_page = vendor_card
    vendor_page.save(update_fields=['card_page'])

    vendor_ctrl, _ = PageControl.objects.get_or_create(
        page=vendor_page,
        name='VendorListControl',
        defaults={
            'control_type': 'Repeater',
            'caption': 'Vendors',
            'source_table': 'Vendor',
            'show_caption': True,
            'editable': False,
            'visible': True,
        },
    )
    vendor_ctrl.editable = False
    vendor_ctrl.save(update_fields=['editable'])
    _seed_fields(vendor_ctrl, vendor_page, [
        dict(name='no',      caption='No.',     field_type='Code',    visible=True, editable=False, primary_key=True,  tab_index=0),
        dict(name='name',    caption='Name',    field_type='Text',    visible=True, editable=False, primary_key=False, tab_index=1),
        dict(name='phone',   caption='Phone',   field_type='Text',    visible=True, editable=False, primary_key=False, tab_index=2),
        dict(name='email',   caption='E-Mail',  field_type='Text',    visible=True, editable=False, primary_key=False, tab_index=3),
        dict(name='balance', caption='Balance', field_type='Decimal', visible=True, editable=False, primary_key=False, tab_index=4),
        dict(name='blocked', caption='Blocked', field_type='Boolean', visible=True, editable=False, primary_key=False, tab_index=5),
    ])

    bank_page, _ = Page.objects.get_or_create(
        name='BankAccountList',
        defaults={
            'caption': 'Bank Accounts',
            'source_table': 'BankAccount',
            'page_type': 'List',
            'editable': True,
            'insert_allowed': True,
            'delete_allowed': True,
            'modify_allowed': True,
            'card_page': bank_card,
        },
    )
    bank_page.card_page = bank_card
    bank_page.save(update_fields=['card_page'])

    bank_ctrl, _ = PageControl.objects.get_or_create(
        page=bank_page,
        name='BankAccountListControl',
        defaults={
            'control_type': 'Repeater',
            'caption': 'Bank Accounts',
            'source_table': 'BankAccount',
            'show_caption': True,
            'editable': False,
            'visible': True,
        },
    )
    bank_ctrl.editable = False
    bank_ctrl.save(update_fields=['editable'])
    _seed_fields(bank_ctrl, bank_page, [
        dict(name='no',                         caption='No.',                    field_type='Code',    visible=True, editable=False, primary_key=True,  tab_index=0, freeze_column=True),
        dict(name='name',                       caption='Name',                   field_type='Text',    visible=True, editable=False, primary_key=False, tab_index=1),
        dict(name='bank_account_posting_group', caption='Bank Acc. Posting Group', field_type='Code',    visible=True, editable=False, primary_key=False, tab_index=2),
        dict(name='bank_account_no',            caption='Account No.',            field_type='Text',    visible=True, editable=False, primary_key=False, tab_index=3),
        dict(name='balance',                    caption='Balance',                field_type='Decimal', visible=True, editable=False, primary_key=False, tab_index=4),
    ])

    # ── Chart of Accounts (G/L Account) card + list ───────────────────────────

    gl_card, _ = Page.objects.get_or_create(
        name='GLAccountCard',
        defaults={
            'caption': 'G/L Account',
            'source_table': 'G_LAccount',
            'page_type': 'Card',
            'editable': True,
            'insert_allowed': True,
            'delete_allowed': True,
            'modify_allowed': True,
            'title_field': 'name',
        },
    )
    gl_card_ctrl, _ = PageControl.objects.get_or_create(
        page=gl_card,
        name='GLAccountCardGroup',
        defaults={
            'control_type': 'Group',
            'caption': 'General',
            'source_table': 'G_LAccount',
            'show_caption': False,
            'editable': True,
            'visible': True,
        },
    )
    _seed_fields(gl_card_ctrl, gl_card, [
        dict(name='no',              caption='No.',               field_type='Code',    visible=True, editable=True,  primary_key=True,  tab_index=0),
        dict(name='name',            caption='Name',              field_type='Text',    visible=True, editable=True,  primary_key=False, tab_index=1),
        dict(name='income_balance',  caption='Income/Balance',    field_type='Enum',    visible=True, editable=True,  primary_key=False, tab_index=2,
             enum_values='Income Statement,Balance Sheet'),
        dict(name='accountcategory', caption='Account Category', field_type='Enum',    visible=True, editable=True,  primary_key=False, tab_index=3,
             enum_values='Assets,Liabilities,Equity,Income,Cost of Goods Sold,Expense'),
        dict(name='debit_credit',   caption='Debit/Credit',      field_type='Enum',    visible=True, editable=True,  primary_key=False, tab_index=4,
             enum_values='Both,Debit,Credit'),
        dict(name='accounttype',    caption='Account Type',      field_type='Enum',    visible=True, editable=True,  primary_key=False, tab_index=5,
             enum_values='Posting,Heading,Total,Begin-Total,End-Total'),
        dict(name='totaling',        caption='Totaling',          field_type='Text',    visible=True, editable=True,  primary_key=False, tab_index=6),
        dict(name='direct_posting', caption='Direct Posting',    field_type='Boolean', visible=True, editable=True,  primary_key=False, tab_index=7),
        dict(name='blocked',        caption='Blocked',           field_type='Boolean', visible=True, editable=True,  primary_key=False, tab_index=8),
        dict(name='indentation',    caption='Indentation',       field_type='Integer', visible=True, editable=False, primary_key=False, tab_index=9),
        dict(name='balance',        caption='Balance',           field_type='Decimal', visible=True, editable=False, primary_key=False, tab_index=10),
    ])

    gl_list, _ = Page.objects.get_or_create(
        name='GLAccountList',
        defaults={
            'caption': 'Chart of Accounts',
            'source_table': 'G_LAccount',
            'page_type': 'List',
            'editable': False,
            'insert_allowed': True,
            'delete_allowed': False,
            'modify_allowed': False,
            'card_page': gl_card,
        },
    )
    gl_list.card_page = gl_card
    gl_list.caption = 'Chart of Accounts'
    gl_list.save(update_fields=['card_page', 'caption'])

    gl_list_ctrl, _ = PageControl.objects.get_or_create(
        page=gl_list,
        name='GLAccountListControl',
        defaults={
            'control_type': 'Repeater',
            'caption': 'Chart of Accounts',
            'source_table': 'G_LAccount',
            'show_caption': False,
            'editable': False,
            'visible': True,
        },
    )
    _seed_fields(gl_list_ctrl, gl_list, [
        dict(name='no',              caption='No.',            field_type='Code',    visible=True, editable=False, primary_key=True,  tab_index=0, freeze_column=True),
        dict(name='name',            caption='Name',           field_type='Text',    visible=True, editable=False, primary_key=False, tab_index=1),
        dict(name='income_balance',  caption='Income/Balance', field_type='Enum',    visible=True, editable=False, primary_key=False, tab_index=2),
        dict(name='accountcategory', caption='Account Category', field_type='Enum', visible=True, editable=False, primary_key=False, tab_index=3),
        dict(name='accounttype',     caption='Account Type',   field_type='Enum',    visible=True, editable=False, primary_key=False, tab_index=4),
        dict(name='direct_posting',  caption='Direct Posting', field_type='Boolean', visible=True, editable=False, primary_key=False, tab_index=5),
        dict(name='blocked',         caption='Blocked',        field_type='Boolean', visible=True, editable=False, primary_key=False, tab_index=6),
        dict(name='balance',         caption='Balance',        field_type='Decimal', visible=True, editable=False, primary_key=False, tab_index=7),
    ])

    # ── Ledger entry list pages (read-only, drill-down targets) ───────────────

    customer_ledger_page = _create_ledger_list_page(
        name='CustomerLedgerEntryList',
        caption='Customer Ledger Entries',
        source_table='CustomerLedgerEntry',
        context_filter_field='customer__no',
        fields=[
            dict(name='posting_date', caption='Posting Date', field_type='Date', tab_index=0),
            dict(name='document_type', caption='Document Type', field_type='Text', tab_index=1),
            dict(name='document_no', caption='Document No.', field_type='Code', tab_index=2),
            dict(name='description', caption='Description', field_type='Text', tab_index=3),
            dict(name='amount', caption='Amount', field_type='Decimal', tab_index=4),
            dict(name='remaining_amount', caption='Remaining Amount', field_type='Decimal', tab_index=5),
            dict(name='due_date', caption='Due Date', field_type='Date', tab_index=6),
            dict(name='customer__no', caption='Customer No.', field_type='Code', tab_index=7),
            dict(name='global_dimension_1', caption='Branch', field_type='Code', tab_index=8),
            dict(name='id', caption='Entry No.', field_type='Integer', tab_index=9, primary_key=True),
        ],
    )

    vendor_ledger_page = _create_ledger_list_page(
        name='VendorLedgerEntryList',
        caption='Vendor Ledger Entries',
        source_table='VendorLedger',
        context_filter_field='vendor__no',
        fields=[
            dict(name='posting_date', caption='Posting Date', field_type='Date', tab_index=0),
            dict(name='document_type', caption='Document Type', field_type='Text', tab_index=1),
            dict(name='document_no', caption='Document No.', field_type='Code', tab_index=2),
            dict(name='description', caption='Description', field_type='Text', tab_index=3),
            dict(name='amount', caption='Amount', field_type='Decimal', tab_index=4),
            dict(name='remaining_amount', caption='Remaining Amount', field_type='Decimal', tab_index=5),
            dict(name='due_date', caption='Due Date', field_type='Date', tab_index=6),
            dict(name='vendor__no', caption='Vendor No.', field_type='Code', tab_index=7),
            dict(name='global_dimension_1', caption='Branch', field_type='Code', tab_index=8),
            dict(name='id', caption='Entry No.', field_type='Integer', tab_index=9, primary_key=True),
        ],
    )

    _vendor_applied_fields = [
        dict(name='posting_date', caption='Posting Date', field_type='Date', tab_index=0),
        dict(name='document_type', caption='Document Type', field_type='Text', tab_index=1),
        dict(name='document_no', caption='Document No.', field_type='Code', tab_index=2),
        dict(name='description', caption='Description', field_type='Text', tab_index=3),
        dict(name='amount', caption='Amount', field_type='Decimal', tab_index=4),
        dict(name='remaining_amount', caption='Remaining Amount', field_type='Decimal', tab_index=5),
        dict(name='due_date', caption='Due Date', field_type='Date', tab_index=6),
        dict(name='vendor__no', caption='Vendor No.', field_type='Code', tab_index=7),
        dict(name='applies_to_id', caption='Applies-to ID', field_type='Code', tab_index=8),
        dict(name='id', caption='Entry No.', field_type='Integer', tab_index=9, primary_key=True),
    ]
    _customer_applied_fields = [
        dict(name='posting_date', caption='Posting Date', field_type='Date', tab_index=0),
        dict(name='document_type', caption='Document Type', field_type='Text', tab_index=1),
        dict(name='document_no', caption='Document No.', field_type='Code', tab_index=2),
        dict(name='description', caption='Description', field_type='Text', tab_index=3),
        dict(name='amount', caption='Amount', field_type='Decimal', tab_index=4),
        dict(name='remaining_amount', caption='Remaining Amount', field_type='Decimal', tab_index=5),
        dict(name='due_date', caption='Due Date', field_type='Date', tab_index=6),
        dict(name='customer__no', caption='Customer No.', field_type='Code', tab_index=7),
        dict(name='applies_to_id', caption='Applies-to ID', field_type='Code', tab_index=8),
        dict(name='id', caption='Entry No.', field_type='Integer', tab_index=9, primary_key=True),
    ]

    _create_applied_ledger_list_page(
        name='VendorAppliedEntriesList',
        caption='Applied Vendor Ledger Entries',
        source_table='VendorLedger',
        fields=_vendor_applied_fields,
    )
    _create_applied_ledger_list_page(
        name='CustomerAppliedEntriesList',
        caption='Applied Customer Ledger Entries',
        source_table='CustomerLedgerEntry',
        fields=_customer_applied_fields,
    )

    _detailed_vendor_fields = [
        dict(name='posting_date', caption='Posting Date', field_type='Date', tab_index=0),
        dict(name='entry_type', caption='Entry Type', field_type='Text', tab_index=1),
        dict(name='document_type', caption='Document Type', field_type='Text', tab_index=2),
        dict(name='document_no', caption='Document No.', field_type='Code', tab_index=3),
        dict(name='amount', caption='Amount', field_type='Integer', tab_index=4),
        dict(name='debit_amount', caption='Debit Amount', field_type='Integer', tab_index=5),
        dict(name='credit_amount', caption='Credit Amount', field_type='Integer', tab_index=6),
        dict(name='applied_vendor_ledger_entry_no', caption='Applied Entry No.', field_type='Integer', tab_index=7),
        dict(name='vendor__no', caption='Vendor No.', field_type='Code', tab_index=8),
        dict(name='entry_no', caption='Entry No.', field_type='Integer', tab_index=9, primary_key=True),
    ]
    _detailed_customer_fields = [
        dict(name='posting_date', caption='Posting Date', field_type='Date', tab_index=0),
        dict(name='entry_type', caption='Entry Type', field_type='Text', tab_index=1),
        dict(name='document_type', caption='Document Type', field_type='Text', tab_index=2),
        dict(name='document_no', caption='Document No.', field_type='Code', tab_index=3),
        dict(name='amount', caption='Amount', field_type='Integer', tab_index=4),
        dict(name='debit_amount', caption='Debit Amount', field_type='Integer', tab_index=5),
        dict(name='credit_amount', caption='Credit Amount', field_type='Integer', tab_index=6),
        dict(name='applied_customer_ledger_entry_no', caption='Applied Entry No.', field_type='Integer', tab_index=7),
        dict(name='customer__no', caption='Customer No.', field_type='Code', tab_index=8),
        dict(name='entry_no', caption='Entry No.', field_type='Integer', tab_index=9, primary_key=True),
    ]

    _create_applied_ledger_list_page(
        name='DetailedVendorLedgerEntryList',
        caption='Detailed Vendor Ledger Entries',
        source_table='DetailedVendorLedgerEntry',
        fields=_detailed_vendor_fields,
    )
    _create_applied_ledger_list_page(
        name='DetailedCustomerLedgerEntryList',
        caption='Detailed Customer Ledger Entries',
        source_table='DetailedCustomerLedgerEntry',
        fields=_detailed_customer_fields,
    )

    _seed_ledger_entry_ribbon_actions(
        vendor_ledger_page,
        party='vendor',
        applied_list_name='VendorAppliedEntriesList',
        detailed_list_name='DetailedVendorLedgerEntryList',
    )
    _seed_ledger_entry_ribbon_actions(
        customer_ledger_page,
        party='customer',
        applied_list_name='CustomerAppliedEntriesList',
        detailed_list_name='DetailedCustomerLedgerEntryList',
    )

    item_ledger_page = _create_ledger_list_page(
        name='ItemLedgerEntryList',
        caption='Item Ledger Entries',
        source_table='ItemLedgerEntries',
        context_filter_field='item_id',
        fields=[
            dict(name='posting_date', caption='Posting Date', field_type='Date', tab_index=0),
            dict(name='entry_type', caption='Entry Type', field_type='Text', tab_index=1),
            dict(name='document_type', caption='Document Type', field_type='Text', tab_index=2),
            dict(name='document_no', caption='Document No.', field_type='Code', tab_index=3),
            dict(name='description', caption='Description', field_type='Text', tab_index=4),
            dict(name='quantity', caption='Quantity', field_type='Integer', tab_index=5),
            dict(name='remaining_quantity', caption='Remaining Qty.', field_type='Integer', tab_index=6),
            dict(name='item_id', caption='Item No.', field_type='Code', tab_index=7),
            dict(name='global_dimension_1', caption='Branch', field_type='Code', tab_index=8),
            dict(name='global_dimension_2', caption='Global Dimension 2', field_type='Code', tab_index=9),
            dict(name='id', caption='Entry No.', field_type='Integer', tab_index=10, primary_key=True),
        ],
    )

    bank_ledger_page = _create_ledger_list_page(
        name='BankAccountLedgerEntryList',
        caption='Bank Account Ledger Entries',
        source_table='BankAccountLedgerEntry',
        context_filter_field='bank_account_no',
        fields=[
            dict(name='posting_date', caption='Posting Date', field_type='Date', tab_index=0),
            dict(name='document_type', caption='Document Type', field_type='Text', tab_index=1),
            dict(name='document_no', caption='Document No.', field_type='Code', tab_index=2),
            dict(name='description', caption='Description', field_type='Text', tab_index=3),
            dict(name='amount', caption='Amount', field_type='Decimal', tab_index=4),
            dict(name='remaining_amount', caption='Remaining Amount', field_type='Decimal', tab_index=5),
            dict(name='bank_account_no_id', caption='Bank Account No.', field_type='Code', tab_index=6),
            dict(name='global_dimension_1', caption='Branch', field_type='Code', tab_index=7),
            dict(name='entry_no', caption='Entry No.', field_type='Integer', tab_index=8, primary_key=True),
        ],
    )

    gl_ledger_page = _create_ledger_list_page(
        name='GeneralLedgerEntryList',
        caption='General Ledger Entries',
        source_table='GeneralLedgerEntry',
        context_filter_field='gl_account__no',
        fields=[
            dict(name='posting_date', caption='Posting Date', field_type='Date', tab_index=0),
            dict(name='document_type', caption='Document Type', field_type='Text', tab_index=1),
            dict(name='document_no', caption='Document No.', field_type='Code', tab_index=2),
            dict(name='description', caption='Description', field_type='Text', tab_index=3),
            dict(name='amount', caption='Amount', field_type='Decimal', tab_index=4),
            dict(name='balance_account_no', caption='Bal. Account No.', field_type='Code', tab_index=5),
            dict(name='gl_account__no', caption='G/L Account No.', field_type='Code', tab_index=6),
            dict(name='global_dimension_1', caption='Branch', field_type='Code', tab_index=7),
            dict(name='global_dimension_2', caption='Global Dimension 2', field_type='Code', tab_index=8),
            dict(name='id', caption='Entry No.', field_type='Integer', tab_index=9, primary_key=True),
        ],
    )

    _link_table_relation(
        page_names=('BankAccountCard', 'BankAccountList'),
        field_name='bank_account_posting_group',
        related_table='BankAccountPostingGroup',
        related_field='code',
        related_display_field='description',
    )

    _link_drill_down(
        page_names=('CustomerCard', 'CustomerList'),
        field_name='balance',
        drill_down_page=customer_ledger_page,
    )
    _link_drill_down(
        page_names=('VendorCard', 'VendorList'),
        field_name='balance',
        drill_down_page=vendor_ledger_page,
    )
    _link_drill_down(
        page_names=('ItemCard', 'ItemList'),
        field_name='inventory',
        drill_down_page=item_ledger_page,
    )
    _link_drill_down(
        page_names=('BankAccountCard', 'BankAccountList'),
        field_name='balance',
        drill_down_page=bank_ledger_page,
    )
    _link_drill_down(
        page_names=('GLAccountCard', 'GLAccountList'),
        field_name='balance',
        drill_down_page=gl_ledger_page,
    )

    # Add balance / inventory to cards and lists
    _ensure_field(cust_card_ctrl, cust_card, dict(
        name='balance', caption='Balance (LCY)', field_type='Decimal',
        visible=True, editable=False, primary_key=False, tab_index=9,
    ), customer_ledger_page)
    _ensure_field(cust_ctrl, cust_page, dict(
        name='balance', caption='Balance', field_type='Decimal',
        visible=True, editable=False, primary_key=False, tab_index=5,
    ), customer_ledger_page)

    _ensure_field(vendor_card_ctrl, vendor_card, dict(
        name='balance', caption='Balance (LCY)', field_type='Decimal',
        visible=True, editable=False, primary_key=False, tab_index=9,
    ), vendor_ledger_page)

    _ensure_field(items_ctrl, items_page, dict(
        name='inventory', caption='Inventory', field_type='Integer',
        visible=True, editable=False, primary_key=False, tab_index=5,
    ), item_ledger_page)
    item_inventory_ctrl = PageControl.objects.get(page=item_card, name='ItemInventoryGroup')
    _ensure_field(item_inventory_ctrl, item_card, dict(
        name='inventory', caption='Inventory', field_type='Integer',
        visible=True, editable=False, primary_key=False, tab_index=0,
    ), item_ledger_page)

    _ensure_field(bank_card_ctrl, bank_card, dict(
        name='balance', caption='Balance', field_type='Decimal',
        visible=True, editable=False, primary_key=False, tab_index=8,
    ), bank_ledger_page)
    _ensure_field(bank_ctrl, bank_page, dict(
        name='balance', caption='Balance', field_type='Decimal',
        visible=True, editable=False, primary_key=False, tab_index=4,
    ), bank_ledger_page)

    _ensure_field(gl_card_ctrl, gl_card, dict(
        name='balance', caption='Balance', field_type='Decimal',
        visible=True, editable=False, primary_key=False, tab_index=10,
    ), gl_ledger_page)
    _ensure_field(gl_list_ctrl, gl_list, dict(
        name='balance', caption='Balance', field_type='Decimal',
        visible=True, editable=False, primary_key=False, tab_index=7,
    ), gl_ledger_page)

    user_setup_page = _seed_user_setup_page()
    users_card, users_page = _seed_users_pages(user_setup_page)
    _ensure_user_setups()
    permission_sets_list = _seed_permission_set_pages()
    user_groups_list = _seed_user_group_pages()
    _ = permission_sets_list, user_groups_list
    user_settings_card, user_settings_list = _seed_user_settings_page()
    _ensure_user_personalizations()
    sales_order_doc, sales_order_list = _seed_sales_order_pages()
    sales_invoice_doc, sales_invoice_list = _seed_sales_invoice_pages()
    sales_credit_memo_doc, sales_credit_memo_list = _seed_sales_credit_memo_pages()
    posted_sales_credit_memo_list = _seed_posted_sales_credit_memo_list(sales_credit_memo_doc)
    _ = sales_credit_memo_list, posted_sales_credit_memo_list
    sales_pos_page = _seed_sales_pos_page()
    _ = sales_pos_page  # registered in role centre nav
    purchase_invoice_doc, purchase_invoice_list = _seed_purchase_invoice_pages()
    posted_sales_invoice_list = _seed_posted_sales_invoice_list(sales_invoice_doc)
    _seed_posted_sales_invoice_list_scope_actions(posted_sales_invoice_list)
    posted_purchase_invoice_list = _seed_posted_purchase_invoice_list(
        _seed_posted_purchase_invoice_pages(),
    )
    _link_drill_down(
        page_names=('UsersList',),
        field_name='full_name',
        drill_down_page=posted_sales_invoice_list,
    )
    expense_card, expense_list = _seed_expense_pages()
    item_journal_card, inventory_adj_list, opening_balance_list, _posted_inv_adj_list = (
        _seed_item_journal_pages()
    )
    item_iuom_list, _adj_by_item_list = _seed_item_card_drill_down_lists(item_journal_card)
    _ = item_iuom_list, _adj_by_item_list
    _seed_item_card_page_actions(item_card)
    _seed_item_list_page_actions(items_page)
    payment_card, payment_list = _seed_payment_journal_pages()
    payment_method_list = _seed_payment_method_list()
    _ = payment_method_list
    _seed_apply_vendor_entries_page()
    _seed_item_tracking_lines_worksheet_page()
    _seed_posted_item_tracking_lines_page()
    _seed_apply_customer_entries_page()
    crj_worksheet, crj_batch_list = _seed_cash_receipt_journal_pages()
    gj_worksheet, gj_batch_list = _seed_general_journal_pages()
    _ = gj_worksheet, gj_batch_list
    _delete_legacy_sales_nav_items()
    rc_business = _seed_role_centre_pages(
        sales_order_list,
        sales_invoice_list,
        posted_sales_invoice_list,
        posted_purchase_invoice_list,
        customer_ledger_page,
        items_page,
    )
    rc_sales = _seed_sales_manager_rc(
        sales_order_list,
        sales_invoice_list,
        posted_sales_invoice_list,
    )
    rc_accounting = _seed_accounting_rc(expense_list, payment_list)
    rc_warehouse = _seed_warehouse_rc(
        posted_purchase_invoice_list,
        inventory_adj_list,
        opening_balance_list,
    )
    rc_cashier = _seed_cashier_rc(
        posted_sales_invoice_list,
        cust_page,
    )
    rc_pharmacist = _seed_pharmacist_rc(
        posted_purchase_invoice_list,
        purchase_invoice_list,
        payment_method_list,
    )
    rc_operations = _seed_operations_manager_rc(
        payment_method_list,
        expense_list,
        payment_list,
    )
    rc_debug_admin = _seed_debug_admin_rc(
        sales_order_list=sales_order_list,
        posted_sales_invoice_list=posted_sales_invoice_list,
        customer_ledger_page=customer_ledger_page,
    )
    _seed_application_profiles(
        business_rc=rc_business,
        sales_rc=rc_sales,
        accounting_rc=rc_accounting,
        warehouse_rc=rc_warehouse,
        cashier_rc=rc_cashier,
        pharmacist_rc=rc_pharmacist,
        operations_manager_rc=rc_operations,
        debug_admin_rc=rc_debug_admin,
    )
    _assign_default_application_profiles()

    # Setup pages (Card — singleton; User Setup stays List)
    _, ns_list, ns_lines_list = _seed_no_series_pages()
    Page.objects.filter(
        name__in=('InventorySetupList', 'ManufacturingSetupList', 'GeneralLedgerSetupList'),
    ).delete()
    inv_setup = _seed_inventory_setup_page()
    global_uom_list = _seed_unit_of_measure_list()
    _seed_inventory_setup_uom_action(inv_setup, global_uom_list)
    _wire_relation_lookup_fields(
        item_card,
        ('unit_of_measure',),
        part_control_name='ItemUnitOfMeasurePart',
        lookup_page=global_uom_list,
    )
    item_list = Page.objects.filter(name='ItemList').first()
    if item_list:
        _wire_relation_lookup_fields(
            item_list,
            ('unit_of_measure',),
            part_control_name='ItemUnitOfMeasurePart',
            lookup_page=global_uom_list,
        )
    _wire_relation_lookup_fields(
        item_card,
        ('sales_unit_of_measure', 'purchase_unit_of_measure'),
        part_control_name='ItemUnitOfMeasurePart',
        lookup_page=item_iuom_list,
    )
    _wire_relation_lookup_fields(
        item_journal_card,
        ('item_unit_of_measure',),
        part_control_name='ItemUnitOfMeasurePart',
        lookup_page=item_iuom_list,
    )
    mfg_setup = _seed_manufacturing_setup_page()
    gl_setup = _seed_general_ledger_setup_page()
    posting_pages = _seed_gl_posting_pages()
    dimension_pages = _seed_dimension_pages()
    financial_report_pages = _seed_financial_report_pages()
    rc_company = _seed_company_card()
    _seed_company_billing_pages()
    _ensure_company_information()

    from pages.restaurant_seed import seed_restaurant_pages

    restaurant_pages = seed_restaurant_pages()

    _apply_all_zentro_page_object_ids()
    from pages.management.commands.align_zentro_page_ids import align_zentro_page_ids

    align_stats = align_zentro_page_ids(sync_permissions=False)
    _sync_page_permission_objects()
    if align_stats['mapped']:
        print(
            f"Aligned {align_stats['mapped']} pages so PageId == ObjectId "
            f"(Zentro 10xxx registry)"
        )

    from pages.desktop_pages import sync_desktop_enabled_flags

    _seed_desktop_sync_queue_page()
    _wire_desktop_queue_nav()
    sync_desktop_enabled_flags()

    print(
        "Seeded: ItemCard, CustomerCard, VendorCard, BankAccountCard, GLAccountCard, UsersCard + linked list pages + "
        "ledger drill-down + User Setup + Sales Order + Sales Invoice + Point of Sale + Purchase Invoice + "
        "Expenses + Item Journals + Payments + Role Centre + Company Card + "
        "Setup pages (No. Series + Inventory/Manufacturing/G/L Setup cards) + User settings list/card + "
        "Restaurant module (orders, tables, menus, role centres) + "
        "Permission Sets + User Groups"
    )
    return {
        'items_list_id':     items_page.page_id,
        'items_card_id':     item_card.page_id,
        'customers_list_id': cust_page.page_id,
        'customers_card_id': cust_card.page_id,
        'vendors_list_id':   vendor_page.page_id,
        'vendors_card_id':   vendor_card.page_id,
        'bank_accounts_list_id': bank_page.page_id,
        'bank_accounts_card_id': bank_card.page_id,
        'gl_accounts_list_id': gl_list.page_id,
        'gl_accounts_card_id': gl_card.page_id,
        'customer_ledger_list_id': customer_ledger_page.page_id,
        'vendor_ledger_list_id': vendor_ledger_page.page_id,
        'item_ledger_list_id': item_ledger_page.page_id,
        'bank_ledger_list_id': bank_ledger_page.page_id,
        'users_list_id': users_page.page_id,
        'users_card_id': users_card.page_id,
        'user_setup_list_id': user_setup_page.page_id,
        'user_settings_list_id': user_settings_list.page_id,
        'user_settings_card_id': user_settings_card.page_id,
        'sales_order_doc_id': sales_order_doc.page_id,
        'sales_order_list_id': sales_order_list.page_id,
        'sales_invoice_doc_id': sales_invoice_doc.page_id,
        'sales_invoice_list_id': sales_invoice_list.page_id,
        'posted_sales_invoice_list_id': posted_sales_invoice_list.page_id,
        'purchase_invoice_doc_id': purchase_invoice_doc.page_id,
        'purchase_invoice_list_id': purchase_invoice_list.page_id,
        'posted_purchase_invoice_list_id': posted_purchase_invoice_list.page_id,
        'expense_list_id': expense_list.page_id,
        'expense_card_id': expense_card.page_id,
        'payment_list_id': payment_list.page_id,
        'payment_card_id': payment_card.page_id,
        'crj_worksheet_id': crj_worksheet.page_id,
        'crj_batch_list_id': crj_batch_list.page_id,
        'gj_worksheet_id': gj_worksheet.page_id,
        'gj_batch_list_id': gj_batch_list.page_id,
        'role_centre_id': rc_business.page_id,
        'sales_role_centre_id': rc_sales.page_id,
        'accounting_role_centre_id': rc_accounting.page_id,
        'warehouse_role_centre_id': rc_warehouse.page_id,
        'cashier_role_centre_id': rc_cashier.page_id,
        'company_card_id': rc_company.page_id,
        'no_series_list_id': ns_list.page_id,
        'no_series_lines_list_id': ns_lines_list.page_id,
        'inventory_setup_card_id': inv_setup.page_id,
        'manufacturing_setup_card_id': mfg_setup.page_id,
        'gl_setup_card_id': gl_setup.page_id,
        'general_posting_setup_list_id': posting_pages['general_posting_setup_list_id'],
        'gen_business_posting_group_list_id': posting_pages['gen_business_posting_group_list_id'],
        'gen_product_posting_group_list_id': posting_pages['gen_product_posting_group_list_id'],
        **dimension_pages,
        **restaurant_pages,
    }


def _apply_all_zentro_page_object_ids() -> None:
    """Assign Zentro page ObjectId (= registry ID) on registered pages."""
    from pages.bc_page_ids import all_registered_page_names
    from pages.permission_sync import apply_object_id_from_registry

    for page_name in all_registered_page_names():
        page = Page.objects.filter(name=page_name).first()
        if page is not None:
            apply_object_id_from_registry(page)


# Backward-compatible name used by older call sites / docs
_apply_all_bc_page_object_ids = _apply_all_zentro_page_object_ids


def _sync_page_permission_objects() -> None:
    from pages.permission_sync import sync_all_page_permission_objects

    sync_all_page_permission_objects()


def _seed_sales_order_pages():
    """Document page + ListPart subform for SalesOrder / SalesOrderLine."""
    subform, _ = Page.objects.update_or_create(
        name='SalesOrderSubform',
        defaults={
            'caption': 'Sales Order Lines',
            'source_table': 'SalesOrderLine',
            'page_type': 'ListPart',
            'editable': True,
            'insert_allowed': True,
            'delete_allowed': True,
            'modify_allowed': True,
        },
    )

    sub_ctrl, _ = PageControl.objects.update_or_create(
        page=subform,
        name='SalesOrderSubformRepeater',
        defaults={
            'control_type': 'Repeater',
            'caption': 'Lines',
            'source_table': 'SalesOrderLine',
            'show_caption': False,
            'editable': True,
            'visible': True,
        },
    )
    _seed_fields(sub_ctrl, subform, [
        dict(name='type', caption='Type', field_type='Option', visible=True, editable=True,
             primary_key=False, tab_index=0, enum_values='item,resource'),
        dict(name='item', caption='No.', field_type='Code', visible=True, editable=True,
             primary_key=False, tab_index=1,
             has_table_relation=True, related_table='Item', related_field='no',
             related_display_field='item_name'),
        dict(name='description', caption='Description', field_type='Text', visible=True,
             editable=True, primary_key=False, tab_index=2),
        dict(name='quantity', caption='Quantity', field_type='Integer', visible=True,
             editable=True, primary_key=False, tab_index=3),
        dict(name='unit_price', caption='Unit Price', field_type='Decimal', visible=True,
             editable=True, primary_key=False, tab_index=4),
        dict(name='amount', caption='Amount', field_type='Decimal', visible=True,
             editable=False, primary_key=False, tab_index=5),
    ])

    doc, _ = Page.objects.update_or_create(
        name='SalesOrder',
        defaults={
            'caption': 'Sales Order',
            'source_table': 'SalesOrder',
            'page_type': 'Document',
            'editable': True,
            'insert_allowed': True,
            'delete_allowed': True,
            'modify_allowed': True,
            'title_field': 'order_no',
        },
    )

    general_ctrl, _ = PageControl.objects.update_or_create(
        page=doc,
        name='SalesOrderGeneral',
        defaults={
            'control_type': 'Group',
            'caption': 'General',
            'source_table': 'SalesOrder',
            'show_caption': True,
            'editable': True,
            'visible': True,
        },
    )
    _seed_fields(general_ctrl, doc, [
        dict(name='order_no', caption='No.', field_type='Code', visible=True, editable=False,
             primary_key=True, tab_index=0),
        dict(name='customer', caption='Customer No.', field_type='Code', visible=True, editable=True,
             primary_key=False, tab_index=1,
             has_table_relation=True, related_table='Customer', related_field='no',
             related_display_field='name'),
        dict(name='order_date', caption='Order Date', field_type='Date', visible=True, editable=True,
             primary_key=False, tab_index=2),
        dict(name='status', caption='Status', field_type='Option', visible=True, editable=False,
             primary_key=False, tab_index=3,
             enum_values='Open,Partially Delivered,Completed,Converted to Invoice'),
        dict(name='total_amount', caption='Amount', field_type='Decimal', visible=True, editable=False,
             primary_key=False, tab_index=4),
        dict(name='notes', caption='Notes', field_type='Text', visible=True, editable=True,
             primary_key=False, tab_index=5),
    ])

    part_ctrl, _ = PageControl.objects.update_or_create(
        page=doc,
        name='SalesOrderLines',
        defaults={
            'control_type': 'Part',
            'caption': 'Lines',
            'source_table': 'SalesOrderLine',
            'show_caption': True,
            'editable': True,
            'visible': True,
            'part_page': subform,
            'link_field': 'sales_order__system_id',
        },
    )
    part_ctrl.part_page = subform
    part_ctrl.link_field = 'sales_order__system_id'
    part_ctrl.save(update_fields=['part_page', 'link_field'])

    list_page, _ = Page.objects.update_or_create(
        name='SalesOrderList',
        defaults={
            'caption': 'Sales Orders',
            'source_table': 'SalesOrder',
            'page_type': 'List',
            'editable': True,
            'insert_allowed': True,
            'delete_allowed': True,
            'modify_allowed': True,
            'card_page': doc,
            'title_field': 'order_no',
        },
    )
    list_page.card_page = doc
    list_page.save(update_fields=['card_page'])

    list_ctrl, _ = PageControl.objects.update_or_create(
        page=list_page,
        name='SalesOrderListControl',
        defaults={
            'control_type': 'Repeater',
            'caption': 'Sales Orders',
            'source_table': 'SalesOrder',
            'show_caption': True,
            'editable': False,
            'visible': True,
        },
    )
    _seed_fields(list_ctrl, list_page, [
        dict(name='order_no', caption='No.', field_type='Code', visible=True, editable=False,
             primary_key=True, tab_index=0),
        dict(name='customer', caption='Customer', field_type='Code', visible=True, editable=False,
             primary_key=False, tab_index=1),
        dict(name='order_date', caption='Order Date', field_type='Date', visible=True, editable=False,
             primary_key=False, tab_index=2),
        dict(name='status', caption='Status', field_type='Option', visible=True, editable=False,
             primary_key=False, tab_index=3),
        dict(name='total_amount', caption='Amount', field_type='Decimal', visible=True, editable=False,
             primary_key=False, tab_index=4),
    ])

    return doc, list_page


def _seed_sales_invoice_pages():
    """Document page + ListPart subform for SalesInvoice / SalesInvoiceLine."""
    subform, _ = Page.objects.update_or_create(
        name='SalesInvoiceSubform',
        defaults={
            'caption': 'Sales Invoice Lines',
            'source_table': 'SalesInvoiceLine',
            'page_type': 'ListPart',
            'editable': True,
            'insert_allowed': True,
            'delete_allowed': True,
            'modify_allowed': True,
        },
    )

    sub_ctrl, _ = PageControl.objects.update_or_create(
        page=subform,
        name='SalesInvoiceSubformRepeater',
        defaults={
            'control_type': 'Repeater',
            'caption': 'Lines',
            'source_table': 'SalesInvoiceLine',
            'show_caption': False,
            'editable': True,
            'visible': True,
        },
    )
    _seed_fields(sub_ctrl, subform, [
        dict(name='type', caption='Type', field_type='Option', visible=True, editable=True,
             primary_key=False, tab_index=0, enum_values='item,resource'),
        dict(name='item', caption='No.', field_type='Code', visible=True, editable=True,
             primary_key=False, tab_index=1,
             has_table_relation=True, related_table='Item', related_field='no',
             related_display_field='item_name'),
        dict(name='description', caption='Description', field_type='Text', visible=True,
             editable=True, primary_key=False, tab_index=2),
        dict(name='quantity', caption='Quantity', field_type='Integer', visible=True,
             editable=True, primary_key=False, tab_index=3),
        dict(name='unit_price', caption='Unit Price', field_type='Decimal', visible=True,
             editable=True, primary_key=False, tab_index=4),
        dict(name='total_amount', caption='Amount', field_type='Decimal', visible=True,
             editable=False, primary_key=False, tab_index=5),
    ])

    doc, _ = Page.objects.update_or_create(
        name='SalesInvoice',
        defaults={
            'caption': 'Sales Invoice',
            'source_table': 'SalesInvoice',
            'page_type': 'Document',
            'editable': True,
            'insert_allowed': True,
            'delete_allowed': True,
            'modify_allowed': True,
            'title_field': 'invoice_no',
        },
    )

    general_ctrl, _ = PageControl.objects.update_or_create(
        page=doc,
        name='SalesInvoiceGeneral',
        defaults={
            'control_type': 'Group',
            'caption': 'General',
            'source_table': 'SalesInvoice',
            'show_caption': True,
            'editable': True,
            'visible': True,
        },
    )
    _seed_fields(general_ctrl, doc, [
        dict(name='invoice_no', caption='No.', field_type='Code', visible=True, editable=False,
             primary_key=True, tab_index=0),
        dict(name='customer', caption='Customer No.', field_type='Code', visible=True, editable=True,
             primary_key=False, tab_index=1,
             has_table_relation=True, related_table='Customer', related_field='no',
             related_display_field='name'),
        dict(name='document_date', caption='Document Date', field_type='Date', visible=True, editable=True,
             primary_key=False, tab_index=2),
        dict(name='posting_date', caption='Posting Date', field_type='Date', visible=True, editable=True,
             primary_key=False, tab_index=3),
        dict(name='due_date', caption='Due Date', field_type='Date', visible=True, editable=True,
             primary_key=False, tab_index=4),
        dict(name='payment_method', caption='How did you pay?', field_type='Code', visible=True,
             editable=True, primary_key=False, tab_index=5,
             has_table_relation=True, related_table='PaymentMethod', related_field='code',
             related_display_field='description'),
        dict(name='status', caption='Status', field_type='Option', visible=True, editable=False,
             primary_key=False, tab_index=6,
             enum_values='Draft,Open,Posted,Cancelled'),
        dict(name='total_amount', caption='Amount', field_type='Decimal', visible=True, editable=False,
             primary_key=False, tab_index=7),
    ])
    PageControlField.objects.filter(
        page_control=general_ctrl,
        name='total_vat_amount',
    ).update(visible=False)

    part_ctrl, _ = PageControl.objects.update_or_create(
        page=doc,
        name='SalesInvoiceLines',
        defaults={
            'control_type': 'Part',
            'caption': 'Lines',
            'source_table': 'SalesInvoiceLine',
            'show_caption': True,
            'editable': True,
            'visible': True,
            'part_page': subform,
            'link_field': 'sales_invoice__system_id',
        },
    )
    part_ctrl.part_page = subform
    part_ctrl.link_field = 'sales_invoice__system_id'
    part_ctrl.save(update_fields=['part_page', 'link_field'])

    list_page, _ = Page.objects.update_or_create(
        name='SalesInvoiceList',
        defaults={
            'caption': 'Sales Invoices',
            'source_table': 'SalesInvoice',
            'page_type': 'List',
            'editable': True,
            'insert_allowed': True,
            'delete_allowed': True,
            'modify_allowed': True,
            'card_page': doc,
            'title_field': 'invoice_no',
            'list_filter_field': 'status',
            'list_filter_value': 'Open,Draft',
        },
    )
    list_page.card_page = doc
    list_page.list_filter_field = 'status'
    list_page.list_filter_value = 'Open,Draft'
    list_page.save(update_fields=['card_page', 'list_filter_field', 'list_filter_value'])

    list_ctrl, _ = PageControl.objects.update_or_create(
        page=list_page,
        name='SalesInvoiceListControl',
        defaults={
            'control_type': 'Repeater',
            'caption': 'Sales Invoices',
            'source_table': 'SalesInvoice',
            'show_caption': True,
            'editable': False,
            'visible': True,
        },
    )
    _seed_fields(list_ctrl, list_page, [
        dict(name='invoice_no', caption='No.', field_type='Code', visible=True, editable=False,
             primary_key=True, tab_index=0, freeze_column=True),
        dict(name='customer', caption='Customer', field_type='Code', visible=True, editable=False,
             primary_key=False, tab_index=1),
        dict(name='document_date', caption='Document Date', field_type='Date', visible=True, editable=False,
             primary_key=False, tab_index=2),
        dict(name='due_date', caption='Due Date', field_type='Date', visible=True, editable=False,
             primary_key=False, tab_index=3),
        dict(name='status', caption='Status', field_type='Option', visible=True, editable=False,
             primary_key=False, tab_index=4,
             enum_values='Draft,Open,Posted,Cancelled'),
    ])

    PageAction.objects.update_or_create(
        page=doc,
        name='preview_sales_invoice',
        defaults={
            'caption': 'Preview Posting',
            'requires_confirmation': False,
            'confirmation_message': '',
            'tooltip': 'Preview ledger entries before posting',
            'visible': True,
            'ribbon_tab': 'Home',
            'image_url': 'Eye',
            'visible_when_field': 'status',
            'visible_when_values': 'Open,Draft',
        },
    )
    PageAction.objects.update_or_create(
        page=doc,
        name='post_sales_invoice',
        defaults={
            'caption': 'Post',
            'requires_confirmation': True,
            'confirmation_message': 'Post this sales invoice to the general ledger?',
            'tooltip': 'Post sales invoice',
            'visible': True,
            'ribbon_tab': 'Home',
            'image_url': 'CircleCheck',
            'visible_when_field': 'status',
            'visible_when_values': 'Open,Draft',
        },
    )

    return doc, list_page


def _seed_sales_credit_memo_pages():
    """Document page + ListPart subform for SalesCreditMemo / SalesCreditMemoLine."""
    subform, _ = Page.objects.update_or_create(
        name='SalesCreditMemoSubform',
        defaults={
            'caption': 'Sales Credit Memo Lines',
            'source_table': 'SalesCreditMemoLine',
            'page_type': 'ListPart',
            'editable': False,
            'insert_allowed': False,
            'delete_allowed': False,
            'modify_allowed': False,
        },
    )

    sub_ctrl, _ = PageControl.objects.update_or_create(
        page=subform,
        name='SalesCreditMemoSubformRepeater',
        defaults={
            'control_type': 'Repeater',
            'caption': 'Lines',
            'source_table': 'SalesCreditMemoLine',
            'show_caption': False,
            'editable': False,
            'visible': True,
        },
    )
    _seed_fields(sub_ctrl, subform, [
        dict(name='item', caption='No.', field_type='Code', visible=True, editable=False,
             primary_key=False, tab_index=0,
             has_table_relation=True, related_table='Item', related_field='no',
             related_display_field='item_name'),
        dict(name='description', caption='Description', field_type='Text', visible=True,
             editable=False, primary_key=False, tab_index=1),
        dict(name='location_code', caption='Location Code', field_type='Code', visible=True,
             editable=False, primary_key=False, tab_index=2,
             has_table_relation=True, related_table='Location', related_field='code',
             related_display_field='description'),
        dict(name='quantity', caption='Quantity', field_type='Integer', visible=True,
             editable=False, primary_key=False, tab_index=3),
        dict(name='unit_price', caption='Unit Price Excl. VAT', field_type='Decimal', visible=True,
             editable=False, primary_key=False, tab_index=4),
        dict(name='amount', caption='Line Amount Excl. VAT', field_type='Decimal', visible=True,
             editable=False, primary_key=False, tab_index=5),
    ])
    _ensure_table_relation('SalesCreditMemoLine', 'item', 'Item', 'no', 'item_name')
    _ensure_table_relation('SalesCreditMemoLine', 'location_code', 'Location', 'code', 'description')

    doc, _ = Page.objects.update_or_create(
        name='SalesCreditMemo',
        defaults={
            'caption': 'Sales Credit Memo',
            'source_table': 'SalesCreditMemo',
            'page_type': 'Document',
            'editable': True,
            'insert_allowed': False,
            'delete_allowed': False,
            'modify_allowed': True,
            'title_field': 'credit_memo_no',
        },
    )

    general_ctrl, _ = PageControl.objects.update_or_create(
        page=doc,
        name='SalesCreditMemoGeneral',
        defaults={
            'control_type': 'Group',
            'caption': 'General',
            'source_table': 'SalesCreditMemo',
            'show_caption': True,
            'editable': True,
            'visible': True,
        },
    )
    _seed_fields(general_ctrl, doc, [
        dict(name='credit_memo_no', caption='No.', field_type='Code', visible=True, editable=False,
             primary_key=True, tab_index=0),
        dict(name='customer', caption='Customer Name', field_type='Code', visible=True, editable=False,
             primary_key=False, tab_index=1,
             has_table_relation=True, related_table='Customer', related_field='no',
             related_display_field='name'),
        dict(name='document_date', caption='Document Date', field_type='Date', visible=True, editable=True,
             primary_key=False, tab_index=2),
        dict(name='posting_date', caption='Posting Date', field_type='Date', visible=True, editable=True,
             primary_key=False, tab_index=3),
        dict(name='vat_date', caption='VAT Date', field_type='Date', visible=True, editable=True,
             primary_key=False, tab_index=4),
        dict(name='original_invoice_no', caption='Original Invoice No.', field_type='Code',
             visible=True, editable=False, primary_key=False, tab_index=5),
        dict(name='reason_for_reversal', caption='Reason for Reversal', field_type='Text',
             visible=True, editable=True, primary_key=False, tab_index=6),
        dict(name='status', caption='Status', field_type='Option', visible=True, editable=False,
             primary_key=False, tab_index=7,
             enum_values='Draft,Posted'),
        dict(name='total_amount', caption='Amount', field_type='Decimal', visible=True, editable=False,
             primary_key=False, tab_index=8),
    ])

    part_ctrl, _ = PageControl.objects.update_or_create(
        page=doc,
        name='SalesCreditMemoLines',
        defaults={
            'control_type': 'Part',
            'caption': 'Lines',
            'source_table': 'SalesCreditMemoLine',
            'show_caption': True,
            'editable': False,
            'visible': True,
            'part_page': subform,
            'link_field': 'credit_memo__system_id',
        },
    )
    part_ctrl.part_page = subform
    part_ctrl.link_field = 'credit_memo__system_id'
    part_ctrl.save(update_fields=['part_page', 'link_field'])

    list_page, _ = Page.objects.update_or_create(
        name='SalesCreditMemoList',
        defaults={
            'caption': 'Sales Credit Memos',
            'source_table': 'SalesCreditMemo',
            'page_type': 'List',
            'editable': False,
            'insert_allowed': False,
            'delete_allowed': False,
            'modify_allowed': False,
            'card_page': doc,
            'title_field': 'credit_memo_no',
            'list_filter_field': 'status',
            'list_filter_value': 'Draft',
        },
    )
    list_page.card_page = doc
    list_page.list_filter_field = 'status'
    list_page.list_filter_value = 'Draft'
    list_page.save(update_fields=['card_page', 'list_filter_field', 'list_filter_value'])

    list_ctrl, _ = PageControl.objects.update_or_create(
        page=list_page,
        name='SalesCreditMemoListControl',
        defaults={
            'control_type': 'Repeater',
            'caption': 'Sales Credit Memos',
            'source_table': 'SalesCreditMemo',
            'show_caption': True,
            'editable': False,
            'visible': True,
        },
    )
    _seed_fields(list_ctrl, list_page, [
        dict(name='credit_memo_no', caption='No.', field_type='Code', visible=True, editable=False,
             primary_key=True, tab_index=0, freeze_column=True),
        dict(name='customer', caption='Customer', field_type='Code', visible=True, editable=False,
             primary_key=False, tab_index=1,
             has_table_relation=True, related_table='Customer', related_field='no',
             related_display_field='name'),
        dict(name='document_date', caption='Document Date', field_type='Date', visible=True, editable=False,
             primary_key=False, tab_index=2),
        dict(name='posting_date', caption='Posting Date', field_type='Date', visible=True, editable=False,
             primary_key=False, tab_index=3),
        dict(name='original_invoice_no', caption='Applies-to Doc. No.', field_type='Code',
             visible=True, editable=False, primary_key=False, tab_index=4),
        dict(name='status', caption='Status', field_type='Option', visible=True, editable=False,
             primary_key=False, tab_index=5,
             enum_values='Draft,Posted'),
        dict(name='total_amount', caption='Amount', field_type='Decimal', visible=True, editable=False,
             primary_key=False, tab_index=6),
    ])

    _link_drill_down(
        page_names=('SalesCreditMemoList',),
        field_name='credit_memo_no',
        drill_down_page=doc,
    )

    PageAction.objects.update_or_create(
        page=doc,
        name='preview_credit_memo',
        defaults={
            'caption': 'Preview Posting',
            'requires_confirmation': False,
            'confirmation_message': '',
            'tooltip': 'Preview ledger entries before posting',
            'visible': True,
            'ribbon_tab': 'Home',
            'image_url': 'Eye',
            'visible_when_field': 'status',
            'visible_when_values': 'Draft',
        },
    )
    PageAction.objects.update_or_create(
        page=doc,
        name='post_credit_memo',
        defaults={
            'caption': 'Post',
            'requires_confirmation': True,
            'confirmation_message': 'Post this sales credit memo to the general ledger?',
            'tooltip': 'Post sales credit memo',
            'visible': True,
            'ribbon_tab': 'Home',
            'image_url': 'CircleCheck',
            'visible_when_field': 'status',
            'visible_when_values': 'Draft',
        },
    )

    return doc, list_page


def _seed_posted_sales_credit_memo_list(doc: Page) -> Page:
    """Posted sales credit memos — same document card, filtered to status=Posted."""
    return _seed_status_filtered_list_page(
        name='PostedSalesCreditMemoList',
        caption='Posted Sales Credit Memos',
        source_table='SalesCreditMemo',
        card_page=doc,
        title_field='credit_memo_no',
        control_name='PostedSalesCreditMemoListControl',
        filter_field='status',
        filter_value='Posted',
        list_fields=[
            dict(name='credit_memo_no', caption='No.', field_type='Code', visible=True, editable=False,
                 primary_key=True, tab_index=0, freeze_column=True),
            dict(name='customer', caption='Customer', field_type='Code', visible=True, editable=False,
                 primary_key=False, tab_index=1,
                 has_table_relation=True, related_table='Customer', related_field='no',
                 related_display_field='name'),
            dict(name='posting_date', caption='Posting Date', field_type='Date', visible=True, editable=False,
                 primary_key=False, tab_index=2),
            dict(name='original_invoice_no', caption='Applies-to Doc. No.', field_type='Code',
                 visible=True, editable=False, primary_key=False, tab_index=3),
            dict(name='total_amount', caption='Amount', field_type='Decimal', visible=True, editable=False,
                 primary_key=False, tab_index=4),
            dict(name='status', caption='Status', field_type='Option', visible=True, editable=False,
                 primary_key=False, tab_index=5,
                 enum_values='Draft,Posted'),
        ],
    )


def _seed_sales_pos_page() -> Page:
    """Fullscreen POS checkout — separate from Sales Invoice document editor."""
    pos_page, _ = Page.objects.update_or_create(
        name='SalesPOS',
        defaults={
            'caption': 'Point of Sale',
            'source_table': 'SalesInvoice',
            'page_type': 'POS',
            'editable': True,
            'insert_allowed': True,
            'delete_allowed': False,
            'modify_allowed': False,
        },
    )

    item_list = Page.objects.filter(name='ItemList').first()
    grid_ctrl, _ = PageControl.objects.update_or_create(
        page=pos_page,
        name='POSProductGrid',
        defaults={
            'control_type': 'Part',
            'caption': 'Products',
            'source_table': 'Item',
            'show_caption': False,
            'editable': False,
            'visible': True,
            'tab_index': 0,
            'part_page': item_list,
        },
    )
    if item_list:
        grid_ctrl.part_page = item_list
        grid_ctrl.save(update_fields=['part_page'])

    _seed_pos_page_actions(pos_page)
    return pos_page


def _seed_desktop_sync_queue_page() -> Page:
    """Desktop-only sync queue shell — NavItem targets this like SalesPOS."""
    queue_page, _ = Page.objects.update_or_create(
        name='DesktopSyncQueue',
        defaults={
            'caption': 'Sync Queue',
            'source_table': 'SyncOutbox',
            'page_type': 'Queue',
            'editable': False,
            'insert_allowed': False,
            'delete_allowed': False,
            'modify_allowed': False,
        },
    )
    return queue_page


def _wire_desktop_queue_nav() -> None:
    """Add Sync Queue NavItem to every Role Centre (desktop sidebar)."""
    nav_spec = ('NavSyncQueue', 'Sync Queue', 'DesktopSyncQueue', 'ListOrdered', 'Desktop')
    for rc in Page.objects.filter(page_type='RoleCenter'):
        _seed_rc_nav_actions(rc, [nav_spec])


def _seed_pos_page_actions(pos_page: Page) -> None:
    """Ribbon actions rendered by POSActionBar (client-side handlers + navigation)."""
    actions = [
        dict(
            name='pos_charge',
            caption='Charge',
            image_url='CreditCard',
            ribbon_tab='Home',
            tooltip='Complete payment for the current sale',
        ),
        dict(
            name='pos_save_draft',
            caption='Save draft',
            image_url='Save',
            ribbon_tab='Home',
            requires_confirmation=True,
            confirmation_message='Save this cart as a draft? You can resume it later (max 3 drafts).',
            tooltip='Save cart without posting',
        ),
        dict(
            name='pos_resume_drafts',
            caption='Resume draft',
            image_url='FolderOpen',
            ribbon_tab='Home',
            tooltip='Load a saved POS draft into the cart',
        ),
        dict(
            name='pos_clear_cart',
            caption='Clear cart',
            image_url='Trash2',
            ribbon_tab='Home',
            requires_confirmation=True,
            confirmation_message='Remove all items from the current sale?',
            tooltip='Clear the current sale',
        ),
        dict(
            name='pos_record_payment',
            caption='Record payment',
            image_url='Banknote',
            ribbon_tab='Home',
            tooltip='Record a customer payment against open invoices',
        ),
        dict(
            name='pos_sales_history',
            caption='Sales history',
            image_url='History',
            ribbon_tab='Navigate',
            action_relative_url='PostedSalesInvoiceList',
            tooltip='View posted sales invoices',
        ),
    ]
    for spec in actions:
        PageAction.objects.update_or_create(
            page=pos_page,
            name=spec['name'],
            defaults={
                'caption': spec['caption'],
                'action_type': 'Ribbon',
                'requires_confirmation': spec.get('requires_confirmation', False),
                'confirmation_message': spec.get('confirmation_message'),
                'tooltip': spec.get('tooltip', ''),
                'visible': True,
                'ribbon_tab': spec.get('ribbon_tab', 'Home'),
                'image_url': spec.get('image_url', ''),
                'action_relative_url': spec.get('action_relative_url'),
            },
        )


def _seed_purchase_invoice_pages():
    """Document page + ListPart subform for PurchaseInvoice / PurchaseInvoiceLine."""
    subform, _ = Page.objects.update_or_create(
        name='PurchaseInvoiceSubform',
        defaults={
            'caption': 'Purchase Invoice Lines',
            'source_table': 'PurchaseInvoiceLine',
            'page_type': 'ListPart',
            'editable': True,
            'insert_allowed': True,
            'delete_allowed': True,
            'modify_allowed': True,
        },
    )

    sub_ctrl, _ = PageControl.objects.update_or_create(
        page=subform,
        name='PurchaseInvoiceSubformRepeater',
        defaults={
            'control_type': 'Repeater',
            'caption': 'Lines',
            'source_table': 'PurchaseInvoiceLine',
            'show_caption': False,
            'editable': True,
            'visible': True,
        },
    )
    _seed_fields(sub_ctrl, subform, [
        dict(name='type', caption='Type', field_type='Option', visible=True, editable=True,
             primary_key=False, tab_index=0, enum_values='item,resource,gl_account'),
        dict(name='no', caption='No.', field_type='Code', visible=True, editable=True,
             primary_key=False, tab_index=1,
             has_table_relation=True, related_table='Item', related_field='no',
             related_display_field='item_name',
             relation_context_field='type', relation_context_default='item'),
        dict(name='description', caption='Description', field_type='Text', visible=True,
             editable=True, primary_key=False, tab_index=2),
        dict(name='item_unit_of_measure', caption='Unit of Measure', field_type='Code',
             visible=True, editable=True, primary_key=False, tab_index=3,
             has_table_relation=True, related_table='ItemUnitOfMeasure', related_field='id',
             related_display_field='unit_of_measure__code', relation_context_field='no',
             visible_when_field='type', visible_when_values='item'),
        dict(name='location_code', caption='Location', field_type='Code', visible=True,
             editable=False, primary_key=False, tab_index=4,
             has_table_relation=True, related_table='Location', related_field='code',
             related_display_field='description',
             visible_when_field='type', visible_when_values='item'),
        dict(name='quantity', caption='Quantity', field_type='Integer', visible=True,
             editable=True, primary_key=False, tab_index=5),
        dict(name='unit_cost', caption='Unit Cost', field_type='Decimal', visible=True,
             editable=True, primary_key=False, tab_index=6),
        dict(name='total_amount', caption='Amount', field_type='Decimal', visible=True,
             editable=False, primary_key=False, tab_index=7),
    ])
    _wire_purchase_line_type_relations('PurchaseInvoiceLine')
    _ensure_table_relation('PurchaseInvoiceLine', 'location_code', 'Location', 'code', 'description')
    _hide_purchase_line_legacy_no_fields('PurchaseInvoiceSubformRepeater')

    PageAction.objects.update_or_create(
        page=subform,
        name='ItemTrackingLines',
        defaults={
            'caption': 'Item Tracking Lines',
            'action_relative_url': '#item-tracking-lines',
            'ribbon_tab': 'Line',
            'tooltip': 'Specify lot, serial, or expiry details for this line',
            'visible': True,
            'image_url': 'Barcode',
            'visible_when_field': 'type',
            'visible_when_values': 'item',
        },
    )

    doc, _ = Page.objects.update_or_create(
        name='PurchaseInvoice',
        defaults={
            'caption': 'Purchase Invoice',
            'source_table': 'PurchaseInvoice',
            'page_type': 'Document',
            'editable': True,
            'insert_allowed': True,
            'delete_allowed': True,
            'modify_allowed': True,
            'title_field': 'invoice_no',
        },
    )

    general_ctrl, _ = PageControl.objects.update_or_create(
        page=doc,
        name='PurchaseInvoiceGeneral',
        defaults={
            'control_type': 'Group',
            'caption': 'General',
            'source_table': 'PurchaseInvoice',
            'show_caption': True,
            'editable': True,
            'visible': True,
        },
    )
    _seed_fields(general_ctrl, doc, [
        dict(name='invoice_no', caption='No.', field_type='Code', visible=True, editable=False,
             primary_key=True, tab_index=0),
        dict(name='vendor', caption='Vendor No.', field_type='Code', visible=True, editable=True,
             primary_key=False, tab_index=1,
             has_table_relation=True, related_table='Vendor', related_field='no',
             related_display_field='name'),
        dict(name='vendor_invoice_no', caption='Vendor Invoice No.', field_type='Code', visible=True,
             editable=True, primary_key=False, tab_index=2),
        dict(name='document_date', caption='Document Date', field_type='Date', visible=True, editable=True,
             primary_key=False, tab_index=3),
        dict(name='posting_date', caption='Posting Date', field_type='Date', visible=False, editable=True,
             primary_key=False, tab_index=4),
        dict(name='due_date', caption='Due Date', field_type='Date', visible=False, editable=True,
             primary_key=False, tab_index=5),
        dict(name='payment_method', caption='How did you pay?', field_type='Code', visible=True,
             editable=True, primary_key=False, tab_index=6,
             has_table_relation=True, related_table='PaymentMethod', related_field='code',
             related_display_field='description'),
        dict(name='status', caption='Status', field_type='Option', visible=True, editable=False,
             primary_key=False, tab_index=7,
             enum_values='Open,Posted,Cancelled'),
        dict(name='total_amount', caption='Total', field_type='Decimal', visible=True, editable=False,
             primary_key=False, tab_index=8),
    ])
    PageControlField.objects.filter(
        page_control=general_ctrl,
        name='total_vat_amount',
    ).update(visible=False)

    part_ctrl, _ = PageControl.objects.update_or_create(
        page=doc,
        name='PurchaseInvoiceLines',
        defaults={
            'control_type': 'Part',
            'caption': 'Lines',
            'source_table': 'PurchaseInvoiceLine',
            'show_caption': True,
            'editable': True,
            'visible': True,
            'part_page': subform,
            'link_field': 'purchase_invoice__system_id',
        },
    )
    part_ctrl.part_page = subform
    part_ctrl.link_field = 'purchase_invoice__system_id'
    part_ctrl.save(update_fields=['part_page', 'link_field'])

    attachments_ctrl, _ = PageControl.objects.update_or_create(
        page=doc,
        name='PurchaseInvoiceAttachments',
        defaults={
            'control_type': 'FactBox',
            'caption': 'Attachments',
            'source_table': 'DocumentAttachment',
            'link_field': 'id',
            'show_caption': True,
            'editable': True,
            'visible': True,
            'tab_index': 10,
        },
    )
    attachments_ctrl.link_field = 'id'
    attachments_ctrl.save(update_fields=['link_field'])

    list_page, _ = Page.objects.update_or_create(
        name='PurchaseInvoiceList',
        defaults={
            'caption': 'Purchase Invoices',
            'source_table': 'PurchaseInvoice',
            'page_type': 'List',
            'editable': True,
            'insert_allowed': True,
            'delete_allowed': True,
            'modify_allowed': True,
            'card_page': doc,
            'title_field': 'invoice_no',
            'list_filter_field': 'status',
            'list_filter_value': 'Open',
        },
    )
    list_page.card_page = doc
    list_page.list_filter_field = 'status'
    list_page.list_filter_value = 'Open'
    list_page.save(update_fields=['card_page', 'list_filter_field', 'list_filter_value'])

    list_ctrl, _ = PageControl.objects.update_or_create(
        page=list_page,
        name='PurchaseInvoiceListControl',
        defaults={
            'control_type': 'Repeater',
            'caption': 'Purchase Invoices',
            'source_table': 'PurchaseInvoice',
            'show_caption': True,
            'editable': False,
            'visible': True,
        },
    )
    _seed_fields(list_ctrl, list_page, [
        dict(name='invoice_no', caption='No.', field_type='Code', visible=True, editable=False,
             primary_key=True, tab_index=0, freeze_column=True, has_drill_down_page=True),
        dict(name='vendor', caption='Vendor', field_type='Code', visible=True, editable=False,
             primary_key=False, tab_index=1),
        dict(name='total_amount', caption='Amount', field_type='Decimal', visible=True, editable=False,
             primary_key=False, tab_index=2),
        dict(name='document_date', caption='Document Date', field_type='Date', visible=True, editable=False,
             primary_key=False, tab_index=3),
        dict(name='status', caption='Status', field_type='Option', visible=True, editable=False,
             primary_key=False, tab_index=4,
             enum_values='Open,Posted,Cancelled'),
    ])
    PageControlField.objects.filter(
        page_control=list_ctrl,
        name='vendor_invoice_no',
    ).update(visible=False)

    _link_drill_down(
        page_names=('PurchaseInvoiceList',),
        field_name='invoice_no',
        drill_down_page=doc,
    )

    PageAction.objects.update_or_create(
        page=doc,
        name='preview_purchase_invoice',
        defaults={
            'caption': 'Preview Posting',
            'requires_confirmation': False,
            'confirmation_message': '',
            'tooltip': 'Preview ledger entries before posting',
            'visible': True,
            'ribbon_tab': 'Home',
            'image_url': 'Eye',
            'visible_when_field': 'status',
            'visible_when_values': 'Open',
        },
    )
    PageAction.objects.update_or_create(
        page=doc,
        name='post_purchase_invoice',
        defaults={
            'caption': 'Post',
            'requires_confirmation': True,
            'confirmation_message': 'Post this purchase invoice to the general ledger?',
            'tooltip': 'Post purchase invoice',
            'visible': True,
            'ribbon_tab': 'Home',
            'image_url': 'CircleCheck',
            'visible_when_field': 'status',
            'visible_when_values': 'Open',
        },
    )
    PageAction.objects.update_or_create(
        page=doc,
        name='print_purchase_invoice',
        defaults={
            'caption': 'Print',
            'action_relative_url': '#print',
            'requires_confirmation': False,
            'confirmation_message': '',
            'tooltip': 'Print purchase invoice',
            'visible': True,
            'ribbon_tab': 'Home',
            'image_url': 'Printer',
            'visible_when_field': 'status',
            'visible_when_values': 'Posted',
        },
    )

    return doc, list_page


def _seed_status_filtered_list_page(
    *,
    name: str,
    caption: str,
    source_table: str,
    card_page: Page,
    title_field: str,
    control_name: str,
    list_fields: list[dict],
    filter_field: str,
    filter_value: str,
    exclude_field: str = '',
    exclude_values: str = '',
) -> Page:
    """List page scoped to one field value (e.g. status=Posted) via page-engine metadata."""
    list_page, _ = Page.objects.update_or_create(
        name=name,
        defaults={
            'caption': caption,
            'source_table': source_table,
            'page_type': 'List',
            'editable': False,
            'insert_allowed': False,
            'delete_allowed': False,
            'modify_allowed': False,
            'card_page': card_page,
            'title_field': title_field,
            'list_filter_field': filter_field,
            'list_filter_value': filter_value,
            'list_exclude_field': exclude_field,
            'list_exclude_values': exclude_values,
        },
    )
    list_page.card_page = card_page
    list_page.list_filter_field = filter_field
    list_page.list_filter_value = filter_value
    list_page.list_exclude_field = exclude_field
    list_page.list_exclude_values = exclude_values
    list_page.save(update_fields=[
        'card_page', 'list_filter_field', 'list_filter_value',
        'list_exclude_field', 'list_exclude_values',
    ])

    list_ctrl, _ = PageControl.objects.update_or_create(
        page=list_page,
        name=control_name,
        defaults={
            'control_type': 'Repeater',
            'caption': caption,
            'source_table': source_table,
            'show_caption': True,
            'editable': False,
            'visible': True,
        },
    )
    _seed_fields(list_ctrl, list_page, list_fields)
    return list_page


def _seed_posted_sales_invoice_list(doc: Page) -> Page:
    """Sales History list — backed by PostedSalesInvoice (posted archive), not open SalesInvoice."""
    list_page, _ = Page.objects.update_or_create(
        name='PostedSalesInvoiceList',
        defaults={
            'caption': 'Posted Sales Invoices',
            'source_table': 'PostedSalesInvoice',
            'page_type': 'List',
            'editable': False,
            'insert_allowed': False,
            'delete_allowed': False,
            'modify_allowed': False,
            'card_page': doc,
            'title_field': 'no',
            'list_filter_field': '',
            'list_filter_value': '',
        },
    )
    list_page.card_page = doc
    list_page.list_filter_field = ''
    list_page.list_filter_value = ''
    list_page.save(update_fields=['card_page', 'list_filter_field', 'list_filter_value'])

    list_ctrl, _ = PageControl.objects.update_or_create(
        page=list_page,
        name='PostedSalesInvoiceListControl',
        defaults={
            'control_type': 'Repeater',
            'caption': 'Posted Sales Invoices',
            'source_table': 'PostedSalesInvoice',
            'show_caption': True,
            'editable': False,
            'visible': True,
        },
    )
    _seed_fields(list_ctrl, list_page, [
        dict(name='no', caption='No.', field_type='Code', visible=True, editable=False,
             primary_key=True, tab_index=0, freeze_column=True),
        dict(name='customer', caption='Customer', field_type='Code', visible=True, editable=False,
             primary_key=False, tab_index=1,
             has_table_relation=True, related_table='Customer', related_field='no',
             related_display_field='name'),
        dict(name='posting_date', caption='Posting Date', field_type='Date', visible=True, editable=False,
             primary_key=False, tab_index=2),
        dict(name='total_amount', caption='Amount', field_type='Decimal', visible=True, editable=False,
             primary_key=False, tab_index=3),
        dict(name='user_name', caption='Sales Person', field_type='Text', visible=True, editable=False,
             primary_key=False, tab_index=4),
        dict(name='status', caption='Status', field_type='Option', visible=True, editable=False,
             primary_key=False, tab_index=5,
             enum_values='Posted,Closed'),
        dict(name='document_date', caption='Document Date', field_type='Date', visible=False, editable=False,
             primary_key=False, tab_index=98),
        dict(name='due_date', caption='Due Date', field_type='Date', visible=False, editable=False,
             primary_key=False, tab_index=99),
    ])
    # Remove legacy SalesInvoice list fields from older seeds.
    PageControlField.objects.filter(
        page=list_page,
        page_control__name='PostedSalesInvoiceListControl',
        name__in=('invoice_no', 'total_vat_amount'),
    ).delete()
    return list_page


def _seed_posted_sales_invoice_list_scope_actions(list_page: Page) -> None:
    """Period scope chips on Posted Sales Invoices list (page-engine PageActions)."""
    PageControl.objects.filter(
        page=list_page,
        name='PostedSalesCueGroup',
    ).delete()
    PageControl.objects.filter(
        page=list_page,
        parent_control__name='PostedSalesCueGroup',
    ).delete()

    base = list_page.name
    actions = [
        (
            'list_filter_all',
            'All posted',
            f'{base}',
            'View all posted sales invoices',
        ),
        (
            'list_filter_today',
            'Today',
            f'{base}?posting_date=__today__&filterLabel=Today',
            "Invoices posted today",
        ),
        (
            'list_filter_yesterday',
            'Yesterday',
            f'{base}?posting_date=__yesterday__&filterLabel=Yesterday',
            "Invoices posted yesterday",
        ),
        (
            'list_filter_quarter',
            'This quarter',
            (
                f'{base}?posting_date_from=__quarter_start__'
                f'&posting_date_to=__quarter_end__&filterLabel=This quarter'
            ),
            'Invoices posted in the current calendar quarter',
        ),
        (
            'list_filter_week',
            'This week',
            (
                f'{base}?posting_date_from=__week_start__'
                f'&posting_date_to=__week_end__&filterLabel=This week'
            ),
            'Invoices posted in the current calendar week',
        ),
        (
            'list_filter_month',
            'This month',
            (
                f'{base}?posting_date_from=__month_start__'
                f'&posting_date_to=__month_end__&filterLabel=This month'
            ),
            'Invoices posted in the current calendar month',
        ),
    ]
    for name, caption, relative_url, tooltip in actions:
        PageAction.objects.update_or_create(
            page=list_page,
            name=name,
            defaults={
                'caption': caption,
                'action_type': 'Ribbon',
                'requires_confirmation': False,
                'confirmation_message': '',
                'tooltip': tooltip,
                'visible': True,
                'ribbon_tab': 'Scope',
                'image_url': '',
                'action_relative_url': relative_url,
            },
        )


def _seed_posted_purchase_invoice_pages() -> Page:
    """BC Pages 138 (Document) + 139 (ListPart) on PostedPurchaseInvoice tables."""
    subform, _ = Page.objects.update_or_create(
        name='PostedPurchaseInvoiceSubform',
        defaults={
            'caption': 'Posted Purchase Invoice Lines',
            'source_table': 'PostedPurchaseInvoiceLine',
            'page_type': 'ListPart',
            'editable': False,
            'insert_allowed': False,
            'delete_allowed': False,
            'modify_allowed': False,
        },
    )

    sub_ctrl, _ = PageControl.objects.update_or_create(
        page=subform,
        name='PostedPurchaseInvoiceSubformRepeater',
        defaults={
            'control_type': 'Repeater',
            'caption': 'Lines',
            'source_table': 'PostedPurchaseInvoiceLine',
            'show_caption': False,
            'editable': False,
            'visible': True,
        },
    )
    _seed_fields(sub_ctrl, subform, [
        dict(name='type', caption='Type', field_type='Option', visible=True, editable=False,
             primary_key=False, tab_index=0, enum_values='item,resource,gl_account'),
        dict(name='no', caption='No.', field_type='Code', visible=True, editable=False,
             primary_key=False, tab_index=1),
        dict(name='description', caption='Description', field_type='Text', visible=True,
             editable=False, primary_key=False, tab_index=2),
        dict(name='item_unit_of_measure', caption='Unit of Measure', field_type='Code',
             visible=True, editable=False, primary_key=False, tab_index=3,
             visible_when_field='type', visible_when_values='item'),
        dict(name='location_code', caption='Location', field_type='Code', visible=True,
             editable=False, primary_key=False, tab_index=4,
             visible_when_field='type', visible_when_values='item'),
        dict(name='quantity', caption='Quantity', field_type='Integer', visible=True,
             editable=False, primary_key=False, tab_index=5),
        dict(name='unit_cost', caption='Direct Unit Cost Excl. VAT', field_type='Decimal',
             visible=True, editable=False, primary_key=False, tab_index=6),
        dict(name='amount', caption='Amount', field_type='Decimal', visible=True,
             editable=False, primary_key=False, tab_index=7),
    ])
    _hide_purchase_line_legacy_no_fields('PostedPurchaseInvoiceSubformRepeater')

    PageAction.objects.update_or_create(
        page=subform,
        name='PostedItemTrackingLines',
        defaults={
            'caption': 'Item Tracking Entries',
            'action_relative_url': '#posted-item-tracking-lines',
            'ribbon_tab': 'Line',
            'tooltip': 'View lot, serial, or expiry posted for this line',
            'visible': True,
            'image_url': 'Barcode',
            'visible_when_field': 'type',
            'visible_when_values': 'item',
        },
    )

    doc, _ = Page.objects.update_or_create(
        name='PostedPurchaseInvoice',
        defaults={
            'caption': 'Posted Purchase Invoice',
            'source_table': 'PostedPurchaseInvoice',
            'page_type': 'Document',
            'editable': False,
            'insert_allowed': False,
            'delete_allowed': False,
            'modify_allowed': False,
            'title_field': 'no',
        },
    )

    general_ctrl, _ = PageControl.objects.update_or_create(
        page=doc,
        name='PostedPurchaseInvoiceGeneral',
        defaults={
            'control_type': 'Group',
            'caption': 'General',
            'source_table': 'PostedPurchaseInvoice',
            'show_caption': True,
            'editable': False,
            'visible': True,
        },
    )
    _seed_fields(general_ctrl, doc, [
        dict(name='no', caption='No.', field_type='Code', visible=True, editable=False,
             primary_key=True, tab_index=0),
        dict(name='vendor', caption='Vendor', field_type='Code', visible=True, editable=False,
             primary_key=False, tab_index=1,
             has_table_relation=True, related_table='Vendor', related_field='no',
             related_display_field='name'),
        dict(name='vendor_invoice_no', caption='Vendor Invoice No.', field_type='Code',
             visible=True, editable=False, primary_key=False, tab_index=2),
        dict(name='document_date', caption='Document Date', field_type='Date', visible=True,
             editable=False, primary_key=False, tab_index=3),
        dict(name='posting_date', caption='Posting Date', field_type='Date', visible=True,
             editable=False, primary_key=False, tab_index=4),
        dict(name='vat_date', caption='VAT Date', field_type='Date', visible=False,
             editable=False, primary_key=False, tab_index=5),
        dict(name='due_date', caption='Due Date', field_type='Date', visible=True,
             editable=False, primary_key=False, tab_index=6),
    ])
    PageControlField.objects.filter(
        page=doc,
        page_control__name='PostedPurchaseInvoiceGeneral',
        name='closed',
    ).delete()

    part_ctrl, _ = PageControl.objects.update_or_create(
        page=doc,
        name='PostedPurchaseInvoiceLines',
        defaults={
            'control_type': 'Part',
            'caption': 'Lines',
            'source_table': 'PostedPurchaseInvoiceLine',
            'show_caption': True,
            'editable': False,
            'visible': True,
            'part_page': subform,
            'link_field': 'posted_purchase_invoice__system_id',
        },
    )
    part_ctrl.part_page = subform
    part_ctrl.link_field = 'posted_purchase_invoice__system_id'
    part_ctrl.save(update_fields=['part_page', 'link_field'])

    return doc


def _seed_posted_item_tracking_lines_page() -> Page:
    """BC Page 6511 — Posted Item Tracking Lines (read-only item ledger)."""
    header_card, _ = Page.objects.update_or_create(
        name='PostedItemTrackingLinesHeader',
        defaults={
            'caption': 'General',
            'source_table': 'PostedPurchaseInvoiceLine',
            'page_type': 'Card',
            'editable': False,
            'insert_allowed': False,
            'delete_allowed': False,
            'modify_allowed': False,
        },
    )
    header_ctrl, _ = PageControl.objects.get_or_create(
        page=header_card,
        name='PostedItemTrackingLinesGeneral',
        defaults={
            'control_type': 'Group',
            'caption': 'General',
            'source_table': 'PostedPurchaseInvoiceLine',
            'show_caption': True,
            'editable': False,
            'visible': True,
        },
    )
    PageControlField.objects.filter(page=header_card, page_control=header_ctrl).delete()
    _seed_fields(header_ctrl, header_card, [
        dict(name='item', caption='Item No.', field_type='Code', visible=True, editable=False,
             tab_index=0,
             has_table_relation=True, related_table='Item', related_field='no',
             related_display_field='item_name'),
        dict(name='description', caption='Description', field_type='Text', visible=True,
             editable=False, tab_index=1),
        dict(name='quantity', caption='Quantity', field_type='Integer', visible=True,
             editable=False, tab_index=2),
    ])

    worksheet, _ = Page.objects.update_or_create(
        name='PostedItemTrackingLines',
        defaults={
            'caption': 'Posted Item Tracking Lines',
            'source_table': 'ItemLedgerEntries',
            'page_type': 'Worksheet',
            'editable': False,
            'insert_allowed': False,
            'delete_allowed': False,
            'modify_allowed': False,
            'context_filter_field': 'vendor_invoice_no',
            'header_page': header_card,
        },
    )
    worksheet.header_page = header_card
    worksheet.context_filter_field = 'vendor_invoice_no'
    worksheet.save(update_fields=['header_page', 'context_filter_field'])

    lines_ctrl, _ = PageControl.objects.get_or_create(
        page=worksheet,
        name='PostedItemTrackingLinesRepeater',
        defaults={
            'control_type': 'Repeater',
            'caption': 'Lines',
            'source_table': 'ItemLedgerEntries',
            'show_caption': False,
            'editable': False,
            'visible': True,
        },
    )
    PageControlField.objects.filter(page=worksheet, page_control=lines_ctrl).delete()
    _seed_fields(lines_ctrl, worksheet, [
        dict(name='serial_no', caption='Serial No.', field_type='Code', visible=True,
             editable=False, tab_index=0),
        dict(name='lot_no', caption='Lot No.', field_type='Code', visible=True,
             editable=False, tab_index=1),
        dict(name='expiry_date', caption='Expiration Date', field_type='Date', visible=True,
             editable=False, tab_index=2),
        dict(name='quantity', caption='Quantity', field_type='Integer', visible=True,
             editable=False, tab_index=3),
        dict(name='document_no', caption='Document No.', field_type='Code', visible=False,
             editable=False, tab_index=4),
        dict(name='id', caption='Entry No.', field_type='Integer', visible=False,
             editable=False, tab_index=5, primary_key=True),
    ])
    return worksheet


def _seed_posted_purchase_invoice_list(doc: Page) -> Page:
    list_page, _ = Page.objects.update_or_create(
        name='PostedPurchaseInvoiceList',
        defaults={
            'caption': 'Posted Purchase Invoices',
            'source_table': 'PostedPurchaseInvoice',
            'page_type': 'List',
            'editable': False,
            'insert_allowed': False,
            'delete_allowed': False,
            'modify_allowed': False,
            'card_page': doc,
            'title_field': 'no',
            'list_filter_field': '',
            'list_filter_value': '',
        },
    )
    list_page.card_page = doc
    list_page.list_filter_field = ''
    list_page.list_filter_value = ''
    list_page.save(update_fields=['card_page', 'list_filter_field', 'list_filter_value'])

    list_ctrl, _ = PageControl.objects.update_or_create(
        page=list_page,
        name='PostedPurchaseInvoiceListControl',
        defaults={
            'control_type': 'Repeater',
            'caption': 'Posted Purchase Invoices',
            'source_table': 'PostedPurchaseInvoice',
            'show_caption': True,
            'editable': False,
            'visible': True,
        },
    )
    _seed_fields(list_ctrl, list_page, [
        dict(name='no', caption='No.', field_type='Code', visible=True, editable=False,
             primary_key=True, tab_index=0, freeze_column=True),
        dict(name='vendor', caption='Vendor', field_type='Code', visible=True, editable=False,
             primary_key=False, tab_index=1,
             has_table_relation=True, related_table='Vendor', related_field='no',
             related_display_field='name'),
        dict(name='vendor_invoice_no', caption='Vendor Invoice No.', field_type='Code', visible=True,
             editable=False, primary_key=False, tab_index=2),
        dict(name='posting_date', caption='Posting Date', field_type='Date', visible=True, editable=False,
             primary_key=False, tab_index=3),
        dict(name='document_date', caption='Document Date', field_type='Date', visible=True, editable=False,
             primary_key=False, tab_index=4),
        dict(name='due_date', caption='Due Date', field_type='Date', visible=False, editable=False,
             primary_key=False, tab_index=5),
    ])
    # Remove legacy PurchaseInvoice list fields from older seeds.
    PageControlField.objects.filter(
        page=list_page,
        page_control__name='PostedPurchaseInvoiceListControl',
        name__in=('invoice_no', 'status', 'total_amount', 'user_name', 'total_vat_amount'),
    ).delete()
    return list_page


def _seed_fields(control: PageControl, page: Page, fields: list[dict]):
    for f in fields:
        obj, created = PageControlField.objects.get_or_create(
            page_control=control,
            name=f['name'],
            defaults={
                'page': page,
                'field_id': f.get('tab_index', 0),
                'caption': f['caption'],
                'field_type': f['field_type'],
                'visible': f.get('visible', True),
                'editable': f.get('editable', True),
                'primary_key': f.get('primary_key', False),
                'required': f.get('required', False),
                'tab_index': f.get('tab_index', 0),
                'enum_values': f.get('enum_values'),
                'freeze_column': f.get('freeze_column', False),
            },
        )
        updates: list[str] = []
        if not created and f.get('enum_values') and not obj.enum_values:
            obj.enum_values = f['enum_values']
            updates.append('enum_values')
        if f.get('freeze_column') and not obj.freeze_column:
            obj.freeze_column = True
            updates.append('freeze_column')
        for attr in ('caption', 'field_type', 'visible', 'editable', 'tab_index', 'required', 'primary_key'):
            if attr in f and getattr(obj, attr) != f[attr]:
                setattr(obj, attr, f[attr])
                updates.append(attr)
        if updates:
            obj.save(update_fields=updates)
        if f.get('has_table_relation'):
            obj.has_table_relation = True
            obj.related_table = f.get('related_table')
            obj.related_field = f.get('related_field')
            obj.related_display_field = f.get('related_display_field')
            relation_updates = [
                'has_table_relation', 'related_table', 'related_field', 'related_display_field',
            ]
            if 'relation_context_field' in f:
                obj.relation_context_field = f['relation_context_field']
                relation_updates.append('relation_context_field')
            if 'relation_context_default' in f:
                obj.relation_context_default = f['relation_context_default']
                relation_updates.append('relation_context_default')
            obj.save(update_fields=relation_updates)
        footer_updates: list[str] = []
        if 'relation_lookup_footer' in f:
            obj.relation_lookup_footer = f['relation_lookup_footer']
            footer_updates.append('relation_lookup_footer')
        if 'relation_part_control_name' in f:
            obj.relation_part_control_name = f['relation_part_control_name']
            footer_updates.append('relation_part_control_name')
        if footer_updates:
            obj.save(update_fields=footer_updates)
        visibility_updates: list[str] = []
        if 'visible_when_field' in f:
            obj.visible_when_field = f['visible_when_field']
            visibility_updates.append('visible_when_field')
        if 'visible_when_values' in f:
            obj.visible_when_values = f['visible_when_values']
            visibility_updates.append('visible_when_values')
        if visibility_updates:
            obj.save(update_fields=visibility_updates)
        if f.get('has_drill_down_page'):
            obj.has_drill_down_page = True
            obj.save(update_fields=['has_drill_down_page'])
        if obj.field_id != obj.tab_index:
            obj.field_id = obj.tab_index
            obj.save(update_fields=['field_id'])


def _wire_relation_lookup_fields(
    page: Page,
    field_names: tuple[str, ...],
    *,
    part_control_name: str,
    lookup_page: Page,
) -> None:
    """Enable BC-style relation footer on fields and wire the full-list lookup page."""
    for name in field_names:
        field = PageControlField.objects.filter(page=page, name=name).first()
        if not field:
            continue
        field.relation_lookup_footer = True
        field.relation_part_control_name = part_control_name
        field.has_lookup_page = True
        field.lookup_page = lookup_page
        field.save(
            update_fields=[
                'relation_lookup_footer',
                'relation_part_control_name',
                'has_lookup_page',
                'lookup_page',
            ],
        )


PERMISSION_OBJECT_TYPE_RELATIONS = (
    ('Page', 'Objects'),
    ('Table', 'Objects'),
)


def _wire_permission_object_relations() -> None:
    """Type → Object ID dropdowns on permission set lines (BC-style)."""
    source_table = 'PermissionSetLine'
    source_field = 'object_id'
    TableRelation.objects.filter(
        source_table=source_table,
        source_field=source_field,
    ).delete()
    for context_value, related_table in PERMISSION_OBJECT_TYPE_RELATIONS:
        TableRelation.objects.create(
            source_table=source_table,
            source_field=source_field,
            related_table=related_table,
            related_field='object_id',
            display_field='object_name',
            context_field='object_type',
            context_value=context_value,
        )
    PageControlField.objects.filter(
        page_control__source_table=source_table,
        name=source_field,
    ).update(
        relation_context_field='object_type',
        relation_context_default='Page',
    )


def _wire_purchase_line_type_relations(
    source_table: str,
    source_field: str = 'no',
    context_field: str = 'type',
    context_default: str = 'item',
):
    """Wire unified No. field: lookup table depends on line Type (BC-style)."""
    TableRelation.objects.filter(
        source_table=source_table,
        source_field=source_field,
    ).delete()
    for context_value, related_table in PURCHASE_INVOICE_LINE_TYPE_RELATIONS:
        related_field = 'code' if related_table == 'Resource' else 'no'
        display_field = 'item_name' if related_table == 'Item' else 'name'
        TableRelation.objects.create(
            source_table=source_table,
            source_field=source_field,
            related_table=related_table,
            related_field=related_field,
            display_field=display_field,
            context_field=context_field,
            context_value=context_value,
        )
    PageControlField.objects.filter(
        page_control__source_table=source_table,
        name=source_field,
    ).update(
        relation_context_field=context_field,
        relation_context_default=context_default,
    )


def _hide_purchase_line_legacy_no_fields(repeater_control_name: str) -> None:
    """Hide item/resource/gl_account columns superseded by unified ``no`` on line subforms."""
    PageControlField.objects.filter(
        page_control__name=repeater_control_name,
        name__in=PURCHASE_LINE_LEGACY_NO_FIELD_NAMES,
    ).update(visible=False, editable=False)


def _wire_context_account_relations(
    source_table: str,
    source_field: str,
    context_field: str,
    context_default: str = '',
):
    """Wire Account No. style fields: options depend on Account Type enum value."""
    TableRelation.objects.filter(
        source_table=source_table,
        source_field=source_field,
    ).delete()
    for context_value, related_table in ACCOUNT_TYPE_RELATIONS:
        TableRelation.objects.create(
            source_table=source_table,
            source_field=source_field,
            related_table=related_table,
            related_field='no',
            display_field='name',
            context_field=context_field,
            context_value=context_value,
        )
    PageControlField.objects.filter(
        page_control__source_table=source_table,
        name=source_field,
    ).update(
        relation_context_field=context_field,
        relation_context_default=context_default,
    )


def _seed_user_setup_page() -> Page:
    """List-only editable User Setup page (Business Central style, like sacco)."""
    user_setup_page, _ = Page.objects.update_or_create(
        name='UserSetupList',
        defaults={
            'caption': 'User Setup',
            'source_table': 'UserSetup',
            'page_type': 'List',
            'editable': True,
            'insert_allowed': False,
            'delete_allowed': False,
            'modify_allowed': True,
            'card_page': None,
            'context_filter_field': 'user__full_name',
            'context_key_field': 'full_name',
        },
    )
    user_setup_page.card_page = None
    user_setup_page.context_filter_field = 'user__full_name'
    user_setup_page.context_key_field = 'full_name'
    user_setup_page.save(update_fields=['card_page', 'context_filter_field', 'context_key_field'])

    control, _ = PageControl.objects.get_or_create(
        page=user_setup_page,
        name='UserSetupLines',
        defaults={
            'control_type': 'Repeater',
            'caption': 'User Setup',
            'source_table': 'UserSetup',
            'show_caption': False,
            'editable': True,
            'visible': True,
        },
    )

    PageControlField.objects.filter(page=user_setup_page, page_control=control).delete()
    _seed_fields(control, user_setup_page, [
        dict(
            name='user__full_name', caption='User Name', field_type='Text',
            visible=True, editable=False, primary_key=False, tab_index=0, freeze_column=True,
        ),
        dict(
            name='user__email', caption='Email', field_type='Text',
            visible=True, editable=False, primary_key=False, tab_index=1,
        ),
        dict(
            name='can_see_buying_price', caption='See Buying Price', field_type='Boolean',
            visible=True, editable=True, primary_key=False, tab_index=2,
        ),
        dict(
            name='can_see_profit_margin', caption='See Profit Margin', field_type='Boolean',
            visible=True, editable=True, primary_key=False, tab_index=3,
        ),
        dict(
            name='can_see_item_cost', caption='See Item Cost', field_type='Boolean',
            visible=True, editable=True, primary_key=False, tab_index=4,
        ),
        dict(
            name='can_post_previous_dates', caption='Post Previous Dates', field_type='Boolean',
            visible=True, editable=True, primary_key=False, tab_index=5,
        ),
        dict(
            name='can_reverse_purchase_invoice', caption='Reverse Purchase Invoice', field_type='Boolean',
            visible=True, editable=True, primary_key=False, tab_index=6,
        ),
        dict(
            name='can_reverse_sales_invoice', caption='Reverse Sales Invoice', field_type='Boolean',
            visible=True, editable=True, primary_key=False, tab_index=7,
        ),
        dict(
            name='can_reverse_item_journal', caption='Reverse Item Journal', field_type='Boolean',
            visible=True, editable=True, primary_key=False, tab_index=8,
        ),
        dict(
            name='can_view_only_their_sales', caption='View Only Their Sales', field_type='Boolean',
            visible=True, editable=True, primary_key=False, tab_index=9,
        ),
        dict(
            name='user__can_switch_branch', caption='Can Switch Branch', field_type='Boolean',
            visible=True, editable=True, primary_key=False, tab_index=10,
        ),
    ])
    return user_setup_page


def _seed_users_pages(_user_setup_page: Page) -> tuple[Page, Page]:
    """Users list/card pages (CustomUser), mirroring sacco CompanyUsers pages."""
    users_card, _ = Page.objects.update_or_create(
        name='UsersCard',
        defaults={
            'caption': 'User',
            'source_table': 'CustomUser',
            'page_type': 'Card',
            'editable': True,
            'insert_allowed': True,
            'delete_allowed': True,
            'modify_allowed': True,
            'title_field': 'full_name',
        },
    )

    users_card_ctrl, _ = PageControl.objects.get_or_create(
        page=users_card,
        name='UsersCardGroup',
        defaults={
            'control_type': 'Group',
            'caption': 'General',
            'source_table': 'CustomUser',
            'show_caption': True,
            'editable': True,
            'visible': True,
        },
    )

    PageControlField.objects.filter(page=users_card, page_control=users_card_ctrl).delete()
    _seed_fields(users_card_ctrl, users_card, [
        dict(name='full_name', caption='User Name', field_type='Text',
             visible=True, editable=True, primary_key=True, tab_index=0, required=True),
        dict(name='email', caption='Email', field_type='Text',
             visible=True, editable=True, primary_key=False, tab_index=1, required=True),
        dict(name='username', caption='Username', field_type='Code',
             visible=True, editable=True, primary_key=False, tab_index=2),
        dict(name='phone_number', caption='Phone No.', field_type='Text',
             visible=True, editable=True, primary_key=False, tab_index=3),
        dict(name='is_active', caption='Active', field_type='Boolean',
             visible=True, editable=True, primary_key=False, tab_index=4),
        dict(name='global_dimension_1', caption='Branch', field_type='Lookup',
             visible=True, editable=True, primary_key=False, tab_index=5,
             has_table_relation=True, related_table='DimensionValue', related_field='id',
             related_display_field='code'),
        dict(name='password', caption='Password', field_type='Password',
             visible=True, editable=True, primary_key=False, tab_index=6),
        dict(name='must_change_password', caption='User must change password at next login',
             field_type='Boolean', visible=True, editable=True, primary_key=False, tab_index=7),
    ])
    _ensure_table_relation('CustomUser', 'global_dimension_1', 'DimensionValue', 'id', 'code')

    users_access_ctrl, _ = PageControl.objects.get_or_create(
        page=users_card,
        name='UsersAccessGroup',
        defaults={
            'control_type': 'Group',
            'caption': 'Access',
            'source_table': 'CustomUser',
            'show_caption': True,
            'editable': True,
            'visible': True,
        },
    )
    PageControlField.objects.filter(
        page=users_card, page_control=users_access_ctrl,
    ).delete()
    _seed_fields(users_access_ctrl, users_card, [
        dict(name='assigned_user_groups', caption='User Groups', field_type='Text',
             visible=True, editable=False, primary_key=False, tab_index=0),
    ])

    user_ps_subform, _ = Page.objects.update_or_create(
        name='UserPermissionSetsSubform',
        defaults={
            'caption': 'Permission Sets',
            'source_table': 'UserPermissionSets',
            'page_type': 'ListPart',
            'editable': False,
            'insert_allowed': False,
            'delete_allowed': False,
            'modify_allowed': False,
        },
    )
    user_ps_ctrl, _ = PageControl.objects.get_or_create(
        page=user_ps_subform,
        name='UserPermissionSetsControl',
        defaults={
            'control_type': 'Repeater',
            'caption': 'Permission Sets',
            'source_table': 'UserPermissionSets',
            'show_caption': True,
            'editable': False,
            'visible': True,
        },
    )
    PageControlField.objects.filter(
        page=user_ps_subform, page_control=user_ps_ctrl,
    ).delete()
    _seed_fields(user_ps_ctrl, user_ps_subform, [
        dict(name='code', caption='Permission Set', field_type='Code',
             visible=True, editable=False, primary_key=True, tab_index=0),
        dict(name='name', caption='Name', field_type='Text',
             visible=True, editable=False, primary_key=False, tab_index=1),
        dict(name='via_user_groups', caption='Via User Groups', field_type='Text',
             visible=True, editable=False, primary_key=False, tab_index=2),
        dict(name='description', caption='Description', field_type='Text',
             visible=True, editable=False, primary_key=False, tab_index=3),
    ])
    PageAction.objects.update_or_create(
        page=user_ps_subform,
        name='OpenPermissionSet',
        defaults={
            'caption': 'Permissions',
            'action_relative_url': 'PermissionSetsCard',
            'ribbon_tab': 'Line',
            'tooltip': 'Open the selected permission set',
            'visible': True,
            'image_url': 'Shield',
        },
    )
    user_ps_part, _ = PageControl.objects.update_or_create(
        page=users_card,
        name='UserPermissionSetsPart',
        defaults={
            'control_type': 'Part',
            'caption': 'Permission Sets',
            'source_table': 'UserPermissionSets',
            'show_caption': True,
            'editable': False,
            'visible': True,
            'part_page': user_ps_subform,
            'link_field': '',
        },
    )
    user_ps_part.part_page = user_ps_subform
    user_ps_part.link_field = ''
    user_ps_part.save(update_fields=['part_page', 'link_field'])

    users_page, _ = Page.objects.update_or_create(
        name='UsersList',
        defaults={
            'caption': 'Users',
            'source_table': 'CustomUser',
            'page_type': 'List',
            'editable': False,
            'insert_allowed': True,
            'delete_allowed': False,
            'modify_allowed': False,
            'card_page': users_card,
        },
    )
    users_page.card_page = users_card
    users_page.save(update_fields=['card_page'])

    users_ctrl, _ = PageControl.objects.get_or_create(
        page=users_page,
        name='UsersListControl',
        defaults={
            'control_type': 'Repeater',
            'caption': 'Users',
            'source_table': 'CustomUser',
            'show_caption': False,
            'editable': False,
            'visible': True,
        },
    )

    PageControlField.objects.filter(page=users_page, page_control=users_ctrl).delete()
    _seed_fields(users_ctrl, users_page, [
        dict(name='username', caption='Username', field_type='Code',
             visible=True, editable=False, primary_key=True, tab_index=0),
        dict(name='full_name', caption='Name', field_type='Text',
             visible=True, editable=False, primary_key=False, tab_index=1),
        dict(name='email', caption='Email', field_type='Text',
             visible=True, editable=False, primary_key=False, tab_index=2),
        dict(name='phone_number', caption='Phone No.', field_type='Text',
             visible=True, editable=False, primary_key=False, tab_index=3),
        dict(name='is_active', caption='Active', field_type='Boolean',
             visible=True, editable=False, primary_key=False, tab_index=4),
    ])

    PageAction.objects.update_or_create(
        page=users_card,
        name='OpenUserSetup',
        defaults={
            'caption': 'User Setup',
            'requires_confirmation': False,
            'confirmation_message': '',
            'tooltip': 'Open User Setup for this user',
            'action_relative_url': 'UserSetupList',
            'visible': True,
            'ribbon_tab': 'Home',
            'image_url': 'UserCog',
        },
    )

    return users_card, users_page


def _ensure_user_setups() -> None:
    from authentication.models import CustomUser, UserSetup

    for user in CustomUser.objects.exclude(username='debug_admin'):
        UserSetup.get_or_create_for_user(user)


def _ensure_user_personalizations() -> None:
    from authentication.models import CustomUser, UserPersonalization

    for user in CustomUser.objects.filter(is_active=True, terminated=False).exclude(
        username='debug_admin',
    ):
        UserPersonalization.get_or_create_for_user(user)


def _seed_user_settings_page() -> tuple[Page, Page]:
    """List + card pages for user personalization (language, time zone, role centre, etc.)."""
    card, _ = Page.objects.update_or_create(
        name='UserSettingsCard',
        defaults={
            'caption': 'User settings',
            'source_table': 'UserPersonalization',
            'page_type': 'Card',
            'editable': True,
            'insert_allowed': False,
            'delete_allowed': False,
            'modify_allowed': True,
            'title_field': 'user__username',
        },
    )
    card.title_field = 'user__username'
    card.save(update_fields=['title_field'])

    prefs_ctrl, _ = PageControl.objects.get_or_create(
        page=card,
        name='UserSettingsPreferences',
        defaults={
            'control_type': 'Group',
            'caption': 'Preferences',
            'source_table': 'UserPersonalization',
            'show_caption': True,
            'editable': True,
            'visible': True,
            'tab_index': 0,
        },
    )
    prefs_ctrl.tab_index = 0
    prefs_ctrl.save(update_fields=['tab_index'])

    PageControl.objects.filter(page=card, control_type='Group').exclude(
        name='UserSettingsPreferences',
    ).delete()
    PageControlField.objects.filter(page=card).delete()

    _seed_fields(prefs_ctrl, card, [
        dict(name='user__username', caption='User Name', field_type='Code',
             visible=True, editable=False, primary_key=False, tab_index=0),
        dict(name='user_id', caption='User ID', field_type='Code',
             visible=True, editable=False, primary_key=False, tab_index=1),
        dict(name='role', caption='Role Centre', field_type='Code',
             visible=True, editable=True, primary_key=False, tab_index=2,
             has_table_relation=True, related_table='ApplicationProfile', related_field='code',
             related_display_field='description'),
        dict(name='language', caption='Language', field_type='Enum',
             visible=True, editable=True, primary_key=False, tab_index=3,
             enum_values='en,sw,fr,lg'),
        dict(name='time_zone', caption='Time zone', field_type='Text',
             visible=True, editable=True, primary_key=False, tab_index=4),
        dict(name='teaching_tips', caption='Teaching tips', field_type='Boolean',
             visible=True, editable=True, primary_key=False, tab_index=5),
    ])

    list_page, _ = Page.objects.update_or_create(
        name='UserSettingsList',
        defaults={
            'caption': 'User settings',
            'source_table': 'UserPersonalization',
            'page_type': 'List',
            'editable': False,
            'insert_allowed': False,
            'delete_allowed': False,
            'modify_allowed': False,
            'card_page': card,
        },
    )
    list_page.card_page = card
    list_page.save(update_fields=['card_page'])

    list_ctrl, _ = PageControl.objects.get_or_create(
        page=list_page,
        name='UserSettingsListControl',
        defaults={
            'control_type': 'Repeater',
            'caption': 'User settings',
            'source_table': 'UserPersonalization',
            'show_caption': False,
            'editable': False,
            'visible': True,
        },
    )

    PageControlField.objects.filter(page=list_page, page_control=list_ctrl).delete()
    _seed_fields(list_ctrl, list_page, [
        dict(
            name='user__username', caption='User Name', field_type='Code',
            visible=True, editable=False, primary_key=True, tab_index=0, freeze_column=True,
        ),
        dict(
            name='user_id', caption='User ID', field_type='Code',
            visible=True, editable=False, primary_key=False, tab_index=1,
        ),
        dict(
            name='role', caption='Role Centre', field_type='Code',
            visible=True, editable=False, primary_key=False, tab_index=2,
            has_table_relation=True, related_table='ApplicationProfile', related_field='code',
            related_display_field='description',
        ),
        dict(
            name='language', caption='Language', field_type='Enum',
            visible=True, editable=False, primary_key=False, tab_index=3,
            enum_values='en,sw,fr,lg',
        ),
        dict(
            name='time_zone', caption='Time zone', field_type='Text',
            visible=True, editable=False, primary_key=False, tab_index=4,
        ),
        dict(
            name='teaching_tips', caption='Teaching tips', field_type='Boolean',
            visible=True, editable=False, primary_key=False, tab_index=5,
        ),
    ])
    _ensure_table_relation(
        'UserPersonalization',
        'role',
        'ApplicationProfile',
        related_field='code',
        display_field='description',
    )
    return card, list_page


def _create_ledger_list_page(
    *,
    name: str,
    caption: str,
    source_table: str,
    context_filter_field: str,
    fields: list[dict],
) -> Page:
    ledger_page, _ = Page.objects.update_or_create(
        name=name,
        defaults={
            'caption': caption,
            'source_table': source_table,
            'page_type': 'List',
            'editable': False,
            'insert_allowed': False,
            'delete_allowed': False,
            'modify_allowed': False,
            'context_filter_field': context_filter_field,
            'context_key_field': 'no',
        },
    )

    control, _ = PageControl.objects.get_or_create(
        page=ledger_page,
        name=f'{name}Control',
        defaults={
            'control_type': 'Repeater',
            'caption': caption,
            'source_table': source_table,
            'show_caption': True,
            'editable': False,
            'visible': True,
        },
    )

    _seed_fields(control, ledger_page, fields)

    return ledger_page


def _create_applied_ledger_list_page(
    *,
    name: str,
    caption: str,
    source_table: str,
    fields: list[dict],
) -> Page:
    """Read-only list of ledger entries related via application (BC Applied Entries)."""
    ledger_page, _ = Page.objects.update_or_create(
        name=name,
        defaults={
            'caption': caption,
            'source_table': source_table,
            'page_type': 'List',
            'editable': False,
            'insert_allowed': False,
            'delete_allowed': False,
            'modify_allowed': False,
            'context_filter_field': '',
            'context_key_field': 'no',
        },
    )
    ledger_page.context_filter_field = ''
    ledger_page.save(update_fields=['context_filter_field'])

    control, _ = PageControl.objects.get_or_create(
        page=ledger_page,
        name=f'{name}Control',
        defaults={
            'control_type': 'Repeater',
            'caption': caption,
            'source_table': source_table,
            'show_caption': True,
            'editable': False,
            'visible': True,
        },
    )

    _seed_fields(control, ledger_page, fields)

    return ledger_page


def _seed_ledger_entry_ribbon_actions(
    ledger_page: Page,
    *,
    party: str,
    applied_list_name: str,
    detailed_list_name: str,
) -> None:
    """
    BC Vendor/Customer Ledger Entries promoted actions (Process / Entry / Report).

    Entry group mirrors page 29 Category_Category5: Applied Entries + Detailed Ledger Entries.
    """
    if party == 'vendor':
        detail_param = 'vendor_ledger_entry_id'
    else:
        detail_param = 'customer_ledger_entry_id'

    specs = (
        {
            'name': 'OpenAppliedEntries',
            'caption': 'Applied Entries',
            'action_relative_url': (
                f'{applied_list_name}?applied_to_entry_id={{id}}'
                '&filterLabel=Applied%20entries&ctxLabel={{document_no}}'
            ),
            'ribbon_tab': 'Entry',
            'image_url': 'CheckCircle2',
            'tooltip': 'View the ledger entries that have been applied to this record.',
        },
        {
            'name': 'OpenDetailedLedgerEntries',
            'caption': 'Detailed Ledger Entries',
            'action_relative_url': (
                f'{detailed_list_name}?{detail_param}={{id}}'
                '&filterLabel=Detailed%20ledger%20entries&ctxLabel={{document_no}}'
            ),
            'ribbon_tab': 'Entry',
            'image_url': 'Eye',
            'tooltip': (
                'View detailed ledger entries related to this ledger entry '
                '(BC Detailed Vendor Ledg. Entries).'
            ),
        },
    )
    for spec in specs:
        PageAction.objects.update_or_create(
            page=ledger_page,
            name=spec['name'],
            defaults={
                'caption': spec['caption'],
                'action_type': 'Ribbon',
                'requires_confirmation': False,
                'confirmation_message': '',
                'tooltip': spec['tooltip'],
                'action_relative_url': spec['action_relative_url'],
                'visible': True,
                'ribbon_tab': spec['ribbon_tab'],
                'image_url': spec['image_url'],
            },
        )


def _ensure_field(
    control: PageControl,
    page: Page,
    field_spec: dict,
    drill_down_page: Page,
):
    obj, created = PageControlField.objects.get_or_create(
        page_control=control,
        name=field_spec['name'],
        defaults={
            'page': page,
            'field_id': field_spec.get('tab_index', 0),
            'caption': field_spec['caption'],
            'field_type': field_spec['field_type'],
            'visible': field_spec.get('visible', True),
            'editable': field_spec.get('editable', False),
            'primary_key': field_spec.get('primary_key', False),
            'required': field_spec.get('required', False),
            'tab_index': field_spec.get('tab_index', 0),
        },
    )
    obj.visible = field_spec.get('visible', True)
    obj.editable = field_spec.get('editable', False)
    obj.caption = field_spec['caption']
    obj.field_type = field_spec['field_type']
    if created:
        obj.tab_index = field_spec.get('tab_index', 0)
        obj.field_id = obj.tab_index
    obj.has_drill_down_page = True
    obj.drill_down_page = drill_down_page
    if obj.field_id != obj.tab_index:
        obj.field_id = obj.tab_index
    obj.save()


def _link_drill_down(*, page_names: tuple[str, ...], field_name: str, drill_down_page: Page):
    PageControlField.objects.filter(
        page__name__in=page_names,
        name=field_name,
    ).update(
        has_drill_down_page=True,
        drill_down_page=drill_down_page,
        editable=False,
    )


def _link_table_relation(
    *,
    page_names: tuple[str, ...],
    field_name: str,
    related_table: str,
    related_field: str,
    related_display_field: str,
):
    PageControlField.objects.filter(
        page__name__in=page_names,
        name=field_name,
    ).update(
        has_table_relation=True,
        related_table=related_table,
        related_field=related_field,
        related_display_field=related_display_field,
    )


def _seed_expense_pages() -> tuple[Page, Page]:
    """Expense Card and List pages."""
    expense_card, _ = Page.objects.update_or_create(
        name='ExpenseCard',
        defaults={
            'caption': 'Expense',
            'source_table': 'Expense',
            'page_type': 'Card',
            'editable': True,
            'insert_allowed': True,
            'delete_allowed': True,
            'modify_allowed': True,
            'title_field': 'document_no',
        },
    )

    card_ctrl, _ = PageControl.objects.get_or_create(
        page=expense_card,
        name='ExpenseCardGroup',
        defaults={
            'control_type': 'Group',
            'caption': 'General',
            'source_table': 'Expense',
            'show_caption': False,
            'editable': True,
            'visible': True,
        },
    )

    PageControlField.objects.filter(page=expense_card, page_control=card_ctrl).delete()
    _seed_fields(card_ctrl, expense_card, [
        dict(name='document_no',       caption='Document No.',    field_type='Code',    visible=True,  editable=False, primary_key=True,  tab_index=0),
        dict(name='posting_date',      caption='Posting Date',    field_type='Date',    visible=True,  editable=True,  primary_key=False, tab_index=1),
        dict(name='document_type',     caption='Document Type',   field_type='Enum',    visible=True,  editable=True,  primary_key=False, tab_index=2,
             enum_values='Expense,Refund,Adjustment'),
        dict(name='expense_type',      caption='Expense Type',    field_type='Code',    visible=True,  editable=True,  primary_key=False, tab_index=3,
             has_table_relation=True, related_table='ExpenseType', related_field='code', related_display_field='name'),
        dict(name='description',       caption='Description',     field_type='Text',    visible=True,  editable=True,  primary_key=False, tab_index=4),
        dict(name='amount',            caption='Amount',          field_type='Integer', visible=True,  editable=True,  primary_key=False, tab_index=5),
        dict(name='payment_method',    caption='Payment Method',  field_type='Code',    visible=True,  editable=True,  primary_key=False, tab_index=6,
             has_table_relation=True, related_table='PaymentMethod', related_field='code', related_display_field='description'),
        dict(name='status',            caption='Status',          field_type='Enum',    visible=True,  editable=False, primary_key=False, tab_index=7,
             enum_values='Open,Posted,Reversed'),
        dict(name='external_document_no', caption='Ext. Document No.', field_type='Code', visible=True, editable=True, primary_key=False, tab_index=8),
    ])

    expense_list, _ = Page.objects.update_or_create(
        name='ExpenseList',
        defaults={
            'caption': 'Expenses',
            'source_table': 'Expense',
            'page_type': 'List',
            'editable': False,
            'insert_allowed': True,
            'delete_allowed': True,
            'modify_allowed': True,
            'card_page': expense_card,
            'title_field': 'document_no',
        },
    )
    expense_list.card_page = expense_card
    expense_list.save(update_fields=['card_page'])

    list_ctrl, _ = PageControl.objects.get_or_create(
        page=expense_list,
        name='ExpenseListControl',
        defaults={
            'control_type': 'Repeater',
            'caption': 'Expenses',
            'source_table': 'Expense',
            'show_caption': True,
            'editable': False,
            'visible': True,
        },
    )

    PageControlField.objects.filter(page=expense_list, page_control=list_ctrl).delete()
    _seed_fields(list_ctrl, expense_list, [
        dict(name='document_no',       caption='Document No.',    field_type='Code',    visible=True, editable=False, primary_key=True,  tab_index=0, freeze_column=True),
        dict(name='posting_date',      caption='Posting Date',    field_type='Date',    visible=True, editable=False, primary_key=False, tab_index=1),
        dict(name='expense_type__name', caption='Expense Type',   field_type='Text',    visible=True, editable=False, primary_key=False, tab_index=2),
        dict(name='description',       caption='Description',     field_type='Text',    visible=True, editable=False, primary_key=False, tab_index=3),
        dict(name='amount',            caption='Amount',          field_type='Integer', visible=True, editable=False, primary_key=False, tab_index=4),
        dict(name='status',            caption='Status',          field_type='Enum',    visible=True, editable=False, primary_key=False, tab_index=5,
             enum_values='Open,Posted,Reversed'),
    ])

    PageAction.objects.update_or_create(
        page=expense_card,
        name='post_expense',
        defaults={
            'caption': 'Post Expense',
            'requires_confirmation': True,
            'confirmation_message': 'Post this expense to the general ledger?',
            'tooltip': 'Post expense to G/L accounts',
            'visible': True,
            'ribbon_tab': 'Home',
            'image_url': 'CircleCheck',
            'visible_when_field': 'status',
            'visible_when_values': 'Open',
        },
    )

    return expense_card, expense_list


def _seed_item_journal_pages() -> tuple[Page, Page, Page, Page]:
    """Inventory Adjustment + Opening Balance journals (ItemJournal, filtered by adjustment_type)."""
    card, _ = Page.objects.update_or_create(
        name='ItemJournalCard',
        defaults={
            'caption': 'Item Journal',
            'source_table': 'ItemJournal',
            'page_type': 'Card',
            'editable': True,
            'insert_allowed': True,
            'delete_allowed': True,
            'modify_allowed': True,
            'title_field': 'document_no',
        },
    )

    card_ctrl, _ = PageControl.objects.update_or_create(
        page=card,
        name='ItemJournalCardGroup',
        defaults={
            'control_type': 'Group',
            'caption': 'General',
            'source_table': 'ItemJournal',
            'show_caption': False,
            'editable': True,
            'visible': True,
        },
    )

    PageControlField.objects.filter(page=card, page_control=card_ctrl).delete()
    _seed_fields(card_ctrl, card, [
        dict(name='document_no', caption='Document No.', field_type='Code', visible=True,
             editable=False, primary_key=True, tab_index=0),
        dict(name='item', caption='Item No.', field_type='Code', visible=True, editable=True,
             primary_key=False, tab_index=1,
             has_table_relation=True, related_table='Item', related_field='no',
             related_display_field='item_name'),
        dict(name='item_unit_of_measure', caption='Item Unit of Measure', field_type='Code',
             visible=True, editable=True, primary_key=False, tab_index=2,
             has_table_relation=True, related_table='ItemUnitOfMeasure', related_field='id',
             related_display_field='unit_of_measure__code', relation_context_field='item',
             relation_lookup_footer=True),
        dict(name='description', caption='Item Name', field_type='Text', visible=True, editable=True,
             primary_key=False, tab_index=3),
        dict(name='entry_type', caption='Entry Type', field_type='Enum', visible=True, editable=True,
             primary_key=False, tab_index=4,
             enum_values='PositiveAdjustment,NegativeAdjustment'),
        dict(name='quantity', caption='Quantity', field_type='Integer', visible=True, editable=True,
             primary_key=False, tab_index=5),
        dict(name='unit_amount', caption='Unit Amount', field_type='Decimal', visible=True, editable=True,
             primary_key=False, tab_index=6),
        dict(name='amount', caption='Amount', field_type='Decimal', visible=True, editable=False,
             primary_key=False, tab_index=7),
        dict(name='location_code', caption='Location', field_type='Code', visible=True, editable=True,
             primary_key=False, tab_index=8,
             has_table_relation=True, related_table='Location', related_field='code',
             related_display_field='description'),
        dict(name='date', caption='Date', field_type='Date', visible=True, editable=True,
             primary_key=False, tab_index=9),
        dict(name='adjustment_type', caption='Adjustment Type', field_type='Enum', visible=True,
             editable=False, primary_key=False, tab_index=10,
             enum_values='operational,opening_balance'),
        dict(name='status', caption='Status', field_type='Enum', visible=True, editable=False,
             primary_key=False, tab_index=11, enum_values='Open,Posted'),
    ])
    _ensure_table_relation(
        'ItemJournal', 'item_unit_of_measure', 'ItemUnitOfMeasure', 'id', 'unit_of_measure__code',
    )

    PageAction.objects.update_or_create(
        page=card,
        name='preview_item_journal',
        defaults={
            'caption': 'Preview Posting',
            'requires_confirmation': False,
            'confirmation_message': '',
            'tooltip': 'Preview ledger entries before posting',
            'visible': True,
            'ribbon_tab': 'Home',
            'image_url': 'Eye',
            'visible_when_field': 'status',
            'visible_when_values': 'Open',
        },
    )
    PageAction.objects.update_or_create(
        page=card,
        name='post_item_journal',
        defaults={
            'caption': 'Post',
            'requires_confirmation': True,
            'confirmation_message': 'Post this inventory adjustment to the ledger?',
            'tooltip': 'Post journal to item ledger',
            'visible': True,
            'ribbon_tab': 'Home',
            'image_url': 'CircleCheck',
            'visible_when_field': 'status',
            'visible_when_values': 'Open',
        },
    )

    list_fields = [
        dict(name='document_no', caption='Document No.', field_type='Code', visible=True,
             editable=False, primary_key=True, tab_index=0, freeze_column=True),
        dict(name='item__item_name', caption='Item Name', field_type='Text', visible=True,
             editable=False, primary_key=False, tab_index=1),
        dict(
            name='item_unit_of_measure__unit_of_measure__code',
            caption='Unit of Measure',
            field_type='Code',
            visible=True,
            editable=False,
            primary_key=False,
            tab_index=2,
        ),
        dict(name='entry_type', caption='Entry Type', field_type='Enum', visible=True,
             editable=False, primary_key=False, tab_index=3,
             enum_values='PositiveAdjustment,NegativeAdjustment'),
        dict(name='quantity', caption='Quantity', field_type='Integer', visible=True,
             editable=False, primary_key=False, tab_index=4),
        dict(name='unit_amount', caption='Unit Amount', field_type='Decimal', visible=True,
             editable=False, primary_key=False, tab_index=5),
        dict(name='amount', caption='Amount', field_type='Decimal', visible=True,
             editable=False, primary_key=False, tab_index=6),
        dict(name='date', caption='Date', field_type='Date', visible=True, editable=False,
             primary_key=False, tab_index=7),
        dict(name='user__full_name', caption='Adjusted By', field_type='Text', visible=True,
             editable=False, primary_key=False, tab_index=8),
        dict(name='status', caption='Status', field_type='Enum', visible=True, editable=False,
             primary_key=False, tab_index=9, enum_values='Open,Posted'),
    ]

    posted_list_fields = [
        dict(name='document_no', caption='Document No.', field_type='Code', visible=True,
             editable=False, primary_key=True, tab_index=0, freeze_column=True),
        dict(name='item__item_name', caption='Item Name', field_type='Text', visible=True,
             editable=False, primary_key=False, tab_index=1),
        dict(
            name='item_unit_of_measure__unit_of_measure__code',
            caption='Unit of Measure',
            field_type='Code',
            visible=True,
            editable=False,
            primary_key=False,
            tab_index=2,
        ),
        dict(name='entry_type', caption='Entry Type', field_type='Enum', visible=True,
             editable=False, primary_key=False, tab_index=3,
             enum_values='PositiveAdjustment,NegativeAdjustment'),
        dict(name='adjustment_type', caption='Adjustment Type', field_type='Enum', visible=True,
             editable=False, primary_key=False, tab_index=4,
             enum_values='operational,opening_balance'),
        dict(name='quantity', caption='Quantity', field_type='Integer', visible=True,
             editable=False, primary_key=False, tab_index=5),
        dict(name='unit_amount', caption='Unit Amount', field_type='Decimal', visible=True,
             editable=False, primary_key=False, tab_index=6),
        dict(name='amount', caption='Amount', field_type='Decimal', visible=True,
             editable=False, primary_key=False, tab_index=7),
        dict(name='date', caption='Date', field_type='Date', visible=True, editable=False,
             primary_key=False, tab_index=8),
        dict(name='user__full_name', caption='Adjusted By', field_type='Text', visible=True,
             editable=False, primary_key=False, tab_index=9),
        dict(name='status', caption='Status', field_type='Enum', visible=True, editable=False,
             primary_key=False, tab_index=10, enum_values='Open,Posted'),
    ]

    operational_list = _seed_status_filtered_list_page(
        name='InventoryAdjustmentJournalList',
        caption='Inventory Adjustment',
        source_table='ItemJournal',
        card_page=card,
        title_field='document_no',
        control_name='InventoryAdjustmentJournalListControl',
        filter_field='adjustment_type',
        filter_value='operational',
        exclude_field='status',
        exclude_values='Posted',
        list_fields=list_fields,
    )
    operational_list.insert_allowed = True
    operational_list.delete_allowed = True
    operational_list.modify_allowed = True
    operational_list.save(update_fields=['insert_allowed', 'delete_allowed', 'modify_allowed'])
    _seed_item_journal_list_actions(operational_list)

    opening_list = _seed_status_filtered_list_page(
        name='OpeningBalanceJournalList',
        caption='Opening Balance',
        source_table='ItemJournal',
        card_page=card,
        title_field='document_no',
        control_name='OpeningBalanceJournalListControl',
        filter_field='adjustment_type',
        filter_value='opening_balance',
        exclude_field='status',
        exclude_values='Posted',
        list_fields=list_fields,
    )
    opening_list.insert_allowed = True
    opening_list.delete_allowed = True
    opening_list.modify_allowed = True
    opening_list.save(update_fields=['insert_allowed', 'delete_allowed', 'modify_allowed'])
    _seed_item_journal_list_actions(opening_list)

    posted_list = _seed_status_filtered_list_page(
        name='PostedInventoryAdjustmentList',
        caption='Posted Inventory Adjustments',
        source_table='ItemJournal',
        card_page=card,
        title_field='document_no',
        control_name='PostedInventoryAdjustmentListControl',
        filter_field='status',
        filter_value='Posted',
        list_fields=posted_list_fields,
    )
    posted_list.insert_allowed = False
    posted_list.delete_allowed = False
    posted_list.modify_allowed = False
    posted_list.save(update_fields=['insert_allowed', 'delete_allowed', 'modify_allowed'])
    # Posted list is view-only — remove any open-journal ribbon actions if re-seeded.
    PageAction.objects.filter(
        page=posted_list,
        name__in=(
            'ItemJournalListNew',
            'ItemJournalListDelete',
            'ItemJournalListSelectMore',
            'preview_item_journal',
            'post_item_journal',
        ),
    ).delete()

    return card, operational_list, opening_list, posted_list


def _seed_item_journal_list_actions(list_page: Page) -> None:
    """Select More + Preview Posting + Post on inventory/opening-balance journal lists."""
    _seed_ribbon_actions(list_page, (
        ('ItemJournalListNew', 'New', '#new', 'Home', 'Plus'),
        ('ItemJournalListDelete', 'Delete', '#delete', 'Home', 'Trash2'),
        ('ItemJournalListSelectMore', 'Select More', '#select-more', 'Home', 'ListChecks'),
    ))
    PageAction.objects.update_or_create(
        page=list_page,
        name='preview_item_journal',
        defaults={
            'caption': 'Preview Posting',
            'requires_confirmation': False,
            'confirmation_message': '',
            'tooltip': 'Preview ledger entries before posting',
            'visible': True,
            'ribbon_tab': 'Home',
            'image_url': 'Eye',
            'visible_when_field': 'status',
            'visible_when_values': 'Open',
        },
    )
    PageAction.objects.update_or_create(
        page=list_page,
        name='post_item_journal',
        defaults={
            'caption': 'Post',
            'requires_confirmation': True,
            'confirmation_message': 'Post the selected journal(s) to the ledger?',
            'tooltip': 'Post journal to item ledger',
            'visible': True,
            'ribbon_tab': 'Home',
            'image_url': 'CircleCheck',
            'visible_when_field': 'status',
            'visible_when_values': 'Open',
        },
    )


def _seed_payment_journal_pages() -> tuple[Page, Page]:
    """Payment Journal as a Document (header + lines subform) + List page."""

    # ── Lines subform ──────────────────────────────────────────────────────────
    lines_sub, _ = Page.objects.update_or_create(
        name='PaymentLinesSubform',
        defaults={
            'caption': 'Payment Lines',
            'source_table': 'PaymentLine',
            'page_type': 'ListPart',
            'editable': True,
            'insert_allowed': True,
            'delete_allowed': True,
            'modify_allowed': True,
        },
    )
    lines_sub_ctrl, _ = PageControl.objects.update_or_create(
        page=lines_sub,
        name='PaymentLinesRepeater',
        defaults={
            'control_type': 'Repeater',
            'caption': 'Lines',
            'source_table': 'PaymentLine',
            'show_caption': False,
            'editable': True,
            'visible': True,
        },
    )
    PageControlField.objects.filter(page=lines_sub, page_control=lines_sub_ctrl).delete()
    _seed_fields(lines_sub_ctrl, lines_sub, [
        dict(name='account_type',  caption='Account Type', field_type='Enum',    visible=True,  editable=True,  primary_key=False, tab_index=1,
             enum_values='Customer,Vendor,G/L Account'),
        dict(name='account_no',    caption='Account No.',  field_type='Code',    visible=True,  editable=True,  primary_key=False, tab_index=2,
             has_table_relation=True, related_table='G_LAccount', related_field='no', related_display_field='name',
             relation_context_field='account_type', relation_context_default='Customer'),
        dict(name='description',   caption='Description',  field_type='Text',    visible=True,  editable=True,  primary_key=False, tab_index=3),
        dict(name='amount',        caption='Amount',       field_type='Integer', visible=True,  editable=True,  primary_key=False, tab_index=4),
    ])
    _wire_context_account_relations('PaymentLine', 'account_no', 'account_type', 'Customer')

    PageAction.objects.update_or_create(
        page=lines_sub,
        name='ApplyVendorEntries',
        defaults={
            'caption': 'Apply Entries',
            'action_relative_url': '#apply-entries',
            'ribbon_tab': 'Line',
            'visible_when_field': 'account_type',
            'visible_when_values': 'Vendor',
            'tooltip': 'Apply payment to open vendor ledger entries',
            'visible': True,
            'image_url': 'Link2',
        },
    )
    PageAction.objects.update_or_create(
        page=lines_sub,
        name='ApplyCustomerEntries',
        defaults={
            'caption': 'Apply Entries',
            'action_relative_url': '#apply-customer-entries',
            'ribbon_tab': 'Line',
            'visible_when_field': 'account_type',
            'visible_when_values': 'Customer',
            'tooltip': 'Apply payment to open customer ledger entries',
            'visible': True,
            'image_url': 'Link2',
        },
    )

    # ── Document page (header + Part) ─────────────────────────────────────────
    payment_doc, _ = Page.objects.update_or_create(
        name='PaymentJournalCard',
        defaults={
            'caption': 'Payment',
            'source_table': 'PaymentJournal',
            'page_type': 'Document',
            'editable': True,
            'insert_allowed': True,
            'delete_allowed': True,
            'modify_allowed': True,
            'title_field': 'document_no',
        },
    )

    header_ctrl, _ = PageControl.objects.update_or_create(
        page=payment_doc,
        name='PaymentJournalGeneral',
        defaults={
            'control_type': 'Group',
            'caption': 'General',
            'source_table': 'PaymentJournal',
            'show_caption': True,
            'editable': True,
            'visible': True,
        },
    )
    PageControlField.objects.filter(page=payment_doc, page_control=header_ctrl).delete()
    _seed_fields(header_ctrl, payment_doc, [
        dict(name='document_no',          caption='Document No.',      field_type='Code',    visible=True,  editable=False, primary_key=True,  tab_index=0),
        dict(name='posting_date',         caption='Posting Date',      field_type='Date',    visible=True,  editable=True,  primary_key=False, tab_index=1),
        dict(name='document_type',        caption='Document Type',     field_type='Enum',    visible=True,  editable=True,  primary_key=False, tab_index=2,
             enum_values='Payment,Invoice,Credit Memo,Finance Charge Memo,Reminder,Refund'),
        dict(name='account_type',         caption='Account Type',      field_type='Enum',    visible=True,  editable=True,  primary_key=False, tab_index=3,
             enum_values='Customer,Vendor,G/L Account'),
        dict(name='description',          caption='Description',       field_type='Text',    visible=True,  editable=True,  primary_key=False, tab_index=4),
        dict(name='amount',               caption='Total Amount',      field_type='Integer', visible=True,  editable=False, primary_key=False, tab_index=5),
        dict(name='payment_method',       caption='Payment Method',    field_type='Code',    visible=True,  editable=True,  primary_key=False, tab_index=6,
             has_table_relation=True, related_table='PaymentMethod', related_field='code', related_display_field='description'),
        dict(name='status',               caption='Status',            field_type='Enum',    visible=True,  editable=False, primary_key=False, tab_index=7,
             enum_values='Open,Posted,Void,Cancelled'),
        dict(name='applies_to_object_id',  caption='Applies-to Entry',    field_type='Integer', visible=False, editable=False, primary_key=False, tab_index=8),
    ])

    lines_part, _ = PageControl.objects.update_or_create(
        page=payment_doc,
        name='PaymentLines',
        defaults={
            'control_type': 'Part',
            'caption': 'Lines',
            'source_table': 'PaymentLine',
            'show_caption': True,
            'editable': True,
            'visible': True,
            'part_page': lines_sub,
            'link_field': 'payment__system_id',
        },
    )
    lines_part.part_page = lines_sub
    lines_part.link_field = 'payment__system_id'
    lines_part.save(update_fields=['part_page', 'link_field'])

    # ── List page ─────────────────────────────────────────────────────────────
    payment_list, _ = Page.objects.update_or_create(
        name='PaymentJournalList',
        defaults={
            'caption': 'Payment Journal',
            'source_table': 'PaymentJournal',
            'page_type': 'List',
            'editable': False,
            'insert_allowed': True,
            'delete_allowed': True,
            'modify_allowed': True,
            'card_page': payment_doc,
            'title_field': 'document_no',
        },
    )
    payment_list.card_page = payment_doc
    payment_list.save(update_fields=['card_page'])

    list_ctrl, _ = PageControl.objects.update_or_create(
        page=payment_list,
        name='PaymentJournalListControl',
        defaults={
            'control_type': 'Repeater',
            'caption': 'Payments',
            'source_table': 'PaymentJournal',
            'show_caption': True,
            'editable': False,
            'visible': True,
        },
    )
    PageControlField.objects.filter(page=payment_list, page_control=list_ctrl).delete()
    _seed_fields(list_ctrl, payment_list, [
        dict(name='document_no',   caption='Document No.',  field_type='Code',    visible=True, editable=False, primary_key=True,  tab_index=0, freeze_column=True),
        dict(name='posting_date',  caption='Posting Date',  field_type='Date',    visible=True, editable=False, primary_key=False, tab_index=1),
        dict(name='document_type', caption='Document Type', field_type='Enum',    visible=True, editable=False, primary_key=False, tab_index=2,
             enum_values='Payment,Invoice,Credit Memo,Finance Charge Memo,Reminder,Refund'),
        dict(name='account_type',  caption='Account Type',  field_type='Enum',    visible=True, editable=False, primary_key=False, tab_index=3,
             enum_values='Customer,Vendor,G/L Account'),
        dict(name='description',   caption='Description',   field_type='Text',    visible=True, editable=False, primary_key=False, tab_index=4),
        dict(name='amount',        caption='Amount',        field_type='Integer', visible=True, editable=False, primary_key=False, tab_index=5),
        dict(name='status',        caption='Status',        field_type='Enum',    visible=True, editable=False, primary_key=False, tab_index=6,
             enum_values='Open,Posted,Void,Cancelled'),
    ])

    PageAction.objects.update_or_create(
        page=payment_doc,
        name='preview_payment_journal',
        defaults={
            'caption': 'Preview Posting',
            'requires_confirmation': False,
            'confirmation_message': '',
            'tooltip': 'Preview ledger entries before posting',
            'visible': True,
            'ribbon_tab': 'Home',
            'image_url': 'Eye',
            'visible_when_field': 'status',
            'visible_when_values': 'Open',
        },
    )
    PageAction.objects.update_or_create(
        page=payment_doc,
        name='post_payment_journal',
        defaults={
            'caption': 'Post',
            'requires_confirmation': True,
            'confirmation_message': 'Are you sure you want to post this payment? Ledger entries will be created.',
            'tooltip': 'Post payment journal',
            'visible': True,
            'ribbon_tab': 'Home',
            'image_url': 'CircleCheck',
            'visible_when_field': 'status',
            'visible_when_values': 'Open',
        },
    )
    PageAction.objects.update_or_create(
        page=payment_doc,
        name='print_payment_journal',
        defaults={
            'caption': 'Print Receipt',
            'action_relative_url': '#print-receipt',
            'requires_confirmation': False,
            'confirmation_message': '',
            'tooltip': 'Print payment receipt',
            'visible': True,
            'ribbon_tab': 'Home',
            'image_url': 'Printer',
            'visible_when_field': 'status',
            'visible_when_values': 'Posted',
        },
    )

    return payment_doc, payment_list


def _seed_apply_vendor_entries_page() -> Page:
    """BC Page 233 — Apply Vendor Entries worksheet on Vendor Ledger Entry."""

    header_card, _ = Page.objects.update_or_create(
        name='ApplyVendorEntriesHeader',
        defaults={
            'caption': 'General',
            'source_table': 'PaymentJournal',
            'page_type': 'Card',
            'editable': False,
            'insert_allowed': False,
            'delete_allowed': False,
            'modify_allowed': False,
        },
    )
    header_ctrl, _ = PageControl.objects.get_or_create(
        page=header_card,
        name='ApplyVendorEntriesGeneral',
        defaults={
            'control_type': 'Group',
            'caption': 'General',
            'source_table': 'PaymentJournal',
            'show_caption': True,
            'editable': False,
            'visible': True,
        },
    )
    PageControlField.objects.filter(page=header_card, page_control=header_ctrl).delete()
    _seed_fields(header_ctrl, header_card, [
        dict(name='posting_date', caption='Posting Date', field_type='Date', visible=True, editable=False, tab_index=0),
        dict(name='document_type', caption='Document Type', field_type='Enum', visible=True, editable=False, tab_index=1,
             enum_values='Payment,Invoice,Credit Memo,Finance Charge Memo,Reminder,Refund'),
        dict(name='document_no', caption='Document No.', field_type='Code', visible=True, editable=False, tab_index=2),
        dict(name='amount', caption='Amount', field_type='Integer', visible=True, editable=False, tab_index=3),
    ])

    worksheet, _ = Page.objects.update_or_create(
        name='ApplyVendorEntries',
        defaults={
            'caption': 'Apply Vendor Entries',
            'source_table': 'VendorLedger',
            'page_type': 'Worksheet',
            'editable': False,
            'insert_allowed': False,
            'delete_allowed': False,
            'modify_allowed': False,
            'context_filter_field': 'vendor__no',
            'context_key_field': 'no',
            'header_page': header_card,
            'list_filter_field': 'open',
            'list_filter_value': 'True',
        },
    )
    worksheet.header_page = header_card
    worksheet.context_filter_field = 'vendor__no'
    worksheet.context_key_field = 'no'
    worksheet.list_filter_field = 'open'
    worksheet.list_filter_value = 'True'
    worksheet.save(update_fields=[
        'header_page', 'context_filter_field', 'context_key_field',
        'list_filter_field', 'list_filter_value',
    ])

    lines_ctrl, _ = PageControl.objects.get_or_create(
        page=worksheet,
        name='ApplyVendorEntriesLines',
        defaults={
            'control_type': 'Repeater',
            'caption': 'Lines',
            'source_table': 'VendorLedger',
            'show_caption': False,
            'editable': False,
            'visible': True,
        },
    )
    PageControlField.objects.filter(page=worksheet, page_control=lines_ctrl).delete()
    _seed_fields(lines_ctrl, worksheet, [
        dict(name='applies_to_id', caption='Applies-to ID', field_type='Code', visible=True, editable=True, tab_index=0, freeze_column=True),
        dict(name='posting_date', caption='Posting Date', field_type='Date', visible=True, editable=False, tab_index=1, freeze_column=True),
        dict(name='document_type', caption='Document Type', field_type='Text', visible=True, editable=False, tab_index=2),
        dict(name='document_no', caption='Document No.', field_type='Code', visible=True, editable=False, tab_index=3),
        dict(name='external_document_no', caption='External Document No.', field_type='Code', visible=True, editable=False, tab_index=4),
        dict(name='vendor__no', caption='Vendor No.', field_type='Code', visible=True, editable=False, tab_index=5),
        dict(name='vendor__name', caption='Vendor Name', field_type='Text', visible=True, editable=False, tab_index=6),
        dict(name='description', caption='Description', field_type='Text', visible=True, editable=False, tab_index=7),
        dict(name='remaining_amount', caption='Remaining Amount', field_type='Decimal', visible=True, editable=False, tab_index=8),
        dict(name='appln_remaining_amount', caption='Appln. Remaining Amount', field_type='Decimal', visible=True, editable=False, tab_index=9),
        dict(name='amount_to_apply', caption='Amount to Apply', field_type='Decimal', visible=True, editable=True, tab_index=10),
        dict(name='appln_amount_to_apply', caption='Appln. Amount to Apply', field_type='Decimal', visible=True, editable=False, tab_index=11),
        dict(name='id', caption='Entry No.', field_type='Integer', visible=False, editable=False, tab_index=12, primary_key=True),
    ])

    footer_ctrl, _ = PageControl.objects.get_or_create(
        page=worksheet,
        name='ApplyVendorEntriesFooter',
        defaults={
            'control_type': 'Group',
            'caption': 'Summary',
            'source_table': '',
            'show_caption': False,
            'editable': False,
            'visible': True,
        },
    )
    PageControlField.objects.filter(page=worksheet, page_control=footer_ctrl).delete()
    _seed_fields(footer_ctrl, worksheet, [
        dict(name='amount_to_apply', caption='Amount to Apply', field_type='Decimal', visible=True, editable=False, tab_index=0),
        dict(name='applied_amount', caption='Applied Amount', field_type='Decimal', visible=True, editable=False, tab_index=1),
        dict(name='available_amount', caption='Available Amount', field_type='Decimal', visible=True, editable=False, tab_index=2),
        dict(name='balance', caption='Balance', field_type='Decimal', visible=True, editable=False, tab_index=3),
    ])

    PageAction.objects.update_or_create(
        page=worksheet,
        name='SetAppliesToId',
        defaults={
            'caption': 'Set Applies-to ID',
            'action_relative_url': '#set-applies-to-id',
            'ribbon_tab': 'Home',
            'tooltip': 'Set Applies-to ID on the selected entry to this payment document',
            'visible': True,
            'image_url': 'Link2',
        },
    )
    PageAction.objects.update_or_create(
        page=worksheet,
        name='ShowSelectedOnly',
        defaults={
            'caption': 'Show Only Selected Entries to Be Applied',
            'action_relative_url': '#show-selected-only',
            'ribbon_tab': 'Home',
            'tooltip': 'Filter the list to the selected entry marked for application',
            'visible': True,
            'image_url': 'Filter',
        },
    )

    return worksheet


def _seed_item_tracking_lines_worksheet_page() -> Page:
    """BC Page 6510 — Item Tracking Lines worksheet on Tracking Specification."""

    header_card, _ = Page.objects.update_or_create(
        name='ItemTrackingLinesHeader',
        defaults={
            'caption': 'General',
            'source_table': 'PurchaseInvoiceLine',
            'page_type': 'Card',
            'editable': False,
            'insert_allowed': False,
            'delete_allowed': False,
            'modify_allowed': False,
        },
    )
    header_ctrl, _ = PageControl.objects.get_or_create(
        page=header_card,
        name='ItemTrackingLinesGeneral',
        defaults={
            'control_type': 'Group',
            'caption': 'General',
            'source_table': 'PurchaseInvoiceLine',
            'show_caption': True,
            'editable': False,
            'visible': True,
        },
    )
    PageControlField.objects.filter(page=header_card, page_control=header_ctrl).delete()
    _seed_fields(header_ctrl, header_card, [
        dict(name='item', caption='Item No.', field_type='Code', visible=True, editable=False, tab_index=0,
             has_table_relation=True, related_table='Item', related_field='no',
             related_display_field='item_name'),
        dict(name='description', caption='Description', field_type='Text', visible=True, editable=False, tab_index=1),
        dict(name='quantity', caption='Quantity', field_type='Integer', visible=True, editable=False, tab_index=2),
    ])

    worksheet, _ = Page.objects.update_or_create(
        name='ItemTrackingLinesWorksheet',
        defaults={
            'caption': 'Item Tracking Lines',
            'source_table': 'TrackingSpecification',
            'page_type': 'Worksheet',
            'editable': True,
            'insert_allowed': True,
            'delete_allowed': True,
            'modify_allowed': True,
            'context_filter_field': 'purchase_invoice_line',
            'context_key_field': 'id',
            'header_page': header_card,
        },
    )
    worksheet.header_page = header_card
    worksheet.context_filter_field = 'purchase_invoice_line'
    worksheet.context_key_field = 'id'
    worksheet.save(update_fields=['header_page', 'context_filter_field', 'context_key_field'])

    lines_ctrl, _ = PageControl.objects.get_or_create(
        page=worksheet,
        name='ItemTrackingLinesRepeater',
        defaults={
            'control_type': 'Repeater',
            'caption': 'Lines',
            'source_table': 'TrackingSpecification',
            'show_caption': False,
            'editable': True,
            'visible': True,
        },
    )
    PageControlField.objects.filter(page=worksheet, page_control=lines_ctrl).delete()
    _seed_fields(lines_ctrl, worksheet, [
        dict(name='serial_no', caption='Serial No.', field_type='Code', visible=True, editable=True, tab_index=0),
        dict(name='lot_no', caption='Lot No.', field_type='Code', visible=True, editable=True, tab_index=1),
        dict(name='expiry_date', caption='Expiration Date', field_type='Date', visible=True, editable=True, tab_index=2),
        dict(name='quantity_base', caption='Quantity (Base)', field_type='Integer', visible=True, editable=True,
             required=True, tab_index=3),
        dict(name='description', caption='Description', field_type='Text', visible=True, editable=True, tab_index=4),
        dict(name='id', caption='Entry No.', field_type='Integer', visible=False, editable=False, tab_index=5,
             primary_key=True),
    ])

    footer_ctrl, _ = PageControl.objects.get_or_create(
        page=worksheet,
        name='ItemTrackingLinesFooter',
        defaults={
            'control_type': 'Group',
            'caption': 'Summary',
            'source_table': '',
            'show_caption': False,
            'editable': False,
            'visible': True,
        },
    )
    PageControlField.objects.filter(page=worksheet, page_control=footer_ctrl).delete()
    _seed_fields(footer_ctrl, worksheet, [
        dict(name='expected_quantity', caption='Quantity', field_type='Decimal', visible=True, editable=False, tab_index=0),
        dict(name='total_quantity', caption='Item Tracking', field_type='Decimal', visible=True, editable=False, tab_index=1),
        dict(name='remaining_quantity', caption='Undefined', field_type='Decimal', visible=True, editable=False, tab_index=2),
        dict(name='specifications_count', caption='Lines', field_type='Integer', visible=True, editable=False, tab_index=3),
    ])

    PageAction.objects.update_or_create(
        page=worksheet,
        name='DeleteLine',
        defaults={
            'caption': 'Delete',
            'action_relative_url': '#delete-line',
            'ribbon_tab': 'Manage',
            'tooltip': 'Delete the selected tracking line',
            'visible': True,
            'image_url': 'Trash2',
        },
    )

    return worksheet


def _seed_apply_customer_entries_page() -> Page:
    """BC Page 232 — Apply Customer Entries worksheet on Customer Ledger Entry."""

    header_card, _ = Page.objects.update_or_create(
        name='ApplyCustomerEntriesHeader',
        defaults={
            'caption': 'General',
            'source_table': 'PaymentJournal',
            'page_type': 'Card',
            'editable': False,
            'insert_allowed': False,
            'delete_allowed': False,
            'modify_allowed': False,
        },
    )
    header_ctrl, _ = PageControl.objects.get_or_create(
        page=header_card,
        name='ApplyCustomerEntriesGeneral',
        defaults={
            'control_type': 'Group',
            'caption': 'General',
            'source_table': 'PaymentJournal',
            'show_caption': True,
            'editable': False,
            'visible': True,
        },
    )
    PageControlField.objects.filter(page=header_card, page_control=header_ctrl).delete()
    _seed_fields(header_ctrl, header_card, [
        dict(name='posting_date', caption='Posting Date', field_type='Date', visible=True, editable=False, tab_index=0),
        dict(name='document_type', caption='Document Type', field_type='Enum', visible=True, editable=False, tab_index=1,
             enum_values='Payment,Invoice,Credit Memo,Finance Charge Memo,Reminder,Refund'),
        dict(name='document_no', caption='Document No.', field_type='Code', visible=True, editable=False, tab_index=2),
        dict(name='amount', caption='Amount', field_type='Integer', visible=True, editable=False, tab_index=3),
    ])

    worksheet, _ = Page.objects.update_or_create(
        name='ApplyCustomerEntries',
        defaults={
            'caption': 'Apply Customer Entries',
            'source_table': 'CustomerLedgerEntry',
            'page_type': 'Worksheet',
            'editable': False,
            'insert_allowed': False,
            'delete_allowed': False,
            'modify_allowed': False,
            'context_filter_field': 'customer__no',
            'context_key_field': 'no',
            'header_page': header_card,
            'list_filter_field': 'open',
            'list_filter_value': 'True',
        },
    )
    worksheet.header_page = header_card
    worksheet.context_filter_field = 'customer__no'
    worksheet.context_key_field = 'no'
    worksheet.list_filter_field = 'open'
    worksheet.list_filter_value = 'True'
    worksheet.save(update_fields=[
        'header_page', 'context_filter_field', 'context_key_field',
        'list_filter_field', 'list_filter_value',
    ])

    lines_ctrl, _ = PageControl.objects.get_or_create(
        page=worksheet,
        name='ApplyCustomerEntriesLines',
        defaults={
            'control_type': 'Repeater',
            'caption': 'Lines',
            'source_table': 'CustomerLedgerEntry',
            'show_caption': False,
            'editable': False,
            'visible': True,
        },
    )
    PageControlField.objects.filter(page=worksheet, page_control=lines_ctrl).delete()
    _seed_fields(lines_ctrl, worksheet, [
        dict(name='applies_to_id', caption='Applies-to ID', field_type='Code', visible=True, editable=True, tab_index=0, freeze_column=True),
        dict(name='posting_date', caption='Posting Date', field_type='Date', visible=True, editable=False, tab_index=1, freeze_column=True),
        dict(name='document_type', caption='Document Type', field_type='Text', visible=True, editable=False, tab_index=2),
        dict(name='document_no', caption='Document No.', field_type='Code', visible=True, editable=False, tab_index=3),
        dict(name='external_document_no', caption='External Document No.', field_type='Code', visible=True, editable=False, tab_index=4),
        dict(name='customer__no', caption='Customer No.', field_type='Code', visible=True, editable=False, tab_index=5),
        dict(name='customer__name', caption='Customer Name', field_type='Text', visible=True, editable=False, tab_index=6),
        dict(name='description', caption='Description', field_type='Text', visible=True, editable=False, tab_index=7),
        dict(name='remaining_amount', caption='Remaining Amount', field_type='Decimal', visible=True, editable=False, tab_index=8),
        dict(name='appln_remaining_amount', caption='Appln. Remaining Amount', field_type='Decimal', visible=True, editable=False, tab_index=9),
        dict(name='amount_to_apply', caption='Amount to Apply', field_type='Decimal', visible=True, editable=True, tab_index=10),
        dict(name='appln_amount_to_apply', caption='Appln. Amount to Apply', field_type='Decimal', visible=True, editable=False, tab_index=11),
        dict(name='id', caption='Entry No.', field_type='Integer', visible=False, editable=False, tab_index=12, primary_key=True),
    ])

    footer_ctrl, _ = PageControl.objects.get_or_create(
        page=worksheet,
        name='ApplyCustomerEntriesFooter',
        defaults={
            'control_type': 'Group',
            'caption': 'Summary',
            'source_table': '',
            'show_caption': False,
            'editable': False,
            'visible': True,
        },
    )
    PageControlField.objects.filter(page=worksheet, page_control=footer_ctrl).delete()
    _seed_fields(footer_ctrl, worksheet, [
        dict(name='amount_to_apply', caption='Amount to Apply', field_type='Decimal', visible=True, editable=False, tab_index=0),
        dict(name='applied_amount', caption='Applied Amount', field_type='Decimal', visible=True, editable=False, tab_index=1),
        dict(name='available_amount', caption='Available Amount', field_type='Decimal', visible=True, editable=False, tab_index=2),
        dict(name='balance', caption='Balance', field_type='Decimal', visible=True, editable=False, tab_index=3),
    ])

    PageAction.objects.update_or_create(
        page=worksheet,
        name='SetAppliesToId',
        defaults={
            'caption': 'Set Applies-to ID',
            'action_relative_url': '#set-applies-to-id',
            'ribbon_tab': 'Home',
            'tooltip': 'Set Applies-to ID on the selected entry to this payment document',
            'visible': True,
            'image_url': 'Link2',
        },
    )
    PageAction.objects.update_or_create(
        page=worksheet,
        name='ShowSelectedOnly',
        defaults={
            'caption': 'Show Only Selected Entries to Be Applied',
            'action_relative_url': '#show-selected-only',
            'ribbon_tab': 'Home',
            'tooltip': 'Filter the list to the selected entry marked for application',
            'visible': True,
            'image_url': 'Filter',
        },
    )

    return worksheet


def _wire_general_journal_account_relations(
    source_table: str,
    source_field: str,
    context_field: str,
    context_default: str = 'G/L Account',
):
    """Wire account fields including Bank Account for General Journal lines."""
    TableRelation.objects.filter(
        source_table=source_table,
        source_field=source_field,
    ).delete()
    for context_value, related_table in GENERAL_JOURNAL_ACCOUNT_TYPE_RELATIONS:
        TableRelation.objects.create(
            source_table=source_table,
            source_field=source_field,
            related_table=related_table,
            related_field='no',
            display_field='name',
            context_field=context_field,
            context_value=context_value,
        )
    PageControlField.objects.filter(
        page_control__source_table=source_table,
        name=source_field,
    ).update(
        relation_context_field=context_field,
        relation_context_default=context_default,
    )


def _seed_cash_receipt_journal_pages() -> tuple[Page, Page]:
    """Cash Receipt Journal Worksheet (page 255) + Batch List."""

    # ── Batch card (header used by WorksheetFastTab) ───────────────────────────
    batch_card, _ = Page.objects.update_or_create(
        name='CashReceiptJournalBatchCard',
        defaults={
            'caption': 'Cash Receipt Journal Batch',
            'source_table': 'CashReceiptJournalBatch',
            'page_type': 'Card',
            'editable': True,
            'insert_allowed': True,
            'delete_allowed': True,
            'modify_allowed': True,
            'title_field': 'name',
        },
    )
    batch_card_ctrl, _ = PageControl.objects.get_or_create(
        page=batch_card,
        name='CashReceiptBatchCardGroup',
        defaults={
            'control_type': 'Group',
            'caption': 'General',
            'source_table': 'CashReceiptJournalBatch',
            'show_caption': False,
            'editable': True,
            'visible': True,
        },
    )
    PageControlField.objects.filter(page=batch_card, page_control=batch_card_ctrl).delete()
    _seed_fields(batch_card_ctrl, batch_card, [
        dict(name='name',        caption='Batch Name',  field_type='Code', visible=True, editable=True, primary_key=True,  tab_index=0),
        dict(name='description', caption='Description', field_type='Text', visible=True, editable=True, primary_key=False, tab_index=1),
    ])

    # ── Batch list (navigated from Worksheet ribbon Manage tab) ───────────────
    batch_list, _ = Page.objects.update_or_create(
        name='CashReceiptJournalBatchList',
        defaults={
            'caption': 'Cash Receipt Journal Batches',
            'source_table': 'CashReceiptJournalBatch',
            'page_type': 'List',
            'editable': True,
            'insert_allowed': True,
            'delete_allowed': True,
            'modify_allowed': True,
            'card_page': batch_card,
        },
    )
    batch_list.card_page = batch_card
    batch_list.save(update_fields=['card_page'])

    batch_list_ctrl, _ = PageControl.objects.get_or_create(
        page=batch_list,
        name='CashReceiptBatchListControl',
        defaults={
            'control_type': 'Repeater',
            'caption': 'Batches',
            'source_table': 'CashReceiptJournalBatch',
            'show_caption': True,
            'editable': True,
            'visible': True,
        },
    )
    PageControlField.objects.filter(page=batch_list, page_control=batch_list_ctrl).delete()
    _seed_fields(batch_list_ctrl, batch_list, [
        dict(name='name',        caption='Batch Name',  field_type='Code', visible=True, editable=True, primary_key=True,  tab_index=0, freeze_column=True),
        dict(name='description', caption='Description', field_type='Text', visible=True, editable=True, primary_key=False, tab_index=1),
    ])

    # ── Worksheet (255) ────────────────────────────────────────────────────────
    worksheet, _ = Page.objects.update_or_create(
        name='CashReceiptJournal',
        defaults={
            'caption': 'Cash Receipt Journal',
            'source_table': 'CashReceiptJournalLine',
            'page_type': 'Worksheet',
            'editable': True,
            'insert_allowed': True,
            'delete_allowed': True,
            'modify_allowed': True,
            'context_filter_field': 'batch_name',
            'context_key_field': 'name',
            'header_page': batch_card,
        },
    )
    worksheet.header_page = batch_card
    worksheet.context_filter_field = 'batch_name'
    worksheet.context_key_field = 'name'
    worksheet.save(update_fields=['header_page', 'context_filter_field', 'context_key_field'])

    ws_ctrl, _ = PageControl.objects.get_or_create(
        page=worksheet,
        name='CashReceiptJournalLines',
        defaults={
            'control_type': 'Group',
            'caption': 'Lines',
            'source_table': 'CashReceiptJournalLine',
            'show_caption': False,
            'editable': True,
            'visible': True,
        },
    )
    PageControlField.objects.filter(page=worksheet, page_control=ws_ctrl).delete()
    _seed_fields(ws_ctrl, worksheet, [
        dict(name='posting_date',   caption='Posting Date',    field_type='Date',    visible=True,  editable=True,  primary_key=False, tab_index=0, freeze_column=True),
        dict(name='document_no',    caption='Document No.',    field_type='Code',    visible=True,  editable=True,  primary_key=False, tab_index=1),
        dict(name='account_type',   caption='Account Type',    field_type='Enum',    visible=True,  editable=True,  primary_key=False, tab_index=2,
             enum_values='Customer,Vendor,G/L Account'),
        dict(name='account_no',     caption='Account No.',     field_type='Code',    visible=True,  editable=True,  primary_key=False, tab_index=3,
             has_table_relation=True, related_table='G_LAccount', related_field='no', related_display_field='name',
             relation_context_field='account_type', relation_context_default='Customer'),
        dict(name='description',    caption='Description',     field_type='Text',    visible=True,  editable=True,  primary_key=False, tab_index=4),
        dict(name='amount',         caption='Amount',          field_type='Integer', visible=True,  editable=True,  primary_key=False, tab_index=5),
        dict(name='payment_method', caption='Payment Method',  field_type='Code',    visible=True,  editable=True,  primary_key=False, tab_index=6,
             has_table_relation=True, related_table='PaymentMethod', related_field='code', related_display_field='description'),
        dict(name='bal_account_type', caption='Bal. Account Type', field_type='Enum', visible=True, editable=True, primary_key=False, tab_index=7,
             enum_values='Customer,Vendor,G/L Account'),
        dict(name='bal_account_no', caption='Bal. Account No.', field_type='Code',   visible=True,  editable=True,  primary_key=False, tab_index=8,
             has_table_relation=True, related_table='G_LAccount', related_field='no', related_display_field='name',
             relation_context_field='bal_account_type'),
        dict(name='status',         caption='Status',           field_type='Enum',   visible=False, editable=False, primary_key=False, tab_index=9,
             enum_values='Open,Posted,Void,Cancelled'),
        dict(name='line_no',        caption='Line No.',         field_type='Integer', visible=False, editable=False, primary_key=False, tab_index=10),
    ])
    _wire_context_account_relations('CashReceiptJournalLine', 'account_no', 'account_type', 'Customer')
    _wire_context_account_relations('CashReceiptJournalLine', 'bal_account_no', 'bal_account_type')

    # Seed a DEFAULT batch so the worksheet opens without error
    from payments.models import CashReceiptJournalBatch
    CashReceiptJournalBatch.objects.get_or_create(
        name='DEFAULT',
        defaults={'description': 'Default Cash Receipt Batch'},
    )

    return worksheet, batch_list


def _seed_general_journal_pages() -> tuple[Page, Page]:
    """General Journal worksheet (BC page 39) + Batch List."""

    batch_card, _ = Page.objects.update_or_create(
        name='GeneralJournalBatchCard',
        defaults={
            'caption': 'General Journal Batch',
            'source_table': 'GeneralJournalBatch',
            'page_type': 'Card',
            'editable': True,
            'insert_allowed': True,
            'delete_allowed': True,
            'modify_allowed': True,
            'title_field': 'name',
        },
    )
    batch_card_ctrl, _ = PageControl.objects.get_or_create(
        page=batch_card,
        name='GeneralJournalBatchCardGroup',
        defaults={
            'control_type': 'Group',
            'caption': 'General',
            'source_table': 'GeneralJournalBatch',
            'show_caption': False,
            'editable': True,
            'visible': True,
        },
    )
    PageControlField.objects.filter(page=batch_card, page_control=batch_card_ctrl).delete()
    _seed_fields(batch_card_ctrl, batch_card, [
        dict(name='name', caption='Batch Name', field_type='Code', visible=True, editable=True, primary_key=True, tab_index=0),
        dict(name='description', caption='Description', field_type='Text', visible=True, editable=True, primary_key=False, tab_index=1),
    ])

    batch_list, _ = Page.objects.update_or_create(
        name='GeneralJournalBatchList',
        defaults={
            'caption': 'General Journal Batches',
            'source_table': 'GeneralJournalBatch',
            'page_type': 'List',
            'editable': True,
            'insert_allowed': True,
            'delete_allowed': True,
            'modify_allowed': True,
            'card_page': batch_card,
        },
    )
    batch_list.card_page = batch_card
    batch_list.save(update_fields=['card_page'])

    batch_list_ctrl, _ = PageControl.objects.get_or_create(
        page=batch_list,
        name='GeneralJournalBatchListControl',
        defaults={
            'control_type': 'Repeater',
            'caption': 'Batches',
            'source_table': 'GeneralJournalBatch',
            'show_caption': True,
            'editable': True,
            'visible': True,
        },
    )
    PageControlField.objects.filter(page=batch_list, page_control=batch_list_ctrl).delete()
    _seed_fields(batch_list_ctrl, batch_list, [
        dict(name='name', caption='Batch Name', field_type='Code', visible=True, editable=True, primary_key=True, tab_index=0, freeze_column=True),
        dict(name='description', caption='Description', field_type='Text', visible=True, editable=True, primary_key=False, tab_index=1),
    ])

    worksheet, _ = Page.objects.update_or_create(
        name='GeneralJournal',
        defaults={
            'caption': 'General Journals',
            'source_table': 'GeneralJournalLine',
            'page_type': 'Worksheet',
            'editable': True,
            'insert_allowed': True,
            'delete_allowed': True,
            'modify_allowed': True,
            'context_filter_field': 'batch_name',
            'context_key_field': 'name',
            'header_page': batch_card,
        },
    )
    worksheet.header_page = batch_card
    worksheet.context_filter_field = 'batch_name'
    worksheet.context_key_field = 'name'
    worksheet.save(update_fields=['header_page', 'context_filter_field', 'context_key_field'])

    ws_ctrl, _ = PageControl.objects.get_or_create(
        page=worksheet,
        name='GeneralJournalLines',
        defaults={
            'control_type': 'Group',
            'caption': 'Lines',
            'source_table': 'GeneralJournalLine',
            'show_caption': False,
            'editable': True,
            'visible': True,
        },
    )
    PageControlField.objects.filter(page=worksheet, page_control=ws_ctrl).delete()
    _seed_fields(ws_ctrl, worksheet, [
        dict(name='posting_date', caption='Posting Date', field_type='Date', visible=True, editable=True, primary_key=False, tab_index=0, freeze_column=True),
        dict(name='document_type', caption='Document Type', field_type='Enum', visible=True, editable=True, primary_key=False, tab_index=1,
             enum_values='Payment,Invoice,Credit Memo,Finance Charge Memo,Reminder,Refund'),
        dict(name='document_no', caption='Document No.', field_type='Code', visible=True, editable=True, primary_key=False, tab_index=2),
        dict(name='account_type', caption='Account Type', field_type='Enum', visible=True, editable=True, primary_key=False, tab_index=3,
             enum_values='Customer,Vendor,G/L Account,Bank Account'),
        dict(name='account_no', caption='Account No.', field_type='Code', visible=True, editable=True, primary_key=False, tab_index=4,
             has_table_relation=True, related_table='G_LAccount', related_field='no', related_display_field='name',
             relation_context_field='account_type', relation_context_default='G/L Account'),
        dict(name='account_name', caption='Account Name', field_type='Text', visible=True, editable=False, primary_key=False, tab_index=5),
        dict(name='description', caption='Description', field_type='Text', visible=True, editable=True, primary_key=False, tab_index=6),
        dict(name='amount', caption='Amount', field_type='Integer', visible=True, editable=True, primary_key=False, tab_index=7),
        dict(name='bal_account_type', caption='Bal. Account Type', field_type='Enum', visible=True, editable=True, primary_key=False, tab_index=8,
             enum_values='Customer,Vendor,G/L Account,Bank Account'),
        dict(name='bal_account_no', caption='Bal. Account No.', field_type='Code', visible=True, editable=True, primary_key=False, tab_index=9,
             has_table_relation=True, related_table='G_LAccount', related_field='no', related_display_field='name',
             relation_context_field='bal_account_type', relation_context_default='G/L Account'),
        dict(name='bal_account_name', caption='Bal. Account Name', field_type='Text', visible=True, editable=False, primary_key=False, tab_index=10),
        dict(name='status', caption='Status', field_type='Enum', visible=False, editable=False, primary_key=False, tab_index=11,
             enum_values='Open,Posted,Void,Cancelled'),
        dict(name='line_no', caption='Line No.', field_type='Integer', visible=False, editable=False, primary_key=False, tab_index=12),
        dict(name='applies_to_object_id', caption='Applies-to Entry', field_type='Integer', visible=False, editable=False, primary_key=False, tab_index=13),
    ])
    _wire_general_journal_account_relations('GeneralJournalLine', 'account_no', 'account_type', 'G/L Account')
    _wire_general_journal_account_relations('GeneralJournalLine', 'bal_account_no', 'bal_account_type', 'G/L Account')

    PageAction.objects.update_or_create(
        page=worksheet,
        name='preview_general_journal',
        defaults={
            'caption': 'Preview Posting',
            'requires_confirmation': False,
            'confirmation_message': '',
            'tooltip': 'Preview ledger entries before posting the batch',
            'visible': True,
            'ribbon_tab': 'Home',
            'image_url': 'Eye',
        },
    )
    PageAction.objects.update_or_create(
        page=worksheet,
        name='post_general_journal',
        defaults={
            'caption': 'Post',
            'requires_confirmation': True,
            'confirmation_message': 'Post all open lines in this journal batch?',
            'tooltip': 'Post general journal batch to the ledger',
            'visible': True,
            'ribbon_tab': 'Home',
            'image_url': 'CircleCheck',
        },
    )
    PageAction.objects.update_or_create(
        page=worksheet,
        name='ApplyVendorEntries',
        defaults={
            'caption': 'Apply Entries',
            'action_relative_url': '#apply-entries',
            'ribbon_tab': 'Home',
            'visible_when_field': 'account_type',
            'visible_when_values': 'Vendor',
            'tooltip': 'Apply journal line to open vendor ledger entries',
            'visible': True,
            'image_url': 'Link2',
        },
    )
    PageAction.objects.update_or_create(
        page=worksheet,
        name='ApplyCustomerEntries',
        defaults={
            'caption': 'Apply Entries',
            'action_relative_url': '#apply-customer-entries',
            'ribbon_tab': 'Home',
            'visible_when_field': 'account_type',
            'visible_when_values': 'Customer',
            'tooltip': 'Apply journal line to open customer ledger entries',
            'visible': True,
            'image_url': 'Link2',
        },
    )

    from financials.models import GeneralJournalBatch

    GeneralJournalBatch.objects.get_or_create(
        name='DEFAULT',
        defaults={'description': 'Default General Journal Batch'},
    )

    return worksheet, batch_list


def _seed_role_centre_pages(
    sales_order_list: Page,
    sales_invoice_list: Page,
    posted_sales_invoice_list: Page,
    posted_purchase_invoice_list: Page,
    customer_ledger_page: Page,
    items_page: Page,
) -> Page:
    """Business Manager Role Centre — BC-style Key Totals, Sales Activities, Bricks, Assistance."""

    rc, _ = Page.objects.update_or_create(
        name='BusinessManagerRC',
        defaults={
            'caption': 'Business Manager',
            'source_table': '',
            'page_type': 'RoleCenter',
            'editable': False,
            'insert_allowed': False,
            'delete_allowed': False,
            'modify_allowed': False,
        },
    )

    PageControl.objects.filter(
        page=rc,
        name__in=[
            'RCHeadline',
            'RCExpenses',
            'RCCueOpenExpenses',
            'RCCuePostedExpenses',
            'RCCueCompletedOrders',
            'RCCuePartialOrders',
            'RCCueQuotesOpen',
            'RCCueOpenOrders',
            'RCCueReadyToShip',
            'RCCueDelayedOrders',
            'RCCueOpenInvoices',
            'RCCuePostedInvoices',
        ],
    ).delete()

    # ── CueGroup: Key Totals (Normal cues) ───────────────────────────────────
    key_totals_group, _ = PageControl.objects.update_or_create(
        page=rc,
        name='RCKeyTotals',
        defaults={
            'control_type': 'CueGroup',
            'caption': 'Key Totals',
            'source_table': '',
            'show_caption': True,
            'editable': False,
            'visible': True,
            'tab_index': 1,
        },
    )
    key_totals_group.tab_index = 1
    key_totals_group.save(update_fields=['tab_index'])

    _seed_cue(
        page=rc,
        cue_group=key_totals_group,
        name='RCCueTotalRevenue',
        caption='Sales This Month',
        tab_index=0,
        cue_source_table='SalesInvoiceLine',
        cue_aggregate='sum',
        cue_aggregate_field='quantity',
        cue_filter_field='',
        cue_filter_value='',
        cue_style='Favorable',
        drill_down_page=posted_sales_invoice_list,
        threshold_warning=None,
        threshold_danger=None,
        headline_template='See more',
    )
    _seed_cue(
        page=rc,
        cue_group=key_totals_group,
        name='RCCueReceivables',
        caption='Receivables',
        tab_index=1,
        cue_source_table='CustomerLedgerEntry',
        cue_aggregate='sum',
        cue_aggregate_field='amount',
        cue_filter_field='open',
        cue_filter_value='True',
        cue_style='Unfavorable',
        drill_down_page=customer_ledger_page,
        threshold_warning=None,
        threshold_danger=None,
        headline_template='See more',
    )
    _seed_cue(
        page=rc,
        cue_group=key_totals_group,
        name='RCCueOverdueReceivables',
        caption='Overdue Sales Invoice Amount',
        tab_index=2,
        # Value computed in pages.views._compute_overdue_receivables.
        cue_source_table='CustomerLedgerEntry',
        cue_aggregate='sum',
        cue_aggregate_field='amount',
        cue_filter_field='open',
        cue_filter_value='True',
        cue_style='Unfavorable',
        drill_down_page=customer_ledger_page,
        threshold_warning=None,
        threshold_danger=None,
        headline_template='See more',
    )
    _seed_cue(
        page=rc,
        cue_group=key_totals_group,
        name='RCCueInventoryValue',
        caption='Inventory Value',
        tab_index=3,
        # Value computed in pages.views._compute_inventory_value (G/L 2110 balance).
        cue_source_table='GeneralLedgerEntry',
        cue_aggregate='sum',
        cue_aggregate_field='amount',
        cue_filter_field='',
        cue_filter_value='',
        cue_style='Ambiguous',
        drill_down_page=items_page,
        threshold_warning=None,
        threshold_danger=None,
        headline_template='See more',
    )

    # ── CueGroup: Sales Activities (Standard cues) ───────────────────────────
    sales_cue_group, _ = PageControl.objects.update_or_create(
        page=rc,
        name='RCSalesActivities',
        defaults={
            'control_type': 'CueGroup',
            'caption': 'Sales Activities',
            'source_table': '',
            'show_caption': True,
            'editable': False,
            'visible': True,
            'tab_index': 2,
        },
    )
    sales_cue_group.tab_index = 2
    sales_cue_group.save(update_fields=['tab_index'])

    _seed_cue(
        page=rc,
        cue_group=sales_cue_group,
        name='RCCueTodaySales',
        caption="Today's Sales",
        tab_index=0,
        cue_source_table='SalesInvoice',
        cue_aggregate='sum',
        cue_aggregate_field='',
        cue_filter_field='status',
        cue_filter_value='Posted',
        cue_style='Favorable',
        drill_down_page=posted_sales_invoice_list,
        threshold_warning=None,
        threshold_danger=None,
        headline_template="View today's invoices",
    )
    _seed_cue(
        page=rc,
        cue_group=sales_cue_group,
        name='RCCueAvgDaysDelayed',
        caption='Avg Days Order Delayed',
        tab_index=1,
        cue_source_table='SalesOrder',
        cue_aggregate='count',
        cue_filter_field='',
        cue_filter_value='',
        cue_style='Subordinate',
        drill_down_page=sales_order_list,
        threshold_warning=None,
        threshold_danger=None,
    )

    # ── Reports quick actions (generate / download financial reports) ─────────
    reports_ctrl, _ = PageControl.objects.update_or_create(
        page=rc,
        name='RCReports',
        defaults={
            'control_type': 'Headline',
            'caption': 'Reports',
            'source_table': '',
            'show_caption': True,
            'editable': False,
            'visible': True,
            'tab_index': 3,
            'headline_template': '',
        },
    )
    reports_ctrl.tab_index = 3
    reports_ctrl.save(update_fields=['tab_index'])

    # ── Quick Access bricks ───────────────────────────────────────────────────
    quick_access, _ = PageControl.objects.update_or_create(
        page=rc,
        name='RCQuickAccess',
        defaults={
            'control_type': 'Headline',
            'caption': 'Quick Access — Top Items and Customers',
            'source_table': '',
            'show_caption': True,
            'editable': False,
            'visible': True,
            'tab_index': 4,
            'headline_template': '',
        },
    )
    quick_access.tab_index = 4
    quick_access.save(update_fields=['tab_index'])

    # ── Business Assistance (chart + recent orders) ───────────────────────────
    assistance, _ = PageControl.objects.update_or_create(
        page=rc,
        name='RCBusinessAssistance',
        defaults={
            'control_type': 'Headline',
            'caption': 'Business Assistance',
            'source_table': '',
            'show_caption': True,
            'editable': False,
            'visible': True,
            'tab_index': 5,
            'headline_template': '',
        },
    )
    assistance.tab_index = 5
    assistance.save(update_fields=['tab_index'])

    part_ctrl, _ = PageControl.objects.update_or_create(
        page=rc,
        name='RCRecentSalesOrders',
        defaults={
            'control_type': 'Part',
            'caption': 'Recent Sales Orders',
            'source_table': '',
            'show_caption': True,
            'editable': False,
            'visible': True,
            'tab_index': 6,
            'part_page': sales_order_list,
            'max_records': 5,
        },
    )
    part_ctrl.part_page = sales_order_list
    part_ctrl.max_records = 5
    part_ctrl.tab_index = 6
    part_ctrl.save(update_fields=['part_page', 'max_records', 'tab_index'])

    _seed_rc_nav_actions(rc, [
        ('NavHome', 'Home', '', 'Home', 'General'),
        ('NavItems', 'Items', 'ItemList', 'Package', 'Inventory'),
        ('NavInventoryAdjustment', 'Inventory Adjustment', 'InventoryAdjustmentJournalList', 'PackagePlus', 'Inventory'),
        ('NavOpeningBalance', 'Opening Balance', 'OpeningBalanceJournalList', 'Scale', 'Inventory'),
        ('NavPostedInventoryAdjustments', 'Posted Inventory Adjustments', 'PostedInventoryAdjustmentList', 'FileCheck', 'Inventory'),
        ('NavCustomers', 'Customers', 'CustomerList', 'Users', 'Sales'),
        ('NavVendors', 'Vendors', 'VendorList', 'Truck', 'Purchase'),
        ('NavSalesOrders', 'Sales Orders', 'SalesOrderList', 'Package', 'Sales'),
        ('NavPOS', 'Point of Sale', 'SalesPOS', 'ShoppingCart', 'Sales'),
        ('NavSalesInvoices', 'Sales Invoices', 'SalesInvoiceList', 'FileOutput', 'Sales'),
        ('NavPostedSalesInvoices', 'Posted Sales Invoices', 'PostedSalesInvoiceList', 'FileCheck', 'Sales'),
        ('NavPurchaseInvoices', 'Purchase Invoices', 'PurchaseInvoiceList', 'FileInput', 'Purchase'),
        ('NavPostedPurchaseInvoices', 'Posted Purchase Invoices', 'PostedPurchaseInvoiceList', 'FileCheck', 'Purchase'),
        ('NavBankAccounts', 'Bank Accounts', 'BankAccountList', 'Landmark', 'Finance'),
        ('NavChartOfAccounts', 'Chart of Accounts', 'GLAccountList', 'ListTree', 'Finance'),
        ('NavFinancialReports', 'Financial Reports', 'FinancialReportList', 'FileChart', 'Finance'),
        ('NavPaymentMethods', 'Payment Methods', 'PaymentMethodList', 'Wallet', 'Finance'),
        ('NavExpenses', 'Expenses', 'ExpenseList', 'Receipt', 'Finance'),
        ('NavPayments', 'Payments', 'PaymentJournalList', 'CreditCard', 'Finance'),
        ('NavCashReceiptJournal', 'Cash Receipt Journal', 'CashReceiptJournal', 'BookOpen', 'Finance'),
        ('NavGeneralJournal', 'General Journals', 'GeneralJournal', 'BookOpen', 'Finance'),
        ('NavUsers', 'Users', 'UsersList', 'User', 'Administration'),
        ('NavPermissionSets', 'Permission Sets', 'PermissionSetsList', 'Shield', 'Administration'),
        ('NavUserGroups', 'User Groups', 'UserGroupsList', 'UsersRound', 'Administration'),
        ('NavUserSettings', 'User settings', 'UserSettingsList', 'Settings', 'Setup'),
        ('NavUserSetup', 'User Setup', 'UserSetupList', 'UserCog', 'Setup'),
        ('NavUnitsOfMeasure', 'Units of Measure', 'UnitOfMeasureList', 'Ruler', 'Setup'),
    ], prune=True)
    # Advanced setup stays on Debug Admin RC only — not Business Manager.
    PageAction.objects.filter(
        page=rc,
        name__in=(
            'NavInventorySetup',
            'NavManufacturingSetup',
            'NavGLSetup',
            'NavNoSeries',
            'NavSalesCreditMemos',
            'NavPostedSalesCreditMemos',
        ),
    ).delete()

    _seed_business_manager_headlines(
        rc,
        sales_order_list=sales_order_list,
        posted_sales_invoice_list=posted_sales_invoice_list,
        customer_ledger_page=customer_ledger_page,
    )

    return rc


def _seed_debug_admin_rc(
    *,
    sales_order_list: Page,
    posted_sales_invoice_list: Page,
    customer_ledger_page: Page,
) -> Page:
    """
    Debug Admin Role Centre — full Business Manager nav plus advanced Setup pages
    (Inventory / Manufacturing / G/L Setup, No. Series).
    """
    rc = _create_role_centre_shell('DebugAdminRC', 'Debug Admin')
    _seed_rc_nav_actions(rc, [
        ('NavHome', 'Home', '', 'Home', 'General'),
        ('NavItems', 'Items', 'ItemList', 'Package', 'Inventory'),
        ('NavInventoryAdjustment', 'Inventory Adjustment', 'InventoryAdjustmentJournalList', 'PackagePlus', 'Inventory'),
        ('NavOpeningBalance', 'Opening Balance', 'OpeningBalanceJournalList', 'Scale', 'Inventory'),
        ('NavPostedInventoryAdjustments', 'Posted Inventory Adjustments', 'PostedInventoryAdjustmentList', 'FileCheck', 'Inventory'),
        ('NavCustomers', 'Customers', 'CustomerList', 'Users', 'Sales'),
        ('NavVendors', 'Vendors', 'VendorList', 'Truck', 'Purchase'),
        ('NavSalesOrders', 'Sales Orders', 'SalesOrderList', 'Package', 'Sales'),
        ('NavPOS', 'Point of Sale', 'SalesPOS', 'ShoppingCart', 'Sales'),
        ('NavSalesInvoices', 'Sales Invoices', 'SalesInvoiceList', 'FileOutput', 'Sales'),
        ('NavPostedSalesInvoices', 'Posted Sales Invoices', 'PostedSalesInvoiceList', 'FileCheck', 'Sales'),
        ('NavSalesCreditMemos', 'Sales Credit Memos', 'SalesCreditMemoList', 'FileOutput', 'Sales'),
        ('NavPostedSalesCreditMemos', 'Posted Sales Credit Memos', 'PostedSalesCreditMemoList', 'FileCheck', 'Sales'),
        ('NavPurchaseInvoices', 'Purchase Invoices', 'PurchaseInvoiceList', 'FileInput', 'Purchase'),
        ('NavPostedPurchaseInvoices', 'Posted Purchase Invoices', 'PostedPurchaseInvoiceList', 'FileCheck', 'Purchase'),
        ('NavBankAccounts', 'Bank Accounts', 'BankAccountList', 'Landmark', 'Finance'),
        ('NavChartOfAccounts', 'Chart of Accounts', 'GLAccountList', 'ListTree', 'Finance'),
        ('NavFinancialReports', 'Financial Reports', 'FinancialReportList', 'FileChart', 'Finance'),
        ('NavPaymentMethods', 'Payment Methods', 'PaymentMethodList', 'Wallet', 'Finance'),
        ('NavExpenses', 'Expenses', 'ExpenseList', 'Receipt', 'Finance'),
        ('NavPayments', 'Payments', 'PaymentJournalList', 'CreditCard', 'Finance'),
        ('NavCashReceiptJournal', 'Cash Receipt Journal', 'CashReceiptJournal', 'BookOpen', 'Finance'),
        ('NavGeneralJournal', 'General Journals', 'GeneralJournal', 'BookOpen', 'Finance'),
        ('NavUsers', 'Users', 'UsersList', 'User', 'Administration'),
        ('NavPermissionSets', 'Permission Sets', 'PermissionSetsList', 'Shield', 'Administration'),
        ('NavUserGroups', 'User Groups', 'UserGroupsList', 'UsersRound', 'Administration'),
        ('NavUserSettings', 'User settings', 'UserSettingsList', 'Settings', 'Setup'),
        ('NavUserSetup', 'User Setup', 'UserSetupList', 'UserCog', 'Setup'),
        ('NavInventorySetup', 'Inventory Setup', 'InventorySetupCard', 'Boxes', 'Setup'),
        ('NavUnitsOfMeasure', 'Units of Measure', 'UnitOfMeasureList', 'Ruler', 'Setup'),
        ('NavManufacturingSetup', 'Manufacturing Setup', 'ManufacturingSetupCard', 'Wrench', 'Setup'),
        ('NavGLSetup', 'G/L Setup', 'GeneralLedgerSetupCard', 'Layers', 'Setup'),
        ('NavNoSeries', 'No. Series', 'NoSeriesList', 'FileText', 'Setup'),
    ])
    _seed_business_manager_headlines(
        rc,
        sales_order_list=sales_order_list,
        posted_sales_invoice_list=posted_sales_invoice_list,
        customer_ledger_page=customer_ledger_page,
    )
    return rc


def _seed_cue(
    *,
    page: Page,
    cue_group: PageControl,
    name: str,
    caption: str,
    tab_index: int,
    cue_source_table: str,
    cue_aggregate: str,
    cue_filter_field: str,
    cue_filter_value: str,
    cue_style: str,
    drill_down_page: Page | None,
    threshold_warning: int | None,
    threshold_danger: int | None,
    cue_aggregate_field: str = '',
    headline_template: str = '',
) -> PageControl:
    """Create or update a single Cue control as a child of a CueGroup."""
    cue, _ = PageControl.objects.update_or_create(
        page=page,
        name=name,
        defaults={
            'control_type': 'Cue',
            'caption': caption,
            'source_table': '',
            'show_caption': True,
            'editable': False,
            'visible': True,
            'tab_index': tab_index,
            'parent_control': cue_group,
            'cue_source_table': cue_source_table,
            'cue_aggregate': cue_aggregate,
            'cue_aggregate_field': cue_aggregate_field,
            'cue_filter_field': cue_filter_field,
            'cue_filter_value': cue_filter_value,
            'cue_style': cue_style,
            'drill_down_page': drill_down_page,
            'headline_template': headline_template,
        },
    )
    # Keep parent and aggregate fields in sync on re-seed
    cue.parent_control = cue_group
    cue.cue_source_table = cue_source_table
    cue.cue_aggregate = cue_aggregate
    cue.cue_aggregate_field = cue_aggregate_field
    cue.cue_filter_field = cue_filter_field
    cue.cue_filter_value = cue_filter_value
    cue.cue_style = cue_style
    cue.drill_down_page = drill_down_page
    cue.headline_template = headline_template
    cue.tab_index = tab_index
    cue.save(update_fields=[
        'parent_control', 'cue_source_table', 'cue_aggregate', 'cue_aggregate_field',
        'cue_filter_field', 'cue_filter_value', 'cue_style',
        'drill_down_page', 'headline_template', 'tab_index',
    ])

    # The threshold lives on the Cue's first PageControlField
    field, _ = PageControlField.objects.get_or_create(
        page_control=cue,
        name='value',
        defaults={
            'page': page,
            'field_id': 0,
            'caption': caption,
            'field_type': 'Integer',
            'visible': False,
            'editable': False,
            'primary_key': False,
            'required': False,
            'tab_index': 0,
            'threshold_warning': threshold_warning,
            'threshold_danger': threshold_danger,
        },
    )
    # Update thresholds on re-seed
    field.threshold_warning = threshold_warning
    field.threshold_danger = threshold_danger
    field.save(update_fields=['threshold_warning', 'threshold_danger'])

    return cue


    return cue


def _seed_headline_group(
    page: Page,
    *,
    name: str = 'RCHeadlines',
    caption: str = '',
    tab_index: int = 0,
) -> PageControl:
    """BC HeadlinePart-style container for rotating headline fields."""
    group, _ = PageControl.objects.update_or_create(
        page=page,
        name=name,
        defaults={
            'control_type': 'HeadlineGroup',
            'caption': caption,
            'source_table': '',
            'show_caption': False,
            'editable': False,
            'visible': True,
            'tab_index': tab_index,
        },
    )
    group.control_type = 'HeadlineGroup'
    group.tab_index = tab_index
    group.save(update_fields=['control_type', 'tab_index'])
    return group


def _seed_headline(
    *,
    page: Page,
    headline_group: PageControl,
    name: str,
    caption: str,
    tab_index: int,
    headline_template: str,
    cue_source_table: str = '',
    cue_aggregate: str = 'count',
    cue_aggregate_field: str = '',
    cue_filter_field: str = '',
    cue_filter_value: str = '',
    drill_down_page: Page | None = None,
    visible: bool = True,
) -> PageControl:
    """Single headline line inside a HeadlineGroup (BC HeadlinePart field)."""
    headline, _ = PageControl.objects.update_or_create(
        page=page,
        name=name,
        defaults={
            'control_type': 'Headline',
            'caption': caption,
            'source_table': '',
            'show_caption': True,
            'editable': False,
            'visible': visible,
            'tab_index': tab_index,
            'parent_control': headline_group,
            'headline_template': headline_template,
            'cue_source_table': cue_source_table,
            'cue_aggregate': cue_aggregate,
            'cue_aggregate_field': cue_aggregate_field,
            'cue_filter_field': cue_filter_field,
            'cue_filter_value': cue_filter_value,
            'drill_down_page': drill_down_page,
        },
    )
    headline.parent_control = headline_group
    headline.headline_template = headline_template
    headline.cue_source_table = cue_source_table
    headline.cue_aggregate = cue_aggregate
    headline.cue_aggregate_field = cue_aggregate_field
    headline.cue_filter_field = cue_filter_field
    headline.cue_filter_value = cue_filter_value
    headline.drill_down_page = drill_down_page
    headline.visible = visible
    headline.tab_index = tab_index
    headline.save(update_fields=[
        'parent_control', 'headline_template', 'cue_source_table', 'cue_aggregate',
        'cue_aggregate_field', 'cue_filter_field', 'cue_filter_value',
        'drill_down_page', 'visible', 'tab_index',
    ])
    return headline


def _seed_business_manager_headlines(
    rc: Page,
    *,
    sales_order_list: Page,
    posted_sales_invoice_list: Page,
    customer_ledger_page: Page,
) -> None:
    PageControl.objects.filter(page=rc, name='RCHeadlines').delete()
    PageControl.objects.filter(
        page=rc, name='RCHeadline', parent_control__isnull=True,
    ).delete()

    group = _seed_headline_group(rc, tab_index=0)
    _seed_headline(
        page=rc, headline_group=group, name='RCHeadlineRevenue',
        caption='Insight from this month',
        tab_index=0,
        headline_template='Sales this month total {value}.',
        cue_source_table='SalesInvoiceLine',
        cue_aggregate='sum',
        cue_aggregate_field='quantity',
        drill_down_page=posted_sales_invoice_list,
    )
    _seed_headline(
        page=rc, headline_group=group, name='RCHeadlineReceivables',
        caption='Organizational health',
        tab_index=1,
        headline_template='Outstanding receivables total {value}.',
        cue_source_table='CustomerLedgerEntry',
        cue_aggregate='sum',
        cue_aggregate_field='amount',
        cue_filter_field='open',
        cue_filter_value='True',
        drill_down_page=customer_ledger_page,
    )
    _seed_headline(
        page=rc, headline_group=group, name='RCHeadlineOverdue',
        caption='Insight from collections',
        tab_index=2,
        headline_template='Overdue customer invoices total {value}.',
        cue_source_table='CustomerLedgerEntry',
        cue_aggregate='sum',
        cue_aggregate_field='amount',
        cue_filter_field='open',
        cue_filter_value='True',
        drill_down_page=customer_ledger_page,
    )
    _seed_headline(
        page=rc, headline_group=group, name='RCHeadlineOpenOrders',
        caption='My workday',
        tab_index=3,
        headline_template='{value} sales orders still need your attention.',
        cue_source_table='SalesOrder',
        cue_aggregate='count',
        cue_filter_field='status',
        cue_filter_value='Open',
        drill_down_page=sales_order_list,
    )
    _seed_headline(
        page=rc, headline_group=group, name='RCHeadlineWelcome',
        caption='Getting started',
        tab_index=4,
        headline_template='Welcome to ZentroApp — use Financial Reports under Finance for P&L and more.',
        drill_down_page=None,
    )


def _seed_cashier_headlines(
    rc: Page,
    *,
    posted_sales_invoice_list: Page,
    customer_list: Page,
) -> None:
    PageControl.objects.filter(page=rc, name='RCHeadlines').delete()
    PageControl.objects.filter(
        page=rc, name='RCHeadline', parent_control__isnull=True,
    ).delete()

    group = _seed_headline_group(rc, tab_index=0)
    _seed_headline(
        page=rc, headline_group=group, name='RCHeadlineTodaySales',
        caption='My workday',
        tab_index=0,
        headline_template="You've recorded {value} in sales today.",
        cue_source_table='SalesInvoice',
        cue_aggregate='sum',
        cue_filter_field='status',
        cue_filter_value='Posted',
        drill_down_page=posted_sales_invoice_list,
    )
    _seed_headline(
        page=rc, headline_group=group, name='RCHeadlinePOS',
        caption='Productivity tip',
        tab_index=1,
        headline_template='Open Point of Sale to serve customers and post invoices quickly.',
        drill_down_page=None,
    )
    _seed_headline(
        page=rc, headline_group=group, name='RCHeadlineCustomers',
        caption='My performance',
        tab_index=2,
        headline_template='You are serving {value} customers in the system.',
        cue_source_table='Customer',
        cue_aggregate='count',
        drill_down_page=customer_list,
    )


def _seed_sales_manager_headlines(
    rc: Page,
    *,
    sales_order_list: Page,
    posted_sales_invoice_list: Page,
) -> None:
    PageControl.objects.filter(page=rc, name='RCHeadlines').delete()

    group = _seed_headline_group(rc, tab_index=0)
    _seed_headline(
        page=rc, headline_group=group, name='RCHeadlineTodaySales',
        caption='My workday',
        tab_index=0,
        headline_template="Today's posted sales are {value}.",
        cue_source_table='SalesInvoice',
        cue_aggregate='sum',
        cue_filter_field='status',
        cue_filter_value='Posted',
        drill_down_page=posted_sales_invoice_list,
    )
    _seed_headline(
        page=rc, headline_group=group, name='RCHeadlineOpenOrders',
        caption='My performance',
        tab_index=1,
        headline_template='{value} sales orders are still open.',
        cue_source_table='SalesOrder',
        cue_aggregate='count',
        cue_filter_field='status',
        cue_filter_value='Open',
        drill_down_page=sales_order_list,
    )


def _seed_accounting_headlines(
    rc: Page,
    *,
    expense_list: Page,
) -> None:
    PageControl.objects.filter(page=rc, name='RCHeadlines').delete()

    group = _seed_headline_group(rc, tab_index=0)
    _seed_headline(
        page=rc, headline_group=group, name='RCHeadlineOpenExpenses',
        caption='My workday',
        tab_index=0,
        headline_template='{value} expenses are waiting to be posted.',
        cue_source_table='Expense',
        cue_aggregate='count',
        cue_filter_field='status',
        cue_filter_value='Open',
        drill_down_page=expense_list,
    )
    _seed_headline(
        page=rc, headline_group=group, name='RCHeadlineFinanceTip',
        caption='Productivity tip',
        tab_index=1,
        headline_template='Review open expenses and payment journals daily to keep books current.',
        drill_down_page=None,
    )


def _seed_warehouse_headlines(
    rc: Page,
    *,
    item_list: Page | None,
) -> None:
    PageControl.objects.filter(page=rc, name='RCHeadlines').delete()

    group = _seed_headline_group(rc, tab_index=0)
    _seed_headline(
        page=rc, headline_group=group, name='RCHeadlineItemCount',
        caption='Organizational health',
        tab_index=0,
        headline_template='Your catalog contains {value} active items.',
        cue_source_table='Item',
        cue_aggregate='count',
        drill_down_page=item_list,
    )
    _seed_headline(
        page=rc, headline_group=group, name='RCHeadlineInventoryTip',
        caption='Productivity tip',
        tab_index=1,
        headline_template='Use inventory journals to adjust stock and record opening balances accurately.',
        drill_down_page=None,
    )


def _delete_legacy_sales_nav_items() -> None:
    """Remove sidebar links replaced by cue tiles (today's sales / sales by person)."""
    PageAction.objects.filter(
        page__page_type='RoleCenter',
        action_type='NavItem',
        name__in=('NavTodaySales', 'NavSalesByPerson'),
    ).delete()


def _seed_rc_nav_actions(page: Page, nav_specs: list[tuple], *, prune: bool = False) -> None:
    """Sidebar navigation links stored as NavItem PageActions on a Role Centre page.

    When prune=True, remove NavItems not in nav_specs (keeps NavSyncQueue for desktop wire-up).
    """
    keep_names: set[str] = set()
    for spec in nav_specs:
        name, caption, target_page_name, icon = spec[:4]
        ribbon_tab = spec[4] if len(spec) > 4 else 'Navigation'
        keep_names.add(name)
        PageAction.objects.update_or_create(
            page=page,
            name=name,
            defaults={
                'caption': caption,
                'action_relative_url': target_page_name,
                'image_url': icon,
                'action_type': 'NavItem',
                'requires_confirmation': False,
                'confirmation_message': '',
                'tooltip': caption,
                'visible': True,
                'ribbon_tab': ribbon_tab,
            },
        )
    if prune:
        keep_names.add('NavSyncQueue')
        PageAction.objects.filter(
            page=page,
            action_type='NavItem',
        ).exclude(name__in=keep_names).delete()


def _create_role_centre_shell(name: str, caption: str) -> Page:
    page, _ = Page.objects.update_or_create(
        name=name,
        defaults={
            'caption': caption,
            'source_table': '',
            'page_type': 'RoleCenter',
            'editable': False,
            'insert_allowed': False,
            'delete_allowed': False,
            'modify_allowed': False,
        },
    )
    return page


def _ensure_company_information() -> None:
    from setup.models import CompanyInformation

    try:
        CompanyInformation.sync_from_public_company()
    except Exception:
        pass


def _seed_company_page_action(
    page: Page,
    name: str,
    caption: str,
    action_relative_url: str,
    image_url: str,
    ribbon_tab: str = 'Home',
    tooltip: str = '',
) -> None:
    PageAction.objects.update_or_create(
        page=page,
        name=name,
        defaults={
            'caption': caption,
            'requires_confirmation': False,
            'confirmation_message': '',
            'tooltip': tooltip or caption,
            'action_relative_url': action_relative_url,
            'visible': True,
            'ribbon_tab': ribbon_tab,
            'image_url': image_url,
        },
    )


def _seed_company_billing_pages() -> None:
    """Read-only subscription card and billing list pages (Business Central style drill-down)."""
    sub_card, _ = Page.objects.update_or_create(
        name='CompanySubscriptionCard',
        defaults={
            'caption': 'Billing & Subscription',
            'source_table': 'CompanySubscription',
            'page_type': 'Card',
            'editable': False,
            'insert_allowed': False,
            'delete_allowed': False,
            'modify_allowed': False,
            'title_field': 'plan',
        },
    )
    sub_card.title_field = 'plan'
    sub_card.save(update_fields=['title_field'])

    sub_ctrl, _ = PageControl.objects.get_or_create(
        page=sub_card,
        name='CompanySubscriptionPlanGroup',
        defaults={
            'control_type': 'Group',
            'caption': 'Current Plan',
            'source_table': 'CompanySubscription',
            'show_caption': True,
            'editable': False,
            'visible': True,
            'tab_index': 0,
        },
    )
    PageControl.objects.filter(page=sub_card, control_type='Group').exclude(
        name='CompanySubscriptionPlanGroup',
    ).delete()
    PageControlField.objects.filter(page=sub_card).delete()
    _seed_fields(sub_ctrl, sub_card, [
        dict(name='plan', caption='Plan Name', field_type='Text',
             visible=True, editable=False, primary_key=False, tab_index=0),
        dict(name='status', caption='Status', field_type='Text',
             visible=True, editable=False, primary_key=False, tab_index=1),
        dict(name='billing_cycle', caption='Billing Cycle', field_type='Text',
             visible=True, editable=False, primary_key=False, tab_index=2),
        dict(name='period_end_date', caption='Period Ends (last included day)', field_type='Date',
             visible=True, editable=False, primary_key=False, tab_index=3),
        dict(name='payment_due_date', caption='Payment Due', field_type='Date',
             visible=True, editable=False, primary_key=False, tab_index=4),
        dict(name='days_remaining', caption='Days Left in Current Period', field_type='Integer',
             visible=True, editable=False, primary_key=False, tab_index=5),
        dict(name='in_grace_period', caption='In Grace Period', field_type='Boolean',
             visible=True, editable=False, primary_key=False, tab_index=6),
        dict(name='grace_days_remaining', caption='Grace Days Remaining', field_type='Integer',
             visible=True, editable=False, primary_key=False, tab_index=7),
        dict(name='access_lock_date', caption='Access Lock Date', field_type='Date',
             visible=True, editable=False, primary_key=False, tab_index=8),
        dict(name='is_active', caption='Active', field_type='Boolean',
             visible=True, editable=False, primary_key=False, tab_index=9),
        dict(name='is_paid', caption='Paid', field_type='Boolean',
             visible=True, editable=False, primary_key=False, tab_index=10),
    ])

    _seed_company_page_action(
        sub_card, 'PayUpfrontMonths', 'Pay Upfront Months',
        '/subscription?intent=renew', 'Calendar', 'Billing',
    )
    _seed_company_page_action(
        sub_card, 'ChangePlan', 'Change plan',
        '/subscription?intent=plan-change', 'RefreshCw', 'Billing',
    )
    _seed_company_page_action(
        sub_card, 'OpenBillingHistory', 'Transaction History',
        'CompanyBillingHistoryList', 'History', 'Billing',
    )
    _seed_company_page_action(
        sub_card, 'OpenBillingPaymentMethods', 'Billing Payment Methods',
        'CompanyPaymentMethodList', 'Wallet', 'Billing',
    )

    billing_list, _ = Page.objects.update_or_create(
        name='CompanyBillingHistoryList',
        defaults={
            'caption': 'Transaction History',
            'source_table': 'CompanyBillingHistory',
            'page_type': 'List',
            'editable': False,
            'insert_allowed': False,
            'delete_allowed': False,
            'modify_allowed': False,
        },
    )
    billing_ctrl, _ = PageControl.objects.get_or_create(
        page=billing_list,
        name='CompanyBillingHistoryListControl',
        defaults={
            'control_type': 'Repeater',
            'caption': 'Transactions',
            'source_table': 'CompanyBillingHistory',
            'show_caption': False,
            'editable': False,
            'visible': True,
        },
    )
    PageControlField.objects.filter(page=billing_list).delete()
    _seed_fields(billing_ctrl, billing_list, [
        dict(name='reference_number', caption='Reference', field_type='Code',
             visible=True, editable=False, primary_key=True, tab_index=0),
        dict(name='product', caption='Product', field_type='Text',
             visible=True, editable=False, primary_key=False, tab_index=1),
        dict(name='status', caption='Status', field_type='Text',
             visible=True, editable=False, primary_key=False, tab_index=2),
        dict(name='billing_date', caption='Date', field_type='Date',
             visible=True, editable=False, primary_key=False, tab_index=3),
        dict(name='amount', caption='Amount', field_type='Decimal',
             visible=True, editable=False, primary_key=False, tab_index=4),
        dict(name='currency', caption='Currency', field_type='Code',
             visible=True, editable=False, primary_key=False, tab_index=5),
    ])

    payment_list, _ = Page.objects.update_or_create(
        name='CompanyPaymentMethodList',
        defaults={
            'caption': 'Billing Payment Methods',
            'source_table': 'CompanyPaymentMethod',
            'page_type': 'List',
            'editable': False,
            'insert_allowed': False,
            'delete_allowed': False,
            'modify_allowed': False,
        },
    )
    payment_ctrl, _ = PageControl.objects.get_or_create(
        page=payment_list,
        name='CompanyPaymentMethodListControl',
        defaults={
            'control_type': 'Repeater',
            'caption': 'Payment Methods',
            'source_table': 'CompanyPaymentMethod',
            'show_caption': False,
            'editable': False,
            'visible': True,
        },
    )
    PageControlField.objects.filter(page=payment_list).delete()
    _seed_fields(payment_ctrl, payment_list, [
        dict(name='holder_name', caption='Holder Name', field_type='Text',
             visible=True, editable=False, primary_key=True, tab_index=0),
        dict(name='method_type', caption='Method Type', field_type='Text',
             visible=True, editable=False, primary_key=False, tab_index=1),
        dict(name='last_four_digits', caption='Last Four Digits', field_type='Code',
             visible=True, editable=False, primary_key=False, tab_index=2),
        dict(name='is_primary', caption='Default', field_type='Boolean',
             visible=True, editable=False, primary_key=False, tab_index=3),
        dict(name='is_active', caption='Active', field_type='Boolean',
             visible=True, editable=False, primary_key=False, tab_index=4),
    ])


def _seed_company_card() -> Page:
    """Singleton card for company name, logo, TIN, and contact details."""
    Page.objects.filter(name='CompanyRoleCentre').delete()

    page, _ = Page.objects.update_or_create(
        name='CompanyCard',
        defaults={
            'caption': 'Company',
            'source_table': 'CompanyInformation',
            'page_type': 'Card',
            'editable': True,
            'insert_allowed': False,
            'delete_allowed': False,
            'modify_allowed': True,
            'title_field': 'display_name',
        },
    )
    page.title_field = 'display_name'
    page.save(update_fields=['title_field'])

    general_ctrl, _ = PageControl.objects.get_or_create(
        page=page,
        name='CompanyGeneralGroup',
        defaults={
            'control_type': 'Group',
            'caption': 'General',
            'source_table': 'CompanyInformation',
            'show_caption': True,
            'editable': True,
            'visible': True,
            'tab_index': 0,
        },
    )
    general_ctrl.tab_index = 0
    general_ctrl.save(update_fields=['tab_index'])

    contact_ctrl, _ = PageControl.objects.get_or_create(
        page=page,
        name='CompanyCommunicationGroup',
        defaults={
            'control_type': 'Group',
            'caption': 'Communication',
            'source_table': 'CompanyInformation',
            'show_caption': True,
            'editable': True,
            'visible': True,
            'tab_index': 1,
        },
    )
    contact_ctrl.caption = 'Communication'
    contact_ctrl.name = 'CompanyCommunicationGroup'
    contact_ctrl.tab_index = 1
    contact_ctrl.save(update_fields=['caption', 'name', 'tab_index'])

    PageControl.objects.filter(page=page, control_type='Group').exclude(
        name__in=('CompanyGeneralGroup', 'CompanyCommunicationGroup'),
    ).delete()
    PageControlField.objects.filter(page=page).delete()

    _seed_fields(general_ctrl, page, [
        dict(name='name', caption='Name', field_type='Text',
             visible=True, editable=False, primary_key=False, tab_index=0),
        dict(name='display_name', caption='Display Name', field_type='Text',
             visible=True, editable=True, primary_key=False, tab_index=1),
        dict(name='address', caption='Address', field_type='Text',
             visible=True, editable=True, primary_key=False, tab_index=2),
        dict(name='city', caption='City', field_type='Text',
             visible=True, editable=True, primary_key=False, tab_index=3),
        dict(name='country', caption='Country/Region Code', field_type='Text',
             visible=True, editable=True, primary_key=False, tab_index=4),
        dict(name='tin', caption='VAT Registration No.', field_type='Code',
             visible=True, editable=True, primary_key=False, tab_index=5),
        dict(name='logo', caption='Picture', field_type='Image',
             visible=True, editable=False, primary_key=False, tab_index=6),
    ])
    _seed_fields(contact_ctrl, page, [
        dict(name='phone', caption='Phone No.', field_type='Text',
             visible=True, editable=True, primary_key=False, tab_index=0),
        dict(name='email', caption='Email', field_type='Text',
             visible=True, editable=True, primary_key=False, tab_index=1),
        dict(name='website', caption='Home Page', field_type='Text',
             visible=True, editable=True, primary_key=False, tab_index=2),
    ])

    _seed_company_page_action(
        page, 'OpenCompanySettings', 'Company Settings',
        '/company/settings', 'Settings2', 'Home',
        tooltip='Regional settings and module access',
    )
    _seed_company_page_action(
        page, 'OpenBillingSubscription', 'Billing & Subscription',
        'CompanySubscriptionCard', 'CreditCard', 'Billing',
        tooltip='Open subscription and billing details',
    )
    _seed_company_page_action(
        page, 'OpenBillingHistory', 'Transaction History',
        'CompanyBillingHistoryList', 'History', 'Billing',
    )
    _seed_company_page_action(
        page, 'OpenBillingPaymentMethods', 'Billing Payment Methods',
        'CompanyPaymentMethodList', 'Wallet', 'Billing',
    )
    _seed_company_page_action(
        page, 'PayUpfrontMonths', 'Pay Upfront Months',
        '/subscription?intent=renew', 'Calendar', 'Billing',
    )
    _seed_company_page_action(
        page, 'ChangePlan', 'Change plan',
        '/subscription?intent=plan-change', 'RefreshCw', 'Billing',
    )

    return page


def _seed_sales_manager_rc(
    sales_order_list: Page,
    sales_invoice_list: Page,
    posted_sales_invoice_list: Page,
) -> Page:
    rc = _create_role_centre_shell('SalesManagerRC', 'Sales Manager')

    _seed_sales_manager_headlines(
        rc,
        sales_order_list=sales_order_list,
        posted_sales_invoice_list=posted_sales_invoice_list,
    )

    sales_cue_group, _ = PageControl.objects.update_or_create(
        page=rc,
        name='RCSalesActivities',
        defaults={
            'control_type': 'CueGroup',
            'caption': 'Sales Activities',
            'source_table': '',
            'show_caption': True,
            'editable': False,
            'visible': True,
            'tab_index': 2,
        },
    )
    sales_cue_group.tab_index = 2
    sales_cue_group.save(update_fields=['tab_index'])
    _seed_cue(
        page=rc, cue_group=sales_cue_group, name='RCCueOpenOrders',
        caption='Open Sales Orders', tab_index=0,
        cue_source_table='SalesOrder', cue_aggregate='count',
        cue_filter_field='status', cue_filter_value='Open',
        cue_style='Unfavorable', drill_down_page=sales_order_list,
        threshold_warning=10, threshold_danger=25,
    )
    _seed_cue(
        page=rc, cue_group=sales_cue_group, name='RCCueCompletedOrders',
        caption='Completed Orders', tab_index=1,
        cue_source_table='SalesOrder', cue_aggregate='count',
        cue_filter_field='status', cue_filter_value='Completed',
        cue_style='Favorable', drill_down_page=sales_order_list,
        threshold_warning=None, threshold_danger=None,
    )
    _seed_cue(
        page=rc, cue_group=sales_cue_group, name='RCCuePostedInvoices',
        caption='Posted Sales Invoices', tab_index=2,
        cue_source_table='SalesInvoice', cue_aggregate='count',
        cue_filter_field='status', cue_filter_value='Posted',
        cue_style='Subordinate', drill_down_page=posted_sales_invoice_list,
        threshold_warning=None, threshold_danger=None,
    )
    _seed_cue(
        page=rc, cue_group=sales_cue_group, name='RCCueTodaySales',
        caption="Today's Sales", tab_index=3,
        cue_source_table='SalesInvoice', cue_aggregate='sum',
        cue_aggregate_field='',
        cue_filter_field='status', cue_filter_value='Posted',
        cue_style='Favorable', drill_down_page=posted_sales_invoice_list,
        threshold_warning=None, threshold_danger=None,
        headline_template="View today's invoices",
    )

    part_ctrl, _ = PageControl.objects.update_or_create(
        page=rc,
        name='RCRecentSalesOrders',
        defaults={
            'control_type': 'Part',
            'caption': 'Recent Sales Orders',
            'source_table': '',
            'show_caption': True,
            'editable': False,
            'visible': True,
            'tab_index': 4,
            'part_page': sales_order_list,
            'max_records': 5,
        },
    )
    part_ctrl.part_page = sales_order_list
    part_ctrl.max_records = 5
    part_ctrl.tab_index = 4
    part_ctrl.save(update_fields=['part_page', 'max_records', 'tab_index'])

    _seed_rc_nav_actions(rc, [
        ('NavHome', 'Home', '', 'Home', 'General'),
        ('NavPOS', 'Point of Sale', 'SalesPOS', 'ShoppingCart', 'Sales'),
        ('NavSalesOrders', 'Sales Orders', 'SalesOrderList', 'Package', 'Sales'),
        ('NavCustomers', 'Customers', 'CustomerList', 'Users', 'Sales'),
        ('NavSalesInvoices', 'Sales Invoices', 'SalesInvoiceList', 'FileOutput', 'Sales'),
        ('NavPostedSalesInvoices', 'Posted Sales Invoices', 'PostedSalesInvoiceList', 'FileCheck', 'Sales'),
        ('NavSalesCreditMemos', 'Sales Credit Memos', 'SalesCreditMemoList', 'FileOutput', 'Sales'),
        ('NavPostedSalesCreditMemos', 'Posted Sales Credit Memos', 'PostedSalesCreditMemoList', 'FileCheck', 'Sales'),
        ('NavItems', 'Items', 'ItemList', 'Package', 'Inventory'),
    ])
    return rc


def _seed_accounting_rc(expense_list: Page, payment_list: Page) -> Page:
    rc = _create_role_centre_shell('AccountingRC', 'Accounting')

    _seed_accounting_headlines(rc, expense_list=expense_list)

    expense_cue_group, _ = PageControl.objects.update_or_create(
        page=rc,
        name='RCExpenses',
        defaults={
            'control_type': 'CueGroup',
            'caption': 'Finance',
            'source_table': '',
            'show_caption': True,
            'editable': False,
            'visible': True,
            'tab_index': 2,
        },
    )
    expense_cue_group.tab_index = 2
    expense_cue_group.save(update_fields=['tab_index'])
    _seed_cue(
        page=rc, cue_group=expense_cue_group, name='RCCueOpenExpenses',
        caption='Open Expenses', tab_index=0,
        cue_source_table='Expense', cue_aggregate='count',
        cue_filter_field='status', cue_filter_value='Open',
        cue_style='Ambiguous', drill_down_page=expense_list,
        threshold_warning=5, threshold_danger=10,
    )
    _seed_cue(
        page=rc, cue_group=expense_cue_group, name='RCCuePostedExpenses',
        caption='Posted Expenses', tab_index=1,
        cue_source_table='Expense', cue_aggregate='count',
        cue_filter_field='status', cue_filter_value='Posted',
        cue_style='Favorable', drill_down_page=expense_list,
        threshold_warning=None, threshold_danger=None,
    )

    part_ctrl, _ = PageControl.objects.update_or_create(
        page=rc,
        name='RCRecentExpenses',
        defaults={
            'control_type': 'Part',
            'caption': 'Recent Expenses',
            'source_table': '',
            'show_caption': True,
            'editable': False,
            'visible': True,
            'tab_index': 3,
            'part_page': expense_list,
            'max_records': 5,
        },
    )
    part_ctrl.part_page = expense_list
    part_ctrl.max_records = 5
    part_ctrl.tab_index = 3
    part_ctrl.save(update_fields=['part_page', 'max_records', 'tab_index'])

    _seed_rc_nav_actions(rc, [
        ('NavHome', 'Home', '', 'Home', 'General'),
        ('NavExpenses', 'Expenses', 'ExpenseList', 'Receipt', 'Finance'),
        ('NavPayments', 'Payments', 'PaymentJournalList', 'CreditCard', 'Finance'),
        ('NavBankAccounts', 'Bank Accounts', 'BankAccountList', 'Landmark', 'Finance'),
        ('NavChartOfAccounts', 'Chart of Accounts', 'GLAccountList', 'ListTree', 'Finance'),
        ('NavFinancialReports', 'Financial Reports', 'FinancialReportList', 'FileChart', 'Finance'),
        ('NavPaymentMethods', 'Payment Methods', 'PaymentMethodList', 'Wallet', 'Finance'),
        ('NavDimensions', 'Dimensions', 'DimensionList', 'Layers', 'Setup'),
        ('NavCashReceiptJournal', 'Cash Receipt Journal', 'CashReceiptJournal', 'BookOpen', 'Finance'),
        ('NavGeneralJournal', 'General Journals', 'GeneralJournal', 'BookOpen', 'Finance'),
        ('NavGLSetup', 'G/L Setup', 'GeneralLedgerSetupCard', 'Layers', 'Setup'),
    ])
    return rc


def _seed_warehouse_rc(
    posted_purchase_invoice_list: Page | None = None,
    inventory_adj_list: Page | None = None,
    opening_balance_list: Page | None = None,
) -> Page:
    rc = _create_role_centre_shell('WarehouseRC', 'Warehouse')
    item_list = Page.objects.filter(name='ItemList').first()

    _seed_warehouse_headlines(rc, item_list=item_list)

    inventory_group, _ = PageControl.objects.update_or_create(
        page=rc,
        name='RCInventory',
        defaults={
            'control_type': 'CueGroup',
            'caption': 'Inventory',
            'source_table': '',
            'show_caption': True,
            'editable': False,
            'visible': True,
            'tab_index': 2,
        },
    )
    inventory_group.tab_index = 2
    inventory_group.save(update_fields=['tab_index'])
    _seed_cue(
        page=rc, cue_group=inventory_group, name='RCCueItemCount',
        caption='Items', tab_index=0,
        cue_source_table='Item', cue_aggregate='count',
        cue_filter_field='', cue_filter_value='',
        cue_style='Favorable', drill_down_page=item_list,
        threshold_warning=None, threshold_danger=None,
    )
    if posted_purchase_invoice_list:
        _seed_cue(
            page=rc, cue_group=inventory_group, name='RCCuePostedPurchaseInvoices',
            caption='Posted Purchase Invoices', tab_index=1,
            cue_source_table='PostedPurchaseInvoice', cue_aggregate='count',
            cue_filter_field='', cue_filter_value='',
            cue_style='Subordinate', drill_down_page=posted_purchase_invoice_list,
            threshold_warning=None, threshold_danger=None,
        )

    if item_list:
        part_ctrl, _ = PageControl.objects.update_or_create(
            page=rc,
            name='RCRecentItems',
            defaults={
                'control_type': 'Part',
                'caption': 'Items',
                'source_table': '',
                'show_caption': True,
                'editable': False,
                'visible': True,
                'tab_index': 3,
                'part_page': item_list,
                'max_records': 5,
            },
        )
        part_ctrl.part_page = item_list
        part_ctrl.max_records = 5
        part_ctrl.save(update_fields=['part_page', 'max_records'])

    _seed_rc_nav_actions(rc, [
        ('NavHome', 'Home', '', 'Home', 'General'),
        ('NavItems', 'Items', 'ItemList', 'Package', 'Inventory'),
        ('NavInventoryAdjustment', 'Inventory Adjustment', 'InventoryAdjustmentJournalList', 'PackagePlus', 'Inventory'),
        ('NavOpeningBalance', 'Opening Balance', 'OpeningBalanceJournalList', 'Scale', 'Inventory'),
        ('NavPostedInventoryAdjustments', 'Posted Inventory Adjustments', 'PostedInventoryAdjustmentList', 'FileCheck', 'Inventory'),
        ('NavVendors', 'Vendors', 'VendorList', 'Truck', 'Purchase'),
        ('NavPurchaseInvoices', 'Purchase Invoices', 'PurchaseInvoiceList', 'FileInput', 'Purchase'),
        ('NavPostedPurchaseInvoices', 'Posted Purchase Invoices', 'PostedPurchaseInvoiceList', 'FileCheck', 'Purchase'),
    ])
    return rc


def _seed_cashier_rc(
    posted_sales_invoice_list: Page,
    customer_list: Page,
) -> Page:
    """Cashier Role Centre — POS-first nav, today's sales cues, recent posted invoices."""
    rc = _create_role_centre_shell('CashierRC', 'Cashier')

    _seed_cashier_headlines(
        rc,
        posted_sales_invoice_list=posted_sales_invoice_list,
        customer_list=customer_list,
    )

    sales_cue_group, _ = PageControl.objects.update_or_create(
        page=rc,
        name='RCSalesActivities',
        defaults={
            'control_type': 'CueGroup',
            'caption': 'Sales Activities',
            'source_table': '',
            'show_caption': True,
            'editable': False,
            'visible': True,
            'tab_index': 2,
        },
    )
    sales_cue_group.tab_index = 2
    sales_cue_group.save(update_fields=['tab_index'])

    _seed_cue(
        page=rc,
        cue_group=sales_cue_group,
        name='RCCueTodaySales',
        caption="Today's Sales",
        tab_index=0,
        cue_source_table='SalesInvoice',
        cue_aggregate='sum',
        cue_filter_field='status',
        cue_filter_value='Posted',
        cue_style='Favorable',
        drill_down_page=posted_sales_invoice_list,
        threshold_warning=None,
        threshold_danger=None,
        headline_template="View today's invoices",
    )
    _seed_cue(
        page=rc,
        cue_group=sales_cue_group,
        name='RCCueCustomers',
        caption='Customers',
        tab_index=1,
        cue_source_table='Customer',
        cue_aggregate='count',
        cue_filter_field='',
        cue_filter_value='',
        cue_style='Subordinate',
        drill_down_page=customer_list,
        threshold_warning=None,
        threshold_danger=None,
        headline_template='View customers',
    )
    _seed_cue(
        page=rc,
        cue_group=sales_cue_group,
        name='RCCuePostedInvoices',
        caption='Posted Invoices',
        tab_index=2,
        cue_source_table='SalesInvoice',
        cue_aggregate='count',
        cue_filter_field='status',
        cue_filter_value='Posted',
        cue_style='Ambiguous',
        drill_down_page=posted_sales_invoice_list,
        threshold_warning=None,
        threshold_danger=None,
        headline_template='View posted invoices',
    )

    part_ctrl, _ = PageControl.objects.update_or_create(
        page=rc,
        name='RCRecentPostedInvoices',
        defaults={
            'control_type': 'Part',
            'caption': 'Recent Posted Sales Invoices',
            'source_table': '',
            'show_caption': True,
            'editable': False,
            'visible': True,
            'tab_index': 3,
            'part_page': posted_sales_invoice_list,
            'max_records': 5,
        },
    )
    part_ctrl.part_page = posted_sales_invoice_list
    part_ctrl.max_records = 5
    part_ctrl.tab_index = 3
    part_ctrl.save(update_fields=['part_page', 'max_records', 'tab_index'])

    _seed_rc_nav_actions(rc, [
        ('NavHome', 'Home', '', 'Home', 'General'),
        ('NavPOS', 'Point of Sale', 'SalesPOS', 'ShoppingCart', 'Sales'),
        ('NavCustomers', 'Customers', 'CustomerList', 'Users', 'Sales'),
        ('NavItems', 'Items', 'ItemList', 'Package', 'Inventory'),
        ('NavPostedSalesInvoices', 'Posted Sales Invoices', 'PostedSalesInvoiceList', 'FileCheck', 'Sales'),
        ('NavUserSettings', 'User settings', 'UserSettingsList', 'Settings', 'Setup'),
    ])
    return rc


def _seed_pharmacist_rc(
    posted_purchase_invoice_list: Page | None = None,
    purchase_invoice_list: Page | None = None,
    payment_method_list: Page | None = None,
) -> Page:
    """Pharmacist Role Centre — inventory, purchases, suppliers, payments (no sales)."""
    rc = _create_role_centre_shell('PharmacistRC', 'Pharmacist')
    item_list = Page.objects.filter(name='ItemList').first()

    inventory_group, _ = PageControl.objects.update_or_create(
        page=rc,
        name='RCInventory',
        defaults={
            'control_type': 'CueGroup',
            'caption': 'Inventory & Purchases',
            'source_table': '',
            'show_caption': True,
            'editable': False,
            'visible': True,
            'tab_index': 1,
        },
    )
    inventory_group.tab_index = 1
    inventory_group.save(update_fields=['tab_index'])

    if item_list:
        _seed_cue(
            page=rc, cue_group=inventory_group, name='RCCueItemCount',
            caption='Items', tab_index=0,
            cue_source_table='Item', cue_aggregate='count',
            cue_filter_field='', cue_filter_value='',
            cue_style='Favorable', drill_down_page=item_list,
            threshold_warning=None, threshold_danger=None,
        )
    if posted_purchase_invoice_list:
        _seed_cue(
            page=rc, cue_group=inventory_group, name='RCCuePostedPurchaseInvoices',
            caption='Posted Purchases', tab_index=1,
            cue_source_table='PostedPurchaseInvoice', cue_aggregate='count',
            cue_filter_field='', cue_filter_value='',
            cue_style='Subordinate', drill_down_page=posted_purchase_invoice_list,
            threshold_warning=None, threshold_danger=None,
        )

    nav_specs = [
        ('NavHome', 'Home', '', 'Home', 'General'),
        ('NavItems', 'Items', 'ItemList', 'Package', 'Inventory'),
        ('NavPurchaseInvoices', 'Purchases', 'PurchaseInvoiceList', 'ShoppingCart', 'Purchase'),
        ('NavPostedPurchaseInvoices', 'Posted Purchase Invoices', 'PostedPurchaseInvoiceList', 'FileCheck', 'Purchase'),
        ('NavVendors', 'Suppliers', 'VendorList', 'Truck', 'Purchase'),
        ('NavUserSettings', 'User settings', 'UserSettingsList', 'Settings', 'Setup'),
    ]
    if payment_method_list:
        nav_specs.insert(
            -1,
            ('NavPaymentMethods', 'Payment Methods', 'PaymentMethodList', 'Wallet', 'Payments'),
        )

    _seed_rc_nav_actions(rc, nav_specs)
    return rc


def _seed_operations_manager_rc(
    payment_method_list: Page | None = None,
    expense_list: Page | None = None,
    payment_list: Page | None = None,
) -> Page:
    """Operations Manager Role Centre — nav-only home (no financial/sales dashboard cues)."""
    rc = _create_role_centre_shell('OperationsManagerRC', 'Operations Manager')

    # Remove dashboard widgets copied from Business Manager on earlier seeds.
    PageControl.objects.filter(page=rc, name__in=(
        'RCHeadlines',
        'RCKeyTotals',
        'RCSalesActivities',
        'RCRecentSalesOrders',
    )).delete()
    PageControl.objects.filter(
        page=rc,
        name__startswith='RCHeadline',
        parent_control__isnull=True,
    ).delete()
    PageControl.objects.filter(
        page=rc,
        name__startswith='RCCue',
    ).delete()

    nav_specs = [
        ('NavHome', 'Home', '', 'Home', 'General'),
        ('NavItems', 'Items', 'ItemList', 'Package', 'Inventory'),
        ('NavCustomers', 'Customers', 'CustomerList', 'Users', 'Sales'),
        ('NavVendors', 'Suppliers', 'VendorList', 'Truck', 'Purchase'),
        ('NavSalesOrders', 'Sales Orders', 'SalesOrderList', 'Package', 'Sales'),
        ('NavPOS', 'Point of Sale', 'SalesPOS', 'ShoppingCart', 'Sales'),
        ('NavSalesInvoices', 'Sales Invoices', 'SalesInvoiceList', 'FileOutput', 'Sales'),
        ('NavPurchaseInvoices', 'Purchases', 'PurchaseInvoiceList', 'ShoppingCart', 'Purchase'),
        ('NavPostedPurchaseInvoices', 'Posted Purchase Invoices', 'PostedPurchaseInvoiceList', 'FileCheck', 'Purchase'),
        ('NavUserSettings', 'User settings', 'UserSettingsList', 'Settings', 'Setup'),
        ('NavUserSetup', 'User Setup', 'UserSetupList', 'UserCog', 'Setup'),
    ]
    # Hide posted sales / credit-memo history from Operations Manager.
    PageAction.objects.filter(
        page=rc,
        name__in=(
            'NavUsers',
            'NavUserGroups',
            'NavPostedSalesInvoices',
            'NavSalesCreditMemos',
            'NavPostedSalesCreditMemos',
        ),
    ).delete()
    if payment_method_list:
        nav_specs.insert(-2, ('NavPaymentMethods', 'Payment Methods', 'PaymentMethodList', 'Wallet', 'Payments'))
    if expense_list:
        nav_specs.insert(-2, ('NavExpenses', 'Expenses', 'ExpenseList', 'Receipt', 'Finance'))
    if payment_list:
        nav_specs.insert(-2, ('NavPayments', 'Payments', 'PaymentJournalList', 'CreditCard', 'Finance'))

    _seed_rc_nav_actions(rc, nav_specs)
    return rc


def _seed_application_profiles(
    *,
    business_rc: Page,
    sales_rc: Page,
    accounting_rc: Page,
    warehouse_rc: Page,
    cashier_rc: Page,
    pharmacist_rc: Page | None = None,
    operations_manager_rc: Page | None = None,
    debug_admin_rc: Page | None = None,
) -> None:
    from authentication.models import ApplicationProfile

    specs = (
        ('BUSINESS-MGR', 'Business Manager', business_rc),
        ('SALES-MGR', 'Sales Manager', sales_rc),
        ('ACCOUNTANT', 'Accountant', accounting_rc),
        ('WAREHOUSE', 'Warehouse', warehouse_rc),
        ('CASHIER', 'Cashier', cashier_rc),
    )
    if pharmacist_rc is not None:
        specs = (*specs, ('PHARMACIST', 'Pharmacist', pharmacist_rc))
    if operations_manager_rc is not None:
        specs = (*specs, ('OPERATIONS-MGR', 'Operations Manager', operations_manager_rc))
    if debug_admin_rc is not None:
        specs = (*specs, ('DEBUG-ADMIN', 'Debug Admin', debug_admin_rc))
    for code, description, rc_page in specs:
        ApplicationProfile.objects.update_or_create(
            code=code,
            defaults={
                'description': description,
                'role_centre_page': rc_page,
            },
        )


def _assign_default_application_profiles() -> None:
    """Assign Role Centres from legacy Role / UserGroup access (not blanket BUSINESS-MGR)."""
    from authentication.profile_assignment import assign_application_profiles

    stats = assign_application_profiles(force=True)
    print(
        f"Application profiles assigned: updated={stats['updated']} "
        f"unmapped={stats['unmapped']} users={stats['users']}"
    )


def _seed_item_card() -> Page:
    """Item Card with BC-style inventory, pricing, UOM fields and UOM lines subform."""

    iuom_subform, _ = Page.objects.update_or_create(
        name='ItemUnitOfMeasureSubform',
        defaults={
            'caption': 'Units of Measure',
            'source_table': 'ItemUnitOfMeasure',
            'page_type': 'ListPart',
            'editable': True,
            'insert_allowed': True,
            'delete_allowed': True,
            'modify_allowed': True,
        },
    )
    iuom_ctrl, _ = PageControl.objects.get_or_create(
        page=iuom_subform,
        name='ItemUnitOfMeasureControl',
        defaults={
            'control_type': 'Repeater',
            'caption': 'Units of Measure',
            'source_table': 'ItemUnitOfMeasure',
            'show_caption': True,
            'editable': True,
            'visible': True,
        },
    )
    PageControlField.objects.filter(page=iuom_subform, page_control=iuom_ctrl).delete()
    _seed_fields(iuom_ctrl, iuom_subform, [
        dict(
            name='unit_of_measure', caption='Code', field_type='Code', visible=True,
            editable=True, primary_key=False, tab_index=0, required=True,
            has_table_relation=True, related_table='UnitOfMeasure',
            related_field='code', related_display_field='description',
        ),
        dict(
            name='quantity_per_unit', caption='Qty. per Unit of Measure',
            field_type='Integer', visible=True, editable=True,
            primary_key=False, tab_index=1, required=True,
        ),
        dict(
            name='default', caption='Default', field_type='Boolean',
            visible=True, editable=True, primary_key=False, tab_index=2,
        ),
        dict(
            name='price', caption='Price', field_type='Decimal',
            visible=True, editable=True, primary_key=False, tab_index=3,
        ),
    ])
    _ensure_table_relation('ItemUnitOfMeasure', 'unit_of_measure', 'UnitOfMeasure')

    item_card, _ = Page.objects.update_or_create(
        name='ItemCard',
        defaults={
            'caption': 'Item Card',
            'source_table': 'Item',
            'page_type': 'Card',
            'editable': True,
            'insert_allowed': True,
            'delete_allowed': True,
            'modify_allowed': True,
            'title_field': 'item_name',
        },
    )

    general_ctrl, _ = PageControl.objects.update_or_create(
        page=item_card,
        name='ItemGeneralGroup',
        defaults={
            'control_type': 'Group',
            'caption': 'General',
            'source_table': 'Item',
            'show_caption': True,
            'editable': True,
            'visible': True,
            'tab_index': 0,
        },
    )
    PageControlField.objects.filter(page=item_card, page_control=general_ctrl).delete()
    _seed_fields(general_ctrl, item_card, [
        dict(name='no', caption='No.', field_type='Code', visible=True, editable=False, primary_key=True, tab_index=0),
        dict(name='item_name', caption='Item Name', field_type='Text', visible=True, editable=True, primary_key=False, tab_index=1),
        dict(name='type', caption='Type', field_type='Enum', visible=True, editable=True, primary_key=False, tab_index=2,
             enum_values='Inventory,Service,Non-Inventory'),
        dict(name='description', caption='Description', field_type='Text', visible=True, editable=True, primary_key=False, tab_index=3),
        dict(name='bar_code_no', caption='Barcode', field_type='Code', visible=True, editable=True, primary_key=False, tab_index=4),
        dict(name='blocked', caption='Blocked', field_type='Boolean', visible=True, editable=True, primary_key=False, tab_index=5),
    ])

    pricing_ctrl, _ = PageControl.objects.update_or_create(
        page=item_card,
        name='ItemPricingGroup',
        defaults={
            'control_type': 'Group',
            'caption': 'Pricing',
            'source_table': 'Item',
            'show_caption': True,
            'editable': True,
            'visible': True,
            'tab_index': 1,
        },
    )
    PageControlField.objects.filter(page=item_card, page_control=pricing_ctrl).delete()
    _seed_fields(pricing_ctrl, item_card, [
        dict(name='unit_price', caption='Unit Price', field_type='Decimal', visible=True, editable=True, primary_key=False, tab_index=0),
        dict(name='unit_cost', caption='Buying Price', field_type='Decimal', visible=True, editable=False, primary_key=False, tab_index=1),
    ])

    inventory_ctrl, _ = PageControl.objects.update_or_create(
        page=item_card,
        name='ItemInventoryGroup',
        defaults={
            'control_type': 'Group',
            'caption': 'Inventory',
            'source_table': 'Item',
            'show_caption': True,
            'editable': True,
            'visible': True,
            'tab_index': 2,
        },
    )
    PageControlField.objects.filter(page=item_card, page_control=inventory_ctrl).delete()
    _seed_fields(inventory_ctrl, item_card, [
        dict(name='inventory', caption='Inventory', field_type='Integer', visible=True, editable=False, primary_key=False, tab_index=0),
        dict(name='minimum_stock', caption='Minimum Stock', field_type='Integer', visible=True, editable=True, primary_key=False, tab_index=1),
        dict(
            name='tracking_code', caption='Item Tracking Code', field_type='Code',
            visible=True, editable=True, primary_key=False, tab_index=2,
            has_table_relation=True, related_table='ItemTrackingCodes',
            related_field='code', related_display_field='description',
        ),
    ])
    _ensure_table_relation('Item', 'tracking_code', 'ItemTrackingCodes')

    uom_ctrl, _ = PageControl.objects.update_or_create(
        page=item_card,
        name='ItemUOMGroup',
        defaults={
            'control_type': 'Group',
            'caption': 'Units of Measure',
            'source_table': 'Item',
            'show_caption': True,
            'editable': True,
            'visible': True,
            'tab_index': 3,
        },
    )
    PageControlField.objects.filter(page=item_card, page_control=uom_ctrl).delete()
    _seed_fields(uom_ctrl, item_card, [
        dict(
            name='unit_of_measure', caption='Base Unit of Measure', field_type='Code',
            visible=True, editable=True, primary_key=False, tab_index=0,
            has_table_relation=True, related_table='UnitOfMeasure',
            related_field='code', related_display_field='description',
            relation_lookup_footer=True,
            relation_part_control_name='ItemUnitOfMeasurePart',
        ),
        dict(
            name='sales_unit_of_measure', caption='Sales Unit of Measure', field_type='Code',
            visible=True, editable=True, primary_key=False, tab_index=1,
            has_table_relation=True, related_table='ItemUnitOfMeasure',
            related_field='id', related_display_field='unit_of_measure__code',
            relation_context_field='no',
            relation_lookup_footer=True,
            relation_part_control_name='ItemUnitOfMeasurePart',
        ),
        dict(
            name='purchase_unit_of_measure', caption='Purchase Unit of Measure', field_type='Code',
            visible=True, editable=True, primary_key=False, tab_index=2,
            has_table_relation=True, related_table='ItemUnitOfMeasure',
            related_field='id', related_display_field='unit_of_measure__code',
            relation_context_field='no',
            relation_lookup_footer=True,
            relation_part_control_name='ItemUnitOfMeasurePart',
        ),
    ])
    _ensure_table_relation('Item', 'unit_of_measure', 'UnitOfMeasure')

    iuom_part, _ = PageControl.objects.update_or_create(
        page=item_card,
        name='ItemUnitOfMeasurePart',
        defaults={
            'control_type': 'Part',
            'caption': 'Units of Measure',
            'source_table': 'ItemUnitOfMeasure',
            'show_caption': True,
            'editable': True,
            'visible': False,
            'tab_index': 4,
            'part_page': iuom_subform,
            'link_field': 'item__system_id',
        },
    )
    iuom_part.part_page = iuom_subform
    iuom_part.link_field = 'item__system_id'
    iuom_part.visible = False
    iuom_part.save(update_fields=['part_page', 'link_field', 'visible'])

    PageControl.objects.update_or_create(
        page=item_card,
        name='ItemAttachments',
        defaults={
            'control_type': 'FactBox',
            'caption': 'Product Images',
            'source_table': 'ItemImages',
            'link_field': 'no',
            'show_caption': True,
            'editable': True,
            'visible': True,
            'tab_index': 5,
        },
    )

    PageControl.objects.filter(page=item_card, name='ItemCardGroup').delete()

    return item_card


def _seed_item_card_drill_down_lists(item_journal_card: Page) -> tuple[Page, Page]:
    """List pages opened from Item Card ribbon (filtered by current item no)."""
    uom_list = _create_drill_down_list_page(
        name='ItemUnitOfMeasureList',
        caption='Item Units of Measure',
        source_table='ItemUnitOfMeasure',
        context_filter_field='item__no',
        fields=[
            dict(
                name='id', caption='Entry No.', field_type='Integer',
                visible=False, editable=False, primary_key=True, tab_index=0,
            ),
            dict(
                name='unit_of_measure', caption='Code', field_type='Code', visible=True,
                editable=True, primary_key=False, tab_index=1, required=True,
                freeze_column=True,
                has_table_relation=True, related_table='UnitOfMeasure',
                related_field='code', related_display_field='description',
            ),
            dict(
                name='quantity_per_unit', caption='Qty. per Unit of Measure',
                field_type='Integer', visible=True, editable=True,
                primary_key=False, tab_index=2, required=True,
            ),
            dict(
                name='default', caption='Default', field_type='Boolean',
                visible=True, editable=True, primary_key=False, tab_index=3,
            ),
            dict(
                name='price', caption='Unit Price', field_type='Decimal',
                visible=True, editable=True, primary_key=False, tab_index=4,
            ),
        ],
    )
    uom_list.editable = True
    uom_list.insert_allowed = True
    uom_list.delete_allowed = True
    uom_list.modify_allowed = True
    uom_list.save(update_fields=['editable', 'insert_allowed', 'delete_allowed', 'modify_allowed'])
    uom_ctrl = PageControl.objects.get(page=uom_list, name='ItemUnitOfMeasureListControl')
    uom_ctrl.editable = True
    uom_ctrl.save(update_fields=['editable'])
    _seed_ribbon_actions(uom_list, (
        ('ItemUomListNew', 'New', '#new', 'Home', 'Plus'),
        ('ItemUomListDelete', 'Delete', '#delete', 'Home', 'Trash2'),
    ))

    adj_by_item_list = _create_drill_down_list_page(
        name='ItemInventoryAdjustmentByItemList',
        caption='Inventory Adjustments',
        source_table='ItemJournal',
        context_filter_field='item__no',
        card_page=item_journal_card,
        list_filter_field='adjustment_type',
        list_filter_value='operational',
        fields=[
            dict(name='document_no', caption='Document No.', field_type='Code', visible=True,
                 editable=False, primary_key=True, tab_index=0, freeze_column=True),
            dict(name='entry_type', caption='Entry Type', field_type='Enum', visible=True,
                 editable=False, primary_key=False, tab_index=1,
                 enum_values='PositiveAdjustment,NegativeAdjustment'),
            dict(name='quantity', caption='Quantity', field_type='Integer', visible=True,
                 editable=False, primary_key=False, tab_index=2),
            dict(name='unit_amount', caption='Unit Amount', field_type='Decimal', visible=True,
                 editable=False, primary_key=False, tab_index=3),
            dict(name='amount', caption='Amount', field_type='Decimal', visible=True,
                 editable=False, primary_key=False, tab_index=4),
            dict(name='date', caption='Date', field_type='Date', visible=True, editable=False,
                 primary_key=False, tab_index=5),
            dict(name='status', caption='Status', field_type='Enum', visible=True, editable=False,
                 primary_key=False, tab_index=6, enum_values='Open,Posted'),
        ],
    )
    adj_by_item_list.insert_allowed = True
    adj_by_item_list.delete_allowed = True
    adj_by_item_list.modify_allowed = True
    adj_by_item_list.list_exclude_field = 'status'
    adj_by_item_list.list_exclude_values = 'Posted'
    adj_by_item_list.save(update_fields=[
        'insert_allowed', 'delete_allowed', 'modify_allowed',
        'list_exclude_field', 'list_exclude_values',
    ])

    # Prefer OpeningBalanceJournalList (10204) from Item Card — drop unused by-item list.
    Page.objects.filter(name='ItemOpeningBalanceByItemList').delete()

    return uom_list, adj_by_item_list


def _seed_item_card_page_actions(item_card: Page) -> None:
    """BC-style ribbon on Item Card (Item + Prices & Discounts tabs)."""
    actions = (
        ('OpenItemLedgerEntries', 'Item Ledger Entries', 'ItemLedgerEntryList', 'ScrollText', 'Item'),
        ('OpenItemAdjustments', 'Adjustments', 'ItemInventoryAdjustmentByItemList', 'PackagePlus', 'Item'),
        (
            'OpenItemOpeningBalance',
            'Bring in Opening Balance',
            'OpeningBalanceJournalList?mode=new',
            'Scale',
            'Item',
        ),
        ('OpenItemUnitsOfMeasure', 'Units of Measure', 'ItemUnitOfMeasureList', 'Ruler', 'Item'),
        ('OpenSalesPrices', 'Sales Prices', 'ItemUnitOfMeasureList', 'Tag', 'Prices & Discounts'),
        ('OpenPurchasePrices', 'Purchase Prices', 'ItemUnitOfMeasureList', 'ShoppingCart', 'Prices & Discounts'),
    )
    for name, caption, target_page, icon, ribbon_tab in actions:
        _seed_company_page_action(
            item_card,
            name,
            caption,
            target_page,
            icon,
            ribbon_tab=ribbon_tab,
            tooltip=caption,
        )


def _seed_item_list_page_actions(items_page: Page) -> None:
    """BC-style ribbon on Item List: adjust inventory, import, and export."""
    _seed_ribbon_actions(items_page, (
        ('ItemListNew', 'New', '#new', 'Home', 'Plus'),
        ('ItemListDelete', 'Delete', '#delete', 'Home', 'Trash2'),
        (
            'ItemListAdjustInventory',
            'Adjust Inventory',
            'InventoryAdjustmentJournalList',
            'Home',
            'PackagePlus',
        ),
        (
            'ItemListDownloadTemplate',
            'Download Excel Template',
            '#download-item-template',
            'Home',
            'FileSpreadsheet',
        ),
        ('ItemListImport', 'Import', '#import-items', 'Home', 'Upload'),
        ('ItemListExport', 'Export', '#export-items', 'Home', 'Download'),
    ))


def _create_drill_down_list_page(
    *,
    name: str,
    caption: str,
    source_table: str,
    context_filter_field: str,
    fields: list[dict],
    context_key_field: str = 'no',
    card_page: Page | None = None,
    list_filter_field: str = '',
    list_filter_value: str = '',
) -> Page:
    """List page scoped to a parent card field via ctx query param (see cardAction.ts)."""
    defaults = {
        'caption': caption,
        'source_table': source_table,
        'page_type': 'List',
        'editable': False,
        'insert_allowed': False,
        'delete_allowed': False,
        'modify_allowed': False,
        'context_filter_field': context_filter_field,
        'context_key_field': context_key_field,
    }
    if card_page is not None:
        defaults['card_page'] = card_page
    if list_filter_field:
        defaults['list_filter_field'] = list_filter_field
        defaults['list_filter_value'] = list_filter_value

    list_page, _ = Page.objects.update_or_create(name=name, defaults=defaults)
    list_page.context_filter_field = context_filter_field
    list_page.context_key_field = context_key_field
    update_fields = ['context_filter_field', 'context_key_field']
    if card_page is not None:
        list_page.card_page = card_page
        update_fields.append('card_page')
    if list_filter_field:
        list_page.list_filter_field = list_filter_field
        list_page.list_filter_value = list_filter_value
        update_fields.extend(['list_filter_field', 'list_filter_value'])
    list_page.save(update_fields=update_fields)

    control, _ = PageControl.objects.get_or_create(
        page=list_page,
        name=f'{name}Control',
        defaults={
            'control_type': 'Repeater',
            'caption': caption,
            'source_table': source_table,
            'show_caption': True,
            'editable': False,
            'visible': True,
        },
    )
    PageControlField.objects.filter(page=list_page, page_control=control).delete()
    _seed_fields(control, list_page, fields)
    return list_page


def _seed_no_series_pages() -> tuple[Page, Page]:
    """NoSeries List page + Card with Lines subform."""

    # ── Lines subform (ListPart) ─────────────────────────────────────────────
    ns_lines_subform, _ = Page.objects.update_or_create(
        name='NoSeriesLinesSubform',
        defaults={
            'caption': 'Lines',
            'source_table': 'NoSeriesLines',
            'page_type': 'ListPart',
            'editable': True,
            'insert_allowed': True,
            'delete_allowed': True,
            'modify_allowed': True,
        },
    )
    ns_lines_ctrl, _ = PageControl.objects.get_or_create(
        page=ns_lines_subform,
        name='NoSeriesLinesControl',
        defaults={
            'control_type': 'Repeater',
            'caption': 'Lines',
            'source_table': 'NoSeriesLines',
            'show_caption': True,
            'editable': True,
            'visible': True,
        },
    )
    PageControlField.objects.filter(page=ns_lines_subform, page_control=ns_lines_ctrl).delete()
    _seed_fields(ns_lines_ctrl, ns_lines_subform, [
        dict(name='start_number',    caption='Starting No.',    field_type='Code',    visible=True, editable=True,  primary_key=True,  tab_index=0, required=True),
        dict(name='end_number',      caption='Ending No.',      field_type='Code',    visible=True, editable=True,  primary_key=False, tab_index=1),
        dict(name='last_used_number',caption='Last No. Used',   field_type='Code',    visible=True, editable=False, primary_key=False, tab_index=2),
        dict(name='last_used_date',  caption='Last Date Used',  field_type='Date',    visible=True, editable=False, primary_key=False, tab_index=3),
        dict(name='increment_by',    caption='Increment-by No.',field_type='Integer', visible=True, editable=True,  primary_key=False, tab_index=4),
    ])

    # ── Card page ─────────────────────────────────────────────────────────────
    ns_card, _ = Page.objects.update_or_create(
        name='NoSeriesCard',
        defaults={
            'caption': 'No. Series',
            'source_table': 'NoSeries',
            'page_type': 'Card',
            'editable': True,
            'insert_allowed': True,
            'delete_allowed': True,
            'modify_allowed': True,
            'title_field': 'code',
        },
    )
    ns_card_ctrl, _ = PageControl.objects.get_or_create(
        page=ns_card,
        name='NoSeriesCardGroup',
        defaults={
            'control_type': 'Group',
            'caption': 'General',
            'source_table': 'NoSeries',
            'show_caption': False,
            'editable': True,
            'visible': True,
        },
    )
    PageControlField.objects.filter(page=ns_card, page_control=ns_card_ctrl).delete()
    _seed_fields(ns_card_ctrl, ns_card, [
        dict(name='code',        caption='Code',        field_type='Code', visible=True, editable=True, primary_key=True,  tab_index=0, required=True),
        dict(name='description', caption='Description', field_type='Text', visible=True, editable=True, primary_key=False, tab_index=1),
    ])

    # Lines Part — links by no_series__system_id
    ns_lines_part, _ = PageControl.objects.update_or_create(
        page=ns_card,
        name='NoSeriesLinesPart',
        defaults={
            'control_type': 'Part',
            'caption': 'Lines',
            'source_table': 'NoSeriesLines',
            'show_caption': True,
            'editable': True,
            'visible': True,
            'part_page': ns_lines_subform,
            'link_field': 'no_series__system_id',
        },
    )
    ns_lines_part.part_page = ns_lines_subform
    ns_lines_part.link_field = 'no_series__system_id'
    ns_lines_part.save(update_fields=['part_page', 'link_field'])

    # ── List page ─────────────────────────────────────────────────────────────
    ns_list, _ = Page.objects.update_or_create(
        name='NoSeriesList',
        defaults={
            'caption': 'No. Series',
            'source_table': 'NoSeries',
            'page_type': 'List',
            'editable': True,
            'insert_allowed': True,
            'delete_allowed': True,
            'modify_allowed': True,
            'card_page': ns_card,
        },
    )
    ns_list.card_page = ns_card
    ns_list.save(update_fields=['card_page'])

    ns_list_ctrl, _ = PageControl.objects.get_or_create(
        page=ns_list,
        name='NoSeriesListControl',
        defaults={
            'control_type': 'Repeater',
            'caption': 'No. Series',
            'source_table': 'NoSeries',
            'show_caption': True,
            'editable': False,
            'visible': True,
        },
    )
    PageControlField.objects.filter(page=ns_list, page_control=ns_list_ctrl).delete()
    _seed_fields(ns_list_ctrl, ns_list, [
        dict(name='code',           caption='Code',           field_type='Code', visible=True, editable=False, primary_key=True,  tab_index=0),
        dict(name='description',    caption='Description',    field_type='Text', visible=True, editable=False, primary_key=False, tab_index=1),
        dict(name='starting_no',    caption='Starting No.',   field_type='Code', visible=True, editable=False, primary_key=False, tab_index=2),
        dict(name='ending_no',      caption='Ending No.',     field_type='Code', visible=True, editable=False, primary_key=False, tab_index=3),
        dict(name='last_date_used', caption='Last Date Used', field_type='Date', visible=True, editable=False, primary_key=False, tab_index=4),
        dict(name='last_no_used',   caption='Last No. Used',  field_type='Code', visible=True, editable=False, primary_key=False, tab_index=5),
    ])

    # ── No. Series Lines standalone list (drill-down target) ─────────────────
    ns_lines_list, _ = Page.objects.update_or_create(
        name='NoSeriesLinesList',
        defaults={
            'caption': 'No. Series Lines',
            'source_table': 'NoSeriesLines',
            'page_type': 'List',
            'editable': True,
            'insert_allowed': True,
            'delete_allowed': True,
            'modify_allowed': True,
            'context_filter_field': 'no_series__system_id',
            'context_key_field': 'system_id',
        },
    )
    ns_lines_list_ctrl, _ = PageControl.objects.get_or_create(
        page=ns_lines_list,
        name='NoSeriesLinesListControl',
        defaults={
            'control_type': 'Repeater',
            'caption': 'No. Series Lines',
            'source_table': 'NoSeriesLines',
            'show_caption': True,
            'editable': True,
            'visible': True,
        },
    )
    PageControlField.objects.filter(page=ns_lines_list, page_control=ns_lines_list_ctrl).delete()
    _seed_fields(ns_lines_list_ctrl, ns_lines_list, [
        dict(name='start_number',    caption='Starting No.',     field_type='Code',    visible=True, editable=True,  primary_key=True,  tab_index=0, required=True),
        dict(name='end_number',      caption='Ending No.',       field_type='Code',    visible=True, editable=True,  primary_key=False, tab_index=1),
        dict(name='last_used_number',caption='Last No. Used',    field_type='Code',    visible=True, editable=False, primary_key=False, tab_index=2),
        dict(name='last_used_date',  caption='Last Date Used',   field_type='Date',    visible=True, editable=False, primary_key=False, tab_index=3),
        dict(name='increment_by',    caption='Increment-by No.', field_type='Integer', visible=True, editable=True,  primary_key=False, tab_index=4),
    ])

    # Drill-down from Starting No. and Last No. Used columns → NoSeriesLinesList
    _link_drill_down(page_names=('NoSeriesList',), field_name='starting_no',    drill_down_page=ns_lines_list)
    _link_drill_down(page_names=('NoSeriesList',), field_name='last_no_used',   drill_down_page=ns_lines_list)

    return ns_card, ns_list, ns_lines_list


def _ensure_table_relation(
    source_table: str,
    source_field: str,
    related_table: str,
    related_field: str = 'code',
    display_field: str = 'description',
):
    TableRelation.objects.update_or_create(
        source_table=source_table,
        source_field=source_field,
        context_field='',
        context_value='',
        defaults={
            'related_table': related_table,
            'related_field': related_field,
            'display_field': display_field,
        },
    )


def _seed_ribbon_actions(page: Page, actions: tuple) -> None:
    """Seed ribbon actions on a page (e.g. #new, #delete for list-only pages)."""
    for row in actions:
        name, caption, target, ribbon_tab, *rest = row
        image_url = rest[0] if rest else ''
        PageAction.objects.update_or_create(
            page=page,
            name=name,
            defaults={
                'caption': caption,
                'action_type': 'Ribbon',
                'action_relative_url': target,
                'ribbon_tab': ribbon_tab,
                'image_url': image_url,
                'visible': True,
            },
        )


def _seed_inventory_setup_page() -> Page:
    """Card page for InventorySetup (singleton)."""
    page, _ = Page.objects.update_or_create(
        name='InventorySetupCard',
        defaults={
            'caption': 'Inventory Setup',
            'source_table': 'InventorySetup',
            'page_type': 'Card',
            'editable': True,
            'insert_allowed': False,
            'delete_allowed': False,
            'modify_allowed': True,
        },
    )
    ctrl, _ = PageControl.objects.get_or_create(
        page=page,
        name='InventorySetupGroup',
        defaults={
            'control_type': 'Group',
            'caption': 'General',
            'source_table': 'InventorySetup',
            'show_caption': False,
            'editable': True,
            'visible': True,
        },
    )
    PageControlField.objects.filter(page=page, page_control=ctrl).delete()
    _seed_fields(ctrl, page, [
        dict(name='item_no_series', caption="Item No's.", field_type='Code', visible=True, editable=True,
             primary_key=False, tab_index=0,
             has_table_relation=True, related_table='NoSeries', related_field='code', related_display_field='description'),
        dict(name='item_journal_no_series', caption="Item Journal No's.", field_type='Code', visible=True, editable=True,
             primary_key=False, tab_index=1,
             has_table_relation=True, related_table='NoSeries', related_field='code', related_display_field='description'),
        dict(name='show_adjustment_history_before_after', caption='Show Adj. History B/A', field_type='Boolean',
             visible=True, editable=True, primary_key=False, tab_index=2),
    ])
    _ensure_table_relation('InventorySetup', 'item_no_series', 'NoSeries')
    _ensure_table_relation('InventorySetup', 'item_journal_no_series', 'NoSeries')
    return page


def _seed_payment_method_list() -> Page:
    """BC-style list-only Payment Methods page (financials.PaymentMethod)."""
    page, _ = Page.objects.update_or_create(
        name='PaymentMethodList',
        defaults={
            'caption': 'Payment Methods',
            'source_table': 'PaymentMethod',
            'page_type': 'List',
            'editable': True,
            'insert_allowed': True,
            'delete_allowed': True,
            'modify_allowed': True,
            'card_page': None,
        },
    )
    page.card_page = None
    page.editable = True
    page.insert_allowed = True
    page.delete_allowed = True
    page.modify_allowed = True
    page.save(update_fields=['card_page', 'editable', 'insert_allowed', 'delete_allowed', 'modify_allowed'])

    ctrl, _ = PageControl.objects.get_or_create(
        page=page,
        name='PaymentMethodListRepeater',
        defaults={
            'control_type': 'Repeater',
            'caption': 'Payment Methods',
            'source_table': 'PaymentMethod',
            'show_caption': False,
            'editable': True,
            'visible': True,
        },
    )
    ctrl.editable = True
    ctrl.save(update_fields=['editable'])
    PageControlField.objects.filter(page=page, page_control=ctrl).delete()
    _seed_fields(ctrl, page, [
        dict(name='code', caption='Code', field_type='Code',
             visible=True, editable=True, primary_key=True, required=True, tab_index=0, freeze_column=True),
        dict(name='description', caption='Description', field_type='Text',
             visible=True, editable=True, primary_key=False, required=True, tab_index=1),
        dict(name='bal_account_type', caption='Bal. Account Type', field_type='Enum',
             visible=True, editable=True, primary_key=False, tab_index=2,
             enum_values='G/L Account,Bank Account'),
        dict(name='bal_account_no', caption='Bal. Account No.', field_type='Code',
             visible=True, editable=True, primary_key=False, tab_index=3,
             has_table_relation=True, related_table='G_LAccount', related_field='no',
             related_display_field='name', relation_context_field='bal_account_type',
             relation_context_default='G/L Account'),
        dict(name='requires_amount_received', caption='Requires Amount Received', field_type='Boolean',
             visible=True, editable=True, primary_key=False, tab_index=4),
    ])
    TableRelation.objects.filter(source_table='PaymentMethod', source_field='bal_account_no').delete()
    TableRelation.objects.create(
        source_table='PaymentMethod',
        source_field='bal_account_no',
        related_table='G_LAccount',
        related_field='no',
        display_field='name',
        context_field='bal_account_type',
        context_value='G/L Account',
    )
    TableRelation.objects.create(
        source_table='PaymentMethod',
        source_field='bal_account_no',
        related_table='BankAccount',
        related_field='no',
        display_field='name',
        context_field='bal_account_type',
        context_value='Bank Account',
    )
    PageControlField.objects.filter(
        page=page,
        name='bal_bank_account_no',
    ).delete()
    TableRelation.objects.filter(
        source_table='PaymentMethod',
        source_field='bal_bank_account_no',
    ).delete()
    _seed_ribbon_actions(page, (
        ('PaymentMethodListNew', 'New', '#new', 'Home', 'Plus'),
        ('PaymentMethodListDelete', 'Delete', '#delete', 'Home', 'Trash2'),
    ))

    try:
        from financials.management.commands.seed_payment_methods import ensure_default_payment_methods
        ensure_default_payment_methods()
    except Exception:
        pass

    return page


def _seed_unit_of_measure_list() -> Page:
    """BC-style list-only Units of Measure page (inline edit, no card)."""
    page, _ = Page.objects.update_or_create(
        name='UnitOfMeasureList',
        defaults={
            'caption': 'Units of Measure',
            'source_table': 'UnitOfMeasure',
            'page_type': 'List',
            'editable': True,
            'insert_allowed': True,
            'delete_allowed': True,
            'modify_allowed': True,
            'card_page': None,
        },
    )
    page.card_page = None
    page.editable = True
    page.insert_allowed = True
    page.delete_allowed = True
    page.modify_allowed = True
    page.save(update_fields=['card_page', 'editable', 'insert_allowed', 'delete_allowed', 'modify_allowed'])

    ctrl, _ = PageControl.objects.get_or_create(
        page=page,
        name='UnitOfMeasureListRepeater',
        defaults={
            'control_type': 'Repeater',
            'caption': 'Units of Measure',
            'source_table': 'UnitOfMeasure',
            'show_caption': False,
            'editable': True,
            'visible': True,
        },
    )
    ctrl.editable = True
    ctrl.save(update_fields=['editable'])
    PageControlField.objects.filter(page=page, page_control=ctrl).delete()
    _seed_fields(ctrl, page, [
        dict(name='code', caption='Code', field_type='Code',
             visible=True, editable=True, primary_key=True, required=True, tab_index=0, freeze_column=True),
        dict(name='description', caption='Description', field_type='Text',
             visible=True, editable=True, primary_key=False, required=True, tab_index=1),
        dict(name='international_stnd_code', caption='International Standard Code', field_type='Code',
             visible=False, editable=False, primary_key=False, tab_index=2),
    ])
    _seed_ribbon_actions(page, (
        ('UomListNew', 'New', '#new', 'Home', 'Plus'),
        ('UomListDelete', 'Delete', '#delete', 'Home', 'Trash2'),
    ))
    return page


def _seed_inventory_setup_uom_action(inv_setup: Page, uom_list: Page) -> None:
    """Link Units of Measure from Inventory Setup ribbon."""
    PageAction.objects.update_or_create(
        page=inv_setup,
        name='OpenUnitsOfMeasure',
        defaults={
            'caption': 'Units of Measure',
            'action_type': 'Ribbon',
            'action_relative_url': uom_list.name,
            'ribbon_tab': 'Home',
            'image_url': 'Ruler',
            'visible': True,
        },
    )


def _seed_manufacturing_setup_page() -> Page:
    """Card page for ManufacturingSetup (singleton)."""
    page, _ = Page.objects.update_or_create(
        name='ManufacturingSetupCard',
        defaults={
            'caption': 'Manufacturing Setup',
            'source_table': 'ManufacturingSetup',
            'page_type': 'Card',
            'editable': True,
            'insert_allowed': False,
            'delete_allowed': False,
            'modify_allowed': True,
        },
    )
    ctrl, _ = PageControl.objects.get_or_create(
        page=page,
        name='ManufacturingSetupGroup',
        defaults={
            'control_type': 'Group',
            'caption': 'General',
            'source_table': 'ManufacturingSetup',
            'show_caption': False,
            'editable': True,
            'visible': True,
        },
    )
    PageControlField.objects.filter(page=page, page_control=ctrl).delete()
    _seed_fields(ctrl, page, [
        dict(name='manufacturing_enabled', caption='Manufacturing Enabled', field_type='Boolean',
             visible=True, editable=True, primary_key=False, tab_index=0),
        dict(name='bom_no_series', caption="BOM No's.", field_type='Code', visible=True, editable=True,
             primary_key=False, tab_index=1,
             has_table_relation=True, related_table='NoSeries', related_field='code', related_display_field='description'),
        dict(name='production_order_no_series', caption="Prod. Order No's.", field_type='Code', visible=True, editable=True,
             primary_key=False, tab_index=2,
             has_table_relation=True, related_table='NoSeries', related_field='code', related_display_field='description'),
        dict(name='work_center_no_series', caption="Work Center No's.", field_type='Code', visible=True, editable=True,
             primary_key=False, tab_index=3,
             has_table_relation=True, related_table='NoSeries', related_field='code', related_display_field='description'),
        dict(name='machine_center_no_series', caption="Machine Center No's.", field_type='Code', visible=True, editable=True,
             primary_key=False, tab_index=4,
             has_table_relation=True, related_table='NoSeries', related_field='code', related_display_field='description'),
        dict(name='routing_no_series', caption="Routing No's.", field_type='Code', visible=True, editable=True,
             primary_key=False, tab_index=5,
             has_table_relation=True, related_table='NoSeries', related_field='code', related_display_field='description'),
    ])
    for field_name in (
        'bom_no_series',
        'production_order_no_series',
        'work_center_no_series',
        'machine_center_no_series',
        'routing_no_series',
    ):
        _ensure_table_relation('ManufacturingSetup', field_name, 'NoSeries')
    return page


def _seed_general_ledger_setup_page() -> Page:
    """Card page for GeneralLedgerSetup (singleton, BC Table 98 style)."""
    page, _ = Page.objects.update_or_create(
        name='GeneralLedgerSetupCard',
        defaults={
            'caption': 'General Ledger Setup',
            'source_table': 'GeneralLedgerSetup',
            'page_type': 'Card',
            'editable': True,
            'insert_allowed': False,
            'delete_allowed': False,
            'modify_allowed': True,
        },
    )
    dims_ctrl, _ = PageControl.objects.get_or_create(
        page=page,
        name='GeneralLedgerSetupDimensions',
        defaults={
            'control_type': 'Group',
            'caption': 'Dimensions',
            'source_table': 'GeneralLedgerSetup',
            'show_caption': True,
            'editable': True,
            'visible': True,
            'tab_index': 0,
        },
    )
    dims_ctrl.tab_index = 0
    dims_ctrl.save(update_fields=['tab_index'])
    general_ctrl, _ = PageControl.objects.get_or_create(
        page=page,
        name='GeneralLedgerSetupGeneral',
        defaults={
            'control_type': 'Group',
            'caption': 'General',
            'source_table': 'GeneralLedgerSetup',
            'show_caption': True,
            'editable': True,
            'visible': True,
            'tab_index': 1,
        },
    )
    general_ctrl.tab_index = 1
    general_ctrl.save(update_fields=['tab_index'])
    PageControl.objects.filter(page=page, control_type='Group').exclude(
        name__in=('GeneralLedgerSetupDimensions', 'GeneralLedgerSetupGeneral'),
    ).delete()
    PageControlField.objects.filter(page=page).delete()
    _seed_fields(dims_ctrl, page, [
        dict(name='global_dimension_1', caption='Global Dimension 1', field_type='Code', visible=True, editable=True,
             primary_key=False, tab_index=0,
             has_table_relation=True, related_table='Dimension', related_field='code', related_display_field='description'),
        dict(name='global_dimension_2', caption='Global Dimension 2', field_type='Code', visible=True, editable=True,
             primary_key=False, tab_index=1,
             has_table_relation=True, related_table='Dimension', related_field='code', related_display_field='description'),
    ])
    _seed_fields(general_ctrl, page, [
        dict(name='local_currency_code', caption='Local Currency Code', field_type='Code', visible=True, editable=True,
             primary_key=False, tab_index=0),
        dict(name='enable_multiple_branches', caption='Enable Multiple Branches', field_type='Boolean',
             visible=True, editable=True, primary_key=False, tab_index=1),
        dict(name='enable_sales_line_type_selection', caption='Sales Line Type Selection', field_type='Boolean',
             visible=True, editable=True, primary_key=False, tab_index=2),
        dict(name='vat_enabled', caption='VAT Enabled', field_type='Boolean', visible=True, editable=True,
             primary_key=False, tab_index=3),
        dict(name='default_vat_date', caption='Default VAT Date', field_type='Option', visible=True, editable=True,
             primary_key=False, tab_index=4, enum_values='posting_date,document_date'),
    ])
    _ensure_table_relation('GeneralLedgerSetup', 'global_dimension_1', 'Dimension')
    _ensure_table_relation('GeneralLedgerSetup', 'global_dimension_2', 'Dimension')

    _seed_gl_setup_posting_actions(page)
    return page


def _seed_dimension_pages() -> dict:
    """Dimensions list/card + Dimension Values list/card with navigation actions."""

    dim_card, _ = Page.objects.update_or_create(
        name='DimensionCard',
        defaults={
            'caption': 'Dimension',
            'source_table': 'Dimension',
            'page_type': 'Card',
            'editable': True,
            'insert_allowed': True,
            'delete_allowed': True,
            'modify_allowed': True,
            'title_field': 'description',
        },
    )
    dim_card_ctrl, _ = PageControl.objects.get_or_create(
        page=dim_card,
        name='DimensionCardGroup',
        defaults={
            'control_type': 'Group',
            'caption': 'General',
            'source_table': 'Dimension',
            'show_caption': False,
            'editable': True,
            'visible': True,
        },
    )
    PageControlField.objects.filter(page=dim_card, page_control=dim_card_ctrl).delete()
    _seed_fields(dim_card_ctrl, dim_card, [
        dict(name='code', caption='Code', field_type='Code',
             visible=True, editable=True, primary_key=True, tab_index=0),
        dict(name='description', caption='Name', field_type='Text',
             visible=True, editable=True, primary_key=False, tab_index=1),
    ])

    dim_list, _ = Page.objects.update_or_create(
        name='DimensionList',
        defaults={
            'caption': 'Dimensions',
            'source_table': 'Dimension',
            'page_type': 'List',
            'editable': False,
            'insert_allowed': True,
            'delete_allowed': True,
            'modify_allowed': False,
            'card_page': dim_card,
        },
    )
    dim_list.card_page = dim_card
    dim_list.save(update_fields=['card_page'])

    dim_list_ctrl, _ = PageControl.objects.get_or_create(
        page=dim_list,
        name='DimensionListControl',
        defaults={
            'control_type': 'Repeater',
            'caption': 'Dimensions',
            'source_table': 'Dimension',
            'show_caption': False,
            'editable': False,
            'visible': True,
        },
    )
    PageControlField.objects.filter(page=dim_list, page_control=dim_list_ctrl).delete()
    _seed_fields(dim_list_ctrl, dim_list, [
        dict(name='code', caption='Code', field_type='Code',
             visible=True, editable=False, primary_key=True, tab_index=0, freeze_column=True),
        dict(name='description', caption='Name', field_type='Text',
             visible=True, editable=False, primary_key=False, tab_index=1),
    ])

    dv_card, _ = Page.objects.update_or_create(
        name='DimensionValueCard',
        defaults={
            'caption': 'Dimension Value',
            'source_table': 'DimensionValue',
            'page_type': 'Card',
            'editable': True,
            'insert_allowed': True,
            'delete_allowed': True,
            'modify_allowed': True,
            'title_field': 'description',
        },
    )
    dv_card_ctrl, _ = PageControl.objects.get_or_create(
        page=dv_card,
        name='DimensionValueCardGroup',
        defaults={
            'control_type': 'Group',
            'caption': 'General',
            'source_table': 'DimensionValue',
            'show_caption': False,
            'editable': True,
            'visible': True,
        },
    )
    PageControlField.objects.filter(page=dv_card, page_control=dv_card_ctrl).delete()
    _seed_fields(dv_card_ctrl, dv_card, [
        dict(name='dimension_code', caption='Dimension Code', field_type='Code',
             visible=True, editable=True, primary_key=False, tab_index=0,
             has_table_relation=True, related_table='Dimension',
             related_field='code', related_display_field='description'),
        dict(name='code', caption='Code', field_type='Code',
             visible=True, editable=True, primary_key=True, tab_index=1),
        dict(name='description', caption='Name', field_type='Text',
             visible=True, editable=True, primary_key=False, tab_index=2),
        dict(name='dimension_type', caption='Dimension Value Type', field_type='Enum',
             visible=True, editable=True, primary_key=False, tab_index=3,
             enum_values='Standard,Custom'),
    ])
    _ensure_table_relation('DimensionValue', 'dimension_code', 'Dimension', 'code', 'description')

    dv_list, _ = Page.objects.update_or_create(
        name='DimensionValueList',
        defaults={
            'caption': 'Dimension Values',
            'source_table': 'DimensionValue',
            'page_type': 'List',
            'editable': False,
            'insert_allowed': True,
            'delete_allowed': True,
            'modify_allowed': False,
            'card_page': dv_card,
            'context_filter_field': 'dimension_code__code',
            'context_key_field': 'code',
        },
    )
    dv_list.card_page = dv_card
    dv_list.context_filter_field = 'dimension_code__code'
    dv_list.context_key_field = 'code'
    dv_list.save(update_fields=['card_page', 'context_filter_field', 'context_key_field'])

    dv_list_ctrl, _ = PageControl.objects.get_or_create(
        page=dv_list,
        name='DimensionValueListControl',
        defaults={
            'control_type': 'Repeater',
            'caption': 'Dimension Values',
            'source_table': 'DimensionValue',
            'show_caption': False,
            'editable': False,
            'visible': True,
        },
    )
    PageControlField.objects.filter(page=dv_list, page_control=dv_list_ctrl).delete()
    _seed_fields(dv_list_ctrl, dv_list, [
        dict(name='code', caption='Code', field_type='Code',
             visible=True, editable=False, primary_key=True, tab_index=0, freeze_column=True),
        dict(name='description', caption='Name', field_type='Text',
             visible=True, editable=False, primary_key=False, tab_index=1),
        dict(name='dimension_type', caption='Dimension Value Type', field_type='Enum',
             visible=True, editable=False, primary_key=False, tab_index=2,
             enum_values='Standard,Custom'),
    ])

    for page, name, caption in (
        (dim_card, 'OpenDimensionValues', 'Dimension Values'),
        (dim_list, 'OpenDimensionValues', 'Dimension Values'),
    ):
        PageAction.objects.update_or_create(
            page=page,
            name=name,
            defaults={
                'caption': caption,
                'requires_confirmation': False,
                'confirmation_message': '',
                'tooltip': caption,
                'action_relative_url': 'DimensionValueList',
                'visible': True,
                'ribbon_tab': 'Home',
                'image_url': 'ListTree',
            },
        )

    return {
        'dimension_list_id': dim_list.page_id,
        'dimension_card_id': dim_card.page_id,
        'dimension_value_list_id': dv_list.page_id,
        'dimension_value_card_id': dv_card.page_id,
    }


def _financial_report_row_line_field_defs(*, worksheet: bool = False) -> list[dict]:
    """BC Row Definition line columns (page 104 / Account Schedule style)."""
    freeze = worksheet
    return [
        dict(name='row_no', caption='Row No.', field_type='Code',
             visible=True, editable=True, primary_key=False, tab_index=0,
             freeze_column=freeze, required=False),
        dict(name='description', caption='Description', field_type='Text',
             visible=True, editable=True, primary_key=False, tab_index=1,
             freeze_column=freeze),
        dict(name='totaling_type', caption='Totaling Type', field_type='Enum',
             visible=True, editable=True, primary_key=False, tab_index=2,
             enum_values=(
                 'Posting Accounts,Total Accounts,Formula,Set Base For Percent,'
                 'Cash Flow Accounts,Cost Type,Cost Object'
             )),
        dict(name='totaling', caption='Totaling', field_type='Text',
             visible=True, editable=True, primary_key=False, tab_index=3),
        dict(name='row_amount_basis', caption='Row Type', field_type='Enum',
             visible=True, editable=True, primary_key=False, tab_index=4,
             enum_values='Net Change,Balance at Date,Beginning Balance'),
        dict(name='amount_type', caption='Amount Type', field_type='Enum',
             visible=True, editable=True, primary_key=False, tab_index=5,
             enum_values='Net Amount,Debits,Credits,Debits Minus Credits,Credits Minus Debits'),
        dict(name='show_opposite_sign', caption='Show Opposite Sign', field_type='Boolean',
             visible=True, editable=True, primary_key=False, tab_index=6),
        dict(name='show', caption='Show', field_type='Enum',
             visible=True, editable=True, primary_key=False, tab_index=7,
             enum_values='Yes,No,If Amount Not Zero,If Any Column Not Zero,When Positive Balance,When Negative Balance'),
        dict(name='bold', caption='Bold', field_type='Boolean',
             visible=True, editable=True, primary_key=False, tab_index=8),
        dict(name='italic', caption='Italic', field_type='Boolean',
             visible=True, editable=True, primary_key=False, tab_index=9),
        dict(name='underline', caption='Underline', field_type='Boolean',
             visible=True, editable=True, primary_key=False, tab_index=10),
        dict(name='new_page', caption='New Page', field_type='Boolean',
             visible=True, editable=True, primary_key=False, tab_index=11),
        dict(name='line_no', caption='Line No.', field_type='Integer',
             visible=False, editable=False, primary_key=False, tab_index=12, required=True),
        dict(name='row_type', caption='Line Type', field_type='Enum',
             visible=False, editable=False, primary_key=False, tab_index=13,
             enum_values='Header,Posting,Total,Begin-Total,End-Total'),
        dict(name='indentation', caption='Indentation', field_type='Integer',
             visible=False, editable=True, primary_key=False, tab_index=14),
    ]


def _seed_financial_report_pages() -> dict:
    """Financial Reports (BC 108/490) + row/column definition pages."""

    row_lines_subform, _ = Page.objects.update_or_create(
        name='FinancialReportRowLineSubform',
        defaults={
            'caption': 'Lines',
            'source_table': 'FinancialReportRowLine',
            'page_type': 'ListPart',
            'editable': True,
            'insert_allowed': True,
            'delete_allowed': True,
            'modify_allowed': True,
        },
    )
    row_lines_ctrl, _ = PageControl.objects.get_or_create(
        page=row_lines_subform,
        name='FinancialReportRowLineSubformControl',
        defaults={
            'control_type': 'Repeater',
            'caption': 'Lines',
            'source_table': 'FinancialReportRowLine',
            'show_caption': True,
            'editable': True,
            'visible': True,
        },
    )
    PageControlField.objects.filter(page=row_lines_subform, page_control=row_lines_ctrl).delete()
    _seed_fields(row_lines_ctrl, row_lines_subform, _financial_report_row_line_field_defs())

    row_group_card, _ = Page.objects.update_or_create(
        name='FinancialReportRowGroupCard',
        defaults={
            'caption': 'Financial Report Row Definition',
            'source_table': 'FinancialReportRowGroup',
            'page_type': 'Card',
            'editable': True,
            'insert_allowed': True,
            'delete_allowed': True,
            'modify_allowed': True,
            'title_field': 'description',
        },
    )
    row_group_card_ctrl, _ = PageControl.objects.get_or_create(
        page=row_group_card,
        name='FinancialReportRowGroupCardGroup',
        defaults={
            'control_type': 'Group',
            'caption': 'General',
            'source_table': 'FinancialReportRowGroup',
            'show_caption': False,
            'editable': True,
            'visible': True,
        },
    )
    PageControlField.objects.filter(page=row_group_card, page_control=row_group_card_ctrl).delete()
    _seed_fields(row_group_card_ctrl, row_group_card, [
        dict(name='name', caption='Name', field_type='Code',
             visible=True, editable=True, primary_key=True, tab_index=0, required=True),
        dict(name='description', caption='Description', field_type='Text',
             visible=True, editable=True, primary_key=False, tab_index=1),
    ])
    row_lines_part, _ = PageControl.objects.update_or_create(
        page=row_group_card,
        name='FinancialReportRowLinesPart',
        defaults={
            'control_type': 'Part',
            'caption': 'Lines',
            'source_table': 'FinancialReportRowLine',
            'show_caption': True,
            'editable': True,
            'visible': True,
            'part_page': row_lines_subform,
            'link_field': 'row_group__system_id',
        },
    )
    row_lines_part.part_page = row_lines_subform
    row_lines_part.link_field = 'row_group__system_id'
    row_lines_part.save(update_fields=['part_page', 'link_field'])

    row_group_list, _ = Page.objects.update_or_create(
        name='FinancialReportRowGroupList',
        defaults={
            'caption': 'Financial Report Row Definitions',
            'source_table': 'FinancialReportRowGroup',
            'page_type': 'List',
            'editable': False,
            'insert_allowed': True,
            'delete_allowed': True,
            'modify_allowed': False,
            'card_page': row_group_card,
        },
    )
    row_group_list.card_page = row_group_card
    row_group_list.save(update_fields=['card_page'])
    row_group_list_ctrl, _ = PageControl.objects.get_or_create(
        page=row_group_list,
        name='FinancialReportRowGroupListControl',
        defaults={
            'control_type': 'Repeater',
            'caption': 'Financial Report Row Definitions',
            'source_table': 'FinancialReportRowGroup',
            'show_caption': False,
            'editable': False,
            'visible': True,
        },
    )
    PageControlField.objects.filter(page=row_group_list, page_control=row_group_list_ctrl).delete()
    _seed_fields(row_group_list_ctrl, row_group_list, [
        dict(name='name', caption='Name', field_type='Code',
             visible=True, editable=False, primary_key=True, tab_index=0, freeze_column=True),
        dict(name='description', caption='Description', field_type='Text',
             visible=True, editable=False, primary_key=False, tab_index=1),
    ])

    row_definition_ws, _ = Page.objects.update_or_create(
        name='FinancialReportRowDefinition',
        defaults={
            'caption': 'Row Definition',
            'source_table': 'FinancialReportRowLine',
            'page_type': 'Worksheet',
            'editable': True,
            'insert_allowed': True,
            'delete_allowed': True,
            'modify_allowed': True,
            'context_filter_field': 'row_group__name',
            'context_key_field': 'name',
            'header_page': row_group_card,
            'title_field': 'description',
        },
    )
    row_definition_ws.header_page = row_group_card
    row_definition_ws.context_filter_field = 'row_group__name'
    row_definition_ws.context_key_field = 'name'
    row_definition_ws.insert_allowed = True
    row_definition_ws.delete_allowed = True
    row_definition_ws.modify_allowed = True
    row_definition_ws.editable = True
    row_definition_ws.save(update_fields=[
        'header_page', 'context_filter_field', 'context_key_field',
        'insert_allowed', 'delete_allowed', 'modify_allowed', 'editable',
    ])

    row_definition_ctrl, _ = PageControl.objects.get_or_create(
        page=row_definition_ws,
        name='FinancialReportRowDefinitionLines',
        defaults={
            'control_type': 'Repeater',
            'caption': 'Lines',
            'source_table': 'FinancialReportRowLine',
            'show_caption': False,
            'editable': True,
            'visible': True,
        },
    )
    row_definition_ctrl.editable = True
    row_definition_ctrl.save(update_fields=['editable'])
    PageControlField.objects.filter(page=row_definition_ws, page_control=row_definition_ctrl).delete()
    _seed_fields(row_definition_ctrl, row_definition_ws, _financial_report_row_line_field_defs(worksheet=True))

    _seed_ribbon_actions(row_group_card, (
        ('OpenRowDefinitionWorksheet', 'Row Definition', 'FinancialReportRowDefinition', 'Home', 'ListTree'),
    ))

    _seed_ribbon_actions(row_definition_ws, (
        ('RowDefinitionOutdent', 'Outdent', '#stub', 'Home', 'ChevronLeft'),
        ('RowDefinitionIndent', 'Indent', '#stub', 'Home', 'ChevronRight'),
    ))

    _link_drill_down(
        page_names=('FinancialReportRowGroupList', 'FinancialReportRowGroupCard'),
        field_name='name',
        drill_down_page=row_definition_ws,
    )

    col_lines_subform, _ = Page.objects.update_or_create(
        name='FinancialReportColumnLineSubform',
        defaults={
            'caption': 'Columns',
            'source_table': 'FinancialReportColumnLine',
            'page_type': 'ListPart',
            'editable': True,
            'insert_allowed': True,
            'delete_allowed': True,
            'modify_allowed': True,
        },
    )
    col_lines_ctrl, _ = PageControl.objects.get_or_create(
        page=col_lines_subform,
        name='FinancialReportColumnLineSubformControl',
        defaults={
            'control_type': 'Repeater',
            'caption': 'Columns',
            'source_table': 'FinancialReportColumnLine',
            'show_caption': True,
            'editable': True,
            'visible': True,
        },
    )
    PageControlField.objects.filter(page=col_lines_subform, page_control=col_lines_ctrl).delete()
    _seed_fields(col_lines_ctrl, col_lines_subform, [
        dict(name='line_no', caption='Line No.', field_type='Integer',
             visible=True, editable=True, primary_key=False, tab_index=0, required=True),
        dict(name='column_no', caption='Column No.', field_type='Code',
             visible=True, editable=True, primary_key=False, tab_index=1),
        dict(name='column_header', caption='Column Header', field_type='Text',
             visible=True, editable=True, primary_key=False, tab_index=2),
        dict(name='column_type', caption='Column Type', field_type='Enum',
             visible=True, editable=True, primary_key=False, tab_index=3,
             enum_values='Net Change,Balance at Date,Beginning Balance'),
        dict(name='comparison_period_formula', caption='Period Formula', field_type='Text',
             visible=True, editable=True, primary_key=False, tab_index=4),
        dict(name='amount_type', caption='Amount Type', field_type='Enum',
             visible=True, editable=True, primary_key=False, tab_index=5,
             enum_values='Net Amount,Debits,Credits,Debits Minus Credits,Credits Minus Debits'),
        dict(name='formula', caption='Formula', field_type='Text',
             visible=True, editable=True, primary_key=False, tab_index=6),
        dict(name='show_opposite_sign', caption='Show Opposite Sign', field_type='Boolean',
             visible=True, editable=True, primary_key=False, tab_index=7),
    ])

    col_group_card, _ = Page.objects.update_or_create(
        name='FinancialReportColumnGroupCard',
        defaults={
            'caption': 'Financial Report Column Definition',
            'source_table': 'FinancialReportColumnGroup',
            'page_type': 'Card',
            'editable': True,
            'insert_allowed': True,
            'delete_allowed': True,
            'modify_allowed': True,
            'title_field': 'description',
        },
    )
    col_group_card_ctrl, _ = PageControl.objects.get_or_create(
        page=col_group_card,
        name='FinancialReportColumnGroupCardGroup',
        defaults={
            'control_type': 'Group',
            'caption': 'General',
            'source_table': 'FinancialReportColumnGroup',
            'show_caption': False,
            'editable': True,
            'visible': True,
        },
    )
    PageControlField.objects.filter(page=col_group_card, page_control=col_group_card_ctrl).delete()
    _seed_fields(col_group_card_ctrl, col_group_card, [
        dict(name='name', caption='Name', field_type='Code',
             visible=True, editable=True, primary_key=True, tab_index=0, required=True),
        dict(name='description', caption='Description', field_type='Text',
             visible=True, editable=True, primary_key=False, tab_index=1),
    ])
    col_lines_part, _ = PageControl.objects.update_or_create(
        page=col_group_card,
        name='FinancialReportColumnLinesPart',
        defaults={
            'control_type': 'Part',
            'caption': 'Columns',
            'source_table': 'FinancialReportColumnLine',
            'show_caption': True,
            'editable': True,
            'visible': True,
            'part_page': col_lines_subform,
            'link_field': 'column_group__system_id',
        },
    )
    col_lines_part.part_page = col_lines_subform
    col_lines_part.link_field = 'column_group__system_id'
    col_lines_part.save(update_fields=['part_page', 'link_field'])

    col_group_list, _ = Page.objects.update_or_create(
        name='FinancialReportColumnGroupList',
        defaults={
            'caption': 'Financial Report Column Definitions',
            'source_table': 'FinancialReportColumnGroup',
            'page_type': 'List',
            'editable': False,
            'insert_allowed': True,
            'delete_allowed': True,
            'modify_allowed': False,
            'card_page': col_group_card,
        },
    )
    col_group_list.card_page = col_group_card
    col_group_list.save(update_fields=['card_page'])
    col_group_list_ctrl, _ = PageControl.objects.get_or_create(
        page=col_group_list,
        name='FinancialReportColumnGroupListControl',
        defaults={
            'control_type': 'Repeater',
            'caption': 'Financial Report Column Definitions',
            'source_table': 'FinancialReportColumnGroup',
            'show_caption': False,
            'editable': False,
            'visible': True,
        },
    )
    PageControlField.objects.filter(page=col_group_list, page_control=col_group_list_ctrl).delete()
    _seed_fields(col_group_list_ctrl, col_group_list, [
        dict(name='name', caption='Name', field_type='Code',
             visible=True, editable=False, primary_key=True, tab_index=0, freeze_column=True),
        dict(name='description', caption='Description', field_type='Text',
             visible=True, editable=False, primary_key=False, tab_index=1),
    ])

    fr_card, _ = Page.objects.update_or_create(
        name='FinancialReportCard',
        defaults={
            'caption': 'Financial Report',
            'source_table': 'FinancialReport',
            'page_type': 'Card',
            'editable': True,
            'insert_allowed': True,
            'delete_allowed': True,
            'modify_allowed': True,
            'title_field': 'description',
        },
    )
    fr_card_ctrl, _ = PageControl.objects.get_or_create(
        page=fr_card,
        name='FinancialReportCardGroup',
        defaults={
            'control_type': 'Group',
            'caption': 'General',
            'source_table': 'FinancialReport',
            'show_caption': False,
            'editable': True,
            'visible': True,
        },
    )
    PageControlField.objects.filter(page=fr_card, page_control=fr_card_ctrl).delete()
    _seed_fields(fr_card_ctrl, fr_card, [
        dict(name='name', caption='Name', field_type='Code',
             visible=True, editable=True, primary_key=True, tab_index=0, required=True),
        dict(name='description', caption='Description', field_type='Text',
             visible=True, editable=True, primary_key=False, tab_index=1),
        dict(name='row_definition', caption='Row Definition', field_type='Code',
             visible=True, editable=True, primary_key=False, tab_index=2, required=True,
             has_table_relation=True, related_table='FinancialReportRowGroup',
             related_field='name', related_display_field='description'),
        dict(name='column_definition', caption='Column Definition', field_type='Code',
             visible=True, editable=True, primary_key=False, tab_index=3, required=True,
             has_table_relation=True, related_table='FinancialReportColumnGroup',
             related_field='name', related_display_field='description'),
        dict(name='period_type', caption='Period Type', field_type='Enum',
             visible=True, editable=True, primary_key=False, tab_index=4,
             enum_values='Day,Week,Month,Quarter,Year,Accounting Period'),
        dict(name='start_date', caption='Start Date', field_type='Date',
             visible=False, editable=True, primary_key=False, tab_index=8),
        dict(name='end_date', caption='End Date', field_type='Date',
             visible=False, editable=True, primary_key=False, tab_index=9),
        dict(name='show_all_lines', caption='Show All Lines', field_type='Boolean',
             visible=True, editable=True, primary_key=False, tab_index=5),
        dict(name='use_amounts_in_add_currency', caption='Use Amounts in Add. Reporting Currency',
             field_type='Boolean', visible=True, editable=True, primary_key=False, tab_index=6),
        dict(name='dimension_1_filter', caption='Dimension 1 Filter', field_type='Text',
             visible=True, editable=True, primary_key=False, tab_index=7),
    ])
    _ensure_table_relation('FinancialReport', 'row_definition', 'FinancialReportRowGroup', 'name', 'description')
    _ensure_table_relation('FinancialReport', 'column_definition', 'FinancialReportColumnGroup', 'name', 'description')

    fr_list, _ = Page.objects.update_or_create(
        name='FinancialReportList',
        defaults={
            'caption': 'Financial Reports',
            'source_table': 'FinancialReport',
            'page_type': 'List',
            'editable': True,
            'insert_allowed': True,
            'delete_allowed': True,
            'modify_allowed': True,
            'card_page': fr_card,
        },
    )
    fr_list.card_page = fr_card
    fr_list.editable = True
    fr_list.modify_allowed = True
    fr_list.insert_allowed = True
    fr_list.delete_allowed = True
    fr_list.save(update_fields=['card_page', 'editable', 'modify_allowed', 'insert_allowed', 'delete_allowed'])
    fr_list_ctrl, _ = PageControl.objects.get_or_create(
        page=fr_list,
        name='FinancialReportListControl',
        defaults={
            'control_type': 'Repeater',
            'caption': 'Financial Reports',
            'source_table': 'FinancialReport',
            'show_caption': False,
            'editable': True,
            'visible': True,
        },
    )
    fr_list_ctrl.editable = True
    fr_list_ctrl.save(update_fields=['editable'])
    PageControlField.objects.filter(page=fr_list, page_control=fr_list_ctrl).delete()
    _seed_fields(fr_list_ctrl, fr_list, [
        dict(name='name', caption='Name', field_type='Code',
             visible=True, editable=True, primary_key=True, tab_index=0, freeze_column=True, required=True),
        dict(name='description', caption='Description', field_type='Text',
             visible=True, editable=True, primary_key=False, tab_index=1),
        dict(name='row_definition', caption='Row Definition', field_type='Code',
             visible=True, editable=True, primary_key=False, tab_index=2, required=False,
             has_table_relation=True, related_table='FinancialReportRowGroup',
             related_field='name', related_display_field='description'),
        dict(name='column_definition', caption='Column Definition', field_type='Code',
             visible=True, editable=True, primary_key=False, tab_index=3, required=False,
             has_table_relation=True, related_table='FinancialReportColumnGroup',
             related_field='name', related_display_field='description'),
        dict(name='start_date', caption='Start Date', field_type='Date',
             visible=False, editable=True, primary_key=False, tab_index=4),
        dict(name='end_date', caption='End Date', field_type='Date',
             visible=False, editable=True, primary_key=False, tab_index=5),
    ])

    _seed_ribbon_actions(fr_list, (
        ('FinancialReportListNew', 'New', '#new', 'Home', 'Plus'),
        ('FinancialReportListDelete', 'Delete', '#delete', 'Home', 'Trash2'),
    ))
    PageAction.objects.update_or_create(
        page=fr_list,
        name='RunFinancialReport',
        defaults={
            'caption': 'Run Report',
            'requires_confirmation': False,
            'confirmation_message': '',
            'tooltip': 'Open the financial report overview',
            'action_relative_url': 'FinancialReportOverview',
            'visible': True,
            'ribbon_tab': 'Home',
            'image_url': 'FileChart',
        },
    )
    PageAction.objects.update_or_create(
        page=fr_list,
        name='recalculate_financial_report',
        defaults={
            'caption': 'Recalculate',
            'requires_confirmation': False,
            'confirmation_message': '',
            'tooltip': 'Recalculate report amounts from the general ledger',
            'visible': True,
            'ribbon_tab': 'Home',
            'image_url': 'RefreshCw',
        },
    )
    PageAction.objects.update_or_create(
        page=fr_list,
        name='print_financial_report',
        defaults={
            'caption': 'Print',
            'requires_confirmation': False,
            'confirmation_message': '',
            'tooltip': 'Export the selected financial report to PDF or Excel',
            'visible': True,
            'ribbon_tab': 'Home',
            'image_url': 'Printer',
        },
    )
    PageAction.objects.filter(page=fr_list, name='EditFinancialReport').delete()

    fr_overview, _ = Page.objects.update_or_create(
        name='FinancialReportOverview',
        defaults={
            'caption': 'Financial Report',
            'source_table': 'FinancialReportRowLine',
            'page_type': 'Worksheet',
            'editable': False,
            'insert_allowed': False,
            'delete_allowed': False,
            'modify_allowed': True,
            'context_filter_field': 'row_group',
            'context_key_field': 'name',
            'header_page': fr_card,
            'title_field': 'description',
        },
    )
    fr_overview.header_page = fr_card
    fr_overview.context_filter_field = 'row_group'
    fr_overview.context_key_field = 'name'
    fr_overview.save(update_fields=['header_page', 'context_filter_field', 'context_key_field'])

    fr_overview_ctrl, _ = PageControl.objects.get_or_create(
        page=fr_overview,
        name='FinancialReportOverviewLines',
        defaults={
            'control_type': 'Repeater',
            'caption': 'Lines',
            'source_table': 'FinancialReportRowLine',
            'show_caption': False,
            'editable': False,
            'visible': True,
        },
    )
    PageControlField.objects.filter(page=fr_overview, page_control=fr_overview_ctrl).delete()
    _seed_fields(fr_overview_ctrl, fr_overview, [
        dict(name='line_no', caption='Row No.', field_type='Integer',
             visible=True, editable=False, primary_key=False, tab_index=0, freeze_column=True),
        dict(name='description', caption='Description', field_type='Text',
             visible=True, editable=False, primary_key=False, tab_index=1, freeze_column=True),
        dict(name='row_type', caption='Row Type', field_type='Enum',
             visible=False, editable=False, primary_key=False, tab_index=2,
             enum_values='Header,Posting,Total,Begin-Total,End-Total'),
        dict(name='totaling', caption='Totaling', field_type='Text',
             visible=False, editable=False, primary_key=False, tab_index=3),
    ])

    PageAction.objects.update_or_create(
        page=fr_overview,
        name='recalculate_financial_report',
        defaults={
            'caption': 'Recalculate',
            'requires_confirmation': False,
            'confirmation_message': '',
            'tooltip': 'Recalculate report amounts from the general ledger',
            'visible': True,
            'ribbon_tab': 'Home',
            'image_url': 'RefreshCw',
        },
    )
    PageAction.objects.update_or_create(
        page=fr_overview,
        name='print_financial_report',
        defaults={
            'caption': 'Print',
            'requires_confirmation': False,
            'confirmation_message': '',
            'tooltip': 'Export the financial report to PDF or Excel',
            'visible': True,
            'ribbon_tab': 'Home',
            'image_url': 'Printer',
        },
    )
    PageAction.objects.update_or_create(
        page=fr_overview,
        name='EditFinancialReportFromOverview',
        defaults={
            'caption': 'Edit Financial Report',
            'requires_confirmation': False,
            'confirmation_message': '',
            'tooltip': 'Edit Financial Report',
            'action_relative_url': 'FinancialReportCard',
            'visible': True,
            'ribbon_tab': 'Home',
            'image_url': 'Edit',
        },
    )
    PageAction.objects.filter(
        page=fr_overview,
        name__in=(
            'FinancialReportOverviewRecalculate',
            'FinancialReportOverviewRestoreFilters',
            'FinancialReportOverviewPrint',
        ),
    ).delete()

    _link_drill_down(
        page_names=('FinancialReportList',),
        field_name='name',
        drill_down_page=fr_overview,
    )
    # List Edit List mode must allow typing the report code; drill-down is view-mode only.
    PageControlField.objects.filter(page=fr_list, name='name').update(editable=True)

    _wire_relation_lookup_fields(
        fr_list,
        ('row_definition',),
        part_control_name='FinancialReportListControl',
        lookup_page=row_group_list,
    )
    _wire_relation_lookup_fields(
        fr_list,
        ('column_definition',),
        part_control_name='FinancialReportListControl',
        lookup_page=col_group_list,
    )
    _wire_relation_lookup_fields(
        fr_card,
        ('row_definition',),
        part_control_name='FinancialReportCardGroup',
        lookup_page=row_group_list,
    )
    _wire_relation_lookup_fields(
        fr_card,
        ('column_definition',),
        part_control_name='FinancialReportCardGroup',
        lookup_page=col_group_list,
    )

    for page, name, caption, target in (
        (fr_list, 'EditRowDefinition', 'Edit Row Definition', 'FinancialReportRowGroupList'),
        (fr_list, 'EditColumnDefinition', 'Edit Column Definition', 'FinancialReportColumnGroupList'),
        (fr_card, 'EditRowDefinition', 'Edit Row Definition', 'FinancialReportRowGroupList'),
        (fr_card, 'EditColumnDefinition', 'Edit Column Definition', 'FinancialReportColumnGroupList'),
    ):
        PageAction.objects.update_or_create(
            page=page,
            name=name,
            defaults={
                'caption': caption,
                'requires_confirmation': False,
                'confirmation_message': '',
                'tooltip': caption,
                'action_relative_url': target,
                'visible': True,
                'ribbon_tab': 'Home',
                'image_url': 'ListTree',
            },
        )

    return {
        'financial_report_list_id': fr_list.page_id,
        'financial_report_card_id': fr_card.page_id,
        'financial_report_overview_id': fr_overview.page_id,
        'financial_report_row_group_list_id': row_group_list.page_id,
        'financial_report_row_definition_id': row_definition_ws.page_id,
        'financial_report_column_group_list_id': col_group_list.page_id,
    }


def _seed_gl_setup_posting_actions(gl_setup_card: Page) -> None:
    """Ribbon actions on G/L Setup — Posting tab (BC-style)."""
    actions = (
        ('OpenDimensionsList', 'Dimensions', 'DimensionList', 'Layers'),
        ('OpenGeneralPostingSetup', 'General Posting Setup', 'GeneralPostingSetupList', 'Settings2'),
        ('OpenGenBusinessPostingGroups', 'Gen. Business Posting Groups', 'GeneralBusinessPostingGroupList', 'Building2'),
        ('OpenGenProductPostingGroups', 'Gen. Product Posting Groups', 'GeneralProductPostingGroupList', 'Package'),
    )
    for name, caption, target_page, icon in actions:
        ribbon_tab = 'Home' if name == 'OpenDimensionsList' else 'Posting'
        PageAction.objects.update_or_create(
            page=gl_setup_card,
            name=name,
            defaults={
                'caption': caption,
                'requires_confirmation': False,
                'confirmation_message': '',
                'tooltip': caption,
                'action_relative_url': target_page,
                'visible': True,
                'ribbon_tab': ribbon_tab,
                'image_url': icon,
            },
        )


def _seed_gl_posting_pages() -> dict:
    """List pages for G/L Setup posting actions."""
    gps_list = _seed_general_posting_setup_list()
    gbp_list = _seed_general_business_posting_group_list()
    gpp_list = _seed_general_product_posting_group_list()
    return {
        'general_posting_setup_list_id': gps_list.page_id,
        'gen_business_posting_group_list_id': gbp_list.page_id,
        'gen_product_posting_group_list_id': gpp_list.page_id,
    }


def _seed_general_posting_setup_list() -> Page:
    page, _ = Page.objects.update_or_create(
        name='GeneralPostingSetupList',
        defaults={
            'caption': 'General Posting Setup',
            'source_table': 'GeneralPostingSetup',
            'page_type': 'List',
            'editable': True,
            'insert_allowed': True,
            'delete_allowed': True,
            'modify_allowed': True,
        },
    )
    ctrl, _ = PageControl.objects.get_or_create(
        page=page,
        name='GeneralPostingSetupLines',
        defaults={
            'control_type': 'Repeater',
            'caption': 'General Posting Setup',
            'source_table': 'GeneralPostingSetup',
            'show_caption': False,
            'editable': True,
            'visible': True,
        },
    )
    PageControlField.objects.filter(page=page, page_control=ctrl).delete()
    _seed_fields(ctrl, page, [
        dict(name='general_business_posting_group', caption='Gen. Bus. Posting Group', field_type='Code',
             visible=True, editable=True, primary_key=False, tab_index=0,
             has_table_relation=True, related_table='GeneralBusinessPostingGroup',
             related_field='code', related_display_field='description'),
        dict(name='general_product_posting_group', caption='Gen. Prod. Posting Group', field_type='Code',
             visible=True, editable=True, primary_key=False, tab_index=1,
             has_table_relation=True, related_table='GeneralProductPostingGroup',
             related_field='code', related_display_field='description'),
        dict(name='sales_account', caption='Sales Account', field_type='Code', visible=True, editable=True,
             primary_key=False, tab_index=2,
             has_table_relation=True, related_table='G_LAccount', related_field='no', related_display_field='name'),
        dict(name='purchase_account', caption='Purchase Account', field_type='Code', visible=True, editable=True,
             primary_key=False, tab_index=3,
             has_table_relation=True, related_table='G_LAccount', related_field='no', related_display_field='name'),
        dict(name='cogs_account', caption='COGS Account', field_type='Code', visible=True, editable=True,
             primary_key=False, tab_index=4,
             has_table_relation=True, related_table='G_LAccount', related_field='no', related_display_field='name'),
        dict(name='inventory_adjustment_account', caption='Inventory Adj. Account', field_type='Code',
             visible=True, editable=True, primary_key=False, tab_index=5,
             has_table_relation=True, related_table='G_LAccount', related_field='no', related_display_field='name'),
    ])
    _ensure_table_relation('GeneralPostingSetup', 'general_business_posting_group', 'GeneralBusinessPostingGroup')
    _ensure_table_relation('GeneralPostingSetup', 'general_product_posting_group', 'GeneralProductPostingGroup')
    _ensure_table_relation('GeneralPostingSetup', 'sales_account', 'G_LAccount', 'no', 'name')
    _ensure_table_relation('GeneralPostingSetup', 'purchase_account', 'G_LAccount', 'no', 'name')
    _ensure_table_relation('GeneralPostingSetup', 'cogs_account', 'G_LAccount', 'no', 'name')
    _ensure_table_relation('GeneralPostingSetup', 'inventory_adjustment_account', 'G_LAccount', 'no', 'name')
    return page


def _seed_general_business_posting_group_list() -> Page:
    page, _ = Page.objects.update_or_create(
        name='GeneralBusinessPostingGroupList',
        defaults={
            'caption': 'General Business Posting Groups',
            'source_table': 'GeneralBusinessPostingGroup',
            'page_type': 'List',
            'editable': True,
            'insert_allowed': True,
            'delete_allowed': True,
            'modify_allowed': True,
        },
    )
    ctrl, _ = PageControl.objects.get_or_create(
        page=page,
        name='GeneralBusinessPostingGroupLines',
        defaults={
            'control_type': 'Repeater',
            'caption': 'General Business Posting Groups',
            'source_table': 'GeneralBusinessPostingGroup',
            'show_caption': False,
            'editable': True,
            'visible': True,
        },
    )
    PageControlField.objects.filter(page=page, page_control=ctrl).delete()
    _seed_fields(ctrl, page, [
        dict(name='code', caption='Code', field_type='Code', visible=True, editable=True,
             primary_key=True, tab_index=0, required=True),
        dict(name='description', caption='Description', field_type='Text', visible=True, editable=True,
             primary_key=False, tab_index=1),
        dict(name='default', caption='Default', field_type='Boolean', visible=True, editable=True,
             primary_key=False, tab_index=2),
    ])
    return page


def _seed_general_product_posting_group_list() -> Page:
    page, _ = Page.objects.update_or_create(
        name='GeneralProductPostingGroupList',
        defaults={
            'caption': 'General Product Posting Groups',
            'source_table': 'GeneralProductPostingGroup',
            'page_type': 'List',
            'editable': True,
            'insert_allowed': True,
            'delete_allowed': True,
            'modify_allowed': True,
        },
    )
    ctrl, _ = PageControl.objects.get_or_create(
        page=page,
        name='GeneralProductPostingGroupLines',
        defaults={
            'control_type': 'Repeater',
            'caption': 'General Product Posting Groups',
            'source_table': 'GeneralProductPostingGroup',
            'show_caption': False,
            'editable': True,
            'visible': True,
        },
    )
    PageControlField.objects.filter(page=page, page_control=ctrl).delete()
    _seed_fields(ctrl, page, [
        dict(name='code', caption='Code', field_type='Code', visible=True, editable=True,
             primary_key=True, tab_index=0, required=True),
        dict(name='description', caption='Description', field_type='Text', visible=True, editable=True,
             primary_key=False, tab_index=1),
        dict(name='default', caption='Default', field_type='Boolean', visible=True, editable=True,
             primary_key=False, tab_index=2),
    ])
    return page


def _seed_permission_set_pages() -> Page:
    """Permission Sets list + card with permission lines (Business Central style)."""

    app_objects_list, _ = Page.objects.update_or_create(
        name='ApplicationObjectsList',
        defaults={
            'caption': 'Application Objects',
            'source_table': 'Objects',
            'page_type': 'List',
            'editable': False,
            'insert_allowed': False,
            'delete_allowed': False,
            'modify_allowed': False,
        },
    )
    app_obj_ctrl, _ = PageControl.objects.get_or_create(
        page=app_objects_list,
        name='ApplicationObjectsControl',
        defaults={
            'control_type': 'Repeater',
            'caption': 'Objects',
            'source_table': 'Objects',
            'show_caption': False,
            'editable': False,
            'visible': True,
        },
    )
    PageControlField.objects.filter(
        page=app_objects_list, page_control=app_obj_ctrl,
    ).delete()
    _seed_fields(app_obj_ctrl, app_objects_list, [
        dict(name='object_type', caption='Type', field_type='Text',
             visible=True, editable=False, primary_key=False, tab_index=0),
        dict(name='object_id', caption='Object ID', field_type='Integer',
             visible=True, editable=False, primary_key=True, tab_index=1),
        dict(name='object_name', caption='Name', field_type='Text',
             visible=True, editable=False, primary_key=False, tab_index=2),
        dict(name='object_caption', caption='Caption', field_type='Text',
             visible=True, editable=False, primary_key=False, tab_index=3),
    ])

    ps_lines_subform, _ = Page.objects.update_or_create(
        name='PermissionSetLinesSubform',
        defaults={
            'caption': 'Permissions',
            'source_table': 'PermissionSetLine',
            'page_type': 'ListPart',
            'editable': True,
            'insert_allowed': True,
            'delete_allowed': True,
            'modify_allowed': True,
        },
    )
    ps_lines_ctrl, _ = PageControl.objects.get_or_create(
        page=ps_lines_subform,
        name='PermissionSetLinesControl',
        defaults={
            'control_type': 'Repeater',
            'caption': 'Permissions',
            'source_table': 'PermissionSetLine',
            'show_caption': True,
            'editable': True,
            'visible': True,
        },
    )
    PageControlField.objects.filter(
        page=ps_lines_subform, page_control=ps_lines_ctrl,
    ).delete()
    _seed_fields(ps_lines_ctrl, ps_lines_subform, [
        dict(name='object_type', caption='Type', field_type='Enum',
             visible=True, editable=True, primary_key=False, tab_index=0,
             enum_values='Page,Table'),
        dict(name='object_id', caption='Object ID', field_type='Code',
             visible=True, editable=True, primary_key=False, tab_index=1, required=True,
             has_table_relation=True, related_table='Objects', related_field='object_id',
             related_display_field='object_name',
             relation_context_field='object_type', relation_context_default='Page'),
        dict(name='object_name', caption='Object Name', field_type='Text',
             visible=True, editable=False, primary_key=False, tab_index=2),
        dict(name='read_permission', caption='Read', field_type='Boolean',
             visible=True, editable=True, primary_key=False, tab_index=3),
        dict(name='insert_permission', caption='Insert', field_type='Boolean',
             visible=True, editable=True, primary_key=False, tab_index=4),
        dict(name='modify_permission', caption='Modify', field_type='Boolean',
             visible=True, editable=True, primary_key=False, tab_index=5),
        dict(name='delete_permission', caption='Delete', field_type='Boolean',
             visible=True, editable=True, primary_key=False, tab_index=6),
        dict(name='execute_permission', caption='Execute', field_type='Boolean',
             visible=True, editable=True, primary_key=False, tab_index=7),
    ])
    _wire_permission_object_relations()

    ps_card, _ = Page.objects.update_or_create(
        name='PermissionSetsCard',
        defaults={
            'caption': 'Permission Set',
            'source_table': 'PermissionSet',
            'page_type': 'Card',
            'editable': True,
            'insert_allowed': True,
            'delete_allowed': True,
            'modify_allowed': True,
            'title_field': 'name',
        },
    )
    ps_card_ctrl, _ = PageControl.objects.get_or_create(
        page=ps_card,
        name='PermissionSetsCardGroup',
        defaults={
            'control_type': 'Group',
            'caption': 'General',
            'source_table': 'PermissionSet',
            'show_caption': False,
            'editable': True,
            'visible': True,
        },
    )
    PageControlField.objects.filter(page=ps_card, page_control=ps_card_ctrl).delete()
    _seed_fields(ps_card_ctrl, ps_card, [
        dict(name='code', caption='Permission Set', field_type='Code',
             visible=True, editable=True, primary_key=True, tab_index=0, required=True),
        dict(name='name', caption='Name', field_type='Text',
             visible=True, editable=True, primary_key=False, tab_index=1, required=True),
        dict(name='description', caption='Description', field_type='Text',
             visible=True, editable=True, primary_key=False, tab_index=2),
        dict(name='is_active', caption='Active', field_type='Boolean',
             visible=True, editable=True, primary_key=False, tab_index=3),
    ])

    ps_lines_part, _ = PageControl.objects.update_or_create(
        page=ps_card,
        name='PermissionSetLinesPart',
        defaults={
            'control_type': 'Part',
            'caption': 'Permissions',
            'source_table': 'PermissionSetLine',
            'show_caption': True,
            'editable': True,
            'visible': True,
            'part_page': ps_lines_subform,
            'link_field': 'permissionset_id',
        },
    )
    ps_lines_part.part_page = ps_lines_subform
    ps_lines_part.link_field = 'permissionset_id'
    ps_lines_part.save(update_fields=['part_page', 'link_field'])

    ps_list, _ = Page.objects.update_or_create(
        name='PermissionSetsList',
        defaults={
            'caption': 'Permission Sets',
            'source_table': 'PermissionSet',
            'page_type': 'List',
            'editable': True,
            'insert_allowed': True,
            'delete_allowed': True,
            'modify_allowed': True,
            'card_page': ps_card,
        },
    )
    ps_list.card_page = ps_card
    ps_list.save(update_fields=['card_page'])

    ps_list_ctrl, _ = PageControl.objects.get_or_create(
        page=ps_list,
        name='PermissionSetsListControl',
        defaults={
            'control_type': 'Repeater',
            'caption': 'Permission Sets',
            'source_table': 'PermissionSet',
            'show_caption': True,
            'editable': False,
            'visible': True,
        },
    )
    PageControlField.objects.filter(page=ps_list, page_control=ps_list_ctrl).delete()
    _seed_fields(ps_list_ctrl, ps_list, [
        dict(name='code', caption='Permission Set', field_type='Code',
             visible=True, editable=False, primary_key=True, tab_index=0),
        dict(name='name', caption='Name', field_type='Text',
             visible=True, editable=False, primary_key=False, tab_index=1),
        dict(name='description', caption='Description', field_type='Text',
             visible=True, editable=False, primary_key=False, tab_index=2),
        dict(name='is_active', caption='Active', field_type='Boolean',
             visible=True, editable=False, primary_key=False, tab_index=3),
    ])

    return ps_list


def _seed_user_group_pages() -> Page:
    """User Groups list + card (Business Central style)."""

    ug_card, _ = Page.objects.update_or_create(
        name='UserGroupsCard',
        defaults={
            'caption': 'User Group',
            'source_table': 'UserGroup',
            'page_type': 'Card',
            'editable': True,
            'insert_allowed': True,
            'delete_allowed': True,
            'modify_allowed': True,
            'title_field': 'name',
        },
    )
    ug_card_ctrl, _ = PageControl.objects.get_or_create(
        page=ug_card,
        name='UserGroupsCardGroup',
        defaults={
            'control_type': 'Group',
            'caption': 'General',
            'source_table': 'UserGroup',
            'show_caption': False,
            'editable': True,
            'visible': True,
        },
    )
    PageControlField.objects.filter(page=ug_card, page_control=ug_card_ctrl).delete()
    _seed_fields(ug_card_ctrl, ug_card, [
        dict(name='code', caption='User Group', field_type='Code',
             visible=True, editable=True, primary_key=True, tab_index=0, required=True),
        dict(name='name', caption='Name', field_type='Text',
             visible=True, editable=True, primary_key=False, tab_index=1, required=True),
        dict(name='description', caption='Description', field_type='Text',
             visible=True, editable=True, primary_key=False, tab_index=2),
        dict(name='default_profile', caption='Default Role', field_type='Lookup',
             visible=True, editable=True, primary_key=False, tab_index=3,
             has_table_relation=True, related_table='Role', related_field='system_id',
             related_display_field='name'),
        dict(name='is_active', caption='Active', field_type='Boolean',
             visible=True, editable=True, primary_key=False, tab_index=4),
    ])
    _ensure_table_relation(
        'UserGroup', 'default_profile', 'Role',
        related_field='system_id', display_field='name',
    )

    ug_list, _ = Page.objects.update_or_create(
        name='UserGroupsList',
        defaults={
            'caption': 'User Groups',
            'source_table': 'UserGroup',
            'page_type': 'List',
            'editable': True,
            'insert_allowed': True,
            'delete_allowed': True,
            'modify_allowed': True,
            'card_page': ug_card,
        },
    )
    ug_list.card_page = ug_card
    ug_list.save(update_fields=['card_page'])

    ug_list_ctrl, _ = PageControl.objects.get_or_create(
        page=ug_list,
        name='UserGroupsListControl',
        defaults={
            'control_type': 'Repeater',
            'caption': 'User Groups',
            'source_table': 'UserGroup',
            'show_caption': True,
            'editable': False,
            'visible': True,
        },
    )
    PageControlField.objects.filter(page=ug_list, page_control=ug_list_ctrl).delete()
    _seed_fields(ug_list_ctrl, ug_list, [
        dict(name='code', caption='User Group', field_type='Code',
             visible=True, editable=False, primary_key=True, tab_index=0),
        dict(name='name', caption='Name', field_type='Text',
             visible=True, editable=False, primary_key=False, tab_index=1),
        dict(name='description', caption='Description', field_type='Text',
             visible=True, editable=False, primary_key=False, tab_index=2),
        dict(name='is_active', caption='Active', field_type='Boolean',
             visible=True, editable=False, primary_key=False, tab_index=3),
    ])

    return ug_list


if __name__ == '__main__':
    seed()
