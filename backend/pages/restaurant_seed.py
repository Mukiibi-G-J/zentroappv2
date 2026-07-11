"""
BC-style page engine definitions for the restaurant module.

Seeded from ``pages.seed.seed()`` and ``seed_restaurant_module`` when the
restaurant module is enabled.
"""

from __future__ import annotations

from pages.models import Page, PageControl, PageControlField
from pages.seed import (
    _create_role_centre_shell,
    _ensure_table_relation,
    _seed_cue,
    _seed_fields,
    _seed_rc_nav_actions,
)

_ORDER_STATUS_ENUM = 'new,in_progress,ready,served,completed,cancelled'
_ORDER_TYPE_ENUM = 'dine_in,takeout,delivery'
_ORDER_ITEM_STATUS_ENUM = 'pending,preparing,ready,served,cancelled'
_RESERVATION_STATUS_ENUM = 'pending,confirmed,seated,cancelled,no_show,completed'
_TABLE_STATUS_ENUM = 'available,occupied,reserved,cleaning,maintenance'


def _wire_relation_lookup_footers(
    page: Page,
    field_lookup_pairs: tuple[tuple[str, Page], ...],
) -> None:
    """Enable BC-style dropdown footer (+ New, Select from full list) on relation fields."""
    for field_name, lookup_page in field_lookup_pairs:
        field = PageControlField.objects.filter(page=page, name=field_name).first()
        if not field:
            continue
        field.relation_lookup_footer = True
        field.has_lookup_page = True
        field.lookup_page = lookup_page
        field.save(
            update_fields=[
                'relation_lookup_footer',
                'has_lookup_page',
                'lookup_page',
            ],
        )


def _wire_restaurant_relation_lookup_footers(
    *,
    menu_item_card: Page,
    menu_category_list: Page,
    menu_list: Page,
    table_card: Page,
    floor_list: Page,
    reservation_card: Page,
    table_list: Page,
    order_doc: Page,
) -> None:
    """Wire full-list lookup pages for restaurant card/document relation fields."""
    item_list = Page.objects.filter(name='ItemList').first()
    customer_list = Page.objects.filter(name='CustomerList').first()
    users_list = Page.objects.filter(name='UsersList').first()

    if item_list:
        _wire_relation_lookup_footers(menu_item_card, (('item', item_list),))
    _wire_relation_lookup_footers(
        menu_item_card,
        (
            ('category', menu_category_list),
            ('menu', menu_list),
        ),
    )
    _wire_relation_lookup_footers(table_card, (('floor', floor_list),))
    pairs: list[tuple[str, Page]] = [('table', table_list)]
    if customer_list:
        pairs.append(('customer', customer_list))
    _wire_relation_lookup_footers(reservation_card, tuple(pairs))

    order_pairs: list[tuple[str, Page]] = [('table', table_list)]
    if customer_list:
        order_pairs.append(('customer', customer_list))
    if users_list:
        order_pairs.append(('waiter', users_list))
    _wire_relation_lookup_footers(order_doc, tuple(order_pairs))

def _list_card_pages(
    *,
    list_name: str,
    list_caption: str,
    card_name: str,
    card_caption: str,
    source_table: str,
    title_field: str,
    list_fields: list[dict],
    card_fields: list[dict],
) -> tuple[Page, Page]:
    card, _ = Page.objects.update_or_create(
        name=card_name,
        defaults={
            'caption': card_caption,
            'source_table': source_table,
            'page_type': 'Card',
            'editable': True,
            'insert_allowed': True,
            'delete_allowed': True,
            'modify_allowed': True,
            'title_field': title_field,
        },
    )
    card_ctrl, _ = PageControl.objects.update_or_create(
        page=card,
        name=f'{card_name}Group',
        defaults={
            'control_type': 'Group',
            'caption': 'General',
            'source_table': source_table,
            'show_caption': True,
            'editable': True,
            'visible': True,
        },
    )
    PageControlField.objects.filter(page=card, page_control=card_ctrl).delete()
    _seed_fields(card_ctrl, card, card_fields)

    list_page, _ = Page.objects.update_or_create(
        name=list_name,
        defaults={
            'caption': list_caption,
            'source_table': source_table,
            'page_type': 'List',
            'editable': False,
            'insert_allowed': True,
            'delete_allowed': True,
            'modify_allowed': True,
            'card_page': card,
            'title_field': title_field,
        },
    )
    list_page.card_page = card
    list_page.save(update_fields=['card_page'])

    list_ctrl, _ = PageControl.objects.update_or_create(
        page=list_page,
        name=f'{list_name}Control',
        defaults={
            'control_type': 'Repeater',
            'caption': list_caption,
            'source_table': source_table,
            'show_caption': True,
            'editable': False,
            'visible': True,
        },
    )
    PageControlField.objects.filter(page=list_page, page_control=list_ctrl).delete()
    _seed_fields(list_ctrl, list_page, list_fields)
    return card, list_page


