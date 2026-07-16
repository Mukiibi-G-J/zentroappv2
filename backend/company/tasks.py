import time
import logging
import os
import json
import re
from urllib.parse import urlparse
from datetime import datetime, timedelta

from celery import shared_task, current_task
from django.db import transaction, IntegrityError
from django.db.models import Q
from django_tenants.utils import schema_exists, schema_context
from django.conf import settings
from django_tenants.utils import get_tenant_model
from django.db import connection
from helpers.helpers import (
    send_email,
    send_plain_sms,
    setup_default_no_series,
)
from helpers.send_email import send_transactional_email
from django.template.loader import render_to_string
from django.core.management import call_command
from django_tenants.utils import tenant_context
from celery.utils.log import get_task_logger
from django.utils.html import strip_tags
from io import StringIO
from redis.exceptions import ConnectionError as RedisConnectionError
from celery.exceptions import MaxRetriesExceededError
from django.utils import timezone
from company.enums import SubscriptionStatus
from .models import (
    Company,
    Domain,
    CompanyOnBoarding,
    BusinessCategory,
    BusinessObjective,
    Subscription,
    BillingHistory,
    BillingExpiryReminder,
    ensure_debug_admin_for_schema,
)
from company.enums import SubscriptionPlan
from company.subscription_billing import (
    parse_billing_period_from_metadata,
    subscription_period_end_inclusive,
)
from company.tenant_baseline import (
    assign_user_to_admin_group,
    ensure_branch_location,
    ensure_default_vendor_and_customer,
    ensure_inventory_posting_for_branch,
    run_tenant_baseline_bootstrap,
    tenant_has_baseline_data,
)

from authentication.models import CustomUser as User

logger = get_task_logger(__name__)
DEBUG_ADMIN_USERNAME = getattr(settings, "DEBUG_ADMIN_USERNAME", "debug_admin")


def generate_unique_username_for_tenant(full_name: str) -> str:
    """Derive a unique username from full name (tenant User queryset)."""
    raw = (full_name or "user").lower().strip()
    base = re.sub(r"[^a-z0-9]+", "_", raw).strip("_")[:25]
    if not base:
        base = "user"
    candidate = base
    counter = 1
    while User.objects.filter(username=candidate).exists():
        suffix = f"_{counter}"
        room = max(30 - len(suffix), 1)
        candidate = f"{base[:room]}{suffix}"
        counter += 1
        if counter > 9999:
            candidate = f"user_{counter}"
            break
    return candidate





# create_default_roles lives in company.tenant_baseline (imported above)


def update_task_progress(self, progress, message, status):
    """Helper function to update task progress with proper error handling"""
    try:
        self.update_state(
            state="PROGRESS",
            meta={
                "progress": progress,
                "message": message,
                "status": status,
            },
        )
        # Heartbeat for get_task_status: detect abandoned PROGRESS after worker kill.
        task_id = getattr(getattr(self, "request", None), "id", None)
        if task_id:
            from django.core.cache import cache

            cache.set(
                f"company_create_progress_{task_id}",
                {
                    "progress": progress,
                    "message": message,
                    "status": status,
                    "updated_at": time.time(),
                },
                timeout=3600,
            )
        # Remove the small delay for solo pool on Windows
        # time.sleep(0.1)  # This can cause issues with solo pool
    except Exception as e:
        logger.warning(f"Failed to update task state: {e}")


def _log_company_creation_phase(phase: str, t_start: float, last_mark: list) -> None:
    """Structured timing for create_company_task (grep logs for company_creation_timing)."""
    now = time.perf_counter()
    logger.info(
        "company_creation_timing phase=%s elapsed_total_s=%.3f phase_delta_s=%.3f",
        phase,
        now - t_start,
        now - last_mark[0],
    )
    last_mark[0] = now


@shared_task(bind=False, ignore_result=True)
def send_company_creation_admin_sms_task(
    company_name: str, full_name: str, phone: str
) -> None:
    notify_phone = "256750440865"
    msg = (
        f"ZentroApp: Company created. Company: {company_name}. "
        f"Created by: {full_name}. Phone: {phone}."
    )
    try:
        send_plain_sms(notify_phone, msg)
        logger.info("Company-created SMS sent to %s for %s", notify_phone, company_name)
    except Exception as sms_err:
        logger.warning("Could not send company-created SMS: %s", sms_err, exc_info=True)


@shared_task(bind=False, ignore_result=True)
def send_company_creation_completion_email_task(
    company_email: str, company_name: str, login_url: str
) -> None:
    if not (company_email or "").strip():
        logger.warning("Company has no email; skipping completion email task")
        return
    try:
        subject = f"Your {company_name} account is ready on Zentro"
        html = render_to_string(
            "emails/company_creation_completed.html",
            {
                "company_name": company_name,
                "login_url": login_url,
            },
        )
        plain = strip_tags(html)
        sent = send_transactional_email(
            company_email, subject, html, plain_message=plain
        )
        if sent:
            logger.info(
                "Company-creation completion email sent to %s",
                company_email,
            )
        else:
            logger.warning(
                "Failed to send company-creation completion email to %s",
                company_email,
            )
    except Exception as completion_email_error:
        logger.warning(
            "Could not send company-creation completion email: %s",
            completion_email_error,
            exc_info=True,
        )


