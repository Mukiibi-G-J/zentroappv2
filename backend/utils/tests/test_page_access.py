from utils.page_access import (
    filter_application_profiles_for_user,
    filter_nav_items_by_user_permissions,
    user_has_any_page_access,
)


class FakeUser:
    is_superuser = False

    def check_object_permission(self, _oid, _perm):
        return False, 'denied'


class FakeProfile:
    def __init__(self, pk, code, nav_targets):
        self.pk = pk
        self.code = code
        self.role_centre_page = object()


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


def test_filter_nav_drops_unauthorized_pages(monkeypatch):
    user = FakeUser()
    nav = [
        {'name': 'NavHome', 'targetPageName': ''},
        {'name': 'NavCustomers', 'targetPageName': 'CustomerList'},
        {'name': 'NavItems', 'targetPageName': 'ItemList'},
    ]
    page_permissions = {
        'ItemList': {'read': True, 'insert': False, 'modify': False, 'delete': False},
    }

    filtered = filter_nav_items_by_user_permissions(nav, user, page_permissions)
    names = [item['name'] for item in filtered]
    assert names == ['NavHome', 'NavItems']


def test_user_has_any_page_access_uses_jwt_map():
    user = FakeUser()
    perms = {
        'VendorList': {'read': True, 'insert': False, 'modify': False, 'delete': False},
    }
    assert user_has_any_page_access(user, 'VendorList', perms) is True
    assert user_has_any_page_access(user, 'CustomerList', perms) is False


def test_user_has_any_page_access_uses_related_nav_alias():
    user = FakeUser()
    perms = {
        'PurchaseInvoiceList': {'read': True, 'insert': False, 'modify': False, 'delete': False},
    }
    assert user_has_any_page_access(user, 'PostedPurchaseInvoiceList', perms) is True


def test_filter_application_profiles_keeps_accessible_and_current(monkeypatch):
    user = FakeUser()
    profiles = [
        FakeProfile(1, 'BUSINESS-MGR', []),
        FakeProfile(2, 'PHARMACIST', []),
    ]
    qs = FakeQS(profiles)

    def fake_may_select(_user, profile, page_permissions=None):
        return profile.code == 'PHARMACIST'

    monkeypatch.setattr(
        'utils.page_access._user_may_select_profile',
        fake_may_select,
    )

    filtered = filter_application_profiles_for_user(
        qs, user, current_profile_id=1,
    )
    codes = [p.code for p in filtered._profiles]
    assert codes == ['BUSINESS-MGR', 'PHARMACIST']