def _seed_restaurant_order_pages() -> tuple[Page, Page]:
    subform, _ = Page.objects.update_or_create(
        name='RestaurantOrderSubform',
        defaults={
            'caption': 'Order Lines',
            'source_table': 'RestaurantOrderItem',
            'page_type': 'ListPart',
            'editable': True,
            'insert_allowed': True,
            'delete_allowed': True,
            'modify_allowed': True,
        },
    )
    sub_ctrl, _ = PageControl.objects.update_or_create(
        page=subform,
        name='RestaurantOrderSubformRepeater',
        defaults={
            'control_type': 'Repeater',
            'caption': 'Lines',
            'source_table': 'RestaurantOrderItem',
            'show_caption': False,
            'editable': True,
            'visible': True,
        },
    )
    _seed_fields(sub_ctrl, subform, [
        dict(name='item', caption='Item', field_type='Code', visible=True, editable=True,
             primary_key=False, tab_index=0,
             has_table_relation=True, related_table='Item', related_field='no',
             related_display_field='item_name'),
        dict(name='quantity', caption='Quantity', field_type='Decimal', visible=True,
             editable=True, primary_key=False, tab_index=1),
        dict(name='unit_price', caption='Unit Price', field_type='Decimal', visible=True,
             editable=True, primary_key=False, tab_index=2),
        dict(name='total_price', caption='Amount', field_type='Decimal', visible=True,
             editable=False, primary_key=False, tab_index=3),
        dict(name='status', caption='Status', field_type='Option', visible=True,
             editable=False, primary_key=False, tab_index=4, enum_values=_ORDER_ITEM_STATUS_ENUM),
        dict(name='special_instructions', caption='Instructions', field_type='Text',
             visible=True, editable=True, primary_key=False, tab_index=5),
    ])
    _ensure_table_relation('RestaurantOrderItem', 'item', 'Item', 'no', 'item_name')

    doc, _ = Page.objects.update_or_create(
        name='RestaurantOrder',
        defaults={
            'caption': 'Restaurant Order',
            'source_table': 'RestaurantOrder',
            'page_type': 'Document',
            'editable': True,
            'insert_allowed': True,
            'delete_allowed': True,
            'modify_allowed': True,
            'title_field': 'no',
        },
    )
    general_ctrl, _ = PageControl.objects.update_or_create(
        page=doc,
        name='RestaurantOrderGeneral',
        defaults={
            'control_type': 'Group',
            'caption': 'General',
            'source_table': 'RestaurantOrder',
            'show_caption': True,
            'editable': True,
            'visible': True,
        },
    )
    _seed_fields(general_ctrl, doc, [
        dict(name='no', caption='No.', field_type='Code', visible=True, editable=False,
             primary_key=True, tab_index=0),
        dict(name='table', caption='Table', field_type='Code', visible=True, editable=True,
             primary_key=False, tab_index=1,
             has_table_relation=True, related_table='Table', related_field='no',
             related_display_field='table_number', relation_lookup_footer=True),
        dict(name='customer', caption='Customer', field_type='Code', visible=True, editable=True,
             primary_key=False, tab_index=2,
             has_table_relation=True, related_table='Customer', related_field='no',
             related_display_field='name', relation_lookup_footer=True),
        dict(name='waiter', caption='Waiter', field_type='Code', visible=True, editable=True,
             primary_key=False, tab_index=3,
             has_table_relation=True, related_table='CustomUser', related_field='email',
             related_display_field='full_name', relation_lookup_footer=True),
        dict(name='order_type', caption='Order Type', field_type='Option', visible=True,
             editable=True, primary_key=False, tab_index=4, enum_values=_ORDER_TYPE_ENUM),
        dict(name='status', caption='Status', field_type='Option', visible=True, editable=False,
             primary_key=False, tab_index=5, enum_values=_ORDER_STATUS_ENUM),
        dict(name='covers', caption='Covers', field_type='Integer', visible=True, editable=True,
             primary_key=False, tab_index=6),
        dict(name='total_amount', caption='Amount', field_type='Decimal', visible=True,
             editable=False, primary_key=False, tab_index=7),
        dict(name='notes', caption='Notes', field_type='Text', visible=True, editable=True,
             primary_key=False, tab_index=8),
    ])
    _ensure_table_relation('RestaurantOrder', 'table', 'Table', 'no', 'table_number')
    _ensure_table_relation('RestaurantOrder', 'customer', 'Customer', 'no', 'name')
    _ensure_table_relation('RestaurantOrder', 'waiter', 'CustomUser', 'email', 'full_name')

    part_ctrl, _ = PageControl.objects.update_or_create(
        page=doc,
        name='RestaurantOrderLines',
        defaults={
            'control_type': 'Part',
            'caption': 'Lines',
            'source_table': 'RestaurantOrderItem',
            'show_caption': True,
            'editable': True,
            'visible': True,
            'part_page': subform,
            'link_field': 'order__system_id',
        },
    )
    part_ctrl.part_page = subform
    part_ctrl.link_field = 'order__system_id'
    part_ctrl.save(update_fields=['part_page', 'link_field'])

    list_page, _ = Page.objects.update_or_create(
        name='RestaurantOrderList',
        defaults={
            'caption': 'Restaurant Orders',
            'source_table': 'RestaurantOrder',
            'page_type': 'List',
            'editable': True,
            'insert_allowed': True,
            'delete_allowed': True,
            'modify_allowed': True,
            'card_page': doc,
            'title_field': 'no',
        },
    )
    list_page.card_page = doc
    list_page.save(update_fields=['card_page'])

    list_ctrl, _ = PageControl.objects.update_or_create(
        page=list_page,
        name='RestaurantOrderListControl',
        defaults={
            'control_type': 'Repeater',
            'caption': 'Restaurant Orders',
            'source_table': 'RestaurantOrder',
            'show_caption': True,
            'editable': False,
            'visible': True,
        },
    )
    _seed_fields(list_ctrl, list_page, [
        dict(name='no', caption='No.', field_type='Code', visible=True, editable=False,
             primary_key=True, tab_index=0),
        dict(name='table', caption='Table', field_type='Code', visible=True, editable=False,
             primary_key=False, tab_index=1),
        dict(name='order_type', caption='Type', field_type='Option', visible=True, editable=False,
             primary_key=False, tab_index=2, enum_values=_ORDER_TYPE_ENUM),
        dict(name='status', caption='Status', field_type='Option', visible=True, editable=False,
             primary_key=False, tab_index=3, enum_values=_ORDER_STATUS_ENUM),
        dict(name='total_amount', caption='Amount', field_type='Decimal', visible=True,
             editable=False, primary_key=False, tab_index=4),
    ])
    return doc, list_page