@shared_task(bind=True, max_retries=3)
def create_company_task(self, data):
    """
    Alternative approach: Use Celery's countdown for delays
    Instead of time.sleep(), you can chain tasks with countdown:

    # Example:
    # create_company_task.apply_async(args=[data], countdown=2)
    # This will delay the task execution by 2 seconds
    """
    try:
        # Validate required fields
        required_fields = [
            "name",
            "email",
            "phone",
            "address",
            "country",
            "full_name",
            "password",
            "organization_size",
            "business_category",
            "business_objective",
        ]

        for field in required_fields:
            if field not in data or not data[field]:
                raise ValueError(f"Missing required field: {field}")

        t_start = time.perf_counter()
        phase_mark = [t_start]
        _log_company_creation_phase("validation_complete", t_start, phase_mark)

        # Initial status
        update_task_progress(self, 10, "Validating data...", "validating")

        schema_name = data["name"].lower()
        if not schema_name.replace("_", "").isalnum():
            raise ValueError("Schema name must be alphanumeric")

        domain_suffix = (
            "localhost"
            if settings.ENVIRONMENT == "development"
            else getattr(
                settings,
                "BACKEND_DOMAIN",
                getattr(settings, "DOMAIN", "zentroapp-api.uncodedsolutions.com"),
            )
        )
        full_domain = f"{schema_name}.{domain_suffix}"

        with schema_context("public"):
            if Company.objects.filter(schema_name=schema_name).exists():
                raise ValueError(
                    f"A company with the name '{data['name']}' already exists."
                )
            if Domain.objects.filter(domain=full_domain).exists():
                raise ValueError(f"The domain '{full_domain}' is already taken.")

        update_task_progress(self, 20, "Creating company...", "creating_company")

        onboarding_data = {
            "organization_size": str(data["organization_size"]),
            "business_category": str(data["business_category"]),
            "business_objective": str(data["business_objective"]),
        }

        with schema_context("public"):
            try:
                company = Company.objects.create(
                    name=data["name"],
                    domain_url=full_domain,
                    schema_name=schema_name,
                    address=data["address"],
                    phone=data["phone"],
                    email=data["email"],
                    city=data.get("city") or None,
                    country=data["country"],
                    onboarding_data=onboarding_data,  # Store as JSON
                    enabled_modules=["pos"],  # POS is the base module and required
                )
                # Prefer clone from pre-seeded `_zentro_template`; falls back to migrations.
                _log_company_creation_phase(
                    "tenant_schema_and_migrations_done", t_start, phase_mark
                )

                update_task_progress(
                    self, 40, "Setting up domain...", "setting_domain"
                )

                # Create domain
                Domain.objects.create(
                    domain=full_domain,
                    tenant=company,
                    is_primary=True,
                )
            except IntegrityError as exc:
                logger.warning(
                    "Duplicate company or domain during create (race or concurrent signup): %s",
                    exc,
                )
                raise ValueError(
                    f"A company with the name '{data['name']}' already exists "
                    "or registration is already in progress. Please choose a different name."
                ) from exc

            _log_company_creation_phase(
                "company_and_domain_created", t_start, phase_mark
            )

            update_task_progress(
                self, 60, "Creating admin user...", "creating_user"
            )

            # Remove delay - handled on frontend
            # time.sleep(2)

            with schema_context(company.schema_name), transaction.atomic():
                try:
                    password = data.get("password") or ""
                    if not password or not str(password).strip():
                        raise ValueError("Password is required and cannot be blank")

                    branch_value = ensure_branch_location(
                        address=data.get("address") or "",
                        city=data.get("city") or "",
                        phone=data["phone"],
                        email=data["email"],
                    )

                    admin_username = generate_unique_username_for_tenant(
                        data["full_name"]
                    )
                    user = User.objects.create_superuser(
                        email=data["email"],
                        username=admin_username,
                        full_name=data["full_name"],
                        phone_number=data["phone"],
                        password=password,
                        is_verified=False,
                    )

                    user.global_dimension_1 = branch_value
                    user.save(update_fields=["global_dimension_1"])

                    send_company_creation_admin_sms_task.delay(
                        company_name=company.name,
                        full_name=data["full_name"],
                        phone=data["phone"],
                    )

                    _log_company_creation_phase(
                        "after_admin_user_bootstrap", t_start, phase_mark
                    )

                    created_roles = []
                    command_output = None
                    used_template_baseline = tenant_has_baseline_data()

                    if used_template_baseline:
                        update_task_progress(
                            self,
                            70,
                            "Using pre-seeded template baseline...",
                            "template_baseline",
                        )
                        logger.info(
                            "Skipping baseline bootstrap for %s "
                            "(cloned from pre-seeded template)",
                            company.name,
                        )
                        assign_user_to_admin_group(user)
                        command_output = "skipped: template baseline"
                        _log_company_creation_phase(
                            "after_roles_permissions_user_groups",
                            t_start,
                            phase_mark,
                        )
                        _log_company_creation_phase(
                            "after_tenant_json_import", t_start, phase_mark
                        )
                    else:
                        update_task_progress(
                            self,
                            68,
                            "Bootstrapping tenant baseline...",
                            "creating_roles",
                        )
                        logger.info(
                            "Running full baseline bootstrap for %s "
                            "(template missing or empty)",
                            company.name,
                        )

                        def _baseline_progress(pct, message, status):
                            update_task_progress(self, pct, message, status)

                        baseline = run_tenant_baseline_bootstrap(
                            company.schema_name,
                            progress=_baseline_progress,
                            ensure_branch=False,
                        )
                        created_roles = baseline.get("created_roles") or []
                        command_output = baseline.get("import_output")
                        assign_user_to_admin_group(user)
                        _log_company_creation_phase(
                            "after_roles_permissions_user_groups",
                            t_start,
                            phase_mark,
                        )
                        _log_company_creation_phase(
                            "after_tenant_json_import", t_start, phase_mark
                        )

                    update_task_progress(
                        self,
                        87,
                        "Configuring subscription...",
                        "importing_data",
                    )
                    subscription_data = data.get("subscription", {}) or {}
                    update_subscription = Subscription.objects.get(company=company)
                    plan = subscription_data.get("plan")
                    if plan and update_subscription.plan != plan:
                        if SubscriptionPlan.MULTI_BRANCH.value in str(plan):
                            update_subscription.plan = (
                                SubscriptionPlan.MULTI_BRANCH.value
                            )
                            update_subscription.is_trial = True
                            update_subscription.status = (
                                SubscriptionStatus.PENDING.value
                            )
                        elif SubscriptionPlan.PREMIUM.value in str(plan):
                            update_subscription.plan = SubscriptionPlan.PREMIUM.value
                            update_subscription.is_trial = False
                            update_subscription.status = (
                                SubscriptionStatus.PENDING.value
                            )
                        update_subscription.save()

                    update_task_progress(
                        self,
                        94,
                        "Creating default vendors and customers...",
                        "setting_up_series",
                    )
                    ensure_default_vendor_and_customer(
                        address=data.get("address") or "",
                        city=data.get("city") or "",
                    )
                    ensure_inventory_posting_for_branch(branch_value.code)

                    _log_company_creation_phase(
                        "after_number_series_and_defaults",
                        t_start,
                        phase_mark,
                    )

                    try:
                        ensure_debug_admin_for_schema(company.schema_name)
                    except Exception as _dbg_e:
                        logger.warning(
                            "ensure_debug_admin (post-bootstrap): %s",
                            _dbg_e,
                            exc_info=True,
                        )

                    login_url_ready = _build_company_login_url(company)
                    send_company_creation_completion_email_task.delay(
                        company_email=company.email or "",
                        company_name=company.name,
                        login_url=login_url_ready,
                    )

                    update_task_progress(
                        self, 96, "Finalizing setup...", "finalizing"
                    )

                except Exception as user_error:
                    logger.error(f"Error creating user: {str(user_error)}")
                    raise ValueError(
                        f"Failed to create admin user: {str(user_error)}"
                    )

            _log_company_creation_phase("completed", t_start, phase_mark)

            login_url_ready = _build_company_login_url(company)
            return {
                "state": "SUCCESS",
                "progress": 100,
                "message": "Company setup completed successfully!",
                "status": "completed",
                "company_name": data["name"],
                "login_url": login_url_ready,
                "used_template_baseline": bool(
                    used_template_baseline
                    if "used_template_baseline" in locals()
                    else False
                ),
                "import_details": (
                    command_output if "command_output" in locals() else None
                ),
                "roles_created": (
                    created_roles if "created_roles" in locals() else []
                ),
                "subscription": {
                    "plan": update_subscription.plan,
                    "status": update_subscription.status,
                    "is_trial": update_subscription.is_trial,
                    "trial_end_date": (
                        update_subscription.trial_period_end_date.isoformat()
                        if update_subscription.trial_period_end_date
                        else None
                    ),
                },
            }

    except ValueError as ve:
        logger.error(f"Validation error: {str(ve)}")
        # Do not update_state(FAILURE, meta=dict) — Celery expects exception
        # payloads with exc_type; a plain meta dict breaks task-status polling.
        raise
    except Exception as e:
        logger.error(f"Error in company creation process: {str(e)}")
        # Tenant onboarding after schema creation runs in nested transaction.atomic(...)
        raise


