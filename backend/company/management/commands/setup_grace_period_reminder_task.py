"""
Setup Celery Beat periodic task for grace-period payment reminder emails.
Run: python manage.py setup_grace_period_reminder_task
"""
from django.core.management.base import BaseCommand
from django_celery_beat.models import CrontabSchedule, PeriodicTask


class Command(BaseCommand):
    help = (
        "Setup send_grace_period_payment_reminders Celery Beat task "
        "(daily at 9:00 AM UTC, after expiry-pre window task)"
    )

    def handle(self, *args, **options):
        schedule, _ = CrontabSchedule.objects.get_or_create(
            minute="0",
            hour="9",
            day_of_week="*",
            day_of_month="*",
            month_of_year="*",
            timezone="UTC",
        )

        task, created = PeriodicTask.objects.update_or_create(
            name="Send grace period payment reminders",
            defaults={
                "task": "company.tasks.send_grace_period_payment_reminders",
                "crontab": schedule,
                "enabled": True,
            },
        )

        if created:
            self.stdout.write(
                self.style.SUCCESS(
                    "Created periodic task: Send grace period payment reminders (daily 9:00 AM UTC)"
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    "Updated periodic task: Send grace period payment reminders (daily 9:00 AM UTC)"
                )
            )
