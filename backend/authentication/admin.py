from django.contrib import admin, messages
from django.utils import timezone
from django.utils.html import format_html
from authentication.models import (
    CustomUser,
    Role,
    UserGroup,
    RoleCenter,
    OTP,
    Profile,
    ApplicationProfile,
    UserSetup,
    UserPersonalization,
    RestaurantStaffDevice,
)
from authentication.forms import RoleCenterModuleForm

# Register your models here.


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "role_center",
        "description",
        "is_active",
        "created_at",
        "updated_at",
    )
    list_filter = ("is_active", "role_center", "created_at", "updated_at")
    search_fields = ("name", "description")
    readonly_fields = ("created_at", "updated_at")
    ordering = ("name",)

    fieldsets = (
        ("Basic Information", {"fields": ("name", "description", "is_active")}),
        (
            "Role Center",
            {
                "fields": ("role_center",),
                "description": "Select the Role Center that defines which modules this role can access (like Business Central!)",
            },
        ),
        (
            "Permissions (Legacy)",
            {
                "fields": ("permissions",),
                "classes": ("collapse",),
                "description": 'Legacy module-level permissions. Example: ["view_sales", "create_sales"]',
            },
        ),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )


@admin.register(RoleCenter)
class RoleCenterAdmin(admin.ModelAdmin):
    """Admin interface for Role Centers - No hardcoding needed!"""

    form = RoleCenterModuleForm

    list_display = [
        "name",
        "code",
        "get_modules_display",
        "is_active",
        "created_at",
    ]
    list_filter = ["is_active", "created_at"]
    search_fields = ["name", "code", "description"]
    readonly_fields = ["created_at", "updated_at"]
    ordering = ["name"]

    fieldsets = (
        (
            "Basic Information",
            {
                "fields": ("code", "name", "description", "is_active"),
                "description": "Create a role center and assign it to roles (just like Business Central!)",
            },
        ),
        (
            "Module Configuration",
            {
                "fields": ("modules",),
                "description": "Select which modules to show in the navigation. No need to edit JSON.",
            },
        ),
        (
            "Advanced (Optional)",
            {
                "fields": ("features", "dashboard_widgets"),
                "classes": ("collapse",),
                "description": "Optional: Configure specific features and widgets",
            },
        ),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    def get_assigned_roles_display(self, obj):
        """Display roles that use this role center"""
        roles = obj.assigned_roles.all()
        if not roles:
            return format_html('<span style="color: gray;">No roles assigned</span>')

        role_names = ", ".join([role.name for role in roles])
        return format_html(
            '<span style="color: blue; font-weight: bold;">{}</span>', role_names
        )

    get_assigned_roles_display.short_description = "Assigned to Roles"

    def get_modules_display(self, obj):
        """Display modules in a nice format"""
        if not obj.modules:
            return format_html('<span style="color: gray;">No modules</span>')

        modules_html = ", ".join(
            [
                f'<span style="background-color: #4CAF50; color: white; padding: 2px 6px; border-radius: 3px; margin: 2px;">{m}</span>'
                for m in obj.modules
            ]
        )
        return format_html(modules_html)

    get_modules_display.short_description = "Modules"


@admin.register(CustomUser)
class UserAdmin(admin.ModelAdmin):
    actions = ["force_logout_selected", "force_logout_all_active_users"]

    list_display = (
        "email",
        "full_name",
        "get_user_groups_display",
        "global_dimension_1",
        "can_switch_branch",
        "is_active",
        "is_staff",
        "is_superuser",
        "is_verified",
        "last_login",
    )
    list_filter = ("is_active", "is_staff", "is_superuser", "user_groups")
    search_fields = ("email", "full_name")
    readonly_fields = ("created_at", "updated_at", "get_inherited_roles_display")
    ordering = ("email",)

    def get_actions(self, request):
        actions = super().get_actions(request)
        if not request.user.is_superuser:
            actions.pop("force_logout_all_active_users", None)
        return actions

    @admin.action(description="Force logout selected users (invalidate API / JWT tokens)")
    def force_logout_selected(self, request, queryset):
        ts = timezone.now()
        updated = queryset.update(token_valid_after=ts)
        self.message_user(
            request,
            f"Invalidated JWTs for {updated} user(s). They must sign in again.",
            messages.SUCCESS,
        )

    @admin.action(
        description="Force logout ALL active users in this tenant (invalidate API / JWT tokens)"
    )
    def force_logout_all_active_users(self, request, queryset):
        if not request.user.is_superuser:
            self.message_user(
                request,
                "Only superusers may run this action.",
                messages.ERROR,
            )
            return
        ts = timezone.now()
        updated = CustomUser.objects.filter(is_active=True).update(
            token_valid_after=ts
        )
        self.message_user(
            request,
            f"Invalidated JWTs for {updated} active user(s) in this tenant.",
            messages.SUCCESS,
        )

    fieldsets = (
        (
            "Basic Information",
            {
                "fields": (
                    "email",
                    "username",
                    "full_name",
                    "phone_number",
                    "avatar",
                    "password",
                    "global_dimension_1",
                    "can_switch_branch",
                ),
                "description": "User password is not displayed in the admin panel. It can be set using the reset password button.",
            },
        ),
        (
            "Permissions & Access",
            {
                "fields": ("is_active", "is_staff", "is_superuser", "is_verified"),
                "description": "User permissions. Note: Roles are inherited from User Groups.",
            },
        ),
        (
            "Inherited Roles (Read-Only)",
            {
                "fields": ("get_inherited_roles_display",),
                "classes": ("collapse",),
                "description": "Roles that this user inherits from their User Groups. To change roles, modify the user's group membership.",
            },
        ),
        (
            "Timestamps",
            {
                "fields": ("created_at", "updated_at", "last_login"),
                "classes": ("collapse",),
            },
        ),
    )

    def get_user_groups_display(self, obj):
        """Display user groups"""
        groups = obj.user_groups.filter(is_active=True)
        if not groups:
            return format_html('<span style="color: gray;">No groups</span>')

        group_names = ", ".join([g.name for g in groups])
        return format_html(
            '<span style="color: blue; font-weight: bold;">{}</span>', group_names
        )

    get_user_groups_display.short_description = "User Groups"

    def get_inherited_roles_display(self, obj):
        """Display roles inherited from user groups"""
        roles = []

        # Get roles from user groups
        for group in obj.user_groups.filter(is_active=True):
            if group.default_profile and group.default_profile.is_active:
                roles.append(f"{group.default_profile.name} (from {group.name})")

        if not roles:
            return format_html(
                '<span style="color: gray;">No roles inherited from groups</span>'
            )

        roles_html = "<br>".join(
            [
                f'<span style="background-color: #2196F3; color: white; padding: 2px 8px; border-radius: 3px; margin: 2px; display: inline-block;">{r}</span>'
                for r in roles
            ]
        )
        return format_html(roles_html)

    get_inherited_roles_display.short_description = "Inherited Roles"


@admin.register(UserGroup)
class UserGroupAdmin(admin.ModelAdmin):
    """Admin interface for User Groups"""

    list_display = [
        "name",
        "code",
        "default_profile",
        "is_active",
        "member_count",
        "permission_set_count",
        "created_at",
    ]
    list_filter = ["is_active", "default_profile", "created_at"]
    search_fields = ["name", "code", "description"]
    filter_horizontal = ["permission_sets", "members"]
    readonly_fields = ["created_at", "updated_at"]

    fieldsets = (
        (
            "Basic Information",
            {"fields": ("code", "name", "description", "is_active")},
        ),
        (
            "Permissions",
            {
                "fields": ("default_profile", "permission_sets"),
                "description": "Set default role and assign permission sets to this group",
            },
        ),
        (
            "Members",
            {
                "fields": ("members",),
                "description": "Users who belong to this group will inherit the default role and permission sets",
            },
        ),
        (
            "Audit Information",
            {
                "fields": ("created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    def member_count(self, obj):
        """Display the number of members in the group"""
        count = obj.members.count()
        if count > 0:
            return format_html(
                '<span style="color: green; font-weight: bold;">{} members</span>',
                count,
            )
        return format_html('<span style="color: gray;">No members</span>')

    member_count.short_description = "Members"

    def permission_set_count(self, obj):
        """Display the number of permission sets"""
        count = obj.permission_sets.count()
        if count > 0:
            return format_html(
                '<span style="color: blue; font-weight: bold;">{} sets</span>', count
            )
        return format_html('<span style="color: gray;">No sets</span>')

    permission_set_count.short_description = "Permission Sets"


@admin.register(OTP)
class OTPAdmin(admin.ModelAdmin):
    """Admin interface for OTP (One-Time Password) management"""

    list_display = [
        "user",
        "get_user_email",
        "otp_expiry",
        "is_expired",
        "created_at",
    ]
    list_filter = ["otp_expiry", "created_at"]
    search_fields = ["user__email", "user__full_name"]
    readonly_fields = ["otp_hash", "created_at", "updated_at", "is_expired"]
    ordering = ["-created_at"]

    fieldsets = (
        (
            "User Information",
            {
                "fields": ("user",),
                "description": "User associated with this OTP",
            },
        ),
        (
            "OTP Details",
            {
                "fields": ("otp_hash", "otp_expiry", "is_expired"),
                "description": "OTP hash and expiration details. OTPs expire after 5 minutes.",
            },
        ),
        (
            "Timestamps",
            {
                "fields": ("created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    def get_user_email(self, obj):
        """Display user email"""
        return obj.user.email

    get_user_email.short_description = "Email"
    get_user_email.admin_order_field = "user__email"

    def is_expired(self, obj):
        """Display whether OTP is expired"""
        from django.utils import timezone

        if timezone.now() > obj.otp_expiry:
            return format_html(
                '<span style="color: red; font-weight: bold;">✗ Expired</span>'
            )
        return format_html(
            '<span style="color: green; font-weight: bold;">✓ Valid</span>'
        )

    is_expired.short_description = "Status"


@admin.register(UserSetup)
class UserSetupAdmin(admin.ModelAdmin):
    """Admin interface for User Setup - Permission-based controls"""

    list_display = [
        "user",
        "get_user_email",
        "can_see_buying_price",
        "can_see_profit_margin",
        "can_see_item_cost",
        "can_post_previous_dates",
        "can_reverse_purchase_invoice",
        "can_reverse_sales_invoice",
        "can_reverse_item_journal",
        "can_view_only_their_sales",
        "created_at",
    ]
    list_filter = [
        "can_see_buying_price",
        "can_see_profit_margin",
        "can_see_item_cost",
        "can_post_previous_dates",
        "can_reverse_purchase_invoice",
        "can_reverse_sales_invoice",
        "can_reverse_item_journal",
        "can_view_only_their_sales",
        "created_at",
    ]
    search_fields = ["user__email", "user__full_name", "user__username", "notes"]
    readonly_fields = ["created_at", "updated_at"]
    ordering = ["user__username"]

    fieldsets = (
        (
            "User Information",
            {
                "fields": ("user",),
                "description": "User this setup belongs to",
            },
        ),
        (
            "Pricing & Profit Permissions",
            {
                "fields": (
                    "can_see_buying_price",
                    "can_see_profit_margin",
                    "can_see_item_cost",
                ),
                "description": "Control what pricing information the user can see",
            },
        ),
        (
            "Posting Permissions",
            {
                "fields": (
                    "can_post_previous_dates",
                    "can_reverse_purchase_invoice",
                    "can_reverse_sales_invoice",
                    "can_reverse_item_journal",
                    "can_view_only_their_sales",
                ),
                "description": (
                    "Control posting date rules and whether the user can reverse "
                    "posted purchase invoices, sales invoices, or item journals."
                ),
            },
        ),
        (
            "Additional Notes",
            {
                "fields": ("notes",),
                "classes": ("collapse",),
                "description": "Any additional notes about this user's setup",
            },
        ),
        (
            "Timestamps",
            {
                "fields": ("created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    def get_user_email(self, obj):
        """Display user email"""
        return obj.user.email

    get_user_email.short_description = "Email"
    get_user_email.admin_order_field = "user__email"


@admin.register(ApplicationProfile)
class ApplicationProfileAdmin(admin.ModelAdmin):
    list_display = ['code', 'description', 'role_centre_page', 'updated_at']
    search_fields = ['code', 'description', 'role_centre_page__name']
    list_filter = ['role_centre_page']
    ordering = ['code']


@admin.register(UserPersonalization)
class UserPersonalizationAdmin(admin.ModelAdmin):
    """Admin interface for per-user personalization preferences."""

    list_display = [
        "user",
        "get_user_email",
        "role",
        "language",
        "time_zone",
        "teaching_tips",
        "modified_by",
        "updated_at",
    ]
    list_filter = ["language", "teaching_tips", "time_zone"]
    search_fields = [
        "user__email",
        "user__full_name",
        "user__username",
        "role__code",
        "role__description",
        "created_by",
        "modified_by",
    ]
    readonly_fields = ["system_id", "created_at", "updated_at", "created_by", "modified_by"]
    ordering = ["user__username"]

    fieldsets = (
        (
            "User",
            {"fields": ("user",)},
        ),
        (
            "Preferences",
            {
                "fields": (
                    "role",
                    "language",
                    "time_zone",
                    "teaching_tips",
                ),
            },
        ),
        (
            "System",
            {
                "fields": (
                    "system_id",
                    "created_at",
                    "created_by",
                    "updated_at",
                    "modified_by",
                ),
            },
        ),
    )

    def get_user_email(self, obj):
        return obj.user.email

    get_user_email.short_description = "Email"
    get_user_email.admin_order_field = "user__email"


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    """Admin interface for User Profiles"""

    list_display = [
        "user",
        "get_user_email",
        "location",
        "birth_date",
        "phone_number",
        "created_at",
    ]
    list_filter = ["location", "created_at"]
    search_fields = ["user__email", "user__full_name", "location", "phone_number"]
    readonly_fields = ["created_at", "updated_at"]
    ordering = ["-created_at"]

    fieldsets = (
        (
            "User Information",
            {
                "fields": ("user",),
                "description": "User associated with this profile",
            },
        ),
        (
            "Profile Details",
            {
                "fields": ("location", "birth_date", "phone_number"),
                "description": "Additional user profile information",
            },
        ),
        (
            "Timestamps",
            {
                "fields": ("created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    def get_user_email(self, obj):
        """Display user email"""
        return obj.user.email

    get_user_email.short_description = "Email"
    get_user_email.admin_order_field = "user__email"


@admin.register(RestaurantStaffDevice)
class RestaurantStaffDeviceAdmin(admin.ModelAdmin):
    list_display = (
        "device_id",
        "user",
        "is_revoked",
        "failed_attempts",
        "locked_until",
        "created_at",
    )
    list_filter = ("is_revoked",)
    search_fields = ("device_id", "user__email", "user__username")
    readonly_fields = ("created_at", "updated_at", "system_id")