def _seed_kitchen_display_page() -> Page:
    """Touch-friendly kitchen display (KDS) — replaces generic list for kitchen staff."""
    page, _ = Page.objects.update_or_create(
        name='KitchenDisplay',
        defaults={
            'caption': 'Kitchen Display',
            'source_table': 'RestaurantOrderItem',
            'page_type': 'POS',
            'editable': False,
            'insert_allowed': False,
            'delete_allowed': False,
            'modify_allowed': False,
        },
    )
    return page


def _seed_kitchen_display_list() -> Page:
    """KDS-style list of active order lines (kitchen staff)."""
    page, _ = Page.objects.update_or_create(
        name='KitchenDisplayList',
        defaults={
            'caption': 'Kitchen Display',
            'source_table': 'RestaurantOrderItem',
            'page_type': 'List',
            'editable': True,
            'insert_allowed': False,
            'delete_allowed': False,
            'modify_allowed': True,
            'title_field': 'id',
        },
    )
    ctrl, _ = PageControl.objects.update_or_create(
        page=page,
        name='KitchenDisplayListControl',
        defaults={
            'control_type': 'Repeater',
            'caption': 'Kitchen Queue',
            'source_table': 'RestaurantOrderItem',
            'show_caption': True,
            'editable': True,
            'visible': True,
        },
    )
    _seed_fields(ctrl, page, [
        dict(name='order', caption='Order', field_type='Code', visible=True, editable=False,
             primary_key=False, tab_index=0),
        dict(name='item', caption='Item', field_type='Code', visible=True, editable=False,
             primary_key=False, tab_index=1),
        dict(name='quantity', caption='Qty', field_type='Decimal', visible=True, editable=False,
             primary_key=False, tab_index=2),
        dict(name='status', caption='Status', field_type='Option', visible=True, editable=True,
             primary_key=False, tab_index=3, enum_values=_ORDER_ITEM_STATUS_ENUM),
        dict(name='special_instructions', caption='Instructions', field_type='Text',
             visible=True, editable=False, primary_key=False, tab_index=4),
    ])
    return page


