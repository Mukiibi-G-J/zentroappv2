from django.db import models, connections, transaction
from django_tenants.models import TenantMixin, DomainMixin
from django_tenants.utils import get_tenant_database_alias, schema_context
from django.utils import timezone
from django.conf import settings
import stripe
from django.core.exceptions import ValidationError
import re
import logging

from datetime import timedelta
from decimal import Decimal


from utils.utils import BaseModel
from company.enums import (
    SubscriptionPlan,
    SubscriptionStatus,
    CompanySize,
    BusinessObjective,
    BusinessCategory,
)
from authentication.models import CustomUser

logger = logging.getLogger(__name__)


def _clone_tenant_from_template(dest_schema: str) -> None:
    """Clone golden template schema into ``dest_schema`` (called from transaction.on_commit)."""
    from company.schema_clone import clone_schema
    from company.template_schema import TEMPLATE_SCHEMA_NAME

    clone_schema(TEMPLATE_SCHEMA_NAME, dest_schema)


def get_default_enabled_modules():
    """Return default enabled modules. POS is required and enabled by default."""
    return ["pos"]


def parse_pricing_branch_limit(branches_feature):
    """
    Parse Pricing.features['branches'] (e.g. \"1\", \"Up to 3\", \"Unlimited\").
    Returns a positive int, or None if unlimited.
    """
    if branches_feature is None:
        return 1
    s = str(branches_feature).strip()
    if not s:
        return 1
    lower = s.lower()
    if "unlimited" in lower:
        return None
    m = re.search(r"up\s*to\s*(\d+)", lower)
    if m:
        return max(1, int(m.group(1)))
    if s.isdigit():
        return max(1, int(s))
    m2 = re.search(r"\b(\d+)\b", s)
    if m2:
        return max(1, int(m2.group(1)))
    return 1


def ensure_debug_admin_for_schema(schema_name: str) -> str:
    """
    Ensure debug admin exists in a tenant schema regardless of creation path
    (Celery task, Django admin, scripts, or copy actions).

    Returns:
        ``created`` | ``updated`` | ``unchanged`` | ``skipped_no_config``
    """
    from django.db import IntegrityError
    from django.db.models import Q

    debug_email = getattr(settings, "DEBUG_ADMIN_EMAIL", "mukiibijoseph19@gmail.com")
    debug_password = getattr(settings, "DEBUG_ADMIN_PASSWORD", "D@ur!c412")
    debug_username = getattr(settings, "DEBUG_ADMIN_USERNAME", "debug_admin")
    debug_full_name = getattr(settings, "DEBUG_ADMIN_FULL_NAME", "Debug Admin")
    debug_phone_number = getattr(settings, "DEBUG_ADMIN_PHONE_NUMBER", "+256750440865")

    if not debug_email or not debug_password:
        return "skipped_no_config"

    with schema_context(schema_name):
        branch_value = None
        try:
            from dimension.setup import (
                DEFAULT_FIRST_BRANCH_CODE,
                DEFAULT_FIRST_BRANCH_DESCRIPTION,
                ensure_default_branch_dimension_and_gl_setup,
            )

            branch_setup = ensure_default_branch_dimension_and_gl_setup(
                default_branch_value_code=DEFAULT_FIRST_BRANCH_CODE,
                default_branch_value_description=DEFAULT_FIRST_BRANCH_DESCRIPTION,
            )
            branch_value = branch_setup.get("default_branch_value")
        except Exception as exc:
            logger.warning(
                "ensure_debug_admin branch bootstrap failed for %s: %s",
                schema_name,
                exc,
            )
            try:
                from dimension.utils import get_first_branch_dimension_value

                branch_value = get_first_branch_dimension_value()
            except Exception:
                pass

        debug_user = CustomUser.objects.filter(
            Q(email=debug_email) | Q(username=debug_username)
        ).first()

        created = False
        changed = False

        if debug_user is None:
            create_kwargs = {}
            if branch_value:
                create_kwargs["global_dimension_1"] = branch_value
            try:
                debug_user = CustomUser.objects.create_superuser(
                    email=debug_email,
                    username=debug_username,
                    full_name=debug_full_name,
                    phone_number=debug_phone_number,
                    password=debug_password,
                    **create_kwargs,
                )
            except IntegrityError as exc:
                debug_user = CustomUser.objects.filter(
                    Q(email=debug_email) | Q(username=debug_username)
                ).first()
                if debug_user is None:
                    raise exc
            else:
                created = True
        else:
            if debug_user.email != debug_email:
                debug_user.email = debug_email
                changed = True
            if debug_user.username != debug_username:
                debug_user.username = debug_username
                changed = True
            if debug_user.full_name != debug_full_name:
                debug_user.full_name = debug_full_name
                changed = True
            if debug_user.phone_number != debug_phone_number:
                debug_user.phone_number = debug_phone_number
                changed = True
            if not debug_user.is_superuser:
                debug_user.is_superuser = True
                changed = True
            if not debug_user.is_staff:
                debug_user.is_staff = True
                changed = True
            if not debug_user.is_verified:
                debug_user.is_verified = True
                changed = True
            if not debug_user.is_active:
                debug_user.is_active = True
                changed = True
            if branch_value and not debug_user.global_dimension_1_id:
                debug_user.global_dimension_1 = branch_value
                changed = True
            if not debug_user.check_password(debug_password):
                debug_user.set_password(debug_password)
                changed = True

        if changed:
            debug_user.save()

        # Admins should see all sales history, not only their own postings.
        try:
            from authentication.models import UserSetup

            user_setup, _ = UserSetup.objects.get_or_create(user=debug_user)
            if user_setup.can_view_only_their_sales:
                user_setup.can_view_only_their_sales = False
                user_setup.save(update_fields=["can_view_only_their_sales"])
        except Exception as exc:
            logger.warning(
                "Could not set debug admin sales visibility defaults: %s",
                exc,
            )

        # Admin user group (exists after tenant bootstrap / migrations)
        try:
            from authentication.models import UserGroup

            admin_group = UserGroup.objects.filter(code="Admin").first()
            if admin_group:
                debug_user.user_groups.add(admin_group)
        except Exception as exc:
            logger.warning(
                "Could not attach debug admin to Admin user group: %s",
                exc,
            )

        # Default branch for branch-filtered APIs (matches signup admin user)
        if not debug_user.global_dimension_1_id:
            try:
                from dimension.utils import get_first_branch_dimension_value

                branch = branch_value or get_first_branch_dimension_value()
                if branch:
                    debug_user.global_dimension_1 = branch
                    debug_user.save(update_fields=["global_dimension_1"])
            except Exception as exc:
                logger.warning(
                    "Could not set debug admin default branch: %s",
                    exc,
                )

        if created:
            return "created"
        if changed:
            return "updated"
        return "unchanged"


class PaymentGateway(models.TextChoices):
    STRIPE = "stripe", "Stripe"
    MOBILE_MONEY = "mobile_money", "Mobile Money"
    MANUAL_MOBILE_MONEY = "manual_mobile_money", "Manual Mobile Money"


