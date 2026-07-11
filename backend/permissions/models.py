from django.db import models
from django.contrib.auth import get_user_model
from base.models import Objects

User = get_user_model()


class PermissionSet(models.Model):
    """
    Permission Set - A collection of permission lines that can be assigned to user groups.
    Each company (tenant) has their own permission sets.
    Permission sets are assigned to User Groups, not directly to Roles.
    """

    name = models.CharField(
        max_length=100, help_text="Display name for the permission set"
    )
    code = models.CharField(
        max_length=50, unique=True, help_text="Unique code for the permission set"
    )
    description = models.TextField(
        blank=True, help_text="Description of what this permission set allows"
    )
    is_active = models.BooleanField(
        default=True, help_text="Whether this permission set is active"
    )

    # Audit fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_permission_sets",
    )

    class Meta:
        db_table = "permissions_permissionset"
        verbose_name = "Permission Set"
        verbose_name_plural = "Permission Sets"
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.code})"

    def get_permission_count(self):
        """Get the number of permission lines in this set"""
        return self.permissionsetline_set.count()


class PermissionSetLine(models.Model):
    """
    Permission Set Line - Individual permission rule within a Permission Set.
    Defines what actions are allowed on specific application objects.
    """

    PERMISSION_CHOICES = [
        ("read", "Read"),
        ("insert", "Insert"),
        ("modify", "Modify"),
        ("delete", "Delete"),
        ("execute", "Execute"),
    ]

    permissionset = models.ForeignKey(
        PermissionSet,
        on_delete=models.CASCADE,
        help_text="The permission set this line belongs to",
    )
    application_object = models.ForeignKey(
        Objects,
        on_delete=models.CASCADE,
        help_text="The application object this permission applies to",
    )

    # Permission flags
    read_permission = models.BooleanField(
        default=False, help_text="Allow reading this object"
    )
    insert_permission = models.BooleanField(
        default=False, help_text="Allow creating new records"
    )
    modify_permission = models.BooleanField(
        default=False, help_text="Allow modifying existing records"
    )
    delete_permission = models.BooleanField(
        default=False, help_text="Allow deleting records"
    )
    execute_permission = models.BooleanField(
        default=False, help_text="Allow executing this object"
    )

    # Audit fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "permissions_permissionsetline"
        verbose_name = "Permission Set Line"
        verbose_name_plural = "Permission Set Lines"
        unique_together = ["permissionset", "application_object"]
        ordering = ["application_object__object_name"]

    def __str__(self):
        permissions = []
        if self.read_permission:
            permissions.append("R")
        if self.insert_permission:
            permissions.append("I")
        if self.modify_permission:
            permissions.append("M")
        if self.delete_permission:
            permissions.append("D")
        if self.execute_permission:
            permissions.append("X")

        perm_str = "".join(permissions) if permissions else "None"
        return f"{self.permissionset.name} - {self.application_object.object_name} ({perm_str})"

    def has_permission(self, permission_type):
        """Check if this line grants a specific permission type"""
        return getattr(self, f"{permission_type}_permission", False)

    def get_permissions_list(self):
        """Get list of granted permissions"""
        permissions = []
        for perm_type, _ in self.PERMISSION_CHOICES:
            if getattr(self, f"{perm_type}_permission", False):
                permissions.append(perm_type)
        return permissions
