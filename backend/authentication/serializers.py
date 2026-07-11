from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from authentication.login_utils import resolve_login_identifier
from authentication.models import OTP, CustomUser as User, Role, UserSetup
from company.models import Subscription
from django_tenants.utils import get_tenant, schema_context
from django.db import connection


class ResendOTPSerializer(serializers.Serializer):
    """Resend verification OTP by email or SMS."""

    email = serializers.EmailField(required=False, allow_blank=True)
    phone = serializers.CharField(required=False, allow_blank=True, max_length=20)
    channel = serializers.ChoiceField(
        choices=["email", "sms"],
        required=False,
        allow_blank=True,
    )

    def validate(self, attrs):
        email = (attrs.get("email") or "").strip()
        phone = (attrs.get("phone") or "").strip()
        channel = (attrs.get("channel") or "").strip().lower()

        if not email and not phone:
            raise serializers.ValidationError(
                "Either email or phone is required."
            )

        if phone and not channel:
            channel = "sms"
        elif email and not channel:
            channel = "email"
        elif not channel:
            channel = "email"

        if channel == "sms" and not phone:
            raise serializers.ValidationError(
                {"phone": "Phone is required when channel is sms."}
            )
        if channel == "email" and not email:
            raise serializers.ValidationError(
                {"email": "Email is required when channel is email."}
            )

        attrs["email"] = email
        attrs["phone"] = phone
        attrs["channel"] = channel
        return attrs


