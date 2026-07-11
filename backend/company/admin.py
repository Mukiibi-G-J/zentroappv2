import json
import logging

from django import forms
from django.contrib import admin, messages
from django.db import connection, connections, DEFAULT_DB_ALIAS, models, transaction
from django.forms import widgets
from django.forms.utils import flatatt
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django_celery_results.models import TaskResult
from django_celery_results.admin import GroupResult
from django_celery_beat.models import (
    ClockedSchedule,
    CrontabSchedule,
    IntervalSchedule,
    SolarSchedule,
    PeriodicTasks,
    PeriodicTask,
)
from django_celery_beat.admin import (
    PeriodicTaskAdmin,
    ClockedScheduleAdmin,
    CrontabScheduleAdmin,
    SolarScheduleAdmin,
    IntervalScheduleAdmin,
)

from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.template.response import TemplateResponse
from django_tenants.utils import schema_context, get_public_schema_name

from .schema_clone import try_set_session_replication_role_replica
from setup.admin import EmailSetupAdmin
from setup.models import EmailSetup

# UploadTemplates
from config_packages.admin import UploadTemplatesAdmin
from config_packages.models import UploadTemplates
from base.models import Objects
from base.admin import ObjectsAdmin
from app_updates.models import AppVersion
from company import models
from company.enums import SubscriptionPlan
from django.utils import timezone

logger = logging.getLogger(__name__)


EXCLUDED_COPY_TABLES = {
    "django_migrations",
}