def _seed_menu_builder_page() -> Page:
    """Unified menu builder (catalog, locations, POS tile layout)."""
    page, _ = Page.objects.update_or_create(
        name='MenuBuilder',
        defaults={
            'caption': 'Menu Builder',
            'source_table': 'Menu',
            'page_type': 'POS',
            'editable': True,
            'insert_allowed': True,
            'delete_allowed': True,
            'modify_allowed': True,
        },
    )
    return page


def _seed_restaurant_pos_page() -> Page:
    """Placeholder POS page — links to order list until dedicated restaurant POS UI ships."""
    pos_page, _ = Page.objects.update_or_create(
        name='RestaurantPOS',
        defaults={
            'caption': 'Restaurant POS',
            'source_table': 'RestaurantOrder',
            'page_type': 'POS',
            'editable': True,
            'insert_allowed': True,
            'delete_allowed': False,
            'modify_allowed': False,
        },
    )
    order_list = Page.objects.filter(name='RestaurantOrderList').first()
    if order_list:
        grid_ctrl, _ = PageControl.objects.update_or_create(
            page=pos_page,
            name='RestaurantPOSOrders',
            defaults={
                'control_type': 'Part',
                'caption': 'Orders',
                'source_table': 'RestaurantOrder',
                'show_caption': False,
                'editable': False,
                'visible': True,
                'tab_index': 0,
                'part_page': order_list,
            },
        )
        grid_ctrl.part_page = order_list
        grid_ctrl.save(update_fields=['part_page'])
    return pos_page


def _seed_restaurant_manager_rc(
    *,
    order_list: Page,
    reservation_list: Page,
    table_list: Page,
    menu_list: Page,
    kitchen_list: Page,
) -> Page:
    rc = _create_role_centre_shell('RestaurantManagerRC', 'Restaurant Manager')

    cue_group, _ = PageControl.objects.update_or_create(
        page=rc,
        name='RCRestaurantActivities',
        defaults={
            'control_type': 'CueGroup',
            'caption': 'Restaurant Activities',
            'source_table': '',
            'show_caption': True,
            'editable': False,
            'visible': True,
            'tab_index': 1,
        },
    )
    _seed_cue(
        page=rc, cue_group=cue_group, name='RCCueOpenRestaurantOrders',
        caption='Open Orders', tab_index=0,
        cue_source_table='RestaurantOrder', cue_aggregate='count',
        cue_filter_field='status', cue_filter_value='new',
        cue_style='Unfavorable', drill_down_page=order_list,
        threshold_warning=15, threshold_danger=30,
    )
    _seed_cue(
        page=rc, cue_group=cue_group, name='RCCueInProgressOrders',
        caption='In Progress', tab_index=1,
        cue_source_table='RestaurantOrder', cue_aggregate='count',
        cue_filter_field='status', cue_filter_value='in_progress',
        cue_style='Ambiguous', drill_down_page=order_list,
        threshold_warning=None, threshold_danger=None,
    )
    _seed_cue(
        page=rc, cue_group=cue_group, name='RCCuePendingReservations',
        caption='Pending Reservations', tab_index=2,
        cue_source_table='Reservation', cue_aggregate='count',
        cue_filter_field='status', cue_filter_value='pending',
        cue_style='Subordinate', drill_down_page=reservation_list,
        threshold_warning=10, threshold_danger=20,
    )

    part_ctrl, _ = PageControl.objects.update_or_create(
        page=rc,
        name='RCRecentRestaurantOrders',
        defaults={
            'control_type': 'Part',
            'caption': 'Recent Orders',
            'source_table': '',
            'show_caption': True,
            'editable': False,
            'visible': True,
            'tab_index': 2,
            'part_page': order_list,
            'max_records': 5,
        },
    )
    part_ctrl.part_page = order_list
    part_ctrl.max_records = 5
    part_ctrl.save(update_fields=['part_page', 'max_records'])

    _seed_rc_nav_actions(rc, [
        ('NavRestHome', 'Home', '', 'Home', 'Restaurant'),
        ('NavRestPOS', 'Restaurant POS', 'RestaurantPOS', 'ShoppingCart', 'Restaurant'),
        ('NavRestOrders', 'Orders', 'RestaurantOrderList', 'ClipboardList', 'Restaurant'),
        ('NavRestTables', 'Tables', 'TableList', 'LayoutGrid', 'Restaurant'),
        ('NavRestReservations', 'Reservations', 'ReservationList', 'Calendar', 'Restaurant'),
        ('NavRestMenuBuilder', 'Menu Builder', 'MenuBuilder', 'BookOpen', 'Restaurant'),
        ('NavRestMenus', 'Menus', 'MenuList', 'List', 'Restaurant'),
        ('NavRestMenuItems', 'Menu Items', 'MenuItemList', 'Utensils', 'Restaurant'),
        ('NavRestKitchen', 'Kitchen Display', 'KitchenDisplay', 'ChefHat', 'Restaurant'),
    ])
    return rc


