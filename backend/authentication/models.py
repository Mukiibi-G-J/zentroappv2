from django.db import models
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
import hashlib
from datetime import timedelta

from utils.utils import BaseModel, UUIField
from dimension.models import DimensionValue


class Role(BaseModel):
    """
    Role model for defining user roles and permissions
    Just like Business Central: Role → specifies Role Center ID
    """

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    permissions = models.JSONField(default=list, blank=True)

    # NEW: Link to Role Center (like Business Central!)
    role_center = models.ForeignKey(
        "RoleCenter",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_roles",
        help_text="Role Center that defines which modules this role can access (like Business Central)",
    )

    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Role"
        verbose_name_plural = "Roles"
        ordering = ["name"]

    def __str__(self):
        return self.name

    def get_modules(self):
        """Get modules from linked role center"""
        if self.role_center and self.role_center.is_active:
            return self.role_center.modules
        return []


class RoleCenter(BaseModel):
    """
    Role Center - Defines which modules are visible.
    Just like Business Central: Create Role Center → Assign to Role

    Example: Create "Dispenser Center" → Assign to "Dispenser" role → Done!
    """

    code = models.CharField(
        max_length=50,
        unique=True,
        help_text="Unique code (e.g., SALES_CENTER, DISPENSER_CENTER)",
    )

    name = models.CharField(
        max_length=100,
        help_text="Display name (e.g., 'Sales Role Center', 'Dispenser Center')",
    )

    description = models.TextField(
        blank=True, help_text="Description of what this role center is for"
    )

    # Modules to show (simple list)
    modules = models.JSONField(
        default=list,
        blank=True,
        help_text="List of module codes to show, e.g., ['sales', 'customers', 'items']",
    )

    # Optional: Features within modules
    features = models.JSONField(
        default=dict,
        blank=True,
        help_text="""
        Optional: Features per module, e.g.:
        {
          "sales": ["dashboard", "invoices", "history"],
          "customers": ["list", "create", "reports"]
        }
        """,
    )

    # Optional: Dashboard widgets
    dashboard_widgets = models.JSONField(
        default=list,
        blank=True,
        help_text="Widget IDs to show on dashboard, e.g., ['sales_chart', 'top_customers']",
    )

    is_active = models.BooleanField(
        default=True, help_text="Enable/disable this role center"
    )

    class Meta:
        db_table = "authentication_rolecenter"
        verbose_name = "Role Center"
        verbose_name_plural = "Role Centers"
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.code})"

    def get_modules_display(self):
        """Return comma-separated list of modules"""
        return ", ".join(self.modules) if self.modules else "None"

    get_modules_display.short_description = "Modules"


class UserGroup(BaseModel):
    """
    User Group - A collection of users with shared permissions.
    Each tenant can create and manage their own user groups.
    """

    code = models.CharField(
        max_length=50,
        unique=True,
        help_text="Unique code for the user group (e.g., SALES_DEPT, WAREHOUSE_TEAM)",
    )

    name = models.CharField(max_length=100, help_text="Display name for the user group")

    description = models.TextField(
        blank=True, help_text="Description of this user group's purpose"
    )

    default_profile = models.ForeignKey(
        "Role",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="user_groups_default",
        help_text="Default role assigned to users in this group",
    )

    permission_sets = models.ManyToManyField(
        "permissions.PermissionSet",
        related_name="user_groups",
        blank=True,
        help_text="Permission sets assigned to this user group",
    )

    members = models.ManyToManyField(
        "CustomUser",
        related_name="user_groups",
        blank=True,
        help_text="Users who belong to this group",
    )

    is_active = models.BooleanField(
        default=True, help_text="Whether this user group is active"
    )

    class Meta:
        db_table = "authentication_usergroup"
        verbose_name = "User Group"
        verbose_name_plural = "User Groups"
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.code})"

    def get_all_permission_sets(self):
        """
        Get all permission sets for this group.
        Returns only directly assigned permission sets (no role-based inheritance).
        Permission sets are assigned to User Groups, not to Roles.
        """
        return list(self.permission_sets.all())

    def add_member(self, user):
        """Add a user to this group and apply default profile"""
        self.members.add(user)

        # Apply default profile (role) if set
        if self.default_profile:
            user.roles.add(self.default_profile)
            user.save()

    def remove_member(self, user):
        """Remove a user from this group"""
        self.members.remove(user)


