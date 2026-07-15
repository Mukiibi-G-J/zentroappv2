from utils.page_modules import (
    filter_application_profiles_by_enabled_modules,
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


def test_restaurant_role_centre_maps_to_restaurant_module():
    assert resolve_module_for_page_name("RestaurantManagerRC") == "restaurant"


def test_filter_application_profiles_drops_restaurant_when_disabled():
    class FakePage:
        def __init__(self, name):
            self.name = name

    class FakeProfile:
        def __init__(self, pk, code, rc_name):
            self.pk = pk
            self.code = code
            self.role_centre_page = FakePage(rc_name)

    class FakeQS:
        def __init__(self, profiles):
            self._profiles = profiles

        def select_related(self, *_args, **_kwargs):
            return self

        def filter(self, pk__in=None, **_kwargs):
            if pk__in is not None:
                self._profiles = [p for p in self._profiles if p.pk in pk__in]
            return self

        def none(self):
            self._profiles = []
            return self

        def __iter__(self):
            return iter(self._profiles)
    qs = FakeQS(profiles)
    filter_application_profiles_by_enabled_modules(qs, ["pos", "sales"])
    codes = [p.code for p in qs._profiles]
    assert codes == ["BUSINESS-MGR"]


def test_filter_application_profiles_keeps_restaurant_when_enabled():
    class FakePage:
        def __init__(self, name):
            self.name = name

    class FakeProfile:
        def __init__(self, pk, code, rc_name):
            self.pk = pk
            self.code = code
            self.role_centre_page = FakePage(rc_name)

    class FakeQS:
        def __init__(self, profiles):
            self._profiles = profiles

        def select_related(self, *_args, **_kwargs):
            return self

        def filter(self, pk__in=None, **_kwargs):
            if pk__in is not None:
                self._profiles = [p for p in self._profiles if p.pk in pk__in]
            return self

        def none(self):
            self._profiles = []
            return self

        def __iter__(self):
            return iter(self._profiles)

    profiles = [
        FakeProfile(1, "BUSINESS-MGR", "BusinessManagerRC"),
        FakeProfile(2, "REST-MGR", "RestaurantManagerRC"),
    ]
    qs = FakeQS(profiles)
    filter_application_profiles_by_enabled_modules(qs, ["pos", "restaurant"])
    codes = [p.code for p in qs._profiles]
    assert codes == ["BUSINESS-MGR", "REST-MGR"]
