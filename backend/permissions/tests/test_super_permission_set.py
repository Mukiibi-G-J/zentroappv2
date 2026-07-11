from unittest.mock import patch

from django.test import TestCase

from authentication.models import CustomUser, UserGroup
from base.models import Objects
from permissions.models import PermissionSet, PermissionSetLine
from permissions.services.super_permission_set import (
    SUPER_PERMISSION_SET_CODE,
    ensure_super_permission_set,
    user_has_super_permission,
)
from permissions.table_permissions import check_source_table_permission


class SuperPermissionSetTests(TestCase):
    def setUp(self):
        self.table_obj, _ = Objects.objects.update_or_create(
            object_id=99011,
            defaults={
                "object_type": "Table",
                "object_name": "SuperTestTable",
                "object_caption": "Super Test Table",
                "related_model": "permissions.PermissionSet",
                "requires_permission": True,
                "is_active": True,
                "app_label": "permissions",
            },
        )
        self.page_obj, _ = Objects.objects.update_or_create(
            object_id=99012,
            defaults={
                "object_type": "Page",
                "object_name": "Super Test Page",
                "object_caption": "Super Test Page",
                "requires_permission": True,
                "is_active": True,
                "app_label": "permissions",
            },
        )
        self.user = CustomUser.objects.create_user(
            email="supertest@example.com",
            username="supertest",
            full_name="Super Test",
            phone_number="+256700000199",
            password="testpass123",
        )
        self.group = UserGroup.objects.create(code="SUPER_GRP", name="Super Group")
        self.group.members.add(self.user)

    def test_ensure_super_creates_full_lines(self):
        permission_set, stats = ensure_super_permission_set(update=True)

        self.assertEqual(permission_set.code, SUPER_PERMISSION_SET_CODE)
        self.assertGreater(stats["lines_created"], 0)

        line = PermissionSetLine.objects.get(
            permissionset=permission_set,
            application_object=self.table_obj,
        )
        self.assertTrue(line.read_permission)
        self.assertTrue(line.insert_permission)
        self.assertTrue(line.modify_permission)
        self.assertTrue(line.delete_permission)
        self.assertTrue(line.execute_permission)

    def test_super_grants_access_without_explicit_line(self):
        permission_set = PermissionSet.objects.create(
            code=SUPER_PERMISSION_SET_CODE,
            name="Super",
            is_active=True,
        )
        self.group.permission_sets.add(permission_set)

        allowed, source = self.user.check_object_permission(
            self.table_obj.object_id,
            "delete",
        )
        self.assertTrue(allowed)
        self.assertEqual(source, "SUPER permission set")

    @patch(
        "permissions.table_permissions.ENFORCED_SOURCE_TABLES",
        frozenset({"SuperTestTable"}),
    )
    def test_super_grants_table_permission(self):
        permission_set = PermissionSet.objects.create(
            code=SUPER_PERMISSION_SET_CODE,
            name="Super",
            is_active=True,
        )
        self.group.permission_sets.add(permission_set)

        allowed, source = check_source_table_permission(
            self.user,
            "SuperTestTable",
            "modify",
        )
        self.assertTrue(allowed)
        self.assertEqual(source, "SUPER permission set")

    def test_user_has_super_permission_helper(self):
        self.assertFalse(user_has_super_permission(self.user))

        permission_set = PermissionSet.objects.create(
            code=SUPER_PERMISSION_SET_CODE,
            name="Super",
            is_active=True,
        )
        self.group.permission_sets.add(permission_set)
        self.assertTrue(user_has_super_permission(self.user))