def _seed_restaurant_foh_rc(
    *,
    order_list: Page,
    table_list: Page,
    reservation_list: Page,
    pos_page: Page,
) -> Page:
    rc = _create_role_centre_shell('RestaurantFOHRC', 'Restaurant Front of House')
    _seed_rc_nav_actions(rc, [
        ('NavFOHHome', 'Home', '', 'Home', 'Restaurant'),
        ('NavFOHPOS', 'Restaurant POS', 'RestaurantPOS', 'ShoppingCart', 'Restaurant'),
        ('NavFOHOrders', 'Orders', 'RestaurantOrderList', 'ClipboardList', 'Restaurant'),
        ('NavFOHTables', 'Tables', 'TableList', 'LayoutGrid', 'Restaurant'),
        ('NavFOHReservations', 'Reservations', 'ReservationList', 'Calendar', 'Restaurant'),
    ])
    _ = pos_page, table_list, order_list, reservation_list
    return rc


def _seed_restaurant_kitchen_rc(*, kitchen_list: Page) -> Page:
    rc = _create_role_centre_shell('RestaurantKitchenRC', 'Restaurant Kitchen')
    _seed_rc_nav_actions(rc, [
        ('NavKitchenHome', 'Home', '', 'Home', 'Restaurant'),
        ('NavKitchenDisplay', 'Kitchen Display', 'KitchenDisplay', 'ChefHat', 'Restaurant'),
        ('NavKitchenOrders', 'Orders', 'RestaurantOrderList', 'ClipboardList', 'Restaurant'),
    ])
    _ = kitchen_list
    return rc


def _seed_restaurant_application_profiles(
    *,
    manager_rc: Page,
    foh_rc: Page,
    kitchen_rc: Page,
) -> None:
    from authentication.models import ApplicationProfile

    specs = (
        ('REST-MGR', 'Restaurant Manager', manager_rc),
        ('REST-FOH', 'Restaurant Front of House', foh_rc),
        ('REST-KITCHEN', 'Restaurant Kitchen', kitchen_rc),
    )
    for code, description, rc_page in specs:
        ApplicationProfile.objects.update_or_create(
            code=code,
            defaults={
                'description': description,
                'role_centre_page': rc_page,
            },
        )


