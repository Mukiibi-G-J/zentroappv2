from django.test import TestCase

from authentication.models import CustomUser, UserGroup
from base.models import Objects
from permissions.models import PermissionSet, PermissionSetLine
from permissions.table_permissions import (
    check_source_table_permission,
    get_table_object_for_source_table,
)


class TablePermissionTests(TestCase):
    def setUp(self):
        self.table_obj, _ = Objects.objects.update_or_create(
            object_id=99001,
            defaults={
                'object_type': 'Table',
                'object_name': 'RestaurantOrder',
                'object_caption': 'Restaurant Order',
                'related_model': 'restaurant_management.RestaurantOrder',
                'requires_permission': True,
                'app_label': 'restaurant_management',
            },
        )
        self.page_obj, _ = Objects.objects.update_or_create(
            object_id=99002,
            defaults={
                'object_type': 'Page',
                'object_name': 'Orders',
                'object_caption': 'Orders',
                'requires_permission': True,
                'app_label': 'restaurant',
            },
        )
        self.user = CustomUser.objects.create_user(
            email='tabletest@example.com',
            username='tabletest',
            full_name='Table Test',
            phone_number='+256700000099',
            password='testpass123',
        )
        self.perm_set = PermissionSet.objects.create(
            code='TEST_TABLE_READ',
            name='Test Table Read',
        )
        PermissionSetLine.objects.create(
            permissionset=self.perm_set,
            application_object=self.table_obj,
            read_permission=True,
        )
        self.group = UserGroup.objects.create(code='TEST_GRP', name='Test Group')
        self.group.members.add(self.user)
        self.group.permission_sets.add(self.perm_set)

    def test_resolve_table_object(self):
        obj = get_table_object_for_source_table('RestaurantOrder')
        self.assertIsNotNone(obj)
        self.assertEqual(obj.object_id, 99001)

    def test_table_read_allowed(self):
        allowed, _ = check_source_table_permission(
            self.user, 'RestaurantOrder', 'read',
        )
        self.assertTrue(allowed)

    def test_table_modify_denied_without_line(self):
        allowed, _ = check_source_table_permission(
            self.user, 'RestaurantOrder', 'modify',
        )
        self.assertFalse(allowed)

    def test_page_fallback_when_no_table_line(self):
        PermissionSetLine.objects.filter(permissionset=self.perm_set).delete()
        page_set = PermissionSet.objects.create(code='TEST_PAGE', name='Test Page')
        PermissionSetLine.objects.create(
            permissionset=page_set,
            application_object=self.page_obj,
            read_permission=True,
        )
        self.group.permission_sets.add(page_set)

        allowed, reason = check_source_table_permission(
            self.user, 'RestaurantOrder', 'read',
        )
        self.assertTrue(allowed)
        self.assertIn('fallback', reason.lower())
