from django.core.management.base import BaseCommand
from django.utils import timezone
from company.models import ZentroStarterOrder, ZentroStarterPayment
from decimal import Decimal


class Command(BaseCommand):
    help = "Update existing starter pack orders to pending status if no payments have been recorded"

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be updated without actually updating',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING("DRY RUN MODE - No changes will be made")
            )

        # Find all orders that are marked as paid/active but have no payments
        orders_to_update = ZentroStarterOrder.objects.filter(
            status__in=["paid", "active"],
            amount_paid=Decimal("0.00")
        )
        
        # Also check if there are any ZentroStarterPayment records
        orders_with_payments = set(
            ZentroStarterPayment.objects.filter(is_confirmed=True)
            .values_list('order_id', flat=True)
            .distinct()
        )
        
        # Filter out orders that have payments
        orders_to_update = orders_to_update.exclude(id__in=orders_with_payments)
        
        count = orders_to_update.count()
        self.stdout.write(
            self.style.SUCCESS(
                f"Found {count} orders to update to pending status"
            )
        )

        updated_count = 0
        skipped_count = 0

        for order in orders_to_update:
            try:
                # Double check that amount_paid is actually 0
                if order.amount_paid > 0:
                    self.stdout.write(
                        self.style.WARNING(
                            f"  [SKIP] Order {order.id} - has amount_paid={order.amount_paid}, skipping"
                        )
                    )
                    skipped_count += 1
                    continue
                
                if not dry_run:
                    order.status = "pending"
                    order.payment_status = "pending"
                    order.save()
                    
                    self.stdout.write(
                        f"  [OK] Updated order {order.id} for company {order.company.name} - "
                        f"Status: {order.status}, Payment Status: {order.payment_status}"
                    )
                else:
                    self.stdout.write(
                        f"  [DRY RUN] Would update order {order.id} for company {order.company.name} - "
                        f"Status: pending, Payment Status: pending"
                    )
                updated_count += 1

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f"  [ERROR] Error updating order {order.id}: {str(e)}"
                    )
                )

        # Summary
        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"\n[SUMMARY]\n"
                f"  Orders updated: {updated_count}\n"
                f"  Orders skipped: {skipped_count}\n"
            )
        )

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    "\nThis was a dry run. Run without --dry-run to apply changes."
                )
            )




