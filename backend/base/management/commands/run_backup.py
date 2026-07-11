"""Queue or run the PostgreSQL -> S3 backup task (same as Celery Beat)."""
import traceback

from django.core.management.base import BaseCommand

from base.tasks import database_backup_task


class Command(BaseCommand):
    help = (
        "Run a full database backup to S3 (backups/daily/ or backups/weekly/) as pg_dump "
        "custom format (.dump, -F c). Restore with pg_restore. "
        "Requires pg_dump on PATH and IAM permission for s3:PutObject/List/Delete on backups/*. "
        "Default: enqueue via Celery; use --sync to run in-process."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--tier",
            choices=("daily", "weekly"),
            default="daily",
            help="S3 prefix tier (default: daily).",
        )
        parser.add_argument(
            "--sync",
            action="store_true",
            help="Execute the task in this process instead of the Celery worker queue.",
        )

    def handle(self, *args, **options):
        tier = options["tier"]
        if options["sync"]:
            self.stdout.write(self.style.NOTICE(f"Running backup synchronously (tier={tier})..."))
            result = database_backup_task.apply(kwargs={"tier": tier})
            if result.successful():
                self.stdout.write(self.style.SUCCESS(f"Done: {result.result!r}"))
            else:
                err = result.result
                if isinstance(err, BaseException):
                    self.stderr.write(
                        "".join(traceback.format_exception(type(err), err, err.__traceback__))
                    )
                else:
                    self.stderr.write(str(err))
                raise SystemExit(1)
        else:
            async_result = database_backup_task.delay(tier=tier)
            self.stdout.write(
                self.style.SUCCESS(
                    f"Queued database backup (tier={tier}); task_id={async_result.id}"
                )
            )