# @shared_task(name="send_newsletter_task")
# def send_newsletter_task(email):
#     try:
#         send_email("mukiibijoseph19@gmail.com")
#     except Exception as e:
#         raise e


@shared_task
def send_newsletter_task(
    email=None,
):  # Make email parameter optional with default value
    try:
        # If no email is provided, use default
        target_email = email or "mukiibijoseph19@gmail.com"
        send_email(target_email)
        return {
            "status": "success",
            "message": f"Verification email sent to {target_email}",
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


@shared_task
def send_installment_reminders():
    """
    Send reminder emails for upcoming installment due dates.
    Run this daily via Celery Beat.
    """
    from .models import ZentroStarterOrder, ZentroStarterInstallmentReminder
    from django.utils import timezone
    from datetime import timedelta, datetime

    logger = get_task_logger(__name__)
    payment_url = getattr(
        settings, "INSTALLMENT_PAYMENT_URL", "https://zentroapp.app/subscription"
    )

    try:
        # Find orders with installment plans that have upcoming due dates
        now = timezone.now()
        three_days_from_now = now + timedelta(days=3)
        one_day_from_now = now + timedelta(days=1)

        with schema_context("public"):
            # Get orders with installment schedules
            orders = (
                ZentroStarterOrder.objects.filter(
                    payment_plan="installments",
                    status__in=["paid", "active"],
                )
                .exclude(installment_schedule={})
                .select_related("company")
            )
            reminders_sent = 0

            for order in orders:
                try:
                    schedule = order.installment_schedule.get("installments", [])
                    if not schedule:
                        continue

                    # Check each installment
                    for installment in schedule:
                        if installment.get("status") != "pending":
                            continue

                        due_date_str = installment.get("due_date")
                        if not due_date_str:
                            continue

                        # Parse due date
                        try:
                            due_date = datetime.strptime(
                                due_date_str, "%Y-%m-%d"
                            ).date()
                        except (ValueError, TypeError):
                            continue

                        due_datetime = timezone.make_aware(
                            datetime.combine(due_date, datetime.min.time())
                        )

                        # Check if reminder should be sent (3 days before or 1 day before)
                        should_remind_3days = (
                            due_datetime <= three_days_from_now
                            and due_datetime > one_day_from_now
                        )
                        should_remind_1day = (
                            due_datetime <= one_day_from_now and due_datetime > now
                        )

                        if should_remind_3days or should_remind_1day:
                            # Check if reminder already sent
                            reminder_type = (
                                "payment_due" if should_remind_3days else "overdue"
                            )

                            existing_reminder = (
                                ZentroStarterInstallmentReminder.objects.filter(
                                    order=order,
                                    reminder_type=reminder_type,
                                    scheduled_date__date=due_date,
                                ).exists()
                            )

                            if not existing_reminder:
                                # Create reminder record
                                reminder = ZentroStarterInstallmentReminder.objects.create(
                                    order=order,
                                    reminder_type=reminder_type,
                                    scheduled_date=due_datetime,
                                    notes=f"Installment amount: {installment.get('amount', 0):,.2f} UGX",
                                )

                                # Send email
                                if order.company.email:
                                    amount_str = f"{installment.get('amount', 0):,.2f}"
                                    days_until_due = (due_date - now.date()).days
                                    html = render_to_string(
                                        "emails/installment_reminder.html",
                                        {
                                            "company_name": order.company.name,
                                            "due_date": due_date_str,
                                            "amount": amount_str,
                                            "days_until_due": days_until_due,
                                            "payment_url": payment_url,
                                        },
                                    )
                                    subject = (
                                        f"Payment due in {days_until_due} day(s) - {amount_str} UGX"
                                        if days_until_due != 1
                                        else f"Payment due tomorrow - {amount_str} UGX"
                                    )
                                    if send_transactional_email(
                                        order.company.email, subject, html
                                    ):
                                        reminder.email_sent = True
                                        reminder.sent_at = timezone.now()
                                        reminder.save(
                                            update_fields=["email_sent", "sent_at"]
                                        )
                                        reminders_sent += 1
                                else:
                                    logger.warning(
                                        f"Company {order.company.name} has no email - skipping installment reminder"
                                    )

                except Exception as e:
                    logger.error(f"Error processing order {order.id}: {e}")
                    continue

        logger.info(f"Sent {reminders_sent} installment reminders")
        return {"status": "success", "reminders_sent": reminders_sent}

    except Exception as e:
        logger.error(f"Error in send_installment_reminders: {e}")
        raise


@shared_task
def send_trial_end_reminders():
    """
    Send reminder emails for free trials ending in 3 days or 1 day.
    Covers both Subscription (legacy 14-day trial) and ZentroStarterOrder (starter pack free period).
    Run this daily via Celery Beat (e.g. 9:00 AM).
    """
    from .models import (
        ZentroStarterOrder,
        TrialEndReminder,
    )

    logger = get_task_logger(__name__)
    reminders_sent = 0
    payment_url = getattr(
        settings, "TRIAL_REMINDER_PAYMENT_URL", "https://zentroapp.app/subscription"
    )

    try:
        now = timezone.now().date()
        three_days_later = now + timedelta(days=3)
        one_day_later = now + timedelta(days=1)

        with schema_context("public"):
            # --- Subscription trials (status=TRIAL, is_trial) ---
            subscriptions = Subscription.objects.filter(
                status=SubscriptionStatus.TRIAL.value,
                is_trial=True,
                trial_period_end_date__gte=now,
                trial_period_end_date__lte=three_days_later,
            ).select_related("company")

            for sub in subscriptions:
                trial_end = sub.trial_period_end_date
                days_left = (trial_end - now).days
                reminder_type = "3_days" if days_left == 3 else "1_day"

                if days_left not in (1, 3):
                    continue

                if not sub.company.email:
                    logger.warning(
                        f"Company {sub.company.name} has no email - skipping trial reminder"
                    )
                    continue

                exists = TrialEndReminder.objects.filter(
                    company=sub.company,
                    reminder_type=reminder_type,
                    trial_end_date=trial_end,
                    source="subscription",
                    source_id=sub.id,
                ).exists()

                if exists:
                    continue

                html = render_to_string(
                    "emails/trial_end_reminder.html",
                    {
                        "company_name": sub.company.name,
                        "trial_end_date": trial_end,
                        "days_remaining": days_left,
                        "payment_url": payment_url,
                        "source": "subscription",
                    },
                )
                subject = f"Your Zentro free trial ends in {days_left} day(s) - Subscribe to continue"
                if send_transactional_email(sub.company.email, subject, html):
                    TrialEndReminder.objects.create(
                        company=sub.company,
                        reminder_type=reminder_type,
                        trial_end_date=trial_end,
                        source="subscription",
                        source_id=sub.id,
                    )
                    reminders_sent += 1

            # --- ZentroStarterOrder free period ---
            starter_orders = (
                ZentroStarterOrder.objects.filter(
                    status="active",
                )
                .exclude(
                    free_period_end_date__isnull=True,
                )
                .select_related("company")
            )

            for order in starter_orders:
                if not order.is_free_period_active or not order.free_period_end_date:
                    continue

                trial_end = order.free_period_end_date.date()
                if trial_end < now or trial_end > three_days_later:
                    continue

                days_left = (trial_end - now).days
                if days_left not in (1, 3):
                    continue

                reminder_type = "3_days" if days_left == 3 else "1_day"

                if not order.company.email:
                    logger.warning(
                        f"Company {order.company.name} has no email - skipping trial reminder"
                    )
                    continue

                exists = TrialEndReminder.objects.filter(
                    company=order.company,
                    reminder_type=reminder_type,
                    trial_end_date=trial_end,
                    source="starter_order",
                    source_id=order.id,
                ).exists()

                if exists:
                    continue

                html = render_to_string(
                    "emails/trial_end_reminder.html",
                    {
                        "company_name": order.company.name,
                        "trial_end_date": trial_end,
                        "days_remaining": days_left,
                        "payment_url": payment_url,
                        "source": "starter_order",
                    },
                )
                subject = f"Your Zentro free period ends in {days_left} day(s) - Subscribe to continue"
                if send_transactional_email(order.company.email, subject, html):
                    TrialEndReminder.objects.create(
                        company=order.company,
                        reminder_type=reminder_type,
                        trial_end_date=trial_end,
                        source="starter_order",
                        source_id=order.id,
                    )
                    reminders_sent += 1

        logger.info(f"Sent {reminders_sent} trial-end reminders")
        return {"status": "success", "reminders_sent": reminders_sent}

    except Exception as e:
        logger.exception(f"Error in send_trial_end_reminders: {e}")
        raise


@shared_task
def send_overdue_notices():
    """
    Send overdue payment notices for past due installments.
    Run this daily via Celery Beat.
    """
    from .models import ZentroStarterOrder, ZentroStarterInstallmentReminder
    from django.utils import timezone
    from datetime import datetime, timedelta

    logger = get_task_logger(__name__)
    payment_url = getattr(
        settings, "INSTALLMENT_PAYMENT_URL", "https://zentroapp.app/subscription"
    )

    try:
        now = timezone.now()

        with schema_context("public"):
            # Find orders with overdue installments
            orders = (
                ZentroStarterOrder.objects.filter(
                    payment_plan="installments",
                    status__in=["paid", "active"],
                )
                .exclude(installment_schedule={})
                .select_related("company")
            )
            notices_sent = 0

            for order in orders:
                try:
                    schedule = order.installment_schedule.get("installments", [])
                    if not schedule:
                        continue

                    # Check each installment
                    for installment in schedule:
                        if installment.get("status") != "pending":
                            continue

                        due_date_str = installment.get("due_date")
                        if not due_date_str:
                            continue

                        try:
                            due_date = datetime.strptime(
                                due_date_str, "%Y-%m-%d"
                            ).date()
                        except (ValueError, TypeError):
                            continue

                        # Check if overdue
                        if due_date < now.date():
                            due_datetime = timezone.make_aware(
                                datetime.combine(due_date, datetime.min.time())
                            )

                            # Check if notice already sent in last 7 days
                            seven_days_ago = now - timedelta(days=7)
                            existing_notice = (
                                ZentroStarterInstallmentReminder.objects.filter(
                                    order=order,
                                    reminder_type="overdue",
                                    scheduled_date__gte=seven_days_ago,
                                    scheduled_date__date=due_date,
                                ).exists()
                            )

                            if not existing_notice:
                                # Create overdue notice
                                reminder = ZentroStarterInstallmentReminder.objects.create(
                                    order=order,
                                    reminder_type="overdue",
                                    scheduled_date=due_datetime,
                                    notes=f"Overdue installment: {installment.get('amount', 0):,.2f} UGX (Due: {due_date_str})",
                                )

                                # Send email
                                if order.company.email:
                                    amount_str = f"{installment.get('amount', 0):,.2f}"
                                    days_overdue = (now.date() - due_date).days
                                    html = render_to_string(
                                        "emails/installment_overdue.html",
                                        {
                                            "company_name": order.company.name,
                                            "due_date": due_date_str,
                                            "amount": amount_str,
                                            "days_overdue": days_overdue,
                                            "payment_url": payment_url,
                                        },
                                    )
                                    subject = f"Overdue payment notice - {amount_str} UGX ({days_overdue} day(s) overdue)"
                                    if send_transactional_email(
                                        order.company.email, subject, html
                                    ):
                                        reminder.email_sent = True
                                        reminder.sent_at = timezone.now()
                                        reminder.save(
                                            update_fields=[
                                                "email_sent",
                                                "sent_at",
                                            ]
                                        )
                                        notices_sent += 1
                                else:
                                    logger.warning(
                                        f"Company {order.company.name} has no email - skipping overdue notice"
                                    )

                except Exception as e:
                    logger.error(f"Error processing order {order.id}: {e}")
                    continue

        logger.info(f"Sent {notices_sent} overdue notices")
        return {"status": "success", "notices_sent": notices_sent}

    except Exception as e:
        logger.error(f"Error in send_overdue_notices: {e}")
        raise


# Product terms that indicate subscription billing (for 10-day expiry reminders)
_BILLING_SUBSCRIPTION_PRODUCT_TERMS = [
    "subscription",
    "standard",
    "premium",
    "multi-branch",
    "multi_branch",
    "business",
    "pro",
    "starter",
    "efris",
]


def _get_companies_for_expiry_reminders_window(days_min=1, days_max=10):
    """
    Get list of (company, billing_history_or_none, period_end_date, days_remaining, source, source_id)
    for companies in a configurable expiry window.
    Includes: BillingHistory (paid), Subscription (trial), ZentroStarterOrder (free period).
    """
    now = timezone.now().date()
    results = []
    seen_company_keys = set()  # (company_id, source, source_id) to avoid dupes

    def in_window(days_remaining):
        min_ok = True if days_min is None else days_remaining >= days_min
        max_ok = True if days_max is None else days_remaining <= days_max
        return min_ok and max_ok

    # 1. Subscription trials (status=TRIAL, trial_period_end_date in configured window)
    subscriptions = Subscription.objects.filter(
        status=SubscriptionStatus.TRIAL.value,
    )
    if days_min is not None:
        subscriptions = subscriptions.filter(
            trial_period_end_date__gte=now + timedelta(days=days_min)
        )
    if days_max is not None:
        subscriptions = subscriptions.filter(
            trial_period_end_date__lte=now + timedelta(days=days_max)
        )
    subscriptions = subscriptions.select_related("company")
    for sub in subscriptions:
        days_remaining = (sub.trial_period_end_date - now).days
        if in_window(days_remaining):
            key = (sub.company_id, "subscription", sub.id)
            if key not in seen_company_keys:
                seen_company_keys.add(key)
                results.append(
                    (
                        sub.company,
                        None,
                        sub.trial_period_end_date,
                        days_remaining,
                        "subscription",
                        sub.id,
                    )
                )

    # 2. ZentroStarterOrder (active, free_period_end_date or subscription_end_date in configured window)
    from .models import ZentroStarterOrder

    for order in ZentroStarterOrder.objects.filter(status="active").select_related(
        "company"
    ):
        end_date = None
        if order.free_period_end_date:
            end_date = order.free_period_end_date.date()
        elif order.subscription_end_date:
            end_date = order.subscription_end_date.date()
        if not end_date or end_date < now:
            continue
        days_remaining = (end_date - now).days
        if in_window(days_remaining):
            key = (order.company_id, "starter_order", order.id)
            if key not in seen_company_keys:
                seen_company_keys.add(key)
                results.append(
                    (
                        order.company,
                        None,
                        end_date,
                        days_remaining,
                        "starter_order",
                        order.id,
                    )
                )

    # 3. BillingHistory (paid, period_end = billing_date + 30 in configured window)
    product_filter = Q()
    for term in _BILLING_SUBSCRIPTION_PRODUCT_TERMS:
        product_filter |= Q(product__icontains=term)
    paid_billings = (
        BillingHistory.objects.filter(
            status="paid",
        )
        .filter(product_filter)
        .select_related("company")
        .order_by("company_id", "-billing_date")
    )

    seen_billing_companies = set()
    for billing in paid_billings:
        if billing.company_id in seen_billing_companies:
            continue
        seen_billing_companies.add(billing.company_id)
        months, bc = parse_billing_period_from_metadata(billing.metadata)
        period_end_date = subscription_period_end_inclusive(
            billing.billing_date, months, bc
        )
        days_remaining = (period_end_date - now).days
        if in_window(days_remaining):
            results.append(
                (
                    billing.company,
                    billing,
                    period_end_date,
                    days_remaining,
                    "billing_history",
                    billing.id,
                )
            )

    return results


def _get_companies_for_expiry_reminders(days_min=1, days_max=10):
    return _get_companies_for_expiry_reminders_window(
        days_min=days_min, days_max=days_max
    )


def _get_company_superuser_emails(company):
    """Get superuser emails from the tenant schema for a given company."""
    recipients = []
    try:
        if not company or not getattr(company, "schema_name", None):
            return recipients
        if not schema_exists(company.schema_name):
            return recipients
        with schema_context(company.schema_name):
            recipients = list(
                User.objects.filter(is_superuser=True)
                .exclude(username=DEBUG_ADMIN_USERNAME)
                .values_list("email", flat=True)
            )
    except Exception as exc:
        logger.warning(
            f"Could not resolve superusers for company={getattr(company, 'name', '-')}: {exc}"
        )
        recipients = []
    return [email for email in recipients if email]


class _SafeFormatDict(dict):
    def __missing__(self, key):
        return "{" + key + "}"


def _render_custom_reminder_html(company_name, message, payment_url=None):
    safe_company = company_name or "Customer"
    body_lines = (message or "").splitlines()
    body_html = "<br>".join(
        line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        for line in body_lines
    )
    cta_html = ""
    if payment_url:
        safe_payment_url = (
            str(payment_url)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
        cta_html = (
            "<p style='margin-top: 18px;'>"
            f"<a href='{safe_payment_url}' "
            "style='background:#0b5ed7;color:#fff;padding:10px 16px;text-decoration:none;border-radius:4px;'>"
            "Open Company Page"
            "</a>"
            "</p>"
        )

    return (
        "<html><body style='font-family: Arial, sans-serif; color: #333;'>"
        f"<p>Hello {safe_company},</p>"
        f"<p>{body_html}</p>"
        f"{cta_html}"
        "<p>Regards,<br>The Zentro Team</p>"
        "</body></html>"
    )


def _build_company_subscription_url(company):
    """
    Build per-company frontend URL for subscription/company page.
    Example (dev): http://primewise.localhost:5173/app/company
    """
    fallback = getattr(
        settings, "TRIAL_REMINDER_PAYMENT_URL", "https://zentroapp.app/subscription"
    )
    if not company or not getattr(company, "domain_url", None):
        return fallback

    raw_domain = str(company.domain_url).strip().rstrip("/")
    if not raw_domain:
        return fallback

    scheme = ""
    host = raw_domain
    if raw_domain.startswith("http://") or raw_domain.startswith("https://"):
        parsed = urlparse(raw_domain)
        scheme = parsed.scheme
        host = parsed.netloc

    host_lower = host.lower()
    # Tenant `domain_url` is the API host; map to the frontend host for links.
    backend_domain = getattr(
        settings, "BACKEND_DOMAIN", "zentroapp-api.uncodedsolutions.com"
    )
    frontend_domain = getattr(settings, "DOMAIN", "zentroapp.uncodedsolutions.com")
    if backend_domain and backend_domain in host_lower:
        host = host.replace(backend_domain, frontend_domain)
    # Legacy V1 mapping
    elif "zentroapp-backend.com" in host_lower:
        host = host.replace("zentroapp-backend.com", "zentroapp.app")

    is_local = host_lower.endswith(".localhost") or host_lower == "localhost"

    if not scheme:
        scheme = "http" if is_local else "https"

    has_explicit_port = ":" in host and host.rsplit(":", 1)[1].isdigit()
    if is_local and not has_explicit_port:
        host = f"{host}:5173"

    return f"{scheme}://{host}/app/company"


def _build_company_login_url(company):
    """Build per-company frontend login URL."""
    frontend_domain = getattr(settings, "DOMAIN", "zentroapp.uncodedsolutions.com")
    fallback = f"https://{frontend_domain}/login"
    if not company or not getattr(company, "domain_url", None):
        return fallback

    raw_domain = str(company.domain_url).strip().rstrip("/")
    if not raw_domain:
        return fallback

    scheme = ""
    host = raw_domain
    if raw_domain.startswith("http://") or raw_domain.startswith("https://"):
        parsed = urlparse(raw_domain)
        scheme = parsed.scheme
        host = parsed.netloc

    host_lower = host.lower()
    backend_domain = getattr(
        settings, "BACKEND_DOMAIN", "zentroapp-api.uncodedsolutions.com"
    )
    if backend_domain and backend_domain in host_lower:
        host = host.replace(backend_domain, frontend_domain)
        host_lower = host.lower()
    elif "zentroapp-backend.com" in host_lower:
        host = host.replace("zentroapp-backend.com", "zentroapp.app")
        host_lower = host.lower()

    is_local = host_lower.endswith(".localhost") or host_lower == "localhost"
    if not scheme:
        scheme = "http" if is_local else "https"

    has_explicit_port = ":" in host and host.rsplit(":", 1)[1].isdigit()
    if is_local and not has_explicit_port:
        # Next.js app (V2) defaults to 3000; override with FRONTEND_DEV_PORT if needed.
        front_port = getattr(settings, "FRONTEND_DEV_PORT", None) or os.getenv(
            "FRONTEND_DEV_PORT", "3000"
        )
        host = f"{host}:{front_port}"

    return f"{scheme}://{host}/login"


@shared_task
def send_billing_expiry_reminders_custom(
    reminder_key,
    subject_template,
    body_template,
    send_email=True,
    days_min=1,
    days_max=10,
    selected_recipients_map=None,
):
    """
    Parameterized expiry reminder sender used by admin preview/send page.
    Sends to tenant superusers per company (excluding debug_admin).
    """
    logger = get_task_logger(__name__)
    now = timezone.now().date()

    reminders_sent = 0
    reminders_skipped = 0
    companies_without_superusers = []
    companies_excluded_by_selection = []
    recipient_emails_sent = 0
    recipient_emails_failed = []

    try:
        with schema_context("public"):
            rows = list(
                _get_companies_for_expiry_reminders(
                    days_min=days_min,
                    days_max=days_max,
                )
            )
            logger.info(
                f"Found {len(rows)} companies in {days_min}-{days_max} day expiry window for reminder_key={reminder_key}"
            )

            for (
                company,
                billing_history,
                period_end_date,
                days_remaining,
                source,
                source_id,
            ) in rows:
                row_key = f"{company.id}:{source}:{source_id}"
                already_sent = BillingExpiryReminder.objects.filter(
                    company=company,
                    source=source,
                    source_id=source_id,
                    reminder_key=reminder_key,
                    sent_at__date=now,
                ).exists()
                if already_sent:
                    reminders_skipped += 1
                    continue

                base_recipients = _get_company_superuser_emails(company)
                recipients = list(base_recipients)
                if isinstance(selected_recipients_map, dict):
                    selected_for_row = selected_recipients_map.get(row_key, [])
                    selected_set = (
                        set(selected_for_row)
                        if isinstance(selected_for_row, list)
                        else set()
                    )
                    recipients = [
                        email for email in recipients if email in selected_set
                    ]

                if not recipients:
                    if not base_recipients:
                        companies_without_superusers.append(company.name)
                    elif isinstance(selected_recipients_map, dict):
                        companies_excluded_by_selection.append(company.name)
                    else:
                        companies_without_superusers.append(company.name)
                    continue

                fmt_ctx = _SafeFormatDict(
                    {
                        "company_name": company.name,
                        "days_remaining": days_remaining,
                        "period_end_date": str(period_end_date),
                        "payment_url": _build_company_subscription_url(company),
                    }
                )
                subject = (subject_template or "").format_map(fmt_ctx).strip()
                body_text = (body_template or "").format_map(fmt_ctx).strip()
                html = _render_custom_reminder_html(
                    company.name,
                    body_text,
                    payment_url=fmt_ctx.get("payment_url"),
                )

                email_failed = False
                if send_email:
                    for recipient in recipients:
                        sent = send_transactional_email(
                            recipient,
                            subject,
                            html,
                            plain_message=body_text,
                        )
                        if sent:
                            recipient_emails_sent += 1
                        else:
                            email_failed = True
                            recipient_emails_failed.append(recipient)

                if send_email and not email_failed:
                    BillingExpiryReminder.objects.create(
                        company=company,
                        billing_history=billing_history,
                        source=source,
                        source_id=source_id,
                        period_end_date=period_end_date,
                        days_remaining=days_remaining,
                        reminder_key=reminder_key,
                    )
                    reminders_sent += 1

        return {
            "status": "success",
            "reminders_sent": reminders_sent,
            "reminders_skipped": reminders_skipped,
            "recipient_emails_sent": recipient_emails_sent,
            "recipient_emails_failed": recipient_emails_failed,
            "companies_without_superusers": companies_without_superusers,
            "companies_excluded_by_selection": companies_excluded_by_selection,
            "companies_found": len(rows),
        }
    except Exception as exc:
        logger.exception(f"Error in send_billing_expiry_reminders_custom: {exc}")
        raise


@shared_task
def send_billing_expiry_10day_reminders():
    """
    Send reminder emails every day for companies in the 10-day expiry window.
    Includes BillingHistory, Subscription (trial), ZentroStarterOrder.
    BCC to superuser (excl. debug_admin).
    Run daily via Celery Beat at 8:00 AM UTC.
    """
    logger = get_task_logger(__name__)
    payment_url = getattr(
        settings, "TRIAL_REMINDER_PAYMENT_URL", "https://zentroapp.app/subscription"
    )

    try:
        now = timezone.now().date()
        reminders_sent = 0
        reminders_skipped = 0
        reminders_failed = []
        companies_no_email = []

        with schema_context("public"):
            # BCC to superuser - User may be tenant-specific, wrap to avoid schema errors
            try:
                bcc_emails = list(
                    User.objects.filter(is_superuser=True)
                    .exclude(username=DEBUG_ADMIN_USERNAME)
                    .values_list("email", flat=True)
                )
                bcc_emails = [e for e in bcc_emails if e]
            except Exception as e:
                logger.warning(
                    f"Could not fetch BCC superusers: {e}. Sending without BCC."
                )
                bcc_emails = []

            rows = list(_get_companies_for_expiry_reminders())
            logger.info(f"Found {len(rows)} companies in 10-day expiry window")

            for (
                company,
                billing_history,
                period_end_date,
                days_remaining,
                source,
                source_id,
            ) in rows:
                if not company.email:
                    companies_no_email.append(company.name)
                    continue

                # Skip if already sent today (by source/source_id since billing_history can be null)
                already_sent = BillingExpiryReminder.objects.filter(
                    company=company,
                    source=source,
                    source_id=source_id,
                    reminder_key="expiry_10_day",
                    sent_at__date=now,
                ).exists()
                if already_sent:
                    reminders_skipped += 1
                    continue

                html = render_to_string(
                    "emails/trial_end_reminder.html",
                    {
                        "company_name": company.name,
                        "trial_end_date": period_end_date,
                        "days_remaining": days_remaining,
                        "payment_url": payment_url,
                    },
                )
                subject = f"Your Zentro subscription expires in {days_remaining} day(s) - Renew to continue"
                success = send_transactional_email(
                    company.email,
                    subject,
                    html,
                    bcc=bcc_emails if bcc_emails else None,
                )
                if success:
                    BillingExpiryReminder.objects.create(
                        company=company,
                        billing_history=billing_history,
                        source=source,
                        source_id=source_id,
                        period_end_date=period_end_date,
                        days_remaining=days_remaining,
                        reminder_key="expiry_10_day",
                    )
                    reminders_sent += 1
                else:
                    reminders_failed.append(company.name)
                    logger.warning(
                        f"Failed to send expiry reminder to {company.name} ({company.email})"
                    )

        logger.info(
            f"Sent {reminders_sent} billing expiry reminders; skipped {reminders_skipped}; failed {len(reminders_failed)}; companies_found={len(rows)}"
        )
        return {
            "status": "success",
            "reminders_sent": reminders_sent,
            "reminders_skipped": reminders_skipped,
            "reminders_failed": reminders_failed,
            "companies_no_email": companies_no_email,
            "companies_found": len(rows),
        }

    except Exception as e:
        logger.exception(f"Error in send_billing_expiry_10day_reminders: {e}")
        raise


@shared_task
def send_grace_period_payment_reminders():
    """
    Daily: email company contact during subscription grace (payment overdue).
    Deduped via BillingExpiryReminder per (company, period_end, offset).
    """
    logger = get_task_logger(__name__)
    payment_url = getattr(
        settings, "TRIAL_REMINDER_PAYMENT_URL", "https://zentroapp.app/subscription"
    )
    today = timezone.now().date()
    reminders_sent = 0
    reminders_skipped = 0
    reminders_failed = []

    from company.subscription_grace import (
        access_lock_date_for,
        expiry_kind_for_subscription,
        grace_days_for_company,
        in_grace_period,
        payment_due_date,
        period_end_date,
        reminder_offsets_for_company,
    )

    try:
        with schema_context("public"):
            try:
                bcc_emails = list(
                    User.objects.filter(is_superuser=True)
                    .exclude(username=DEBUG_ADMIN_USERNAME)
                    .values_list("email", flat=True)
                )
                bcc_emails = [e for e in bcc_emails if e]
            except Exception as e:
                logger.warning(f"Grace reminders: could not load BCC: {e}")
                bcc_emails = []

            for company in Company.objects.all().iterator():
                sub = Subscription.objects.filter(company=company).first()
                if not sub:
                    continue
                if not in_grace_period(today, sub, company):
                    continue
                due = payment_due_date(sub)
                if not due:
                    continue
                period_end = period_end_date(sub)
                offsets = reminder_offsets_for_company(company)
                gd = grace_days_for_company(company)
                lock = access_lock_date_for(sub, company)
                days_until_lock = (lock - today).days if lock else 0

                for offset in offsets:
                    if offset < 0 or offset >= gd:
                        continue
                    reminder_day = due + timedelta(days=offset)
                    if reminder_day != today:
                        continue
                    key = f"grace_payment_offset_{offset}"
                    if BillingExpiryReminder.objects.filter(
                        company=company,
                        reminder_key=key,
                        period_end_date=period_end,
                        source="grace_period",
                        source_id=offset,
                    ).exists():
                        reminders_skipped += 1
                        continue

                    to_email = company.email
                    if not to_email:
                        reminders_skipped += 1
                        continue

                    kind = expiry_kind_for_subscription(sub)
                    if kind == "trial":
                        body_lead = (
                            "Your trial period has ended and payment is now due to keep using Zentro."
                        )
                        subject = (
                            f"Action needed: complete your Zentro subscription — {company.name}"
                        )
                    else:
                        body_lead = (
                            "Your subscription payment is overdue. Please renew to keep full access."
                        )
                        subject = (
                            f"Payment overdue: renew your Zentro subscription — {company.name}"
                        )

                    html = render_to_string(
                        "emails/grace_period_reminder.html",
                        {
                            "company_name": company.name,
                            "body_lead": body_lead,
                            "payment_url": payment_url,
                            "lock_date": lock.isoformat() if lock else "",
                            "days_until_lock": max(0, days_until_lock),
                        },
                    )
                    ok = send_transactional_email(
                        to_email,
                        subject,
                        html,
                        bcc=bcc_emails if bcc_emails else None,
                    )
                    if ok:
                        BillingExpiryReminder.objects.create(
                            company=company,
                            billing_history=None,
                            source="grace_period",
                            source_id=offset,
                            reminder_key=key,
                            period_end_date=period_end,
                            days_remaining=max(0, days_until_lock),
                        )
                        reminders_sent += 1
                    else:
                        reminders_failed.append(company.name)

        logger.info(
            "Grace period reminders: sent=%s skipped=%s failed=%s",
            reminders_sent,
            reminders_skipped,
            len(reminders_failed),
        )
        return {
            "status": "success",
            "reminders_sent": reminders_sent,
            "reminders_skipped": reminders_skipped,
            "reminders_failed": reminders_failed,
        }
    except Exception as e:
        logger.exception(f"Error in send_grace_period_payment_reminders: {e}")
        raise


@shared_task
def generate_pending_receipts():
    """
    Generate PDF receipts for payments that don't have receipts yet.
    Run this hourly via Celery Beat.
    """
    from .models import ZentroStarterPayment
    from .receipt_utils import generate_receipt_pdf

    logger = get_task_logger(__name__)

    try:
        # Find payments without PDF receipts
        payments = ZentroStarterPayment.objects.filter(
            is_confirmed=True,
        ).filter(Q(invoice_pdf_path__isnull=True) | Q(invoice_pdf_path=""))

        generated = 0

        for payment in payments:
            try:
                generate_receipt_pdf(payment, save_to_file=True)
                generated += 1
            except Exception as e:
                logger.error(f"Error generating receipt for payment {payment.id}: {e}")
                continue

        logger.info(f"Generated {generated} receipt PDFs")
        return {"status": "success", "generated": generated}

    except Exception as e:
        logger.error(f"Error in generate_pending_receipts: {e}")
        raise


@shared_task(bind=True)
def import_initial_data_task(self, company_name, file_path):
    try:
        # Switch to public schema first
        with schema_context("public"):
            # Get the company
            company = Company.objects.get(name=company_name)

            # Then switch to company schema for import
            with tenant_context(company):
                self.update_state(
                    state="PROGRESS",
                    meta={
                        "progress": 30,
                        "message": "Starting data import...",
                        "status": "starting_import",
                    },
                )

                try:
                    logger.info(
                        f"Starting data import for {company_name} using {file_path}"
                    )

                    from io import StringIO
                    import sys

                    # Capture command output
                    output = StringIO()
                    sys.stdout = output

                    self.update_state(
                        state="PROGRESS",
                        meta={
                            "progress": 50,
                            "message": "Importing initial data...",
                            "status": "importing_data",
                        },
                    )

                    result = call_command(
                        "import_tenant_data",
                        company.schema_name,
                        file_path,
                        verbosity=1,  # Increase verbosity to see output
                    )

                    # Restore stdout
                    sys.stdout = sys.__stdout__
                    command_output = output.getvalue()
                    logger.info(f"Import command output: {command_output}")

                    if not isinstance(result, dict):
                        logger.warning(f"Unexpected result type: {type(result)}")
                        result = {"success": False, "error": "Invalid command result"}

                    if not result.get("success", False):
                        error_msg = result.get(
                            "error", "Unknown error during data import"
                        )
                        logger.error(f"Import failed: {error_msg}")
                        raise Exception(error_msg)

                    self.update_state(
                        state="PROGRESS",
                        meta={
                            "progress": 85,
                            "message": "Setting up number series...",
                            "status": "setting_up_series",
                        },
                    )

                    # Setup number series
                    series_result = setup_default_no_series()
                    logger.info(f"Number series setup result: {series_result}")

                    self.update_state(
                        state="PROGRESS",
                        meta={
                            "progress": 95,
                            "message": "Finalizing setup...",
                            "status": "finalizing",
                        },
                    )

                except Exception as import_error:
                    logger.error(f"Error during data import: {str(import_error)}")
                    raise import_error

                return {
                    "state": "SUCCESS",
                    "progress": 100,
                    "message": "Setup completed successfully!",
                    "status": "completed",
                    "company_name": company_name,
                    "import_details": (
                        command_output if "command_output" in locals() else None
                    ),
                }

    except Exception as e:
        logger.error(f"Error importing initial data: {str(e)}")
        return {
            "state": "FAILURE",
            "progress": 0,
            "message": f"Error importing initial data: {str(e)}",
            "error": str(e),
            "status": "failed",
        }