class CustomManager(BaseUserManager):
    def create_user(
        self,
        email,
        username,
        full_name,
        phone_number,
        password=None,
        **extra_fields,
    ):
        if not email:
            raise ValueError(_("You must provide an email address"))

        email = self.normalize_email(email)
        user = self.model(
            email=email,
            username=username,
            full_name=full_name,
            phone_number=phone_number,
            **extra_fields,
        )

        user.set_password(password)

        user.save(using=self._db)
        return user

    def create_superuser(
        self,
        email,
        username,
        full_name,
        phone_number,
        password=None,
        **extra_fields,
    ):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_verified", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Super user must be assigned to is_staff=True")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Super user must be assigned to is_superuser=True")
        user = self.create_user(
            email,
            username,
            full_name,
            phone_number,
            password,
            **extra_fields,
        )
        # user.is_staff = True
        # user.is_superuser = True
        user.save(using=self._db)
        return user


class CustomUser(AbstractBaseUser, PermissionsMixin):
    system_id = UUIField(verbose_name="System ID")
    email = models.EmailField(_("email address"), unique=True)
    username = models.CharField(max_length=255, unique=True)
    full_name = models.CharField(max_length=255)
    phone_number = models.CharField(max_length=20, unique=True)
    avatar = models.ImageField(upload_to="avatars/", blank=True, null=True)
    start_date = models.DateField(default=timezone.now)
    is_verified = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)
    roles = models.ManyToManyField(Role, related_name="users", blank=True)
    global_dimension_1 = models.ForeignKey(
        DimensionValue,
        on_delete=models.CASCADE,
        related_name="user_global_dim_1_entries",
        blank=True,
        null=True,
        db_column="dimension_1",  # Keep for migration compatibility
    )
    dimensions = models.ManyToManyField(
        DimensionValue,
        related_name="dimension_entries",
        blank=True,
        db_column="dimensions",
    )
    can_switch_branch = models.BooleanField(
        default=True,
        help_text=(
            "When Multiple Branches is enabled: if False, user is locked to their "
            "assigned branch (Global Dimension 1); X-Branch-Id is ignored for them."
        ),
    )
    restaurant_pin_hash = models.CharField(
        max_length=128,
        blank=True,
        null=True,
        help_text=(
            "Hashed restaurant/POS PIN for mobile quick login. "
            "Must be unique among active users with a PIN set within the tenant."
        ),
    )
    restaurant_pin_set_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text="When the restaurant PIN was last set or changed (for rotation / expiry).",
    )
    is_active = models.BooleanField(default=True)
    must_change_password = models.BooleanField(
        default=False,
        help_text="When enabled, the user must set a new password at next login.",
    )
    terminated = models.BooleanField(
        default=False,
        help_text="When true, user is terminated and hidden from user lists.",
    )
    token_valid_after = models.DateTimeField(
        blank=True,
        null=True,
        db_index=True,
        help_text="Invalidate access tokens issued before this timestamp.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    objects = CustomManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username", "full_name", "phone_number"]

    def clean(self):
        """Enforce branch assignment when multi-branch is enabled."""
        try:
            from financials.models import GeneralLedgerSetup

            gl_setup = GeneralLedgerSetup.objects.first()
            if gl_setup and getattr(gl_setup, "enable_multiple_branches", False):
                if not self.global_dimension_1_id:
                    raise ValidationError(
                        {
                            "global_dimension_1": _(
                                "Branch (Global Dimension 1) is required when "
                                "Multiple Branches is enabled in General Ledger Setup."
                            )
                        }
                    )
        except Exception:
            pass  # Skip if financials not available

    def save(self, *args, **kwargs):
        # Skip full_clean when only updating last_login (e.g. during login).
        # This avoids blocking login when dimension_1 has legacy string data.
        # Run: python manage.py tenant_command fix_user_dimension_1 --schema=<schema>
        update_fields = kwargs.get("update_fields")
        if update_fields is None or set(update_fields) != {"last_login"}:
            self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return (self.full_name or "").strip() or self.username or self.email

    def get_authority(self):
        """
        Get user's authority based on roles and permissions
        """
        if self.is_superuser:
            return ["admin"]

        authority = []
        for role in self.roles.filter(is_active=True):
            if role.permissions:
                if "all" in role.permissions:
                    return ["admin"]  # Role with "all" permission gets admin
                else:
                    authority.extend(role.permissions)

        # Remove duplicates and ensure unique permissions
        authority = list(set(authority))

        # If no specific permissions, give basic user access
        if not authority:
            authority = ["user"]

        return authority

    def check_object_permission(self, object_id, permission_type, object_type=None):
        """
        Check if user has specific permission on an object.

        Args:
            object_id: BC object ID (e.g. 31 for Item List, 22 for Customer List)
            permission_type: 'read', 'insert', 'modify', 'delete', or 'execute'
            object_type: Optional BC object type ('Page', 'Table', …). When omitted,
                resolves by object_id; prefers Page if multiple types share the ID.

        Returns:
            tuple: (bool, str) - (has_permission, source)
        """
        from base.models import Objects
        from permissions.models import PermissionSetLine, PermissionSet

        # Superusers always have permission
        if self.is_superuser:
            return True, "Superuser access"

        from permissions.services.super_permission_set import user_has_super_permission

        if user_has_super_permission(self):
            return True, "SUPER permission set"

        try:
            if object_type:
                app_object = Objects.objects.get(
                    object_type=object_type,
                    object_id=object_id,
                )
            else:
                matches = Objects.objects.filter(object_id=object_id)
                if matches.count() > 1:
                    app_object = matches.filter(object_type='Page').first() or matches.first()
                else:
                    app_object = matches.get()

            # If object doesn't require permission, allow all
            if not app_object.requires_permission:
                return True, "Object does not require permission"

            # Get all permission sets from groups only
            # (Role → Role Center system is separate from Permission Sets)
            permission_sets = []

            # From user groups
            for group in self.user_groups.filter(is_active=True):
                permission_sets.extend(group.get_all_permission_sets())

            # Remove duplicates
            permission_sets = list(set(permission_sets))

            if not permission_sets:
                return False, "No permission sets assigned"

            # Check if user has the permission
            permission_field = f"{permission_type}_permission"

            permission_lines = PermissionSetLine.objects.filter(
                permissionset__in=permission_sets,
                application_object=app_object,
                **{permission_field: True},
            ).select_related("permissionset", "application_object")

            if permission_lines.exists():
                line = permission_lines.first()
                return True, f"{line.permissionset.name} permission set"

            return False, "No matching permission found"

        except Objects.DoesNotExist:
            # If object not found, deny by default
            return False, "Object not found"

    def get_all_permissions(self):
        """Get all permissions for this user from groups and roles"""
        from permissions.models import PermissionSetLine, PermissionSet

        if self.is_superuser:
            return {"superuser": True}

        # Get all permission sets from groups only
        # (Role → Role Center system is separate from Permission Sets)
        permission_sets = []

        # From user groups
        for group in self.user_groups.filter(is_active=True):
            permission_sets.extend(group.get_all_permission_sets())

        # Remove duplicates
        permission_sets = list(set(permission_sets))

        permissions = {}
        permission_lines = PermissionSetLine.objects.filter(
            permissionset__in=permission_sets
        ).select_related("application_object")

        for line in permission_lines:
            key = f"obj_{line.application_object.object_id}"
            permissions[key] = {
                "object_id": line.application_object.object_id,
                "object_name": line.application_object.object_name,
                "read": line.read_permission,
                "insert": line.insert_permission,
                "modify": line.modify_permission,
                "delete": line.delete_permission,
                "execute": line.execute_permission,
            }

        return permissions

    def get_user_groups_info(self):
        """Get user's group membership info for JWT token"""
        groups = []
        for group in self.user_groups.filter(is_active=True):
            groups.append(
                {
                    "code": group.code,
                    "name": group.name,
                    "default_role": (
                        group.default_profile.name if group.default_profile else None
                    ),
                    "permission_sets": [ps.code for ps in group.permission_sets.all()],
                }
            )
        return groups