class AuthTokenViewSerializer(TokenObtainPairSerializer):

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)

        # Add custom claims
        token["username"] = user.username
        token["full_name"] = user.full_name
        token["email"] = user.email
        token["verified"] = user.is_verified
        token["is_superuser"] = user.is_superuser
        token["phone"] = user.phone_number
        token["user_id"] = user.id  # Add user ID for additional validation
        # Branch switching capability (frontend uses this to decide whether to prompt for branch selection).
        token["can_switch_branch"] = getattr(user, "can_switch_branch", True)
        token["must_change_password"] = getattr(user, "must_change_password", False)

        # Add branch (global_dimension_1) for multi-branch filtering
        if user.global_dimension_1_id:
            token["global_dimension_1"] = {
                "id": user.global_dimension_1.id,
                "code": user.global_dimension_1.code,
                "description": user.global_dimension_1.description or "",
            }
        else:
            token["global_dimension_1"] = None

        # Add enable_multiple_branches for branch selection prompt on login
        try:
            from financials.models import GeneralLedgerSetup
            from financials.currency import get_local_currency_code

            gl_setup = GeneralLedgerSetup.objects.first()
            token["enable_multiple_branches"] = (
                gl_setup.enable_multiple_branches if gl_setup else False
            )
            token["local_currency_code"] = get_local_currency_code()
        except Exception:
            token["enable_multiple_branches"] = False
            token["local_currency_code"] = "UGX"

        # Extract authority from user roles
        authority = []
        if user.is_superuser:
            authority = ["admin"]  # Superuser gets admin authority
        else:
            # Get all user roles (from groups AND direct assignment)
            all_roles = []

            # 1. Get roles from user groups (PRIMARY source - Business Central style!)
            for group in user.user_groups.filter(is_active=True):
                if group.default_profile and group.default_profile.is_active:
                    all_roles.append(group.default_profile)

            # 2. Get direct role assignments (FALLBACK for backward compatibility)
            for role in user.roles.filter(is_active=True):
                if role not in all_roles:  # Avoid duplicates
                    all_roles.append(role)

            # Get permissions from all collected roles
            for role in all_roles:
                if role.permissions:
                    if "all" in role.permissions:
                        authority = ["admin"]  # Role with "all" permission gets admin
                        break
                    else:
                        authority.extend(role.permissions)

            # Remove duplicates and ensure unique permissions
            authority = list(set(authority))

            # If no specific permissions, give basic user access
            if not authority:
                authority = ["user"]

        token["authority"] = authority

        # Add enabled modules from company (with self-healing)
        try:
            from company.models import Company
            from django.db import connection

            if hasattr(connection, "tenant") and connection.tenant:
                tenant = connection.tenant
                modules = getattr(tenant, "enabled_modules", None) or []
                if not modules or modules == ["pos"]:
                    try:
                        tenant.compute_enabled_modules()
                        tenant.refresh_from_db(fields=["enabled_modules"])
                        modules = tenant.enabled_modules or ["pos"]
                    except Exception:
                        modules = modules or ["pos"]
                token["enabled_modules"] = modules
            else:
                token["enabled_modules"] = ["pos"]
        except Exception as e:
            print(f"Error loading enabled modules: {e}")
            token["enabled_modules"] = ["pos"]

        # Add subscription details if user has a company
        try:
            # Guard for public-schema/FakeTenant contexts where tenant has no DB PK.
            tenant = getattr(connection, "tenant", None)
            company_id = getattr(tenant, "id", None)
            if not isinstance(company_id, int):
                company_id = None

            # Use filter().first() instead of get() to handle missing subscription gracefully
            subscription = (
                Subscription.objects.filter(company_id=company_id).first()
                if company_id is not None
                else None
            )
            if subscription:
                lock_d = subscription.access_lock_date()
                token["subscription"] = {
                    "plan": subscription.plan,
                    "status": subscription.status,
                    "is_trial": subscription.is_trial_active(),
                    "is_active": subscription.is_active(),
                    "in_grace_period": subscription.is_in_grace_period(),
                    "access_lock_date": lock_d.isoformat() if lock_d else None,
                    "trial_end_date": (
                        subscription.trial_period_end_date.isoformat()
                        if subscription.trial_period_end_date
                        else None
                    ),
                    "subscription_end_date": (
                        subscription.subscription_end_date.isoformat()
                        if subscription.subscription_end_date
                        else None
                    ),
                }
            else:
                # No subscription found - set default values
                token["subscription"] = {
                    "plan": None,
                    "status": None,
                    "is_trial": False,
                    "is_active": False,
                    "in_grace_period": False,
                    "access_lock_date": None,
                    "trial_end_date": None,
                    "subscription_end_date": None,
                }
            token["schema_name"] = (
                getattr(tenant, "schema_name", None) or connection.schema_name
            )

            # Add Zentro Starter pack status
            try:
                from company.models import ZentroStarterOrder

                starter_order = (
                    ZentroStarterOrder.objects.filter(
                        company_id=company_id,
                        status__in=["paid", "active", "free_period_ended"],
                    )
                    .order_by("-created_at")
                    .first()
                )

                if starter_order:
                    try:
                        token["starter_pack"] = {
                            "has_starter_pack": True,
                            "order_id": starter_order.id,
                            "offer_name": starter_order.offer.name,
                            "payment_amount": str(starter_order.payment_amount),
                            "payment_status": starter_order.payment_status,
                            "order_status": starter_order.status,
                            "device_included": starter_order.device_included,
                            "free_months_earned": starter_order.free_months_earned,
                            "free_period_active": starter_order.is_free_period_active,
                            "free_period_days_remaining": starter_order.free_period_days_remaining,
                            "subscription_active": starter_order.is_subscription_active,
                            "subscription_days_remaining": starter_order.subscription_days_remaining,
                            "should_start_monthly": starter_order.should_start_monthly_subscription,
                            "offer_was_active_at_payment": starter_order.is_offer_active_at_payment,
                            "order_date": (
                                starter_order.order_date.isoformat()
                                if starter_order.order_date
                                else None
                            ),
                            "subscription_start_date": (
                                starter_order.subscription_start_date.isoformat()
                                if starter_order.subscription_start_date
                                else None
                            ),
                            "subscription_end_date": (
                                starter_order.subscription_end_date.isoformat()
                                if starter_order.subscription_end_date
                                else None
                            ),
                            "free_period_end_date": (
                                starter_order.free_period_end_date.isoformat()
                                if starter_order.free_period_end_date
                                else None
                            ),
                        }
                    except Exception as e:
                        # If there's any error with starter order data, set default values
                        token["starter_pack"] = {
                            "has_starter_pack": True,
                            "order_id": starter_order.id if starter_order else None,
                            "offer_name": "Zentro Starter Pack",
                            "payment_amount": "0.00",
                            "payment_status": "unknown",
                            "order_status": "unknown",
                            "device_included": False,
                            "free_months_earned": 0,
                            "free_period_active": False,
                            "free_period_days_remaining": 0,
                            "subscription_active": False,
                            "subscription_days_remaining": 0,
                            "should_start_monthly": False,
                            "offer_was_active_at_payment": False,
                            "order_date": None,
                            "subscription_start_date": None,
                            "subscription_end_date": None,
                            "free_period_end_date": None,
                            "error": str(e),
                        }
                else:
                    token["starter_pack"] = {
                        "has_starter_pack": False,
                        "message": "Company has not purchased a Zentro Starter pack yet",
                    }
            except ImportError:
                # If company app is not available, set default values
                token["starter_pack"] = {
                    "has_starter_pack": False,
                    "message": "Starter pack status unavailable",
                }
            except Exception as e:
                # Catch any other errors and set default values
                token["starter_pack"] = {
                    "has_starter_pack": False,
                    "message": f"Error loading starter pack status: {str(e)}",
                }

        except (Subscription.DoesNotExist, AttributeError):
            token["subscription"] = None
            token["starter_pack"] = {
                "has_starter_pack": False,
                "message": "Company subscription and starter pack status unavailable",
            }

        # Add user groups info (NEW - Day 2)
        try:
            token["user_groups"] = user.get_user_groups_info()
        except Exception as e:
            print(f"Error loading user groups: {e}")
            token["user_groups"] = []

        # Add permission sets (NEW - Day 2)
        try:
            from permissions.models import PermissionSet

            permission_sets = []

            # Get permission sets from user groups
            for group in user.user_groups.filter(is_active=True):
                permission_sets.extend(group.permission_sets.all())

            # Get permission sets from direct role assignments
            for role in user.roles.all():
                role_sets = PermissionSet.objects.filter(
                    linked_role=role, is_active=True
                )
                permission_sets.extend(role_sets)

            # Remove duplicates and create list of codes
            unique_sets = list(set(permission_sets))
            token["permission_sets"] = [ps.code for ps in unique_sets]
        except Exception as e:
            print(f"Error loading permission sets: {e}")
            token["permission_sets"] = []

        # Add role names and role center modules (NEW - Role Center) - Business Central Style!
        try:
            role_center_modules = []
            all_roles = []

            # 1. Get roles from user groups (PRIMARY source - Business Central style!)
            for group in user.user_groups.filter(is_active=True):
                if group.default_profile and group.default_profile.is_active:
                    all_roles.append(group.default_profile)

            # 2. Get direct role assignments (FALLBACK for backward compatibility)
            for role in user.roles.filter(is_active=True):
                if role not in all_roles:  # Avoid duplicates
                    all_roles.append(role)

            # Set roles in token from all_roles (includes user group roles!)
            token["roles"] = [role.name for role in all_roles]

            # Get modules from each role's role center (just like Business Central!)
            for role in all_roles:
                if role.role_center and role.role_center.is_active:
                    if role.role_center.modules:
                        role_center_modules.extend(role.role_center.modules)

            # Admin users: merge company enabled_modules so trial-enabled modules show in sidebar
            role_names = [r.name for r in all_roles]
            if user.is_superuser or "Administrator" in role_names:
                enabled = token.get("enabled_modules") or []
                role_center_modules = list(set(role_center_modules) | set(enabled))

            # Remove duplicates
            token["role_center_modules"] = list(set(role_center_modules))
        except Exception as e:
            print(f"Error loading roles and role center modules: {e}")
            token["roles"] = []
            token["role_center_modules"] = []

        # Page-level permissions + SPA module visibility (merge Page app_label → role_center_modules)
        try:
            from authentication.permission_claims import (
                merge_role_center_modules_with_page_derived_visible_modules,
                page_permissions_from_user_groups,
            )

            from permissions.services.super_permission_set import user_has_super_permission

            page_permissions = page_permissions_from_user_groups(user)
            token["page_permissions"] = page_permissions
            token["has_super_permission"] = user_has_super_permission(user)
            token["role_center_modules"] = (
                merge_role_center_modules_with_page_derived_visible_modules(
                    token.get("role_center_modules") or [],
                    page_permissions,
                )
            )
        except Exception as e:
            print(f"Error loading page permissions: {e}")
            token["page_permissions"] = {}

        # Add user setup permissions (NEW - User-specific permissions)
        try:
            user_setup = UserSetup.get_or_create_for_user(user)
            token["user_permissions"] = {
                "canSeeBuyingPrice": user_setup.can_see_buying_price,
                "canSeeProfitMargin": user_setup.can_see_profit_margin,
                "canSeeItemCost": user_setup.can_see_item_cost,
                "canReversePurchaseInvoice": user_setup.can_reverse_purchase_invoice,
                "canReverseSalesInvoice": user_setup.can_reverse_sales_invoice,
                "canReverseItemJournal": user_setup.can_reverse_item_journal,
            }
        except Exception as e:
            print(f"Error loading user setup: {e}")
            # Default to all permissions granted if error
            token["user_permissions"] = {
                "canSeeBuyingPrice": True,
                "canSeeProfitMargin": True,
                "canSeeItemCost": True,
                "canReversePurchaseInvoice": True,
                "canReverseSalesInvoice": True,
                "canReverseItemJournal": False,
            }

        return token

    def validate(self, attrs):
        # USERNAME_FIELD is email; allow email, phone, or username in the email field.
        identifier = (attrs.get(self.username_field) or "").strip()
        self.login_via_phone = False

        if identifier:
            _user, resolved_email, login_via_phone = resolve_login_identifier(
                identifier
            )
            self.login_via_phone = login_via_phone
            if _user:
                attrs[self.username_field] = resolved_email

        data = super().validate(attrs)
        user = getattr(self, "user", None)
        if user is not None and getattr(user, "pk", None):
            try:
                from authentication.models import RestaurantStaffDevice

                RestaurantStaffDevice.objects.filter(user=user).update(
                    failed_attempts=0,
                    locked_until=None,
                )
            except Exception:
                pass
            data["must_change_password"] = getattr(user, "must_change_password", False)
        return data