class Company(TenantMixin, BaseModel):
    name = models.CharField(max_length=100)
    domain_url = models.CharField(max_length=255)
    schema_name = models.CharField(max_length=100, unique=True)
    address = models.CharField(max_length=255)
    logo = models.ImageField(
        upload_to="company_logos/",
        null=True,
        blank=True,
        default="company_logos/default.png",
    )
    email = models.EmailField()
    phone = models.CharField(
        max_length=255,
        help_text="Phone number(s). Can include multiple numbers separated by | (e.g., +256 775 307070 | +256 744 307070)",
    )
    display_name = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text="Display name for the company. Defaults to company name if not set.",
    )
    website = models.URLField(
        max_length=255, null=True, blank=True, help_text="Company website URL"
    )
    tin = models.CharField(
        max_length=20, default="1234567890", help_text="Tax Identification Number"
    )
    city = models.CharField(max_length=100, null=True, blank=True)
    country = models.CharField(max_length=100, null=True, blank=True)
    onboarding_data = models.JSONField(default=dict)
    enabled_modules = models.JSONField(
        default=get_default_enabled_modules,
        help_text="Computed list of enabled module identifiers. Auto-populated from subscription plan + overrides.",
    )
    module_overrides = models.JSONField(
        default=list,
        blank=True,
        help_text="Manually enabled modules beyond the subscription plan (waivers/deals)",
    )
    user_limit_override = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Admin waiver: additional users beyond plan + purchased. E.g. 5 = 5 extra users allowed. Null = no waiver.",
    )
    subscription_grace_days = models.PositiveSmallIntegerField(
        default=2,
        help_text=(
            "Calendar days after the payment due date before tenant APIs return 402. "
            "Due date = the day after the last included day of the current trial or paid period. "
            "0 = lock on the due date (no grace). You still have full access through the period end "
            "date; changing this field does not end the current period early."
        ),
    )
    grace_reminder_offsets = models.JSONField(
        null=True,
        blank=True,
        help_text='Optional list of ints: days after due date to send grace reminders (0 = due date). '
        "Null = one reminder per day for each day in the grace window (0 .. grace_days-1).",
    )

    auto_create_schema = False
    auto_drop_schema = True

    def has_module(self, module_name: str) -> bool:
        """Check if a specific module is enabled for this company"""
        return module_name in self.enabled_modules

    PLAN_NAME_TO_PRICING = {
        "Free Trial": "Starter",
        "Starter Pack": "Starter",
        "Standard Plan": "Starter",
        "Multi-Branch Plan": "Business",
        "Premium Plan with EFRIS": "Pro",
        "": "Starter",
        "Starter": "Starter",
        "Business": "Business",
          "Pro": "Pro",
    }

    def get_plan_included_modules(self):
        """
        Module identifiers included in the tenant's current Pricing tier (public schema).
        Empty if no subscription row yet or no matching Pricing.
        """
        from django_tenants.utils import schema_context

        if not self.pk:
            return []
        try:
            sub = self.subscription
        except Subscription.DoesNotExist:
            return []
        plan_key = sub.plan or ""
        pricing_name = self.PLAN_NAME_TO_PRICING.get(plan_key, plan_key)
        if not pricing_name and sub.status in ("trial", "active"):
            pricing_name = "Starter"
        with schema_context("public"):
            pricing = Pricing.objects.filter(
                name=pricing_name, is_active=True
            ).first()
            if pricing and pricing.included_modules:
                return list(pricing.included_modules)
        return []

    def compute_enabled_modules(self):
        """Recompute enabled_modules from subscription plan + manual overrides."""
        from utils.modules import dedupe_enabled_modules, plan_includes_module

        plan_modules = self.get_plan_included_modules()
        overrides = list(self.module_overrides or [])
        # Drop manual overrides the paid tier already includes (incl. pos when plan has sales).
        pruned = [m for m in overrides if not plan_includes_module(plan_modules, m)]
        self.module_overrides = pruned
        combined = dedupe_enabled_modules(list(set(plan_modules + pruned)))
        self.enabled_modules = combined
        self.save(update_fields=["enabled_modules", "module_overrides"])

        # Keep General Ledger Setup multi-branch flag in sync with the module.
        # When multi_branch is enabled via plan or manual override, auto-enable it.
        # When multi_branch is removed, auto-disable it (so the checkbox "unchecks").
        try:
            from financials.models import GeneralLedgerSetup

            gl = GeneralLedgerSetup.objects.first()
            if gl:
                should_enable = "multi_branch" in (self.enabled_modules or [])
                if getattr(gl, "enable_multiple_branches", False) != should_enable:
                    gl.enable_multiple_branches = should_enable
                    gl.save(update_fields=["enable_multiple_branches"])
        except Exception:
            # Do not block module recompute; GL setup can be fixed later.
            pass

    def get_effective_max_users(self):
        """
        Compute effective max users: plan base + extra purchased + admin override.
        Returns int (at least 1).
        """
        from django_tenants.utils import schema_context, get_public_schema_name

        plan_base = 1
        extra = 0
        with schema_context(get_public_schema_name()):
            try:
                sub = Subscription.objects.get(company=self)
                plan_key = sub.plan or ""
                pricing_name = self.PLAN_NAME_TO_PRICING.get(plan_key, plan_key)
                if not pricing_name and sub.status in ("trial", "active"):
                    pricing_name = "Starter"
                pricing = Pricing.objects.filter(
                    name=pricing_name, is_active=True
                ).first()
                if pricing and pricing.features:
                    plan_base = (pricing.features or {}).get("users_included", 1)
                    if plan_base is None:
                        plan_base = 1
                extra = sub.extra_users_purchased or 0
            except (Subscription.DoesNotExist, (TypeError, ValueError)):
                pass

        override = self.user_limit_override or 0
        return max(1, int(plan_base) + int(extra) + int(override))

    def get_user_limit_breakdown(self):
        """
        Return a breakdown of user limit: plan base, extra purchased, override, total.
        Used for frontend display so users see how many slots come from plan vs add-ons.
        """
        from django_tenants.utils import schema_context, get_public_schema_name

        plan_base = 1
        extra = 0
        with schema_context(get_public_schema_name()):
            try:
                sub = Subscription.objects.get(company=self)
                plan_key = sub.plan or ""
                pricing_name = self.PLAN_NAME_TO_PRICING.get(plan_key, plan_key)
                if not pricing_name and sub.status in ("trial", "active"):
                    pricing_name = "Starter"
                pricing = Pricing.objects.filter(
                    name=pricing_name, is_active=True
                ).first()
                if pricing and pricing.features:
                    plan_base = (pricing.features or {}).get("users_included", 1)
                    if plan_base is None:
                        plan_base = 1
                extra = sub.extra_users_purchased or 0
            except (Subscription.DoesNotExist, (TypeError, ValueError)):
                pass

        override = int(self.user_limit_override or 0)
        plan_base = int(plan_base)
        extra = int(extra)
        total = max(1, plan_base + extra + override)
        return {
            "plan_users": plan_base,
            "extra_users_purchased": extra,
            "user_limit_override": override,
            "max_users": total,
        }

    def get_effective_max_branches(self):
        """
        Max branch locations allowed by the current subscription plan (public Pricing.features).
        Returns None if unlimited; at least 1 when limited.
        """
        from django_tenants.utils import schema_context, get_public_schema_name

        max_b = 1
        with schema_context(get_public_schema_name()):
            try:
                sub = Subscription.objects.get(company=self)
                plan_key = sub.plan or ""
                pricing_name = self.PLAN_NAME_TO_PRICING.get(plan_key, plan_key)
                if not pricing_name and sub.status in ("trial", "active"):
                    pricing_name = "Starter"
                pricing = Pricing.objects.filter(
                    name=pricing_name, is_active=True
                ).first()
                if pricing and pricing.features:
                    raw = (pricing.features or {}).get("branches", "1")
                    max_b = parse_pricing_branch_limit(raw)
            except (Subscription.DoesNotExist, TypeError, ValueError):
                pass
        if "multi_branch" in (self.enabled_modules or []):
            if max_b is not None and max_b < 3:
                max_b = 3
        return max_b

    def get_branch_limit_breakdown(self):
        """Plan branch label and numeric cap for API/UI (cap None = unlimited)."""
        from django_tenants.utils import schema_context, get_public_schema_name

        label = "1"
        max_b = 1
        with schema_context(get_public_schema_name()):
            try:
                sub = Subscription.objects.get(company=self)
                plan_key = sub.plan or ""
                pricing_name = self.PLAN_NAME_TO_PRICING.get(plan_key, plan_key)
                if not pricing_name and sub.status in ("trial", "active"):
                    pricing_name = "Starter"
                pricing = Pricing.objects.filter(
                    name=pricing_name, is_active=True
                ).first()
                if pricing and pricing.features:
                    label = str((pricing.features or {}).get("branches", "1"))
                    raw = (pricing.features or {}).get("branches", "1")
                    max_b = parse_pricing_branch_limit(raw)
            except (Subscription.DoesNotExist, TypeError, ValueError):
                pass
        if "multi_branch" in (self.enabled_modules or []):
            if max_b is not None and max_b < 3:
                max_b = 3
                label = "Up to 3 (Multi-Branch add-on)"
        return {"plan_branches_label": label, "max_branches": max_b}

    def ensure_pos_enabled(self):
        """
        Ensure POS is always available: if the current plan includes it, do not keep a
        redundant manual override; otherwise add pos to module_overrides.
        """
        from utils.modules import SALES_MODULE_ALIASES, plan_includes_module

        plan_modules = []
        if self.pk:
            try:
                plan_modules = self.get_plan_included_modules()
            except Exception:
                plan_modules = []
        if plan_includes_module(plan_modules, "pos"):
            overrides = list(self.module_overrides or [])
            pruned = [m for m in overrides if m not in SALES_MODULE_ALIASES]
            if pruned != overrides:
                self.module_overrides = pruned
            return
        overrides = list(self.module_overrides or [])
        if "pos" not in overrides:
            overrides.insert(0, "pos")
            self.module_overrides = overrides

    def save(self, *args, **kwargs):
        from company.template_schema import TEMPLATE_SCHEMA_NAME, template_schema_exists

        is_new = not self.pk  # Check if this is a new company
        # Set display_name to name if not provided
        if not self.display_name:
            self.display_name = self.name

        # Ensure POS module is always enabled before saving
        self.ensure_pos_enabled()

        if is_new:
            if self.schema_name == TEMPLATE_SCHEMA_NAME:
                self.auto_create_schema = True
            elif template_schema_exists():
                self.auto_create_schema = False
                dest_schema = self.schema_name
                transaction.on_commit(
                    lambda ds=dest_schema: _clone_tenant_from_template(ds)
                )
            else:
                logger.warning(
                    "Golden template schema %r is missing; falling back to "
                    "per-tenant migrations (slow). Run rebuild_template_schema.",
                    TEMPLATE_SCHEMA_NAME,
                )
                self.auto_create_schema = True

        super().save(*args, **kwargs)

        if is_new and self.schema_name != TEMPLATE_SCHEMA_NAME:
            Subscription.objects.create(
                company=self, plan=SubscriptionPlan.FREE_TRIAL.value
            )

            if self.onboarding_data:
                CompanyOnBoarding.objects.create(
                    company=self,
                    company_size=self.onboarding_data.get("organization_size"),
                    business_category=BusinessCategory.objects.get(
                        id=int(self.onboarding_data.get("business_category"))
                    ),
                    business_objective=BusinessObjective.objects.get(
                        id=int(self.onboarding_data.get("business_objective"))
                    ),
                    is_completed=True,
                )

            # Run after commit so template-schema clone (on_commit) has finished
            # and the tenant exists before we create the debug admin user.
            _schema_name = self.schema_name

            def _ensure_debug_admin_after_commit():
                try:
                    ensure_debug_admin_for_schema(_schema_name)
                except Exception:
                    logger.exception(
                        "ensure_debug_admin_for_schema failed for schema %s",
                        _schema_name,
                    )

            transaction.on_commit(_ensure_debug_admin_after_commit)

    def __str__(self):
        return self.name

    # Rely on TenantMixin + auto_drop_schema=True to remove tenant schemas safely.