class RestaurantStaffDevice(BaseModel):
    """
    Registered device (tablet/kiosk) for restaurant PIN login within a tenant.
    """

    device_id = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
        help_text="Client-generated stable ID (e.g. UUID).",
    )
    user = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="restaurant_staff_devices",
        help_text="Last staff member who successfully signed in on this device.",
    )
    is_revoked = models.BooleanField(default=False)
    failed_attempts = models.PositiveSmallIntegerField(default=0)
    locked_until = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = "authentication_restaurantstaffdevice"
        verbose_name = "Restaurant staff device"
        verbose_name_plural = "Restaurant staff devices"

    def __str__(self):
        return f"{self.device_id} → {self.user_id or 'unbound'}"


class DevicePushToken(BaseModel):
    """FCM token for a user's mobile device (tenant-scoped)."""

    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="device_push_tokens",
    )
    device_id = models.CharField(max_length=128, db_index=True)
    fcm_token = models.TextField()
    platform = models.CharField(max_length=16, default="android")
    is_active = models.BooleanField(default=True)
    last_seen_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "authentication_devicepushtoken"
        verbose_name = "Device push token"
        verbose_name_plural = "Device push tokens"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "device_id"],
                name="uniq_device_push_token_user_device",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "is_active"]),
            models.Index(fields=["fcm_token"]),
        ]

    def __str__(self):
        return f"{self.user_id}@{self.device_id} ({self.platform})"


