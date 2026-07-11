"""
Management command to clean up duplicate ZentroStarterOrder records.

This command finds companies with multiple active/pending/paid orders and:
1. Keeps the most recent order (or the one with payments)
2. Moves payments from duplicate orders to the kept order
3. Cancels or deletes duplicate orders

Usage:
    python manage.py cleanup_duplicate_orders --schema=public
    python manage.py cleanup_duplicate_orders --schema=public --dry-run  # Preview changes
    python manage.py cleanup_duplicate_orders --schema=public --keep-oldest  # Keep oldest instead of newest
    python manage.py cleanup_duplicate_orders --schema=public --delete-duplicates  # Delete instead of cancel
"""

from django.core.management.base import BaseCommand
from django.db.models import Count, Sum
from django.utils import timezone
from company.models import ZentroStarterOrder, ZentroStarterPayment
from decimal import Decimal


class Command(BaseCommand):
    help = "Clean up duplicate ZentroStarterOrder records, keeping only one active order per company"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview changes without making them",
        )
        parser.add_argument(
            "--keep-oldest",
            action="store_true",
            help="Keep the oldest order instead of the newest (default: keep newest)",
        )
        parser.add_argument(
            "--delete-duplicates",
            action="store_true",
            help="Delete duplicate orders instead of cancelling them (default: cancel)",
        )
        parser.add_argument(
            "--status",
            type=str,
            default="pending,paid,active",
            help="Comma-separated list of statuses to consider as 'active' (default: pending,paid,active)",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        keep_oldest = options["keep_oldest"]
        delete_duplicates = options["delete_duplicates"]
        status_list = [s.strip() for s in options["status"].split(",")]

        self.stdout.write(self.style.WARNING("=" * 70))
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN MODE - No changes will be made"))
        else:
            self.stdout.write(self.style.ERROR("LIVE MODE - Changes will be applied!"))
        self.stdout.write(self.style.WARNING("=" * 70))
        self.stdout.write("")

        # Find companies with multiple active orders
        duplicate_companies = (
            ZentroStarterOrder.objects.filter(status__in=status_list)
            .values("company")
            .annotate(order_count=Count("id"))
            .filter(order_count__gt=1)
        )

        if not duplicate_companies:
            self.stdout.write(
                self.style.SUCCESS("No companies with duplicate orders found!")
            )
            return

        total_companies = len(duplicate_companies)
        self.stdout.write(
            self.style.WARNING(
                f"Found {total_companies} companies with duplicate orders"
            )
        )
        self.stdout.write("")

        total_orders_to_process = 0
        total_payments_moved = 0
        total_orders_cancelled = 0
        total_orders_deleted = 0

        for company_info in duplicate_companies:
            company_id = company_info["company"]
            company = ZentroStarterOrder.objects.filter(
                company_id=company_id, status__in=status_list
            ).first().company

            orders = ZentroStarterOrder.objects.filter(
                company_id=company_id, status__in=status_list
            ).order_by("-created_at" if not keep_oldest else "created_at")

            self.stdout.write(
                self.style.NOTICE(
                    f"\nCompany: {company.name} (ID: {company.id}, Schema: {company.schema_name})"
                )
            )
            self.stdout.write(
                f"  Found {len(orders)} duplicate orders to process"
            )

            # Determine which order to keep
            # Prefer order with payments, otherwise keep newest/oldest
            order_to_keep = None
            for order in orders:
                payment_count = order.payments.filter(is_confirmed=True).count()
                if payment_count > 0:
                    order_to_keep = order
                    break

            if not order_to_keep:
                # No orders with payments, keep the first one (newest or oldest)
                order_to_keep = orders.first()

            orders_to_process = [o for o in orders if o.id != order_to_keep.id]
            total_orders_to_process += len(orders_to_process)

            self.stdout.write(
                f"  KEEPING Order #{order_to_keep.id} "
                f"(Created: {order_to_keep.created_at.date()}, "
                f"Status: {order_to_keep.status}, "
                f"Payments: {order_to_keep.payments.filter(is_confirmed=True).count()}, "
                f"Amount Paid: {order_to_keep.amount_paid:,.2f} UGX)"
            )

            # Process duplicate orders
            for duplicate_order in orders_to_process:
                payment_count = duplicate_order.payments.filter(
                    is_confirmed=True
                ).count()
                duplicate_amount_paid = duplicate_order.amount_paid

                self.stdout.write(
                    f"  {'[DELETE]' if delete_duplicates else '[CANCEL]'} "
                    f"Order #{duplicate_order.id} "
                    f"(Created: {duplicate_order.created_at.date()}, "
                    f"Status: {duplicate_order.status}, "
                    f"Payments: {payment_count}, "
                    f"Amount Paid: {duplicate_amount_paid:,.2f} UGX)"
                )

                if not dry_run:
                    # Move payments from duplicate to kept order
                    if payment_count > 0:
                        payments_to_move = ZentroStarterPayment.objects.filter(
                            order=duplicate_order
                        )
                        moved_count = 0
                        for payment in payments_to_move:
                            payment.order = order_to_keep
                            payment.save()
                            moved_count += 1

                        total_payments_moved += moved_count
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"    -> Moved {moved_count} payment(s) to Order #{order_to_keep.id}"
                            )
                        )

                    # Cancel or delete the duplicate order
                    if delete_duplicates:
                        duplicate_order.delete()
                        total_orders_deleted += 1
                        self.stdout.write(
                            self.style.ERROR(f"    -> Deleted Order #{duplicate_order.id}")
                        )
                    else:
                        duplicate_order.status = "cancelled"
                        duplicate_order.payment_status = "refunded"
                        duplicate_order.save()
                        total_orders_cancelled += 1
                        self.stdout.write(
                            self.style.WARNING(
                                f"    -> Cancelled Order #{duplicate_order.id}"
                            )
                        )

            # Refresh the kept order to show updated payment totals
            if not dry_run and orders_to_process:
                order_to_keep.refresh_from_db()
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  Final state of kept Order #{order_to_keep.id}: "
                        f"{order_to_keep.payments.filter(is_confirmed=True).count()} payments, "
                        f"{order_to_keep.amount_paid:,.2f} UGX paid"
                    )
                )

        # Summary
        self.stdout.write("")
        self.stdout.write(self.style.WARNING("=" * 70))
        self.stdout.write(self.style.WARNING("SUMMARY"))
        self.stdout.write(self.style.WARNING("=" * 70))
        self.stdout.write(f"Companies processed: {total_companies}")
        self.stdout.write(f"Duplicate orders to process: {total_orders_to_process}")

        if not dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Payments moved: {total_payments_moved}"
                )
            )
            if delete_duplicates:
                self.stdout.write(
                    self.style.ERROR(f"Orders deleted: {total_orders_deleted}")
                )
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f"Orders cancelled: {total_orders_cancelled}"
                    )
                )
        else:
            self.stdout.write(
                self.style.WARNING(
                    "DRY RUN - Run without --dry-run to apply changes"
                )
            )

        self.stdout.write("")
        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    "This was a DRY RUN. Run again without --dry-run to apply changes."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS("Cleanup completed successfully!")
            )