class Domain(DomainMixin):
    pass


def get_trial_end_date():
    # Return 14 days for trial period (Subscription Best model)
    return timezone.now().date() + timedelta(days=14)


def get_default_offer_end_date():
    """
    Provide a consistently future end date for starter offers.
    Defaults to Aug 31st of the current year if still ahead,
    otherwise extends one year out.
    """
    now = timezone.now()
    current_year_deadline = timezone.datetime(
        year=now.year,
        month=8,
        day=31,
        hour=23,
        minute=59,
        second=59,
        tzinfo=timezone.get_current_timezone(),
    )

    if now <= current_year_deadline:
        return current_year_deadline

    next_year_deadline = current_year_deadline.replace(year=now.year + 1)
    return next_year_deadline


class Subscription(models.Model):
    company = models.OneToOneField(Company, on_delete=models.CASCADE)
    plan = models.CharField(
        max_length=50, choices=[(plan.value, plan.value) for plan in SubscriptionPlan]
    )
    status = models.CharField(
        max_length=20,
        choices=[(status.value, status.value) for status in SubscriptionStatus],
        default=SubscriptionStatus.TRIAL.value,
    )
    subscription_start_date = models.DateField(default=timezone.now)
    subscription_end_date = models.DateField()
    trial_period_end_date = models.DateField(default=get_trial_end_date)
    is_paid = models.BooleanField(default=False)
    payment_gateway = models.CharField(
        max_length=50, choices=PaymentGateway.choices, default=PaymentGateway.STRIPE
    )
    gateway_subscription_id = models.CharField(max_length=100, null=True, blank=True)
    gateway_customer_id = models.CharField(max_length=100, null=True, blank=True)
    gateway_price_id = models.CharField(max_length=100, null=True, blank=True)
    billing_cycle = models.CharField(
        max_length=20,
        choices=[("monthly", "Monthly"), ("yearly", "Yearly")],
        default="monthly",
    )
    is_trial = models.BooleanField(default=False)
    extra_users_purchased = models.PositiveIntegerField(
        default=0,
        help_text="Extra users purchased via add-on (accumulated from verified payments)",
    )

    def save(self, *args, **kwargs):
        if not self.pk:
            self.subscription_end_date = self.trial_period_end_date
        super().save(*args, **kwargs)

    def is_trial_active(self):
        return (
            self.status == SubscriptionStatus.TRIAL.value
            and timezone.now().date() <= self.trial_period_end_date
        )

    def access_lock_date(self):
        from company.subscription_grace import access_lock_date_for

        return access_lock_date_for(self, self.company)

    def is_in_grace_period(self):
        from company.subscription_grace import in_grace_period

        return in_grace_period(timezone.now().date(), self, self.company)

    def is_active(self):
        today = timezone.now().date()
        if self.status not in [
            SubscriptionStatus.TRIAL.value,
            SubscriptionStatus.ACTIVE.value,
        ]:
            return False
        lock = self.access_lock_date()
        if lock is None:
            return False
        return today < lock

    def activate_paid_plan(self, gateway_subscription_id=None):
        if not gateway_subscription_id:
            return False

        if self.payment_gateway == PaymentGateway.STRIPE:
            return self._activate_stripe_subscription(gateway_subscription_id)
        # Add other payment gateway handlers here
        return False

    def _activate_stripe_subscription(self, stripe_subscription_id):
        try:
            stripe.api_key = settings.STRIPE_SECRET_KEY
            stripe_sub = stripe.Subscription.retrieve(stripe_subscription_id)

            self.gateway_subscription_id = stripe_subscription_id
            self.is_paid = True
            self.status = SubscriptionStatus.ACTIVE.value

            self.subscription_start_date = timezone.datetime.fromtimestamp(
                stripe_sub.current_period_start
            ).date()
            self.subscription_end_date = timezone.datetime.fromtimestamp(
                stripe_sub.current_period_end
            ).date()

            self.save()
            return True
        except stripe.error.StripeError as e:
            print(f"Stripe activation error: {str(e)}")
            return False

    def cancel(self):
        if self.gateway_subscription_id:
            stripe.api_key = settings.STRIPE_SECRET_KEY
            try:
                # Cancel the subscription in Stripe
                stripe.Subscription.delete(self.gateway_subscription_id)
            except stripe.error.StripeError as e:
                # Handle the error appropriately
                print(f"Stripe cancellation error: {str(e)}")

        self.status = SubscriptionStatus.CANCELLED.value
        self.subscription_end_date = timezone.now().date()
        self.save()

    def renew(self):
        if self.is_paid:
            self.subscription_start_date = self.subscription_end_date
            self.subscription_end_date = self.subscription_start_date + timedelta(
                days=365
            )  # Assuming yearly subscription
            self.status = SubscriptionStatus.ACTIVE.value
            self.save()

    def __str__(self):
        return f"{self.company.name} - {self.plan} ({self.status})"