class OTP(BaseModel):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    otp_hash = models.CharField(max_length=255)
    otp_expiry = models.DateTimeField()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.otp_expiry:
            self.otp_expiry = timezone.now()

    def set_otp(self, otp):
        # Ensure otp is a string
        otp_str = str(otp)
        self.otp_hash = hashlib.sha256(otp_str.encode()).hexdigest()
        self.otp_expiry = timezone.now() + timedelta(minutes=5)
        self.save()

    def validate_otp(self, otp):
        if timezone.now() > self.otp_expiry:
            print("expired")
            return False  # OTP expired
        # Ensure otp is a string
        otp_str = str(otp)
        print("befor validate", otp)
        return hashlib.sha256(otp_str.encode()).hexdigest() == self.otp_hash


class PasswordResetToken(BaseModel):
    """Token for link-based password reset. Single-use, expires in 1 hour."""

    user = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE, related_name="password_reset_tokens"
    )
    token_hash = models.CharField(max_length=255, db_index=True)
    expires_at = models.DateTimeField(db_index=True)

    class Meta:
        verbose_name = "Password Reset Token"
        verbose_name_plural = "Password Reset Tokens"

    def is_valid(self, token: str) -> bool:
        if timezone.now() > self.expires_at:
            return False
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        return token_hash == self.token_hash


class UserSetup(BaseModel):
    """
    User Setup - Permission-based controls for individual users.
    Controls what financial information users can see.
    """

    user = models.OneToOneField(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="setup",
        help_text="User this setup belongs to",
    )

    # Pricing & Profit Permissions
    can_see_buying_price = models.BooleanField(
        default=True,
        help_text="Allow user to see buying/cost prices on items",
    )

    can_see_profit_margin = models.BooleanField(
        default=True,
        help_text="Allow user to see profit margins and markup percentages",
    )

    can_see_item_cost = models.BooleanField(
        default=True,
        help_text="Allow user to see item cost in transactions",
    )

    # Posting Permissions
    can_post_previous_dates = models.BooleanField(
        default=True,
        help_text="Allow user to post sales or purchases for previous dates",
    )

    can_reverse_purchase_invoice = models.BooleanField(
        default=True,
        help_text="Allow user to reverse posted purchase invoices",
    )

    can_reverse_sales_invoice = models.BooleanField(
        default=True,
        help_text="Allow user to reverse posted sales invoices",
    )

    can_reverse_item_journal = models.BooleanField(
        default=False,
        help_text=(
            "Allow user to reverse posted item journals from Django admin "
            "(preview reversing G/L, item ledger, and value entries before applying)."
        ),
    )

    can_view_only_their_sales = models.BooleanField(
        default=True,
        help_text="When enabled, Sales History shows only sales made by this user",
    )

    # Notes
    notes = models.TextField(
        blank=True,
        help_text="Additional notes about this user's setup",
    )

    class Meta:
        db_table = "authentication_usersetup"
        verbose_name = "User Setup"
        verbose_name_plural = "User Setups"
        ordering = ["user__full_name", "user__email"]

    def __str__(self):
        user_label = (self.user.full_name or "").strip() or self.user.username or self.user.email
        return f"Setup for {user_label}"

    @classmethod
    def get_or_create_for_user(cls, user):
        """Get or create user setup with default permissions"""
        setup, created = cls.objects.get_or_create(
            user=user,
            defaults={
                "can_see_buying_price": True,
                "can_see_profit_margin": True,
                "can_see_item_cost": True,
                "can_post_previous_dates": True,
                "can_reverse_purchase_invoice": True,
                "can_view_only_their_sales": True,
            },
        )
        return setup