class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = ["id", "name", "description", "permissions", "is_active"]


class UserSerializer(serializers.ModelSerializer):
    roles = RoleSerializer(many=True, read_only=True)
    avatar_url = serializers.SerializerMethodField()

    def get_avatar_url(self, obj):
        if obj.avatar:
            request = self.context.get("request")
            if request:
                return request.build_absolute_uri(obj.avatar.url)
            return obj.avatar.url
        return None

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "username",
            "full_name",
            "phone_number",
            "avatar",
            "avatar_url",
            "roles",
            "is_active",
            "is_staff",
        ]


class UserSetupSerializer(serializers.ModelSerializer):
    """Serializer for User Setup permissions"""

    userId = serializers.IntegerField(source="user.id", read_only=True)
    username = serializers.CharField(source="user.username", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)
    fullName = serializers.CharField(source="user.full_name", read_only=True)
    canSeeBuyingPrice = serializers.BooleanField(source="can_see_buying_price")
    canSeeProfitMargin = serializers.BooleanField(source="can_see_profit_margin")
    canSeeItemCost = serializers.BooleanField(source="can_see_item_cost")
    canPostPreviousDates = serializers.BooleanField(source="can_post_previous_dates")
    canReversePurchaseInvoice = serializers.BooleanField(
        source="can_reverse_purchase_invoice"
    )
    canReverseSalesInvoice = serializers.BooleanField(
        source="can_reverse_sales_invoice"
    )
    canReverseItemJournal = serializers.BooleanField(source="can_reverse_item_journal")
    canViewOnlyTheirSales = serializers.BooleanField(source="can_view_only_their_sales")
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)

    class Meta:
        model = UserSetup
        fields = [
            "id",
            "user",
            "userId",
            "username",
            "email",
            "fullName",
            "canSeeBuyingPrice",
            "canSeeProfitMargin",
            "canSeeItemCost",
            "canPostPreviousDates",
            "canReversePurchaseInvoice",
            "canReverseSalesInvoice",
            "canReverseItemJournal",
            "canViewOnlyTheirSales",
            "notes",
            "createdAt",
            "updatedAt",
        ]
        read_only_fields = [
            "id",
            "userId",
            "username",
            "email",
            "fullName",
            "createdAt",
            "updatedAt",
        ]