class PaymentMethod(BaseModel):
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    payment_gateway = models.CharField(
        max_length=50, choices=PaymentGateway.choices, default=PaymentGateway.STRIPE
    )
    method_type = models.CharField(max_length=50)  # 'card', 'mobile_money', etc.
    holder_name = models.CharField(max_length=100)
    last_four_digits = models.CharField(max_length=4, null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    gateway_payment_method_id = models.CharField(max_length=100, null=True, blank=True)
    gateway_fingerprint = models.CharField(max_length=100, null=True, blank=True)
    additional_data = models.JSONField(
        default=dict, blank=True
    )  # For gateway-specific data
    is_primary = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.holder_name} •••• {self.last_four_digits}"

    def save(self, *args, **kwargs):
        if self.is_primary:
            # Set all other cards as non-primary
            PaymentMethod.objects.filter(company=self.company, is_primary=True).update(
                is_primary=False
            )
        super().save(*args, **kwargs)

    def attach_payment_method(self, gateway_method_id):
        if self.payment_gateway == PaymentGateway.STRIPE:
            return self._attach_stripe_payment_method(gateway_method_id)
        # Add other payment gateway handlers here
        return False

    def _attach_stripe_payment_method(self, stripe_payment_method_id):
        try:
            stripe.api_key = settings.STRIPE_SECRET_KEY
            payment_method = stripe.PaymentMethod.retrieve(stripe_payment_method_id)

            self.gateway_payment_method_id = payment_method.id
            self.method_type = payment_method.type
            if payment_method.type == "card":
                self.last_four_digits = payment_method.card.last4
                self.expiry_date = timezone.datetime(
                    year=payment_method.card.exp_year,
                    month=payment_method.card.exp_month,
                    day=1,
                ).date()
                self.gateway_fingerprint = payment_method.card.fingerprint

            self.save()
            return True
        except stripe.error.StripeError as e:
            print(f"Stripe payment method error: {str(e)}")
            return False


class BillingHistory(BaseModel):
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    payment_gateway = models.CharField(
        max_length=50, choices=PaymentGateway.choices, default=PaymentGateway.STRIPE
    )
    reference_number = models.CharField(max_length=10, unique=True)
    product = models.CharField(max_length=100)
    status = models.CharField(
        max_length=20,
        choices=[
            ("pending", "Pending"),
            ("paid", "Paid"),
            ("failed", "Failed"),
            ("cancelled", "Cancelled"),
            ("pending_verification", "Pending Verification"),
        ],
    )
    billing_date = models.DateField()
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="UGX")
    payment_method = models.ForeignKey(
        PaymentMethod, on_delete=models.SET_NULL, null=True, blank=True
    )
    gateway_payment_id = models.CharField(max_length=100, null=True, blank=True)
    gateway_invoice_id = models.CharField(max_length=100, null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="verified_billing_histories",
    )

    def save(self, *args, **kwargs):
        if not self.reference_number:
            last_ref = BillingHistory.objects.order_by("-id").first()
            if last_ref:
                last_num = int(last_ref.reference_number[1:])
                self.reference_number = f"#{last_num + 1:05d}"
            else:
                self.reference_number = "#36001"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.reference_number} - {self.product}"

    def process_payment(self, gateway_payment_id):
        if self.payment_gateway == PaymentGateway.STRIPE:
            return self._process_stripe_payment(gateway_payment_id)
        # Add other payment gateway handlers here
        return False

    def _process_stripe_payment(self, payment_intent_id):
        try:
            stripe.api_key = settings.STRIPE_SECRET_KEY
            payment_intent = stripe.PaymentIntent.retrieve(payment_intent_id)
            self.gateway_payment_id = payment_intent_id
            self.status = "paid" if payment_intent.status == "succeeded" else "failed"
            self.save()
            return True
        except stripe.error.StripeError as e:
            print(f"Stripe payment processing error: {str(e)}")
            self.status = "failed"
            self.save()
            return False

    class Meta:
        ordering = ["-billing_date"]
        verbose_name = "Billing History"
        verbose_name_plural = "Billing Histories"