def clone_tenant_schema_data(source_schema: str, target_schema: str):
    """
    Copy all table data (including users) from source_schema into target_schema.
    Existing rows in the target tables are removed before copying.
    """
    with schema_context(get_public_schema_name()):
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT tablename
                FROM pg_tables
                WHERE schemaname = %s
                ORDER BY tablename
                """,
                [source_schema],
            )
            tables = [row[0] for row in cursor.fetchall()]

        if not tables:
            return

        # SET LOCAL applies only within this transaction and is reverted on commit/rollback.
        # A session-level SET + finally DEFAULT breaks when any statement fails: Postgres
        # aborts the transaction, then finally runs another command and surfaces only
        # "current transaction is aborted, commands ignored until end of transaction block".
        with transaction.atomic():
            with connection.cursor() as cursor:
                try_set_session_replication_role_replica(cursor)
                for table in tables:
                    if table in EXCLUDED_COPY_TABLES:
                        continue

                    cursor.execute(f'DELETE FROM "{target_schema}"."{table}";')
                    cursor.execute(
                        f'INSERT INTO "{target_schema}"."{table}" '
                        f'SELECT * FROM "{source_schema}"."{table}";'
                    )

                    cursor.execute(
                        """
                        SELECT column_name
                        FROM information_schema.columns
                        WHERE table_schema = %s
                          AND table_name = %s
                          AND column_default LIKE 'nextval%%'
                        """,
                        [target_schema, table],
                    )
                    sequence_columns = [row[0] for row in cursor.fetchall()]

                    for column in sequence_columns:
                        cursor.execute(
                            "SELECT pg_get_serial_sequence(%s, %s)",
                            [f"{target_schema}.{table}", column],
                        )
                        result = cursor.fetchone()
                        if not result or not result[0]:
                            continue

                        sequence_name = result[0]
                        cursor.execute(
                            f"""
                            SELECT setval(
                                %s,
                                COALESCE(
                                    (SELECT MAX("{column}") FROM "{target_schema}"."{table}"),
                                    1
                                ),
                                true
                            )
                            """,
                            [sequence_name],
                        )


class CopyCompanyForm(forms.Form):
    new_name = forms.CharField(
        max_length=100,
        label="New company name",
        help_text="Provide a unique company name.",
    )
    new_domain_url = forms.CharField(
        max_length=255,
        label="Domain",
        help_text="Example: newcompany.zentroapp.app",
    )
    new_schema_name = forms.CharField(
        max_length=63,
        label="Schema name",
        help_text="Lowercase letters, numbers, and underscores only.",
    )
    new_email = forms.EmailField(
        label="Contact email",
        required=False,
        help_text="Leave empty to reuse the original company's email.",
    )

    def clean_new_name(self):
        name = self.cleaned_data["new_name"].strip()
        if models.Company.objects.filter(name__iexact=name).exists():
            raise forms.ValidationError("A company with this name already exists.")
        return name

    def clean_new_domain_url(self):
        domain = self.cleaned_data["new_domain_url"].strip().lower()
        if models.Company.objects.filter(domain_url__iexact=domain).exists():
            raise forms.ValidationError("This domain URL is already in use.")
        if models.Domain.objects.filter(domain__iexact=domain).exists():
            raise forms.ValidationError(
                "A tenant domain with this value already exists."
            )
        return domain

    def clean_new_schema_name(self):
        schema = self.cleaned_data["new_schema_name"].strip().lower()
        if not schema.replace("_", "").isalnum():
            raise forms.ValidationError(
                "Schema name can only contain lowercase letters, numbers, and underscores."
            )
        if models.Company.objects.filter(schema_name__iexact=schema).exists():
            raise forms.ValidationError("This schema name is already in use.")
        return schema


class AddHistoricalMoMoForm(forms.Form):
    """Form to record a historical mobile money payment and activate subscription."""

    company = forms.ModelChoiceField(
        queryset=models.Company.objects.order_by("name"),
        required=True,
        label="Company",
    )
    plan = forms.ChoiceField(
        choices=[
            (p.value, p.value)
            for p in [
                SubscriptionPlan.STANDARD,
                SubscriptionPlan.MULTI_BRANCH,
                SubscriptionPlan.PREMIUM,
                SubscriptionPlan.STARTER,
                SubscriptionPlan.BUSINESS,
                SubscriptionPlan.PRO,
            ]
        ],
        required=True,
        label="Plan",
    )
    amount = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=True,
        min_value=0,
        label="Amount (UGX)",
    )
    payment_date = forms.DateField(
        required=True,
        initial=timezone.now,
        label="Payment date",
    )
    mobile_money_reference = forms.CharField(
        max_length=100,
        required=False,
        label="Mobile money reference",
        help_text="Optional reference from mobile money transaction",
    )
    notes = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3}),
        required=False,
        label="Notes",
    )
    extra_users_count = forms.IntegerField(
        min_value=0,
        required=False,
        initial=0,
        label="Extra users (add-on)",
        help_text="Number of extra users purchased with this payment. Applied on save.",
    )


class ExpiryReminderPreviewForm(forms.Form):
    REMINDER_TYPE_CHOICES = [
        ("general", "General reminder (no day restriction)"),
        ("migration_14_day", "14-day subscription migration reminder"),
        ("expiry_10_day", "10-day expiry reminder"),
    ]

    reminder_type = forms.ChoiceField(
        choices=REMINDER_TYPE_CHOICES,
        required=True,
        label="Reminder type",
    )
    subject = forms.CharField(
        max_length=255,
        required=True,
        label="Email subject",
    )
    message_body = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 6}),
        required=True,
        label="Email message",
        help_text=(
            "You can use {company_name}, {days_remaining}, {period_end_date}, and "
            "{payment_url} placeholders."
        ),
    )
    send_email = forms.BooleanField(
        required=False,
        initial=True,
        label="Send Email",
    )
    selected_recipients_json = forms.CharField(
        required=False,
        widget=forms.HiddenInput(),
    )

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("send_email"):
            raise forms.ValidationError(
                "Select at least one send channel. Currently only Email is available."
            )
        return cleaned


class _SafeFormatDict(dict):
    def __missing__(self, key):
        return "{" + key + "}"


class BillingHistoryAdminForm(forms.ModelForm):
    """Custom form for BillingHistory with dynamic amount help text for Extra Users."""

    class Meta:
        model = models.BillingHistory
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk and self.instance.product == "Extra Users":
            self.fields["amount"].help_text = (
                "For Extra Users payments, you may adjust this to the actual amount "
                "received (e.g. if the customer negotiated a discount). "
                "Slots granted are based on extra_users_count in metadata."
            )


class BillingHistoryAdmin(admin.ModelAdmin):
    form = BillingHistoryAdminForm
    change_list_template = "admin/company/billinghistory/change_list.html"
    list_display = (
        "reference_number",
        "company",
        "product",
        "amount",
        "payment_gateway",
        "status",
        "billing_date",
        "verified_at",
        "verified_by",
    )
    list_filter = ("payment_gateway", "status", "billing_date")
    search_fields = ("reference_number", "company__name", "product")
    readonly_fields = (
        "reference_number",
        "created_at",
        "updated_at",
        "verified_at",
        "verified_by",
    )
    actions = ["verify_payment_action"]
    REMINDER_PRESETS = {
        "general": {
            "days_min": None,
            "days_max": None,
            "subject": (
                "Important Update from Zentro - Subscription Transition"
            ),
            "message_body": (
                "ZentroApp is transitioning to a subscription-based service to improve reliability "
                "and service delivery.\n\n"
                "Kindly review your subscription and check your remaining days on your company page. "
                "Please make your payment in advance to avoid any service interruption.\n\n"
                "Access your company page here: {payment_url}\n"
                "Then click the \"Pay Upfront Month\" button to complete your payment.\n\n"
                "Regards,\n"
                "The Zentro Team"
            ),
        },
        "migration_14_day": {
            "days_min": 1,
            "days_max": 14,
            "subject": (
                "Zentro is moving to Subscription pages - your subscription ends in "
                "{days_remaining} day(s)"
            ),
            "message_body": (
                "Zentro is transitioning to a subscription-based service. Your current subscription "
                "will expire in {days_remaining} day(s), on {period_end_date}.\n\n"
                "Kindly review your subscription and make your payment in advance to avoid any "
                "service interruption.\n\n"
                "Access your company page here: {payment_url}\n"
                "Then click the \"Pay Upfront Month\" button to complete your payment.\n\n"
                "Regards,\n"
                "The Zentro Team"
            ),
        },
        "expiry_10_day": {
            "days_min": 1,
            "days_max": 10,
            "subject": "Your Zentro subscription expires in {days_remaining} day(s)",
            "message_body": (
                "Your Zentro access expires in {days_remaining} day(s) on "
                "{period_end_date}.\n\n"
                "Please renew now to continue without interruption.\n"
                "Open your company page: {payment_url}\n"
                "Then click the \"Pay upfront month\" button.\n\n"
                "Regards,\n"
                "The Zentro Team"
            ),
        },
    }

    @staticmethod
    def _parse_selected_recipients_map(raw_value):
        if not raw_value:
            return None
        try:
            parsed = json.loads(raw_value)
        except (TypeError, json.JSONDecodeError):
            return None
        if not isinstance(parsed, dict):
            return None
        cleaned = {}
        for row_key, recipients in parsed.items():
            if not isinstance(row_key, str):
                continue
            if not isinstance(recipients, list):
                continue
            cleaned[row_key] = [email for email in recipients if isinstance(email, str)]
        return cleaned

    def get_urls(self):
        from django.urls import path

        urls = super().get_urls()
        custom_urls = [
            path(
                "add-historical-momo/",
                self.admin_site.admin_view(self.add_historical_momo_view),
                name="company_billinghistory_add_historical_momo",
            ),
            path(
                "send-expiry-reminders-preview/",
                self.admin_site.admin_view(self.send_expiry_reminders_preview_view),
                name="company_billinghistory_send_expiry_preview",
            ),
        ]
        return custom_urls + urls

    def changelist_view(self, request, extra_context=None):
        from django.urls import reverse

        extra_context = extra_context or {}
        extra_context["add_historical_momo_url"] = reverse(
            "global_admin_site:company_billinghistory_add_historical_momo"
        )
        extra_context["send_expiry_preview_url"] = reverse(
            "global_admin_site:company_billinghistory_send_expiry_preview"
        )
        return super().changelist_view(request, extra_context)

    def send_expiry_reminders_preview_view(self, request):
        from django.http import HttpResponseForbidden

        # Restrict to superuser, exclude debug_admin
        if not request.user.is_superuser or request.user.username == "debug_admin":
            return HttpResponseForbidden("Access denied.")

        selected_reminder_type = request.POST.get("reminder_type", "general")
        selected_preset = self.REMINDER_PRESETS.get(
            selected_reminder_type, self.REMINDER_PRESETS["general"]
        )
        selected_recipients_map = self._parse_selected_recipients_map(
            request.POST.get("selected_recipients_json")
        )

        if request.method == "POST":
            form = ExpiryReminderPreviewForm(request.POST)
            if form.is_valid():
                with schema_context(get_public_schema_name()):
                    from company.tasks import send_billing_expiry_reminders_custom

                    result = send_billing_expiry_reminders_custom(
                        reminder_key=form.cleaned_data["reminder_type"],
                        subject_template=form.cleaned_data["subject"],
                        body_template=form.cleaned_data["message_body"],
                        send_email=form.cleaned_data["send_email"],
                        days_min=selected_preset["days_min"],
                        days_max=selected_preset["days_max"],
                        selected_recipients_map=selected_recipients_map,
                    )

                reminders_sent = result.get("reminders_sent", 0)
                recipients_sent = result.get("recipient_emails_sent", 0)
                recipients_failed = result.get("recipient_emails_failed", [])
                skipped = result.get("reminders_skipped", 0)
                companies_found = result.get("companies_found", 0)
                companies_without_recipients = result.get(
                    "companies_without_superusers", []
                )
                companies_excluded_by_selection = result.get(
                    "companies_excluded_by_selection", []
                )

                parts = [
                    f"Sent {reminders_sent} reminder record(s) to {recipients_sent} recipient email(s)."
                ]
                if companies_found == 0:
                    parts.append("No companies in the selected reminder window.")
                if skipped:
                    parts.append(f"Skipped {skipped} (already sent today for this reminder type).")
                if recipients_failed:
                    parts.append(
                        f"Failed recipients: {', '.join(recipients_failed)}. Check email config/logs."
                    )
                if companies_without_recipients:
                    parts.append(
                        "No tenant superuser emails for: "
                        f"{', '.join(companies_without_recipients)}."
                    )
                if companies_excluded_by_selection:
                    parts.append(
                        "Excluded by selection: "
                        f"{', '.join(companies_excluded_by_selection)}."
                    )

                level = messages.SUCCESS if reminders_sent > 0 else (
                    messages.WARNING
                    if recipients_failed
                    or companies_without_recipients
                    or companies_excluded_by_selection
                    else messages.INFO
                )
                self.message_user(request, " ".join(parts), level=level)
                from django.shortcuts import redirect
                return redirect("global_admin_site:company_billinghistory_changelist")
        else:
            form = ExpiryReminderPreviewForm(
                initial={
                    "reminder_type": selected_reminder_type,
                    "subject": selected_preset["subject"],
                    "message_body": selected_preset["message_body"],
                    "send_email": True,
                }
            )

        active_reminder_type = (
            form.cleaned_data["reminder_type"]
            if request.method == "POST" and form.is_valid()
            else selected_reminder_type
        )
        active_preset = self.REMINDER_PRESETS.get(
            active_reminder_type, self.REMINDER_PRESETS["general"]
        )

        with schema_context(get_public_schema_name()):
            from company.tasks import (
                _get_companies_for_expiry_reminders,
                _get_company_superuser_emails,
                _build_company_subscription_url,
            )

            rows = _get_companies_for_expiry_reminders(
                days_min=active_preset["days_min"],
                days_max=active_preset["days_max"],
            )
            preview_rows = []
            for company, _bh, period_end_date, days_remaining, _src, _src_id in rows:
                row_key = f"{company.id}:{_src}:{_src_id}"
                recipients = _get_company_superuser_emails(company)
                selected_recipients_for_row = (
                    selected_recipients_map.get(row_key)
                    if isinstance(selected_recipients_map, dict)
                    else None
                )
                recipient_lines = []
                for email in recipients:
                    is_included = (
                        True
                        if selected_recipients_for_row is None
                        else email in selected_recipients_for_row
                    )
                    recipient_lines.append({"email": email, "included": is_included})
                preview_rows.append(
                    {
                        "row_key": row_key,
                        "company_name": company.name,
                        "recipients": recipients,
                        "recipient_lines": recipient_lines,
                        "recipients_display": ", ".join(recipients)
                        if recipients
                        else "(no tenant superuser emails)",
                        "period_end_date": str(period_end_date),
                        "days_remaining": days_remaining,
                        "payment_url": _build_company_subscription_url(company),
                    }
                )

        sample_subject = ""
        sample_message = ""
        if preview_rows:
            sample = preview_rows[0]
            subject_template = (
                form.cleaned_data["subject"]
                if request.method == "POST" and form.is_valid()
                else form.initial.get("subject", active_preset["subject"])
            )
            message_template = (
                form.cleaned_data["message_body"]
                if request.method == "POST" and form.is_valid()
                else form.initial.get("message_body", active_preset["message_body"])
            )
            sample_context = _SafeFormatDict({
                "company_name": sample["company_name"],
                "days_remaining": sample["days_remaining"],
                "period_end_date": sample["period_end_date"],
                "payment_url": sample.get("payment_url"),
            })
            sample_subject = subject_template.format_map(sample_context)
            sample_message = message_template.format_map(sample_context)

        context = {
            "title": "Send expiry reminders - Preview",
            "opts": self.model._meta,
            "form": form,
            "preview_rows": preview_rows,
            "selected_days_window": (
                "Not restricted"
                if active_preset["days_min"] is None and active_preset["days_max"] is None
                else f"{active_preset['days_min']}-{active_preset['days_max']}"
            ),
            "sample_subject": sample_subject,
            "sample_message": sample_message,
            "selected_recipients_json": json.dumps(
                {
                    row["row_key"]: [
                        line["email"]
                        for line in row["recipient_lines"]
                        if line["included"]
                    ]
                    for row in preview_rows
                }
            ),
            "reminder_presets_json": json.dumps(
                {
                    key: {
                        "subject": preset["subject"],
                        "message_body": preset["message_body"],
                    }
                    for key, preset in self.REMINDER_PRESETS.items()
                }
            ),
        }
        return TemplateResponse(
            request,
            "admin/company/billinghistory/send_expiry_preview.html",
            context,
        )

    @admin.action(description="Verify payment")
    def verify_payment_action(self, request, queryset):
        from company.views import activate_subscription_from_billing
        from company.models import PaymentGateway
        from company.billing_receipt_email import (
            send_verified_mobile_money_subscription_receipt,
        )

        verified = 0
        for billing in queryset:
            if billing.status != "pending_verification":
                continue
            if billing.payment_gateway not in (
                PaymentGateway.MANUAL_MOBILE_MONEY,
                PaymentGateway.MOBILE_MONEY,
            ):
                continue
            try:
                with schema_context(get_public_schema_name()):
                    billing.status = "paid"
                    billing.verified_at = timezone.now()
                    billing.verified_by = request.user
                    billing.save()

                    success, _ = activate_subscription_from_billing(
                        billing.company, billing, billing.billing_date
                    )
                    if success:
                        sub = models.Subscription.objects.get(
                            company=billing.company
                        )
                        sub.payment_gateway = PaymentGateway.MANUAL_MOBILE_MONEY
                        sub.gateway_subscription_id = None
                        sub.save()
                        try:
                            send_verified_mobile_money_subscription_receipt(billing)
                        except Exception:
                            logger.exception(
                                "Failed sending receipt email for billing %s",
                                billing.reference_number,
                            )
                    verified += 1
            except Exception as e:
                self.message_user(
                    request,
                    f"Error verifying {billing.reference_number}: {e}",
                    level=messages.ERROR,
                )
        if verified:
            self.message_user(
                request,
                f"Verified {verified} payment(s) and activated subscription(s).",
                level=messages.SUCCESS,
            )

    def add_historical_momo_view(self, request):
        from django.http import HttpResponseRedirect
        from django.urls import reverse
        from company.views import activate_subscription_from_billing
        from company.models import PaymentGateway

        if request.method == "POST":
            form = AddHistoricalMoMoForm(request.POST)
            if form.is_valid():
                try:
                    with schema_context(get_public_schema_name()):
                        company = form.cleaned_data["company"]
                        plan_display = form.cleaned_data["plan"]
                        amount = form.cleaned_data["amount"]
                        payment_date = form.cleaned_data["payment_date"]
                        momo_ref = form.cleaned_data.get(
                            "mobile_money_reference", ""
                        ).strip()
                        notes = form.cleaned_data.get("notes", "").strip()
                        extra_users = form.cleaned_data.get("extra_users_count") or 0

                        metadata = {"notes": notes, "source": "admin_historical_momo"}
                        if extra_users > 0:
                            metadata["extra_users_count"] = extra_users

                        billing = models.BillingHistory.objects.create(
                            company=company,
                            payment_gateway=PaymentGateway.MOBILE_MONEY,
                            product=plan_display,
                            status="paid",
                            billing_date=payment_date,
                            amount=amount,
                            currency="UGX",
                            gateway_payment_id=momo_ref or None,
                            metadata=metadata,
                        )

                        success, msg = activate_subscription_from_billing(
                            company, billing, payment_date
                        )
                        if success:
                            sub = models.Subscription.objects.get(company=company)
                            sub.payment_gateway = PaymentGateway.MOBILE_MONEY
                            sub.gateway_subscription_id = None
                            sub.save()

                    self.message_user(
                        request,
                        f"Recorded mobile money payment for {company.name} "
                        f"({plan_display}, {amount} UGX) and activated subscription.",
                        level=messages.SUCCESS,
                    )
                    return HttpResponseRedirect(
                        reverse(
                            "global_admin_site:company_billinghistory_changelist"
                        )
                    )
                except Exception as e:
                    form.add_error(None, str(e))
        else:
            form = AddHistoricalMoMoForm()

        context = {
            "title": "Record historical mobile money payment",
            "form": form,
            "opts": self.model._meta,
        }
        return TemplateResponse(
            request,
            "admin/company/add_historical_momo.html",
            context,
        )


class GlobalAdminSite(admin.AdminSite):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Note: Company is registered separately below with CompanyAdmin
        self.register(models.Domain)
        self.register(EmailSetup, EmailSetupAdmin)
        self.register(UploadTemplates, UploadTemplatesAdmin)
        self.register(models.Subscription)
        self.register(models.BillingHistory, BillingHistoryAdmin)
        self.register(models.BillingExpiryReminder)
        self.register(models.CompanyOnBoarding)
        self.register(models.BusinessCategory)
        self.register(models.BusinessObjective)

        # celery flower
        self.register(TaskResult)
        self.register(GroupResult)

        # celery beat
        self.register(PeriodicTask, PeriodicTaskAdmin)
        self.register(ClockedSchedule, ClockedScheduleAdmin)
        self.register(CrontabSchedule, CrontabScheduleAdmin)
        self.register(IntervalSchedule, IntervalScheduleAdmin)
        self.register(SolarSchedule, SolarScheduleAdmin)
        self.register(models.Pricing)
        self.register(Objects, ObjectsAdmin)
        self.register(models.ZentroStarterOffer)
        self.register(models.ZentroStarterOrder)
        self.register(models.ZentroStarterPayment)
        self.register(models.ZentroStarterInstallmentReminder)
        self.register(models.TrialEndReminder)

        # self.register(PeriodicTasks)


# Custom admin site configuration
admin.site.site_header = "ZentroApp Administration"
admin.site.site_title = "ZentroApp Admin"
admin.site.index_title = "Welcome to ZentroApp Administration"

# Global admin site for multi-tenancy
global_admin_site = GlobalAdminSite(name="global_admin_site")


class ModuleSelectorWidget(widgets.Textarea):
    """
    Custom widget for selecting enabled modules with checkboxes
    Displays checkboxes for each available module with descriptions and dependency warnings
    Uses a hidden textarea to store JSON, and renders checkboxes with JavaScript to update it
    """

    def render(self, name, value, attrs=None, renderer=None):
        from utils.modules import get_available_modules, get_module_config

        # Get current enabled modules
        if value:
            if isinstance(value, str):
                import json

                try:
                    enabled_modules = json.loads(value)
                except json.JSONDecodeError:
                    enabled_modules = []
            elif isinstance(value, list):
                enabled_modules = value
            else:
                enabled_modules = []
        else:
            enabled_modules = ["pos"]  # Default to POS

        # Ensure POS is always included
        if "pos" not in enabled_modules:
            enabled_modules = ["pos"] + [m for m in enabled_modules if m != "pos"]

        # Get all available modules
        available_modules = get_available_modules()

        # Build the widget HTML
        widget_id = attrs.get("id", f"id_{name}") if attrs else f"id_{name}"
        html_parts = [
            f'<div class="module-selector-widget" id="{widget_id}_container" style="margin-top: 10px;">'
        ]

        for module_config in available_modules:
            module_id = module_config.identifier
            module_name = module_config.display_name
            module_description = module_config.description
            module_dependencies = module_config.dependencies
            is_checked = module_id in enabled_modules
            is_pos = module_id == "pos"

            # Check if dependencies are met
            missing_deps = [
                dep for dep in module_dependencies if dep not in enabled_modules
            ]
            dependency_names = [
                get_module_config(dep).display_name if get_module_config(dep) else dep
                for dep in missing_deps
            ]

            # Build dependency warning
            dependency_warning = ""
            if missing_deps:
                dependency_warning = format_html(
                    '<div class="help" style="color: #dc3545; font-size: 11px; margin-top: 4px; margin-left: 24px;">⚠ Requires: {}</div>',
                    ", ".join(dependency_names),
                )

            checkbox_html = format_html(
                '<div style="margin-bottom: 15px; padding: 12px; border: 1px solid #ddd; border-radius: 4px; background-color: {};">'
                '<label style="font-weight: bold; display: block; margin-bottom: 5px; cursor: {};">'
                '<input type="checkbox" class="module-checkbox" data-module="{}" {} {} style="margin-right: 8px;">'
                "{}"
                "</label>"
                '<div style="color: #666; font-size: 12px; margin-left: 24px; margin-bottom: 5px;">{}</div>'
                "{}"
                "</div>",
                "#f0f0f0" if is_pos else "#fff",
                "default" if not is_pos else "not-allowed",
                module_id,
                "checked" if is_checked else "",
                "disabled" if is_pos else "",
                module_name + (" (Required)" if is_pos else ""),
                module_description,
                dependency_warning,
            )
            html_parts.append(checkbox_html)

        html_parts.append("</div>")

        # Hidden textarea to store the JSON value (Django admin expects this)
        import json

        json_value = json.dumps(enabled_modules)
        textarea_attrs = {"id": widget_id, "name": name, "style": "display: none;"}
        if attrs:
            textarea_attrs.update(attrs)
            textarea_attrs["style"] = "display: none;"  # Always hide

        textarea_html = format_html(
            '<textarea{}>{}</textarea>',
            flatatt(textarea_attrs),
            json_value,
        )

        # JavaScript to update textarea when checkboxes change
        js = format_html(
            """
        <script>
        (function() {{
            var textarea = document.getElementById('{}');
            var container = document.getElementById('{}_container');
            var checkboxes = container.querySelectorAll('.module-checkbox');
            
            function updateTextarea() {{
                var selectedModules = [];
                checkboxes.forEach(function(checkbox) {{
                    if (checkbox.checked) {{
                        selectedModules.push(checkbox.getAttribute('data-module'));
                    }}
                }});
                // Ensure POS is always included
                if (selectedModules.indexOf('pos') === -1) {{
                    selectedModules.unshift('pos');
                }}
                textarea.value = JSON.stringify(selectedModules);
            }}
            
            checkboxes.forEach(function(checkbox) {{
                checkbox.addEventListener('change', updateTextarea);
            }});
            
            // Initialize on page load
            updateTextarea();
        }})();
        </script>
        """,
            widget_id,
            widget_id,
        )

        return mark_safe(textarea_html + "".join(html_parts) + js)

    def value_from_datadict(self, data, files, name):
        """
        Extract the value from the form data
        The textarea contains JSON string which we parse to list
        """
        import json

        value = data.get(name)
        if value:
            try:
                if isinstance(value, str):
                    parsed = json.loads(value)
                    # Ensure POS is always included
                    if "pos" not in parsed:
                        parsed.insert(0, "pos")
                    return parsed
                elif isinstance(value, list):
                    # Ensure POS is always included
                    if "pos" not in value:
                        value.insert(0, "pos")
                    return value
            except (json.JSONDecodeError, TypeError):
                pass
        # Default to POS if nothing is set
        return ["pos"]


class CompanyAdminForm(forms.ModelForm):
    """Custom form for Company admin with module selector widget"""

    class Meta:
        model = models.Company
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Use custom widget for enabled_modules field
        self.fields["enabled_modules"].widget = ModuleSelectorWidget()
        self.fields["enabled_modules"].help_text = (
            "Select the modules to enable for this company. "
            "POS module is required and cannot be disabled."
        )

    def clean_enabled_modules(self):
        """Ensure POS is always included"""
        value = self.cleaned_data.get("enabled_modules", [])
        if not isinstance(value, list):
            value = []
        # Ensure POS is always included and first
        if "pos" not in value:
            value = ["pos"] + value
        else:
            # Move POS to the front
            value = ["pos"] + [m for m in value if m != "pos"]
        return value


@admin.register(models.Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "phone", "active_plan", "created_at")
    search_fields = ("name", "email", "phone")
    list_filter = ("created_at",)
    readonly_fields = ("created_at", "updated_at", "enabled_modules")
    actions = [
        "delete_selected_tenants",
        "copy_company",
        "recompute_enabled_modules",
        "ensure_debug_admin_selected",
        "ensure_debug_admin_all_tenants",
        "send_eid_sms_test",
        "send_eid_sms_to_companies",
        "queue_database_backup_daily",
        "queue_database_backup_weekly",
    ]
    fieldsets = (
        (None, {"fields": ("name", "domain_url", "schema_name", "display_name", "address", "email", "phone", "website", "tin", "city", "country", "logo")}),
        ("Module Overrides (Waivers / Deals)", {
            "description": "Add module identifiers here to grant access beyond the company's subscription plan. "
                           "These are combined with the plan's modules to form the final enabled_modules list.",
            "fields": ("module_overrides", "enabled_modules"),
        }),
        ("User Limit Waiver", {
            "description": "Additional users beyond plan + purchased. E.g. 5 = allow 5 extra users. Leave blank for no waiver.",
            "fields": ("user_limit_override",),
        }),
        ("Subscription / billing", {
            "description": "Grace period: full API access continues for N calendar days after the payment due date (day after period end).",
            "fields": ("subscription_grace_days", "grace_reminder_offsets"),
        }),
        ("System", {
            "fields": ("onboarding_data", "created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )

    def active_plan(self, obj):
        try:
            return obj.subscription.plan
        except Exception:
            return "-"
    active_plan.short_description = "Plan"

    @admin.action(description="Recompute enabled modules from subscription plan")
    def recompute_enabled_modules(self, request, queryset):
        count = 0
        for company in queryset:
            try:
                company.compute_enabled_modules()
                count += 1
            except Exception as exc:
                self.message_user(request, f"Error for {company.name}: {exc}", level=messages.ERROR)
        self.message_user(request, f"Recomputed modules for {count} company(ies).", level=messages.SUCCESS)

    def _ensure_debug_admin_for_companies(self, request, companies):
        """Create or sync debug_admin in tenant schemas (public admin only)."""
        from company.models import ensure_debug_admin_for_schema

        if not request.user.is_superuser:
            self.message_user(
                request,
                "Only superusers can manage debug_admin users.",
                level=messages.ERROR,
            )
            return

        if connection.schema_name != get_public_schema_name():
            self.message_user(
                request,
                "Run this action from the public tenant admin (/admin on the public domain).",
                level=messages.ERROR,
            )
            return

        counts = {"created": 0, "updated": 0, "unchanged": 0, "skipped_no_config": 0}
        errors = []

        for company in companies:
            schema = (company.schema_name or "").strip()
            if not schema:
                errors.append(f"{company.name}: missing schema_name")
                continue
            try:
                result = ensure_debug_admin_for_schema(schema)
                if result in counts:
                    counts[result] += 1
                else:
                    errors.append(f"{company.name} ({schema}): unexpected result {result!r}")
            except Exception as exc:
                logger.exception(
                    "ensure_debug_admin failed for %s (%s)", company.name, schema
                )
                errors.append(f"{company.name} ({schema}): {exc}")

        parts = [
            f"Created {counts['created']}",
            f"updated {counts['updated']}",
            f"already OK {counts['unchanged']}",
        ]
        if counts["skipped_no_config"]:
            parts.append(f"skipped (no DEBUG_ADMIN_* config) {counts['skipped_no_config']}")
        level = messages.SUCCESS if not errors else messages.WARNING
        self.message_user(request, "; ".join(parts) + ".", level=level)
        if errors:
            preview = "; ".join(errors[:10])
            if len(errors) > 10:
                preview += f"; … and {len(errors) - 10} more"
            self.message_user(request, f"Errors: {preview}", level=messages.ERROR)

    @admin.action(description="Ensure debug_admin in selected tenants (create if missing)")
    def ensure_debug_admin_selected(self, request, queryset):
        self._ensure_debug_admin_for_companies(request, queryset)

    @admin.action(
        description="Ensure debug_admin in ALL tenants (selection ignored; create if missing)"
    )
    def ensure_debug_admin_all_tenants(self, request, queryset):
        with schema_context(get_public_schema_name()):
            all_companies = models.Company.objects.all().order_by("name")
        self._ensure_debug_admin_for_companies(request, all_companies)

    @admin.action(description="Queue full database backup to S3 (daily prefix; Celery)")
    def queue_database_backup_daily(self, request, queryset):
        from base.tasks import database_backup_task

        if not request.user.is_superuser:
            self.message_user(request, "Only superusers can queue a full database backup.", level=messages.ERROR)
            return
        database_backup_task.delay(tier="daily")
        self.message_user(
            request,
            "Daily database backup has been queued; check Celery worker logs and S3 backups/daily/.",
            level=messages.SUCCESS,
        )

    @admin.action(description="Queue full database backup to S3 (weekly prefix; Celery)")
    def queue_database_backup_weekly(self, request, queryset):
        from base.tasks import database_backup_task

        if not request.user.is_superuser:
            self.message_user(request, "Only superusers can queue a full database backup.", level=messages.ERROR)
            return
        database_backup_task.delay(tier="weekly")
        self.message_user(
            request,
            "Weekly database backup has been queued; check Celery worker logs and S3 backups/weekly/.",
            level=messages.SUCCESS,
        )

    EID_SMS_MESSAGE = (
        "May this special Eid celebration fill your life with peace, happiness, and prosperity. Thank you for being a valued part of ZentroApp.m"
    )
    EID_SMS_TEST_PHONE = "256750440865"

    @staticmethod
    def _parse_company_phones(phone_field):
        """Parse Company.phone (can have multiple numbers separated by |) into normalized list."""
        if not phone_field or not str(phone_field).strip():
            return []
        numbers = []
        for part in str(phone_field).split("|"):
            normalized = part.strip().replace(" ", "").replace("-", "")
            if normalized.startswith("+"):
                normalized = normalized[1:]
            if normalized and normalized.isdigit() and len(normalized) >= 9:
                numbers.append(normalized)
        return list(dict.fromkeys(numbers))

    @admin.action(description="Send Eid SMS (test to 256750440865)")
    def send_eid_sms_test(self, request, queryset):
        from helpers.helpers import send_plain_sms

        success = send_plain_sms(self.EID_SMS_TEST_PHONE, self.EID_SMS_MESSAGE)
        if success:
            self.message_user(
                request,
                f"Test Eid SMS sent to {self.EID_SMS_TEST_PHONE}.",
                level=messages.SUCCESS,
            )
        else:
            self.message_user(
                request,
                f"Failed to send test Eid SMS to {self.EID_SMS_TEST_PHONE}. Check logs.",
                level=messages.WARNING,
            )

    @admin.action(description="Send Eid SMS to selected companies")
    def send_eid_sms_to_companies(self, request, queryset):
        from helpers.helpers import send_plain_sms

        sent = 0
        skipped = []
        failed = []
        seen_phones = set()

        for company in queryset:
            phones = self._parse_company_phones(company.phone)
            if not phones:
                skipped.append(company.name)
                continue
            for phone in phones:
                if phone in seen_phones:
                    continue
                seen_phones.add(phone)
                success = send_plain_sms(phone, self.EID_SMS_MESSAGE)
                if success:
                    sent += 1
                else:
                    failed.append(f"{company.name} ({phone})")

        parts = [f"Sent {sent} Eid SMS(s)."]
        if skipped:
            parts.append(f"Skipped (no phone): {', '.join(skipped)}.")
        if failed:
            parts.append(f"Failed: {', '.join(failed)}.")

        level = messages.SUCCESS if sent > 0 else (
            messages.WARNING if failed or skipped else messages.INFO
        )
        self.message_user(request, " ".join(parts), level=level)

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if change and "module_overrides" in form.changed_data:
            obj.compute_enabled_modules()

    def get_actions(self, request):
        actions = super().get_actions(request)
        if "delete_selected" in actions:
            del actions["delete_selected"]
        return actions

    def delete_model(self, request, obj):
        self._delete_companies(request, [obj])

    def delete_queryset(self, request, queryset):
        self._delete_companies(request, queryset)

    @admin.action(description="Delete selected tenants (drops schemas)")
    def delete_selected_tenants(self, request, queryset):
        self._delete_companies(request, queryset)

    def _delete_companies(self, request, queryset):
        success_count = 0
        for tenant in queryset:
            try:
                connections[DEFAULT_DB_ALIAS].close()
                with schema_context(get_public_schema_name()):
                    company = models.Company.objects.filter(pk=tenant.pk).first()
                    if company:
                        company.delete()
                success_count += 1
            except Exception as exc:
                self.message_user(
                    request,
                    f'Error deleting tenant "{tenant.name}": {exc}',
                    level=messages.ERROR,
                )
        if success_count:
            self.message_user(
                request,
                f"Successfully deleted {success_count} tenant(s).",
                level=messages.SUCCESS,
            )

    @staticmethod
    def _suggest_with_suffix(base_value: str, suffix: str, exists_fn):
        candidate = f"{base_value}{suffix}"
        counter = 1
        while exists_fn(candidate):
            candidate = f"{base_value}{suffix}-{counter}"
            counter += 1
        return candidate

    def _suggest_domain(self, domain_value: str):
        if "." in domain_value:
            prefix, rest = domain_value.split(".", 1)
            base_prefix = f"{prefix}-copy"

            def exists(candidate_prefix):
                candidate_domain = f"{candidate_prefix}.{rest}"
                return (
                    models.Company.objects.filter(
                        domain_url__iexact=candidate_domain
                    ).exists()
                    or models.Domain.objects.filter(
                        domain__iexact=candidate_domain
                    ).exists()
                )

            selected_prefix = self._suggest_with_suffix(prefix, "-copy", exists)
            return f"{selected_prefix}.{rest}"
        return self._suggest_with_suffix(
            domain_value,
            "-copy",
            lambda value: models.Company.objects.filter(
                domain_url__iexact=value
            ).exists(),
        )

    def _suggest_schema(self, schema_value: str):
        def exists(candidate):
            return models.Company.objects.filter(schema_name__iexact=candidate).exists()

        return self._suggest_with_suffix(schema_value, "_copy", exists)

    @admin.action(description="Copy selected company to a new tenant")
    def copy_company(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(
                request,
                "Please select exactly one company to copy.",
                level=messages.ERROR,
            )
            return None

        source_company = queryset.first()

        if "apply" in request.POST:
            form = CopyCompanyForm(request.POST)
            if form.is_valid():
                try:
                    with schema_context("public"):
                        new_company = models.Company.objects.create(
                            name=form.cleaned_data["new_name"],
                            domain_url=form.cleaned_data["new_domain_url"],
                            schema_name=form.cleaned_data["new_schema_name"],
                            address=source_company.address,
                            logo=source_company.logo,
                            email=form.cleaned_data.get("new_email")
                            or source_company.email,
                            phone=source_company.phone,
                            tin=source_company.tin,
                            city=source_company.city,
                            country=source_company.country,
                            display_name=source_company.display_name,
                            website=source_company.website,
                            onboarding_data=source_company.onboarding_data,
                            enabled_modules=source_company.enabled_modules,
                            module_overrides=source_company.module_overrides,
                            user_limit_override=source_company.user_limit_override,
                            subscription_grace_days=source_company.subscription_grace_days,
                            grace_reminder_offsets=source_company.grace_reminder_offsets,
                        )

                        models.Domain.objects.create(
                            domain=form.cleaned_data["new_domain_url"],
                            tenant=new_company,
                            is_primary=True,
                        )

                        source_subscription = models.Subscription.objects.filter(
                            company=source_company
                        ).first()
                        new_subscription = models.Subscription.objects.filter(
                            company=new_company
                        ).first()

                        if source_subscription and new_subscription:
                            new_subscription.plan = source_subscription.plan
                            new_subscription.status = source_subscription.status
                            new_subscription.subscription_start_date = (
                                source_subscription.subscription_start_date
                            )
                            new_subscription.subscription_end_date = (
                                source_subscription.subscription_end_date
                            )
                            new_subscription.trial_period_end_date = (
                                source_subscription.trial_period_end_date
                            )
                            new_subscription.is_paid = source_subscription.is_paid
                            new_subscription.payment_gateway = (
                                source_subscription.payment_gateway
                            )
                            new_subscription.gateway_subscription_id = (
                                source_subscription.gateway_subscription_id
                            )
                            new_subscription.gateway_customer_id = (
                                source_subscription.gateway_customer_id
                            )
                            new_subscription.gateway_price_id = (
                                source_subscription.gateway_price_id
                            )
                            new_subscription.billing_cycle = (
                                source_subscription.billing_cycle
                            )
                            new_subscription.is_trial = source_subscription.is_trial
                            new_subscription.extra_users_purchased = (
                                source_subscription.extra_users_purchased
                            )
                            new_subscription.save()

                    clone_tenant_schema_data(
                        source_company.schema_name, new_company.schema_name
                    )

                    self.message_user(
                        request,
                        f'Successfully copied "{source_company.name}" to new tenant "{new_company.name}".',
                        level=messages.SUCCESS,
                    )
                    return None
                except Exception as exc:
                    form.add_error(None, str(exc))
        else:
            form = CopyCompanyForm(
                initial={
                    "new_name": self._suggest_with_suffix(
                        source_company.name,
                        " Copy",
                        lambda value: models.Company.objects.filter(
                            name__iexact=value
                        ).exists(),
                    ),
                    "new_domain_url": self._suggest_domain(source_company.domain_url),
                    "new_schema_name": self._suggest_schema(source_company.schema_name),
                    "new_email": source_company.email,
                }
            )

        context = {
            "title": "Copy company",
            "form": form,
            "opts": self.model._meta,
            "action_checkbox_name": ACTION_CHECKBOX_NAME,
            "queryset": queryset,
            "company": source_company,
        }
        return TemplateResponse(
            request,
            "admin/company/copy_company.html",
            context,
        )


# Register CompanyAdmin with global admin site
global_admin_site.register(models.Company, CompanyAdmin)


@admin.register(models.AddOn)
class AddOnAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "price", "is_per_unit", "is_active", "order")
    list_filter = ("is_active", "is_per_unit")
    search_fields = ("name", "code")


@admin.register(models.Pricing)
class PricingPlanAdmin(admin.ModelAdmin):
    list_display = ("name", "price", "annual_price", "is_active", "module_count", "created_at")
    list_filter = ("is_active", "created_at")
    search_fields = ("name",)
    readonly_fields = ("created_at", "updated_at")

    def module_count(self, obj):
        modules = obj.included_modules or []
        return len(modules)
    module_count.short_description = "Modules"


@admin.register(models.ZentroStarterOffer)
class ZentroStarterOfferAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "device_price",
        "free_months",
        "is_active",
        "is_expired",
        "days_remaining",
        "end_date",
        "has_video",
    )
    list_filter = ("is_active", "free_months", "created_at")
    search_fields = ("name",)
    readonly_fields = (
        "created_at",
        "updated_at",
        "is_expired",
        "days_remaining",
        "video_preview",
    )
    actions = ["activate_offers", "deactivate_offers", "extend_offer_deadline"]
    fieldsets = (
        ("Basic Information", {"fields": ("name", "device_price", "free_months")}),
        (
            "Offer Settings",
            {
                "fields": (
                    "is_active",
                    "end_date",
                    "show_time_limit",
                    "payment_plan",
                    "allows_installments",
                    "default_installment_count",
                )
            },
        ),
        (
            "Device Video",
            {
                "fields": ("device_video", "video_description", "video_preview"),
                "classes": ("collapse",),
            },
        ),
        (
            "System Information",
            {
                "fields": ("created_at", "updated_at", "is_expired", "days_remaining"),
                "classes": ("collapse",),
            },
        ),
    )

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .annotate(days_remaining=models.F("end_date") - models.functions.Now())
        )

    def has_video(self, obj):
        return bool(obj.device_video)

    has_video.boolean = True
    has_video.short_description = "Has Video"

    def video_preview(self, obj):
        if obj.device_video:
            return f"""
            <div style="margin: 10px 0;">
                <video width="320" height="240" controls>
                    <source src="{obj.device_video.url}" type="video/mp4">
                    Your browser does not support the video tag.
                </video>
                <br>
                <a href="{obj.device_video.url}" target="_blank" class="button">View Full Video</a>
            </div>
            """
        return "No video uploaded"

    video_preview.short_description = "Video Preview"
    video_preview.allow_tags = True

    @admin.action(description="Activate selected offers")
    def activate_offers(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"{updated} offers have been activated.")

    @admin.action(description="Deactivate selected offers")
    def deactivate_offers(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"{updated} offers have been deactivated.")

    @admin.action(description="Extend offer deadline by 30 days")
    def extend_offer_deadline(self, request, queryset):
        from datetime import timedelta

        updated = 0
        for offer in queryset:
            offer.end_date += timedelta(days=30)
            offer.save()
            updated += 1
        self.message_user(request, f"{updated} offers have been extended by 30 days.")


@admin.register(models.ZentroStarterOrder)
class ZentroStarterOrderAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "company_name",
        "offer_name",
        "payment_plan",
        "total_amount",
        "amount_paid_display",
        "amount_remaining_display",
        "payment_status",
        "order_status",
        "free_period_days_remaining",
        "subscription_days_remaining",
        "order_date",
    )
    list_filter = (
        "status",
        "payment_status",
        "payment_plan",
        "device_included",
        "order_date",
        "payment_date",
    )
    search_fields = (
        "company__name",
        "company__email",
        "offer__name",
        "payment_reference",
        "gateway_transaction_id",
    )
    readonly_fields = (
        "created_at",
        "updated_at",
        "order_date",
        "total_amount",
        "amount_paid_display",
        "amount_remaining_display",
        "receipt_prefix",
        "next_receipt_number",
        "free_period_days_remaining",
        "subscription_days_remaining",
        "is_offer_active_at_payment",
        "is_free_period_active",
        "is_subscription_active",
        "should_start_monthly_subscription",
        "subscription_summary",
    )
    actions = [
        "mark_as_paid",
        "mark_as_processing",
        "mark_as_completed",
        "mark_as_cancelled",
        "activate_subscription",
        "start_monthly_subscription",
        "extend_subscription_30_days",
        "extend_subscription_90_days",
        "register_manual_payment",
    ]
    inlines = []  # Will be set after ZentroStarterPaymentInline is defined
    fieldsets = (
        (
            "Order Information",
            {
                "fields": (
                    "company",
                    "offer",
                    "status",
                    "order_date",
                    "device_included",
                    "free_months_earned",
                )
            },
        ),
        (
            "Payment Plan Information",
            {
                "fields": (
                    "payment_plan",
                    "total_amount",
                    "amount_paid_display",
                    "amount_remaining_display",
                    "installment_schedule",
                    "stripe_subscription_id",
                )
            },
        ),
        (
            "Payment Information (Legacy)",
            {
                "fields": (
                    "payment_amount",
                    "payment_status",
                    "payment_date",
                    "payment_reference",
                    "payment_gateway",
                    "gateway_transaction_id",
                    "offer_days_remaining_at_payment",
                    "is_offer_active_at_payment",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Subscription Timeline",
            {
                "fields": (
                    "subscription_start_date",
                    "subscription_end_date",
                    "free_period_end_date",
                    "free_period_days_remaining",
                    "subscription_days_remaining",
                    "is_free_period_active",
                    "is_subscription_active",
                    "should_start_monthly_subscription",
                )
            },
        ),
        (
            "Delivery Information",
            {
                "fields": (
                    "delivery_address",
                    "phone_number",
                )
            },
        ),
        (
            "System Information",
            {
                "fields": (
                    "receipt_prefix",
                    "next_receipt_number",
                    "created_at",
                    "updated_at",
                    "subscription_summary",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    def company_name(self, obj):
        return obj.company.name

    company_name.short_description = "Company"

    def offer_name(self, obj):
        return obj.offer.name

    offer_name.short_description = "Offer"

    def order_status(self, obj):
        return obj.get_status_display()

    order_status.short_description = "Order Status"

    def free_period_days_remaining(self, obj):
        return obj.free_period_days_remaining

    free_period_days_remaining.short_description = "Free Period Days"

    def subscription_days_remaining(self, obj):
        return obj.subscription_days_remaining

    subscription_days_remaining.short_description = "Subscription Days"

    def amount_paid_display(self, obj):
        """Display calculated amount paid from all confirmed payments"""
        paid = obj.amount_paid  # This uses the property
        total = obj.total_amount
        if paid >= total and total > 0:
            return f'<span style="color: green; font-weight: bold;">{paid:,.2f} UGX (Fully Paid)</span>'
        elif paid > 0:
            return f'<span style="color: orange; font-weight: bold;">{paid:,.2f} UGX (Partial)</span>'
        return f'<span style="color: gray;">{paid:,.2f} UGX (Not Paid)</span>'

    amount_paid_display.short_description = "Amount Paid (Calculated)"
    amount_paid_display.allow_tags = True

    def amount_remaining_display(self, obj):
        """Display amount remaining with styling"""
        remaining = obj.amount_remaining
        if remaining == 0:
            return f'<span style="color: green; font-weight: bold;">{remaining:,.2f} UGX (Paid)</span>'
        return (
            f'<span style="color: red; font-weight: bold;">{remaining:,.2f} UGX</span>'
        )

    amount_remaining_display.short_description = "Amount Remaining"
    amount_remaining_display.allow_tags = True

    def subscription_summary(self, obj):
        summary = obj.get_subscription_summary()
        return f"""
        <div style="background: #f8f9fa; padding: 10px; border-radius: 5px; font-family: monospace;">
            <strong>Subscription Summary:</strong><br>
            Order ID: {summary['order_id']}<br>
            Company: {summary['company_name']}<br>
            Offer: {summary['offer_name']}<br>
            Payment: {summary['payment_amount']} ({summary['payment_status']})<br>
            Status: {summary['order_status']}<br>
            Free Period: {summary['free_period_active']} ({summary['free_period_days_remaining']} days)<br>
            Subscription: {summary['subscription_active']} ({summary['subscription_days_remaining']} days)<br>
            Offer Active at Payment: {summary['offer_was_active_at_payment']}<br>
            Should Start Monthly: {summary['should_start_monthly']}
        </div>
        """

    subscription_summary.short_description = "Subscription Summary"
    subscription_summary.allow_tags = True

    @admin.action(description="Mark selected orders as paid")
    def mark_as_paid(self, request, queryset):
        for order in queryset:
            order.payment_status = "completed"
            order.payment_date = timezone.now()
            order.status = "paid"
            order.save()
        self.message_user(request, f"{queryset.count()} orders marked as paid.")

    @admin.action(description="Mark selected orders as processing")
    def mark_as_processing(self, request, queryset):
        queryset.update(payment_status="processing")
        self.message_user(request, f"{queryset.count()} orders marked as processing.")

    @admin.action(description="Mark selected orders as completed")
    def mark_as_completed(self, request, queryset):
        for order in queryset:
            order.payment_status = "completed"
            order.process_payment(
                {
                    "reference": f"ADMIN-{order.id}",
                    "gateway": "admin",
                    "transaction_id": f"ADMIN-{order.id}-{timezone.now().timestamp()}",
                }
            )
        self.message_user(request, f"{queryset.count()} orders marked as completed.")

    @admin.action(description="Mark selected orders as cancelled")
    def mark_as_cancelled(self, request, queryset):
        queryset.update(status="cancelled", payment_status="refunded")
        self.message_user(request, f"{queryset.count()} orders marked as cancelled.")

    @admin.action(description="Activate subscription for selected orders")
    def activate_subscription(self, request, queryset):
        for order in queryset:
            if order.payment_status == "completed":
                order.activate_subscription()
        self.message_user(request, f"{queryset.count()} subscriptions activated.")

    @admin.action(description="Start monthly subscription for selected orders")
    def start_monthly_subscription(self, request, queryset):
        for order in queryset:
            if order.should_start_monthly_subscription:
                order.start_monthly_subscription("monthly")
        self.message_user(request, f"{queryset.count()} monthly subscriptions started.")

    @admin.action(description="Extend subscription by 30 days")
    def extend_subscription_30_days(self, request, queryset):
        for order in queryset:
            order.extend_subscription(30)
        self.message_user(
            request, f"{queryset.count()} subscriptions extended by 30 days."
        )

    @admin.action(description="Extend subscription by 90 days")
    def extend_subscription_90_days(self, request, queryset):
        for order in queryset:
            order.extend_subscription(90)
        self.message_user(
            request, f"{queryset.count()} subscriptions extended by 90 days."
        )

    @admin.action(description="Register Manual Payment")
    def register_manual_payment(self, request, queryset):
        """Register a manual payment for selected orders"""
        from django.http import HttpResponseRedirect
        from django.urls import reverse

        # For now, redirect to the payment registration page
        # In a real implementation, you'd show a custom form
        if queryset.count() != 1:
            self.message_user(
                request,
                "Please select exactly one order to register payment.",
                level=messages.ERROR,
            )
            return

        order = queryset.first()
        # Redirect to a custom admin view for payment registration
        # For now, we'll create a simple message
        self.message_user(
            request,
            f"To register payment for Order {order.id}, edit the order and add a payment in the 'Zentro Starter Payments' section below.",
            level=messages.INFO,
        )

    def save_formset(self, request, form, formset, change):
        """Handle saving of inline formsets, specifically for payments"""
        instances = formset.save(commit=False)
        for instance in instances:
            # Set received_by if not set (for new payments added via inline)
            if isinstance(instance, models.ZentroStarterPayment):
                if not instance.received_by:
                    instance.received_by = request.user
                # Set confirmed_by if payment is confirmed but confirmed_by not set
                if instance.is_confirmed and not instance.confirmed_by:
                    instance.confirmed_by = request.user
            instance.save()
        formset.save_m2m()


class ZentroStarterPaymentInline(admin.TabularInline):
    """Inline admin for payments within ZentroStarterOrder"""

    model = models.ZentroStarterPayment
    fk_name = "order"  # Explicitly specify the foreign key field
    extra = 1  # Show one empty form for adding new payment
    verbose_name = "Payment"
    verbose_name_plural = "Zentro Starter Payments"
    can_delete = False  # Prevent deletion, only mark as unconfirmed if needed
    show_change_link = True  # Show link to edit individual payments
    readonly_fields = (
        "receipt_number",
        "reference_number",
        "receipt_sent",
        "receipt_sent_at",
        "created_at",
        "updated_at",
    )
    fields = (
        "payment_method",
        "amount",
        "payment_date",
        "mobile_money_number",
        "mobile_money_provider",
        "mobile_money_reference",
        "is_confirmed",
        "notes",
        "receipt_number",
        "reference_number",
    )

    def has_add_permission(self, request, obj=None):
        # Allow adding payments through inline when editing an order
        return True


# Add inline to ZentroStarterOrderAdmin
ZentroStarterOrderAdmin.inlines = [ZentroStarterPaymentInline]


@admin.register(models.ZentroStarterPayment)
class ZentroStarterPaymentAdmin(admin.ModelAdmin):
    """Admin interface for managing starter pack payments"""

    list_display = (
        "receipt_number",
        "order",
        "amount",
        "payment_method",
        "payment_date",
        "is_confirmed",
        "receipt_sent",
        "created_at",
    )
    list_filter = (
        "payment_method",
        "is_confirmed",
        "receipt_sent",
        "payment_date",
        "created_at",
    )
    search_fields = (
        "receipt_number",
        "reference_number",
        "order__company__name",
        "order__company__email",
        "mobile_money_number",
        "mobile_money_reference",
        "gateway_transaction_id",
    )
    readonly_fields = (
        "receipt_number",
        "reference_number",
        "invoice_pdf_path",
        "receipt_sent",
        "receipt_sent_at",
        "created_at",
        "updated_at",
    )
    fieldsets = (
        (
            "Payment Information",
            {
                "fields": (
                    "order",
                    "payment_method",
                    "amount",
                    "payment_date",
                    "is_confirmed",
                    "confirmed_at",
                    "confirmed_by",
                )
            },
        ),
        (
            "Payment Reference",
            {
                "fields": (
                    "receipt_number",
                    "reference_number",
                    "gateway_transaction_id",
                )
            },
        ),
        (
            "Mobile Money Details",
            {
                "fields": (
                    "mobile_money_number",
                    "mobile_money_provider",
                    "mobile_money_reference",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Manual Payment Details",
            {
                "fields": (
                    "received_by",
                    "notes",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Receipt Information",
            {
                "fields": (
                    "invoice_pdf_path",
                    "receipt_sent",
                    "receipt_sent_at",
                )
            },
        ),
        (
            "System Information",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                ),
                "classes": ("collapse",),
            },
        ),
    )
    actions = [
        "resend_receipt_email",
        "mark_as_confirmed",
        "mark_as_unconfirmed",
    ]

    @admin.action(description="Resend receipt email")
    def resend_receipt_email(self, request, queryset):
        # TODO: Implement email sending
        count = queryset.count()
        self.message_user(
            request,
            f"Receipt emails will be sent for {count} payment(s).",
            level=messages.INFO,
        )

    @admin.action(description="Mark as confirmed")
    def mark_as_confirmed(self, request, queryset):
        for payment in queryset:
            payment.is_confirmed = True
            payment.confirmed_at = timezone.now()
            payment.confirmed_by = request.user
            payment.save()
        self.message_user(
            request, f"{queryset.count()} payment(s) marked as confirmed."
        )

    @admin.action(description="Mark as unconfirmed")
    def mark_as_unconfirmed(self, request, queryset):
        for payment in queryset:
            payment.is_confirmed = False
            payment.confirmed_at = None
            payment.confirmed_by = None
            payment.save()
        self.message_user(
            request, f"{queryset.count()} payment(s) marked as unconfirmed."
        )


@admin.register(models.ZentroStarterInstallmentReminder)
class ZentroStarterInstallmentReminderAdmin(admin.ModelAdmin):
    """Admin interface for installment reminders"""

    list_display = (
        "order",
        "reminder_type",
        "scheduled_date",
        "sent_at",
        "email_sent",
        "sms_sent",
    )
    list_filter = (
        "reminder_type",
        "email_sent",
        "sms_sent",
        "scheduled_date",
        "sent_at",
    )
    search_fields = (
        "order__company__name",
        "order__company__email",
        "notes",
    )
    readonly_fields = (
        "created_at",
        "updated_at",
    )
    fieldsets = (
        (
            "Reminder Information",
            {
                "fields": (
                    "order",
                    "reminder_type",
                    "scheduled_date",
                    "sent_at",
                )
            },
        ),
        (
            "Delivery Status",
            {
                "fields": (
                    "email_sent",
                    "sms_sent",
                    "notes",
                )
            },
        ),
        (
            "System Information",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                ),
                "classes": ("collapse",),
            },
        ),
    )


@admin.register(AppVersion)
class AppVersionAdmin(admin.ModelAdmin):
    list_display = (
        "version_name",
        "build_number",
        "platform",
        "min_required_build",
        "grace_period_days",
        "released_at",
        "is_active",
    )
    list_filter = ("platform", "is_active")
    list_editable = ("is_active",)
    ordering = ("-build_number",)
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        (
            "Version info",
            {
                "fields": (
                    "platform",
                    "version_name",
                    "build_number",
                    "release_notes",
                    "is_active",
                ),
            },
        ),
        (
            "Update policy",
            {
                "fields": (
                    "min_required_build",
                    "grace_period_days",
                    "released_at",
                ),
                "description": (
                    "min_required_build: installed builds below this are hard-blocked "
                    "immediately with no grace period. "
                    "grace_period_days: builds below latest but above min_required_build "
                    "get a dismissible modal for this many days after released_at."
                ),
            },
        ),
        (
            "Download",
            {
                "fields": ("apk_file", "download_url"),
                "description": (
                    "Upload the APK here, OR paste an external URL. "
                    "If both are set, apk_file (S3 upload) takes priority."
                ),
            },
        ),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )


global_admin_site.register(AppVersion, AppVersionAdmin)
