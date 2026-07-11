"""
Delete Stripe-based subscriptions and billing history, resetting to trial.

Removes BillingHistory records with payment_gateway=STRIPE and resets
Subscription records with payment_gateway=STRIPE to trial state (clearing
Stripe IDs). Run in public schema.

Usage:
  python manage.py delete_stripe_subscriptions
  python manage.py delete_stripe_subscriptions --dry-run
  python manage.py delete_stripe_subscriptions --cancel-stripe
"""

from django.core.management.base import BaseCommand
from django_tenants.utils import schema_context, get_public_schema_name

from company.models import BillingHistory, Subscription
from company.enums import SubscriptionPlan, SubscriptionStatus
from company.models import PaymentGateway


class Command(BaseCommand):
    help = "Delete Stripe billing history and reset Stripe subscriptions to trial"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be changed without making changes",
        )
        parser.add_argument(
            "--cancel-stripe",
            action="store_true",
            help="Attempt to cancel Stripe subscriptions via API before reset (may fail for test IDs)",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        cancel_stripe = options["cancel_stripe"]

        if dry_run:
            self.stdout.write(
                self.style.WARNING("DRY RUN MODE - No changes will be made")
            )

        with schema_context(get_public_schema_name()):
            billing_deleted = 0
            subs_reset = 0

            # 1. Delete BillingHistory where payment_gateway=STRIPE
            billing_qs = BillingHistory.objects.filter(
                payment_gateway=PaymentGateway.STRIPE
            )
            billing_count = billing_qs.count()
            if billing_count:
                self.stdout.write(
                    f"Found {billing_count} BillingHistory record(s) with Stripe gateway"
                )
                if not dry_run:
                    billing_qs.delete()
                    billing_deleted = billing_count
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Deleted {billing_deleted} BillingHistory record(s)"
                        )
                    )
                else:
                    billing_deleted = billing_count
                    self.stdout.write(
                        f"Would delete {billing_count} BillingHistory record(s)"
                    )
            else:
                self.stdout.write("No Stripe BillingHistory records found.")

            # 2. Reset Subscriptions where payment_gateway=STRIPE
            subs_qs = Subscription.objects.filter(
                payment_gateway=PaymentGateway.STRIPE
            )
            subs_count = subs_qs.count()
            if subs_count:
                self.stdout.write(
                    f"Found {subs_count} Subscription(s) with Stripe gateway"
                )

                for sub in subs_qs:
                    if cancel_stripe and sub.gateway_subscription_id:
                        try:
                            import stripe
                            from django.conf import settings
                            stripe.api_key = getattr(
                                settings, "STRIPE_SECRET_KEY", None
                            )
                            if stripe.api_key:
                                stripe.Subscription.delete(
                                    sub.gateway_subscription_id
                                )
                                self.stdout.write(
                                    f"  Cancelled Stripe sub: {sub.gateway_subscription_id}"
                                )
                            else:
                                self.stdout.write(
                                    self.style.WARNING(
                                        "  Skipped Stripe cancel: no API key"
                                    )
                                )
                        except Exception as e:
                            self.stdout.write(
                                self.style.WARNING(
                                    f"  Stripe cancel failed for {sub.gateway_subscription_id}: {e}"
                                )
                            )

                    if not dry_run:
                        sub.status = SubscriptionStatus.TRIAL.value
                        sub.plan = SubscriptionPlan.FREE_TRIAL.value
                        sub.is_paid = False
                        sub.gateway_subscription_id = None
                        sub.gateway_customer_id = None
                        sub.gateway_price_id = None
                        sub.payment_gateway = PaymentGateway.MOBILE_MONEY
                        sub.subscription_end_date = sub.trial_period_end_date
                        sub.is_trial = True
                        sub.save()
                        subs_reset += 1
                        self.stdout.write(
                            f"  Reset subscription for {sub.company.name}"
                        )
                    else:
                        subs_reset += 1
                        self.stdout.write(
                            f"  Would reset subscription for {sub.company.name}"
                        )

                if subs_reset and not dry_run:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Reset {subs_reset} Subscription(s) to trial"
                        )
                    )
            else:
                self.stdout.write("No Stripe Subscription records found.")

        if dry_run:
            self.stdout.write(
                self.style.WARNING("Run without --dry-run to apply changes.")
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Done. BillingHistory deleted: {billing_deleted}, "
                    f"Subscriptions reset: {subs_reset}"
                )
            )