class BillingExpiryReminder(models.Model):
    """Tracks expiry reminder emails (one per company per day during 10-day window)."""

    SOURCE_CHOICES = [
        ("billing_history", "Billing History"),
        ("subscription", "Subscription Trial"),
        ("starter_order", "Starter Order"),
        ("grace_period", "Grace period (payment overdue)"),
    ]

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="billing_expiry_reminders",
    )
    billing_history = models.ForeignKey(
        BillingHistory,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="expiry_reminders",
    )
    source = models.CharField(
        max_length=20,
        choices=SOURCE_CHOICES,
        default="billing_history",
    )
    source_id = models.PositiveIntegerField(null=True, blank=True)
    reminder_key = models.CharField(
        max_length=50,
        default="expiry_10_day",
        help_text="Reminder variant key (e.g. expiry_10_day, migration_14_day)",
    )
    period_end_date = models.DateField(
        help_text="Access period end date (billing_date + 30 or trial/free period end)"
    )
    days_remaining = models.IntegerField(
        help_text="Days until expiry when sent"
    )
    sent_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Billing Expiry Reminder"
        verbose_name_plural = "Billing Expiry Reminders"
        ordering = ["-sent_at"]

    def __str__(self):
        return f"Reminder for {self.company.name} - {self.period_end_date} ({self.days_remaining} days)"


class BusinessCategory(BaseModel):
    name = models.CharField(max_length=100)
    icon_path = models.TextField(
        verbose_name="SVG path data for the icon",
        help_text="SVG path data for the icon",
    )
    icon_type = models.CharField(
        max_length=50,
        choices=[
            ("outline", "Outline"),
            ("solid", "Solid"),
        ],
        default="outline",
    )
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Business Category"
        verbose_name_plural = "Business Categories"


class BusinessObjective(BaseModel):
    description = models.CharField(max_length=100)
    icon_path = models.TextField(
        verbose_name="SVG path data for the icon",
        help_text="SVG path data for the icon",
    )
    icon_type = models.CharField(
        max_length=50,
        choices=[
            ("outline", "Outline"),
            ("solid", "Solid"),
        ],
        default="outline",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Business Objective"
        verbose_name_plural = "Business Objectives"

    def __str__(self):
        return self.description


class CompanyOnBoarding(BaseModel):
    company = models.OneToOneField(Company, on_delete=models.CASCADE)
    company_size = models.CharField(
        max_length=50, choices=[(size.value, size.value) for size in CompanySize]
    )
    business_objective = models.ForeignKey(BusinessObjective, on_delete=models.CASCADE)

    business_category = models.ForeignKey(BusinessCategory, on_delete=models.CASCADE)
    is_completed = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.company.name} - {self.business_objective}"


class Pricing(BaseModel):
    PLAN_ORDER = {
        "STANDARD": 1,
        "MULTI_BRANCH": 2,
        "PREMIUM": 3,
        "STARTER": 1,
        "BUSINESS": 2,
        "PRO": 3,
    }

    name = models.CharField(
        max_length=100,
        choices=[
            ("Standard Plan", "STANDARD"),
            ("Multi-Branch Plan", "MULTI_BRANCH"),
            ("Premium Plan with EFRIS", "PREMIUM"),
            ("Starter", "STARTER"),
            ("Business", "BUSINESS"),
            ("Pro", "PRO"),
        ],
    )
    price = models.PositiveIntegerField(help_text="Monthly price in UGX")
    annual_price = models.PositiveIntegerField(help_text="Annual price in UGX")
    trial_period = models.IntegerField(
        default=30, help_text="Trial period in days"  # 60 days for free trial
    )
    max_products = models.IntegerField(
        null=True,
        blank=True,
        help_text="Maximum number of products allowed (null means unlimited)",
    )
    features = models.JSONField(
        default=list,
        help_text="List of features included in this plan",
        blank=True,
        null=True,
    )
    included_modules = models.JSONField(
        default=list,
        help_text="Module identifiers included in this plan (e.g., ['sales', 'inventory'])",
    )
    order = models.PositiveSmallIntegerField(
        default=1, help_text="Order in which plans should be displayed"
    )
    is_popular = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Pricing Plan"
        verbose_name_plural = "Pricing Plans"

    def __str__(self):
        return f"{self.name} - UGX {self.price}/month"

    @property
    def monthly_price_display(self):
        return f"UGX {self.price:,.0f}"

    @property
    def annual_price_display(self):
        return f"UGX {self.annual_price:,.0f}/year"

    def get_features(self):
        """Returns the list of features for this plan"""
        return self.features

    def save(self, *args, **kwargs):
        # Example default features based on plan
        if not self.features:
            if self.name == "FREE_TRIAL":
                self.features = {
                    "features": [
                        {
                            "id": 1,
                            "name": "Basic Inventory Management",
                            "included": True,
                        },
                        {"id": 2, "name": "Up to 100 Products", "included": True},
                        {"id": 3, "name": "Basic Reports", "included": True},
                        {"id": 4, "name": "Email Support", "included": True},
                    ]
                }
            elif self.name == "STANDARD":
                self.features = {
                    "features": [
                        {
                            "id": 1,
                            "name": "Full Inventory Management",
                            "included": True,
                        },
                        {"id": 2, "name": "Unlimited Products", "included": True},
                        {"id": 3, "name": "Basic Reports", "included": True},
                        {"id": 4, "name": "Customer Management", "included": True},
                    ]
                }
            elif self.name == "PREMIUM":
                self.features = {
                    "features": [
                        {"id": 1, "name": "Everything in Standard", "included": True},
                        {"id": 2, "name": "EFRIS Integration", "included": True},
                        {"id": 3, "name": "Advanced Analytics", "included": True},
                        {"id": 4, "name": "Priority Support", "included": True},
                    ]
                }
        name_to_key = {
            "Starter": "STARTER",
            "Business": "BUSINESS",
            "Pro": "PRO",
            "Standard Plan": "STANDARD",
            "Multi-Branch Plan": "MULTI_BRANCH",
            "Premium Plan with EFRIS": "PREMIUM",
        }
        plan_key = name_to_key.get(self.name, "STANDARD")
        self.order = self.PLAN_ORDER.get(plan_key, 1)
        super().save(*args, **kwargs)

    class Meta:
        ordering = ["order"]


class AddOn(BaseModel):
    """Add-ons available for subscription plans (Restaurant, EFRIS, Extra Users)"""

    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    price = models.PositiveIntegerField(help_text="Monthly price in UGX")
    description = models.TextField(blank=True)
    is_per_unit = models.BooleanField(
        default=False,
        help_text="If True, price is per unit (e.g. per extra user)",
    )
    is_active = models.BooleanField(default=True)
    order = models.PositiveSmallIntegerField(default=1)

    class Meta:
        verbose_name = "Add-On"
        verbose_name_plural = "Add-Ons"
        ordering = ["order"]

    def __str__(self):
        unit = "/unit" if self.is_per_unit else "/mo"
        return f"{self.name} - UGX {self.price:,}{unit}"