def seed_restaurant_pages() -> dict:
    """Seed all restaurant list/card/document pages and role centres."""
    floor_card, floor_list = _list_card_pages(
        list_name='FloorList',
        list_caption='Floors',
        card_name='FloorCard',
        card_caption='Floor',
        source_table='Floor',
        title_field='name',
        list_fields=[
            dict(name='no', caption='No.', field_type='Code', visible=True, editable=False,
                 primary_key=True, tab_index=0),
            dict(name='name', caption='Name', field_type='Text', visible=True, editable=False,
                 primary_key=False, tab_index=1),
            dict(name='display_order', caption='Order', field_type='Integer', visible=True,
                 editable=False, primary_key=False, tab_index=2),
        ],
        card_fields=[
            dict(name='no', caption='No.', field_type='Code', visible=True, editable=False,
                 primary_key=True, tab_index=0),
            dict(name='name', caption='Name', field_type='Text', visible=True, editable=True,
                 primary_key=False, tab_index=1, required=True),
            dict(name='description', caption='Description', field_type='Text', visible=True,
                 editable=True, primary_key=False, tab_index=2),
            dict(name='display_order', caption='Display Order', field_type='Integer',
                 visible=True, editable=True, primary_key=False, tab_index=3),
            dict(name='location', caption='Location', field_type='Code', visible=True,
                 editable=True, primary_key=False, tab_index=4,
                 has_table_relation=True, related_table='Location', related_field='code',
                 related_display_field='description'),
        ],
    )
    _ensure_table_relation('Floor', 'location', 'Location', 'code', 'description')

    table_card, table_list = _list_card_pages(
        list_name='TableList',
        list_caption='Tables',
        card_name='TableCard',
        card_caption='Table',
        source_table='Table',
        title_field='table_number',
        list_fields=[
            dict(name='no', caption='No.', field_type='Code', visible=True, editable=False,
                 primary_key=True, tab_index=0),
            dict(name='table_number', caption='Table No.', field_type='Code', visible=True,
                 editable=False, primary_key=False, tab_index=1),
            dict(name='floor', caption='Floor', field_type='Code', visible=True, editable=False,
                 primary_key=False, tab_index=2),
            dict(name='capacity', caption='Capacity', field_type='Integer', visible=True,
                 editable=False, primary_key=False, tab_index=3),
            dict(name='status', caption='Status', field_type='Option', visible=True,
                 editable=False, primary_key=False, tab_index=4, enum_values=_TABLE_STATUS_ENUM),
        ],
        card_fields=[
            dict(name='no', caption='No.', field_type='Code', visible=True, editable=False,
                 primary_key=True, tab_index=0),
            dict(name='table_number', caption='Table No.', field_type='Code', visible=True,
                 editable=True, primary_key=False, tab_index=1, required=True),
            dict(name='floor', caption='Floor', field_type='Code', visible=True, editable=True,
                 primary_key=False, tab_index=2,
                 has_table_relation=True, related_table='Floor', related_field='no',
                 related_display_field='name', relation_lookup_footer=True),
            dict(name='capacity', caption='Capacity', field_type='Integer', visible=True,
                 editable=True, primary_key=False, tab_index=3),
            dict(name='status', caption='Status', field_type='Option', visible=True,
                 editable=True, primary_key=False, tab_index=4, enum_values=_TABLE_STATUS_ENUM),
            dict(name='notes', caption='Notes', field_type='Text', visible=True, editable=True,
                 primary_key=False, tab_index=5),
        ],
    )
    _ensure_table_relation('Table', 'floor', 'Floor', 'no', 'name')
    _ = floor_card, floor_list

    reservation_card, reservation_list = _list_card_pages(
        list_name='ReservationList',
        list_caption='Reservations',
        card_name='ReservationCard',
        card_caption='Reservation',
        source_table='Reservation',
        title_field='no',
        list_fields=[
            dict(name='no', caption='No.', field_type='Code', visible=True, editable=False,
                 primary_key=True, tab_index=0),
            dict(name='customer', caption='Customer', field_type='Code', visible=True,
                 editable=False, primary_key=False, tab_index=1),
            dict(name='reservation_date', caption='Date', field_type='DateTime', visible=True,
                 editable=False, primary_key=False, tab_index=2),
            dict(name='party_size', caption='Party', field_type='Integer', visible=True,
                 editable=False, primary_key=False, tab_index=3),
            dict(name='status', caption='Status', field_type='Option', visible=True,
                 editable=False, primary_key=False, tab_index=4,
                 enum_values=_RESERVATION_STATUS_ENUM),
        ],
        card_fields=[
            dict(name='no', caption='No.', field_type='Code', visible=True, editable=False,
                 primary_key=True, tab_index=0),
            dict(name='customer', caption='Customer', field_type='Code', visible=True,
                 editable=True, primary_key=False, tab_index=1, required=True,
                 has_table_relation=True, related_table='Customer', related_field='no',
                 related_display_field='name', relation_lookup_footer=True),
            dict(name='table', caption='Table', field_type='Code', visible=True, editable=True,
                 primary_key=False, tab_index=2,
                 has_table_relation=True, related_table='Table', related_field='no',
                 related_display_field='table_number', relation_lookup_footer=True),
            dict(name='reservation_date', caption='Reservation Date', field_type='DateTime',
                 visible=True, editable=True, primary_key=False, tab_index=3, required=True),
            dict(name='party_size', caption='Party Size', field_type='Integer', visible=True,
                 editable=True, primary_key=False, tab_index=4),
            dict(name='status', caption='Status', field_type='Option', visible=True,
                 editable=True, primary_key=False, tab_index=5,
                 enum_values=_RESERVATION_STATUS_ENUM),
            dict(name='special_requests', caption='Special Requests', field_type='Text',
                 visible=True, editable=True, primary_key=False, tab_index=6),
            dict(name='notes', caption='Notes', field_type='Text', visible=True, editable=True,
                 primary_key=False, tab_index=7),
        ],
    )
    _ensure_table_relation('Reservation', 'customer', 'Customer', 'no', 'name')
    _ensure_table_relation('Reservation', 'table', 'Table', 'no', 'table_number')

    menu_category_card, menu_category_list = _list_card_pages(
        list_name='MenuCategoryList',
        list_caption='Menu Categories',
        card_name='MenuCategoryCard',
        card_caption='Menu Category',
        source_table='MenuCategory',
        title_field='name',
        list_fields=[
            dict(name='no', caption='No.', field_type='Code', visible=True, editable=False,
                 primary_key=True, tab_index=0),
            dict(name='name', caption='Name', field_type='Text', visible=True, editable=False,
                 primary_key=False, tab_index=1),
            dict(name='display_order', caption='Order', field_type='Integer', visible=True,
                 editable=False, primary_key=False, tab_index=2),
            dict(name='is_active', caption='Active', field_type='Boolean', visible=True,
                 editable=False, primary_key=False, tab_index=3),
        ],
        card_fields=[
            dict(name='no', caption='No.', field_type='Code', visible=True, editable=False,
                 primary_key=True, tab_index=0),
            dict(name='name', caption='Name', field_type='Text', visible=True, editable=True,
                 primary_key=False, tab_index=1, required=True),
            dict(name='description', caption='Description', field_type='Text', visible=True,
                 editable=True, primary_key=False, tab_index=2),
            dict(name='display_order', caption='Display Order', field_type='Integer',
                 visible=True, editable=True, primary_key=False, tab_index=3),
            dict(name='is_active', caption='Active', field_type='Boolean', visible=True,
                 editable=True, primary_key=False, tab_index=4),
            dict(name='routes_to_kitchen', caption='Routes to Kitchen', field_type='Boolean',
                 visible=True, editable=True, primary_key=False, tab_index=5),
        ],
    )

    menu_card, menu_list = _list_card_pages(
        list_name='MenuList',
        list_caption='Menus',
        card_name='MenuCard',
        card_caption='Menu',
        source_table='Menu',
        title_field='name',
        list_fields=[
            dict(name='code', caption='Code', field_type='Code', visible=True, editable=False,
                 primary_key=True, tab_index=0),
            dict(name='name', caption='Name', field_type='Text', visible=True, editable=False,
                 primary_key=False, tab_index=1),
            dict(name='is_active', caption='Active', field_type='Boolean', visible=True,
                 editable=False, primary_key=False, tab_index=2),
        ],
        card_fields=[
            dict(name='code', caption='Code', field_type='Code', visible=True, editable=False,
                 primary_key=True, tab_index=0),
            dict(name='name', caption='Name', field_type='Text', visible=True, editable=True,
                 primary_key=False, tab_index=1, required=True),
            dict(name='is_active', caption='Active', field_type='Boolean', visible=True,
                 editable=True, primary_key=False, tab_index=2),
            dict(name='start_time', caption='Start Time', field_type='Time', visible=True,
                 editable=True, primary_key=False, tab_index=3),
            dict(name='end_time', caption='End Time', field_type='Time', visible=True,
                 editable=True, primary_key=False, tab_index=4),
        ],
    )

    menu_item_card, menu_item_list = _list_card_pages(
        list_name='MenuItemList',
        list_caption='Menu Items',
        card_name='MenuItemCard',
        card_caption='Menu Item',
        source_table='MenuItem',
        title_field='id',
        list_fields=[
            dict(name='item', caption='Item', field_type='Code', visible=True, editable=False,
                 primary_key=False, tab_index=0),
            dict(name='category', caption='Category', field_type='Code', visible=True,
                 editable=False, primary_key=False, tab_index=1),
            dict(name='is_available', caption='Available', field_type='Boolean', visible=True,
                 editable=False, primary_key=False, tab_index=2),
            dict(name='preparation_time', caption='Prep (min)', field_type='Integer',
                 visible=True, editable=False, primary_key=False, tab_index=3),
        ],
        card_fields=[
            dict(name='item', caption='Item', field_type='Code', visible=True, editable=True,
                 primary_key=False, tab_index=0, required=True,
                 has_table_relation=True, related_table='Item', related_field='no',
                 related_display_field='item_name', relation_lookup_footer=True),
            dict(name='category', caption='Category', field_type='Code', visible=True,
                 editable=True, primary_key=False, tab_index=1,
                 has_table_relation=True, related_table='MenuCategory', related_field='no',
                 related_display_field='name', relation_lookup_footer=True),
            dict(name='menu', caption='Menu', field_type='Code', visible=True, editable=True,
                 primary_key=False, tab_index=2,
                 has_table_relation=True, related_table='Menu', related_field='code',
                 related_display_field='name', relation_lookup_footer=True),
            dict(name='description', caption='Description', field_type='Text', visible=True,
                 editable=True, primary_key=False, tab_index=3),
            dict(name='is_available', caption='Available', field_type='Boolean', visible=True,
                 editable=True, primary_key=False, tab_index=4),
            dict(name='preparation_time', caption='Prep Time (min)', field_type='Integer',
                 visible=True, editable=True, primary_key=False, tab_index=5),
            dict(name='is_featured', caption='Featured', field_type='Boolean', visible=True,
                 editable=True, primary_key=False, tab_index=6),
        ],
    )
    _ensure_table_relation('MenuItem', 'item', 'Item', 'no', 'item_name')
    _ensure_table_relation('MenuItem', 'category', 'MenuCategory', 'no', 'name')
    _ensure_table_relation('MenuItem', 'menu', 'Menu', 'code', 'name')

    order_doc, order_list = _seed_restaurant_order_pages()
    kitchen_list = _seed_kitchen_display_list()
    kitchen_display_page = _seed_kitchen_display_page()
    pos_page = _seed_restaurant_pos_page()
    menu_builder_page = _seed_menu_builder_page()

    manager_rc = _seed_restaurant_manager_rc(
        order_list=order_list,
        reservation_list=reservation_list,
        table_list=table_list,
        menu_list=menu_list,
        kitchen_list=kitchen_list,
    )
    foh_rc = _seed_restaurant_foh_rc(
        order_list=order_list,
        table_list=table_list,
        reservation_list=reservation_list,
        pos_page=pos_page,
    )
    kitchen_rc = _seed_restaurant_kitchen_rc(kitchen_list=kitchen_list)
    _seed_restaurant_application_profiles(
        manager_rc=manager_rc,
        foh_rc=foh_rc,
        kitchen_rc=kitchen_rc,
    )

    _wire_restaurant_relation_lookup_footers(
        menu_item_card=menu_item_card,
        menu_category_list=menu_category_list,
        menu_list=menu_list,
        table_card=table_card,
        floor_list=floor_list,
        reservation_card=reservation_card,
        table_list=table_list,
        order_doc=order_doc,
    )
    _ = menu_category_card, floor_card

    return {
        'restaurant_order_doc_id': order_doc.page_id,
        'restaurant_order_list_id': order_list.page_id,
        'floor_list_id': floor_list.page_id,
        'table_list_id': table_list.page_id,
        'reservation_list_id': reservation_list.page_id,
        'menu_category_list_id': menu_category_list.page_id,
        'menu_list_id': menu_list.page_id,
        'menu_item_list_id': menu_item_list.page_id,
        'kitchen_display_list_id': kitchen_list.page_id,
        'kitchen_display_id': kitchen_display_page.page_id,
        'restaurant_pos_id': pos_page.page_id,
        'menu_builder_id': menu_builder_page.page_id,
        'restaurant_manager_rc_id': manager_rc.page_id,
        'restaurant_foh_rc_id': foh_rc.page_id,
        'restaurant_kitchen_rc_id': kitchen_rc.page_id,
    }
