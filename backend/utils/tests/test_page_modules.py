from utils.page_modules import (
    filter_nav_items_by_enabled_modules,
    resolve_module_for_page_name,
)


def test_home_nav_always_visible():
    assert resolve_module_for_page_name("") is None


def test_sales_page_maps_to_sales_module():
    assert resolve_module_for_page_name("SalesOrderList") == "sales"


def test_filter_drops_disabled_module_nav():
    nav = [
        {"name": "NavSales", "targetPageName": "SalesOrderList"},
        {"name": "NavHotel", "targetPageName": "HotelRoomList"},
        {"name": "NavHome", "targetPageName": ""},
    ]
    filtered = filter_nav_items_by_enabled_modules(nav, ["sales", "inventory"])
    names = [item["name"] for item in filtered]
    assert names == ["NavSales", "NavHome"]


def test_pos_alias_enables_sales_nav():
    nav = [{"name": "NavPOS", "targetPageName": "SalesPOS"}]
    filtered = filter_nav_items_by_enabled_modules(nav, ["pos"])
    assert len(filtered) == 1