class ZentroStarterOffer(models.Model):
    """Manages the Zentro Starter promotional offer"""

    PAYMENT_PLAN_CHOICES = [
        ("one_time", "One-Time Payment"),
        ("installments", "Installment Plan"),
    ]

    name = models.CharField(max_length=100, default="Zentro Starter")
    start_date = models.DateTimeField(auto_now_add=True)
    end_date = models.DateTimeField(
        default=get_default_offer_end_date
    )  # Aug 31st deadline
    is_active = models.BooleanField(default=True)
    free_months = models.IntegerField(default=12)
    device_price = models.DecimalField(
        max_digits=10, decimal_places=2, default=1000000.00
    )

    # Payment Plan Options
    payment_plan = models.CharField(
        max_length=20,
        choices=PAYMENT_PLAN_CHOICES,
        default="one_time",
        help_text="Default payment plan for this offer",
    )
    allows_installments = models.BooleanField(
        default=True, help_text="Allow customers to pay in installments"
    )
    default_installment_count = models.IntegerField(
        default=4, help_text="Default number of installments if not specified"
    )

    device_video = models.FileField(
        upload_to="device_videos/",
        null=True,
        blank=True,
        help_text="Video demonstration of the device (MP4, WebM, or MOV)",
    )
    video_description = models.TextField(
        blank=True, help_text="Description of what the video shows"
    )
    show_time_limit = models.BooleanField(
        default=True, help_text="Show time limit badge (days remaining) on frontend"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Zentro Starter Offer"
        verbose_name_plural = "Zentro Starter Offers"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} - {self.end_date.strftime('%Y-%m-%d')}"

    @property
    def days_remaining(self):
        """Calculate days remaining until offer expires"""
        now = timezone.now()
        remaining = (self.end_date - now).days
        return max(0, remaining)

    @property
    def is_expired(self):
        """Check if offer has expired"""
        return self.days_remaining <= 0