class UserPersonalization(BaseModel):
    """Per-user preferences: language, time zone, teaching tips, etc."""

    LANGUAGE_CHOICES = [
        ('en', 'English'),
        ('sw', 'Swahili'),
        ('fr', 'French'),
        ('lg', 'Luganda'),
    ]

    user = models.OneToOneField(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='personalization',
        help_text='User this personalization belongs to',
    )
    role = models.ForeignKey(
        'ApplicationProfile',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='user_personalizations',
        help_text='Role Centre profile chosen by the user (User Settings)',
    )
    language = models.CharField(
        max_length=20,
        blank=True,
        default='en',
        choices=LANGUAGE_CHOICES,
    )
    time_zone = models.CharField(max_length=60, blank=True, default='Africa/Kampala')
    teaching_tips = models.BooleanField(default=True)
    created_by = models.CharField(max_length=150, blank=True, default='')
    modified_by = models.CharField(max_length=150, blank=True, default='')

    class Meta:
        db_table = 'authentication_userpersonalization'
        verbose_name = 'User Personalization'
        verbose_name_plural = 'User Personalizations'
        ordering = ['user__username']

    def __str__(self):
        return f'{self.user} — personalization'

    @classmethod
    def get_or_create_for_user(cls, user):
        """Get or create personalization defaults for a user."""
        audit_name = user.full_name or user.username or user.email
        default_profile = ApplicationProfile.objects.filter(code='BUSINESS-MGR').first()
        personalization, _created = cls.objects.get_or_create(
            user=user,
            defaults={
                'role': default_profile,
                'created_by': audit_name,
                'modified_by': audit_name,
            },
        )
        if _created and default_profile and not personalization.role_id:
            personalization.role = default_profile
            personalization.save(update_fields=['role'])
        return personalization

    def resolve_role_centre_page(self):
        """Return the Role Centre Page for this user's chosen profile."""
        if self.role_id:
            return self.role.role_centre_page
        from pages.models import Page
        return Page.objects.filter(name='BusinessManagerRC', page_type='RoleCenter').first()

    def get_role_centre_page_id(self) -> int | None:
        page = self.resolve_role_centre_page()
        return page.page_id if page else None


class ApplicationProfile(BaseModel):
    """
    BC-style application profile — maps a profile code to a Role Centre page.
    Users pick a profile on User Settings (self-service).
    """

    code = models.CharField(
        max_length=50,
        unique=True,
        help_text='Profile ID, e.g. SALES-MGR',
    )
    description = models.CharField(max_length=200)
    role_centre_page = models.ForeignKey(
        'pages.Page',
        on_delete=models.PROTECT,
        related_name='application_profiles',
        help_text='Role Centre page shown when this profile is active',
    )

    class Meta:
        db_table = 'authentication_applicationprofile'
        verbose_name = 'Application Profile'
        verbose_name_plural = 'Application Profiles'
        ordering = ['code']

    def __str__(self):
        return f'{self.code} — {self.description}'


class Profile(BaseModel):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE)
    location = models.CharField(max_length=30, blank=True)
    birth_date = models.DateField(null=True, blank=True)
    phone_number = models.CharField(max_length=20, blank=True)
