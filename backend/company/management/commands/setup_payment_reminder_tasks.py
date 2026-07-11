"""
Setup Celery Beat periodic tasks for payment schedule reminder emails.
Run: python manage.py setup_payment_reminder_tasks
"""
from django.core.management.base import BaseCommand
from django_celery_beat.models import CrontabSchedule, PeriodicTask


class Command(BaseCommand):
    help = "Setup Celery Beat periodic tasks for installment and overdue payment reminders"

    def handle(self, *args, **options):
        # Installment reminders: 9:30 AM daily
        schedule_930, _ = CrontabSchedule.objects.get_or_create(
            minute="30",
            hour="9",
            day_of_week="*",
            day_of_month="*",
            month_of_year="*",
            timezone="UTC",
        )

        task1, created1 = PeriodicTask.objects.update_or_create(
            name="Send installment reminders",
            defaults={
                "task": "company.tasks.send_installment_reminders",
                "crontab": schedule_930,
                "enabled": True,
            },
        )

        # Overdue notices: 10:00 AM daily
        schedule_1000, _ = CrontabSchedule.objects.get_or_create(
            minute="0",
            hour="10",
            day_of_week="*",
            day_of_month="*",
            month_of_year="*",
            timezone="UTC",
        )

        task2, created2 = PeriodicTask.objects.update_or_create(
            name="Send overdue notices",
            defaults={
                "task": "company.tasks.send_overdue_notices",
                "crontab": schedule_1000,
                "enabled": True,
            },
        )

        for name, created in [
            ("Send installment reminders (daily 9:30 AM UTC)", created1),
            ("Send overdue notices (daily 10:00 AM UTC)", created2),
        ]:
            if created:
                self.stdout.write(self.style.SUCCESS(f"Created periodic task: {name}"))
            else:
                self.stdout.write(self.style.SUCCESS(f"Updated periodic task: {name}"))