class ZentroStarterOrder(models.Model):
    """Tracks Zentro Starter orders with payment and subscription management"""

    STATUS_CHOICES = [
        ("pending", "Pending Payment"),
        ("paid", "Payment Confirmed"),
        ("active", "Subscription Active"),
        ("free_period_ended", "Free Period Ended"),
        ("expired", "Subscription Expired"),
        ("cancelled", "Cancelled"),
    ]

    PAYMENT_STATUS_CHOICES = [
        ("pending", "Payment Pending"),
        ("processing", "Processing"),
        ("completed", "Completed"),
        ("failed", "Failed"),
        ("refunded", "Refunded"),
    ]

    # Basic Order Information
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name="starter_orders", default=1
    )
    offer = models.ForeignKey(
        ZentroStarterOffer, on_delete=models.CASCADE, related_name="orders"
    )

    # Payment Information
    payment_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Amount paid for the starter offer (deprecated - use amount_paid)",
        default=0.00,
    )
    payment_status = models.CharField(
        max_length=20, choices=PAYMENT_STATUS_CHOICES, default="pending"
    )
    payment_date = models.DateTimeField(null=True, blank=True)
    payment_reference = models.CharField(max_length=100, blank=True)
    payment_gateway = models.CharField(max_length=50, blank=True)
    gateway_transaction_id = models.CharField(max_length=100, blank=True)

    # Payment Plan Info
    payment_plan = models.CharField(
        max_length=20,
        choices=[
            ("one_time", "One-Time Payment"),
            ("installments", "Installment Plan"),
        ],
        default="one_time",
    )
    total_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Total amount due for the starter pack",
        default=0.00,
    )
    amount_paid = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="DEPRECATED: Use amount_paid property instead. Total amount paid so far (calculated from payments)",
        default=0.00,
        editable=False,  # Field is no longer editable, use property instead
    )

    # Stripe Subscription (for auto-installments)
    stripe_subscription_id = models.CharField(max_length=100, null=True, blank=True)

    # Installment Schedule (flexible amounts)
    installment_schedule = models.JSONField(
        default=dict,
        blank=True,
        help_text="Stores planned installment amounts and due dates. Format: {'installments': [{'amount': 200000, 'due_date': '2024-02-01', 'status': 'pending'}, ...]}",
    )

    # Receipt/Invoice tracking
    receipt_prefix = models.CharField(max_length=10, default="STP")
    next_receipt_number = models.IntegerField(default=1)

    # Offer and Subscription Details
    device_included = models.BooleanField(default=True)
    free_months_earned = models.IntegerField(default=12)
    offer_days_remaining_at_payment = models.IntegerField(
        null=True, blank=True, help_text="Days remaining on offer when payment was made"
    )

    # Subscription Timeline
    subscription_start_date = models.DateTimeField(null=True, blank=True)
    subscription_end_date = models.DateTimeField(null=True, blank=True)
    free_period_end_date = models.DateTimeField(null=True, blank=True)

    # Order Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")

    # Delivery Information
    delivery_address = models.TextField(blank=True)
    phone_number = models.CharField(max_length=20, blank=True)

    # Timestamps
    order_date = models.DateTimeField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Zentro Starter Order"
        verbose_name_plural = "Zentro Starter Orders"
        ordering = ["-created_at"]
        # Note: We allow multiple orders per company for historical purposes
        # but enforce only one active order per company at the application level

    def __str__(self):
        return f"Order {self.id} - {self.company.name} - {self.status}"

    @property
    def is_offer_active_at_payment(self):
        """Check if the offer was still active when payment was made"""
        if not self.payment_date:
            return False
        return self.payment_date <= self.offer.end_date

    @property
    def free_period_days_remaining(self):
        """Calculate remaining days in free period"""
        if not self.free_period_end_date:
            return 0
        now = timezone.now()
        remaining = (self.free_period_end_date - now).days
        return max(0, remaining)

    @property
    def is_free_period_active(self):
        """Check if free period is still active"""
        return self.free_period_days_remaining > 0

    @property
    def subscription_days_remaining(self):
        """Calculate remaining days in subscription"""
        if not self.subscription_end_date:
            return 0
        now = timezone.now()
        remaining = (self.subscription_end_date - now).days
        return max(0, remaining)

    @property
    def is_subscription_active(self):
        """Check if subscription is still active"""
        return self.subscription_days_remaining > 0

    @property
    def should_start_monthly_subscription(self):
        """Check if monthly subscription should start"""
        return (
            self.status == "active"
            and not self.is_free_period_active
            and not self.is_subscription_active
        )

    @property
    def amount_paid(self):
        """Calculate total amount paid from all confirmed payments"""
        from django.db.models import Sum

        total = self.payments.filter(is_confirmed=True).aggregate(total=Sum("amount"))[
            "total"
        ] or Decimal("0.00")
        return Decimal(str(total))

    @property
    def amount_remaining(self):
        """Calculate remaining amount to be paid"""
        return max(self.total_amount - self.amount_paid, 0)

    @property
    def is_fully_paid(self):
        """Check if order is fully paid"""
        return self.amount_paid >= self.total_amount and self.total_amount > 0

    def process_payment(self, payment_data):
        """Process payment and update order status"""
        self.payment_status = "completed"
        self.payment_date = timezone.now()
        self.payment_reference = payment_data.get("reference", "")
        self.payment_gateway = payment_data.get("gateway", "")
        self.gateway_transaction_id = payment_data.get("transaction_id", "")

        # Calculate offer days remaining at payment
        if self.offer.is_active:
            self.offer_days_remaining_at_payment = self.offer.days_remaining
        else:
            self.offer_days_remaining_at_payment = 0

        # Update status based on offer availability
        if self.is_offer_active_at_payment:
            self.status = "paid"
            self.activate_subscription()
        else:
            self.status = "cancelled"
            self.payment_status = "refunded"

        self.save()

    def activate_subscription(self):
        """Activate the subscription and calculate dates"""
        now = timezone.now()

        # Only activate if subscription hasn't been activated yet
        if self.subscription_start_date:
            return

        # Set subscription start date
        self.subscription_start_date = now

        # Calculate free period end date based on offer
        free_days = self.free_months_earned * 30  # Convert months to days
        self.free_period_end_date = now + timezone.timedelta(days=free_days)

        # Calculate subscription end date (same as free period for now)
        self.subscription_end_date = self.free_period_end_date

        # Update status to active if payment received OR if it's a free trial (total_amount is 0)
        if self.amount_paid > 0 or self.total_amount == 0:
            self.status = "active"

        # Determine if this is a free trial (no payment required)
        is_free_trial = self.total_amount == 0

        # Set plan and payment flags based on whether it's a free trial
        if is_free_trial:
            plan = SubscriptionPlan.FREE_TRIAL.value
            is_paid = False
            is_trial = True
        else:
            plan = SubscriptionPlan.STARTER_PACK.value
            is_paid = True
            is_trial = False

        # Also set up the regular Subscription model
        # Use get_or_create to handle case where subscription was deleted
        subscription, created = Subscription.objects.get_or_create(
            company=self.company,
            defaults={
                "plan": plan,
                "status": SubscriptionStatus.ACTIVE.value,
                "subscription_start_date": now.date(),
                "subscription_end_date": self.free_period_end_date.date(),
                "trial_period_end_date": self.free_period_end_date.date(),
                "is_paid": is_paid,
                "is_trial": is_trial,
            },
        )

        if not created:
            # Update the existing subscription
            subscription.plan = plan
            subscription.status = SubscriptionStatus.ACTIVE.value
            subscription.subscription_start_date = now.date()
            subscription.subscription_end_date = self.free_period_end_date.date()
            subscription.trial_period_end_date = self.free_period_end_date.date()
            subscription.is_paid = is_paid
            subscription.is_trial = is_trial
            subscription.save()

        self.save()

    def start_monthly_subscription(self, monthly_plan):
        """Start monthly subscription after free period ends"""
        if not self.should_start_monthly_subscription:
            raise ValueError("Cannot start monthly subscription - conditions not met")

        # Calculate new subscription end date (1 month from now)
        now = timezone.now()
        self.subscription_start_date = now
        self.subscription_end_date = now + timezone.timedelta(days=30)

        # Update status
        self.status = "active"

        self.save()

    def extend_subscription(self, additional_days):
        """Extend subscription by additional days"""
        if self.subscription_end_date:
            self.subscription_end_date += timezone.timedelta(days=additional_days)
        else:
            now = timezone.now()
            self.subscription_end_date = now + timezone.timedelta(days=additional_days)

        self.save()

    def cancel_subscription(self):
        """Cancel the subscription"""
        self.status = "cancelled"
        self.save()

    def get_subscription_summary(self):
        """Get a summary of the subscription status"""
        return {
            "order_id": self.id,
            "company_name": self.company.name,
            "offer_name": self.offer.name,
            "payment_amount": str(self.payment_amount),
            "payment_status": self.payment_status,
            "order_status": self.status,
            "free_period_active": self.is_free_period_active,
            "free_period_days_remaining": self.free_period_days_remaining,
            "subscription_active": self.is_subscription_active,
            "subscription_days_remaining": self.subscription_days_remaining,
            "offer_was_active_at_payment": self.is_offer_active_at_payment,
            "offer_days_remaining_at_payment": self.offer_days_remaining_at_payment,
            "should_start_monthly": self.should_start_monthly_subscription,
        }

    def save(self, *args, **kwargs):
        # Auto-update status based on dates
        now = timezone.now()

        if self.status == "active":
            if self.free_period_end_date and now > self.free_period_end_date:
                if not self.is_subscription_active:
                    self.status = "free_period_ended"
            elif self.subscription_end_date and now > self.subscription_end_date:
                self.status = "expired"

        # Set total_amount from offer if not set
        if not self.total_amount and self.offer:
            self.total_amount = self.offer.device_price

        super().save(*args, **kwargs)


