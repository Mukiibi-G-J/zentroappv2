"""
Reset a tenant company's subscription to the normal 14-day Free Trial state.

Use when signup incorrectly set legacy Standard Plan / pending / no trial
(e.g. stale frontend plan name).

Examples::

    python manage.py fix_subscription_reset_free_trial --email=thejunctionbar91@gmail.com

    python manage.py fix_subscription_reset_free_trial --schema=dejunctionbarandresturant

    python manage.py fix_subscription_reset_free_trial --email=... --dry-run
"""

from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

try:
    from django_tenants.utils import get_public_schema_name, schema_context
except ImportError:
    get_public_schema_name = None
    schema_context = None

from company.enums import SubscriptionPlan, SubscriptionStatus
from company.models import Company, Subscription


class Command(BaseCommand):
    help = (
        "Set Subscription to Free Trial with 14-day window from company created_at "
        "and recompute enabled_modules."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--email",
            type=str,
            default=None,
            help="Company.email on the public tenant (Client) row",
        )
        parser.add_argument(
            "--schema",
            type=str,
            default=None,
            help="Tenant schema_name (alternative to --email)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print what would change without saving",
        )
        parser.add_argument(
            "--extend-if-expired",
            action="store_true",
            help=(
                "If created_at+14 is already past, set trial end to today+14 "
                "(support extension). Default: keep created_at+14 only."
            ),
        )

    def handle(self, *args, **options):
        if schema_context is None or get_public_schema_name is None:
            raise CommandError("django-tenants is required for this command.")

        email = options["email"]
        schema = options["schema"]
        if bool(email) == bool(schema) and not (email or schema):
            raise CommandError("Pass exactly one of --email or --schema.")
        if email and schema:
            raise CommandError("Pass only one of --email or --schema.")

        dry_run = options["dry_run"]
        extend_if_expired = options["extend_if_expired"]

        public = get_public_schema_name()
        with schema_context(public):
            if schema:
                company = Company.objects.filter(schema_name=schema).first()
                if not company:
                    raise CommandError(f"No company with schema_name={schema!r}")
            else:
                company = Company.objects.filter(email__iexact=email.strip()).first()
                if not company:
                    raise CommandError(f"No company with email={email!r}")

            try:
                subscription = Subscription.objects.get(company=company)
            except Subscription.DoesNotExist as exc:
                raise CommandError(
                    f"No Subscription for company id={company.pk} {company.name!r}"
                ) from exc

            created = company.created_at
            if created is None:
                trial_end = timezone.now().date() + timedelta(days=14)
            else:
                trial_end = created.date() + timedelta(days=14)

            today = timezone.now().date()
            if extend_if_expired and trial_end < today:
                trial_end = today + timedelta(days=14)

            before = {
                "plan": subscription.plan,
                "status": subscription.status,
                "is_trial": subscription.is_trial,
                "is_paid": subscription.is_paid,
                "trial_period_end_date": subscription.trial_period_end_date,
                "subscription_end_date": subscription.subscription_end_date,
            }

            self.stdout.write(
                f"Company: {company.name!r} schema={company.schema_name!r} "
                f"email={company.email!r}"
            )
            self.stdout.write(f"Before: {before}")
            self.stdout.write(
                f"Target trial end (created_at+14 or extended): {trial_end}"
            )

            if dry_run:
                self.stdout.write(self.style.WARNING("Dry run — no changes saved."))
                return

            subscription.plan = SubscriptionPlan.FREE_TRIAL.value
            subscription.status = SubscriptionStatus.TRIAL.value
            subscription.is_trial = True
            subscription.is_paid = False
            subscription.trial_period_end_date = trial_end
            subscription.subscription_end_date = trial_end
            subscription.save()

            company.compute_enabled_modules()
            company.refresh_from_db(fields=["enabled_modules"])

            self.stdout.write(
                self.style.SUCCESS(
                    f"Updated subscription id={subscription.pk}; "
                    f"plan={subscription.plan!r} status={subscription.status!r} "
                    f"trial_end={trial_end}"
                )
            )