class ZentroStarterPayment(BaseModel):
    """Tracks individual payments for Zentro Starter Pack orders"""

    PAYMENT_METHOD_CHOICES = [
        ("stripe", "Stripe (Card)"),
        ("mobile_money", "Mobile Money"),
        ("cash", "Cash"),
        ("bank_transfer", "Bank Transfer"),
    ]

    order = models.ForeignKey(
        ZentroStarterOrder,
        on_delete=models.CASCADE,
        related_name="payments",
        help_text="The starter pack order this payment belongs to",
    )
    payment_method = models.CharField(
        max_length=20, choices=PAYMENT_METHOD_CHOICES, default="stripe"
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Amount paid in this transaction",
    )
    payment_date = models.DateTimeField(default=timezone.now)

    # Reference number (auto-generated receipt number)
    reference_number = models.CharField(
        max_length=100,
        unique=True,
        blank=True,  # Allow blank - will be auto-generated in save() method
        null=True,  # Allow null for database
        help_text="Internal reference number for this payment - Auto-generated if not provided",
    )

    # Payment gateway info (if Stripe)
    gateway_transaction_id = models.CharField(max_length=100, null=True, blank=True)

    # Mobile Money info
    mobile_money_number = models.CharField(
        max_length=20, blank=True, help_text="Mobile money phone number"
    )
    mobile_money_provider = models.CharField(
        max_length=20, blank=True, help_text="Mobile money provider (MTN, Airtel, etc.)"
    )
    mobile_money_reference = models.CharField(
        max_length=100, blank=True, help_text="Mobile money transaction reference"
    )

    # Cash/Bank Transfer info
    received_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="received_payments",
        help_text="User who registered this payment (for manual payments)",
    )
    notes = models.TextField(
        blank=True, help_text="Additional notes about this payment"
    )

    # Receipt/Invoice
    receipt_number = models.CharField(
        max_length=50,
        unique=True,
        blank=True,  # Allow blank - will be auto-generated in save() method
        null=True,  # Allow null for database
        help_text="Receipt number (STP-001, STP-002, etc.) - Auto-generated if not provided",
    )
    invoice_pdf_path = models.CharField(
        max_length=500, null=True, blank=True, help_text="Path to generated PDF receipt"
    )

    # Status
    is_confirmed = models.BooleanField(
        default=True, help_text="Whether this payment is confirmed"
    )
    confirmed_at = models.DateTimeField(null=True, blank=True)
    confirmed_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="confirmed_payments",
        help_text="User who confirmed this payment",
    )

    # Email tracking
    receipt_sent = models.BooleanField(
        default=False, help_text="Whether receipt email was sent"
    )
    receipt_sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Starter Pack Payment"
        verbose_name_plural = "Starter Pack Payments"
        ordering = ["-payment_date", "-created_at"]

    def __str__(self):
        return (
            f"Payment {self.receipt_number} - {self.amount} UGX - {self.payment_method}"
        )

    def save(self, *args, **kwargs):
        # Generate receipt number if not set
        if not self.receipt_number:
            self.receipt_number = self._generate_receipt_number()

        # Generate reference number if not set
        if not self.reference_number:
            self.reference_number = self._generate_reference_number()

        # Set confirmed_at if is_confirmed is True and it wasn't set before
        if self.is_confirmed and not self.confirmed_at:
            self.confirmed_at = timezone.now()
            # Set confirmed_by if not set (should be set from admin/API, but fallback)
            if not hasattr(self, "_confirmed_by_set") and not self.confirmed_by:
                # Try to get from received_by
                if self.received_by:
                    self.confirmed_by = self.received_by

        is_new = not self.pk
        super().save(*args, **kwargs)

        # Activate subscription if this is the first payment (amount_paid is now calculated property)
        if is_new and self.is_confirmed:
            order = self.order
            order.refresh_from_db()
            # amount_paid is now a calculated property from payments
            # Update order status to active if payment received
            if order.amount_paid > 0:
                order.status = "active"
                order.save()
            # Activate subscription if not already activated
            if order.amount_paid > 0 and not order.subscription_start_date:
                order.activate_subscription()
            # Generate PDF receipt
            try:
                from .receipt_utils import generate_receipt_pdf

                generate_receipt_pdf(self, save_to_file=True)
            except Exception as e:
                # Don't fail payment save if PDF generation fails
                print(f"Error generating receipt PDF: {e}")

    def _generate_receipt_number(self):
        """Generate unique receipt number (STP-001, STP-002, etc.)"""
        prefix = (
            self.order.receipt_prefix
            if hasattr(self.order, "receipt_prefix")
            else "STP"
        )

        # Get the next receipt number from the order
        if hasattr(self.order, "next_receipt_number"):
            receipt_num = self.order.next_receipt_number
            # Increment order's next_receipt_number
            ZentroStarterOrder.objects.filter(id=self.order.id).update(
                next_receipt_number=receipt_num + 1
            )
        else:
            # Fallback: count existing payments
            receipt_num = (
                ZentroStarterPayment.objects.filter(order=self.order).count() + 1
            )

        receipt_number = f"{prefix}-{receipt_num:03d}"

        # Ensure uniqueness
        while ZentroStarterPayment.objects.filter(
            receipt_number=receipt_number
        ).exists():
            receipt_num += 1
            receipt_number = f"{prefix}-{receipt_num:03d}"

        return receipt_number

    def _generate_reference_number(self):
        """Generate unique internal reference number"""
        import uuid

        return f"PAY-{uuid.uuid4().hex[:12].upper()}"


class ZentroStarterInstallmentReminder(BaseModel):
    """Tracks reminder history for installment payments"""

    REMINDER_TYPE_CHOICES = [
        ("payment_due", "Payment Due Reminder"),
        ("overdue", "Overdue Payment Notice"),
        ("final_notice", "Final Notice"),
    ]

    order = models.ForeignKey(
        ZentroStarterOrder,
        on_delete=models.CASCADE,
        related_name="reminders",
        help_text="The starter pack order this reminder is for",
    )
    reminder_type = models.CharField(
        max_length=20, choices=REMINDER_TYPE_CHOICES, default="payment_due"
    )
    scheduled_date = models.DateTimeField(
        help_text="When this reminder was scheduled to be sent"
    )
    sent_at = models.DateTimeField(
        null=True, blank=True, help_text="When this reminder was actually sent"
    )
    email_sent = models.BooleanField(
        default=False, help_text="Whether reminder email was sent"
    )
    sms_sent = models.BooleanField(
        default=False, help_text="Whether reminder SMS was sent"
    )
    notes = models.TextField(
        blank=True, help_text="Additional notes about this reminder"
    )

    class Meta:
        verbose_name = "Installment Reminder"
        verbose_name_plural = "Installment Reminders"
        ordering = ["-scheduled_date"]

    def __str__(self):
        return f"Reminder {self.reminder_type} for Order {self.order.id} - {self.scheduled_date}"


class TrialEndReminder(models.Model):
    """
    Tracks trial-end reminder emails sent to avoid duplicates.
    Used by send_trial_end_reminders Celery task.
    """

    REMINDER_TYPE_CHOICES = [
        ("3_days", "3 Days Before Trial End"),
        ("1_day", "1 Day Before Trial End"),
    ]

    SOURCE_CHOICES = [
        ("subscription", "Subscription"),
        ("starter_order", "Starter Order"),
    ]

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="trial_end_reminders",
    )
    reminder_type = models.CharField(
        max_length=20, choices=REMINDER_TYPE_CHOICES
    )
    trial_end_date = models.DateField(
        help_text="The trial end date this reminder was for"
    )
    sent_at = models.DateTimeField(
        default=timezone.now,
        help_text="When this reminder was sent",
    )
    source = models.CharField(
        max_length=20,
        choices=SOURCE_CHOICES,
        help_text="Subscription or ZentroStarterOrder",
    )
    source_id = models.PositiveIntegerField(
        help_text="ID of Subscription or ZentroStarterOrder",
    )

    class Meta:
        verbose_name = "Trial End Reminder"
        verbose_name_plural = "Trial End Reminders"
        ordering = ["-sent_at"]
        unique_together = [["company", "reminder_type", "trial_end_date", "source", "source_id"]]

    def __str__(self):
        return f"Trial reminder {self.reminder_type} for {self.company.name} - {self.trial_end_date}"


# --- Signals ---
from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender=Subscription)
def recompute_modules_on_plan_change(sender, instance, **kwargs):
    """Auto-recompute enabled_modules when a subscription plan changes."""
    update_fields = kwargs.get("update_fields")
    if update_fields and "enabled_modules" in update_fields:
        return
    try:
        instance.company.compute_enabled_modules()
    except Exception:
        logger.exception(
            "Failed recomputing enabled modules after Subscription save.",
            extra={
                "subscription_id": instance.pk,
                "company_id": instance.company_id,
                "plan": instance.plan,
                "status": instance.status,
            },
        )
        raise
