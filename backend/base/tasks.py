"""Celery tasks: database backups to S3 (outside default STORAGES / media layout)."""
from __future__ import annotations

import os
import shutil
import subprocess
import traceback
import tempfile
from datetime import datetime, timedelta, timezone as dt_timezone
from typing import Any

import boto3
from celery import shared_task
from celery.utils.log import get_task_logger
from django.conf import settings
from django.core.mail import send_mail

logger = get_task_logger(__name__)

BACKUP_PREFIX_DAILY = "backups/daily/"
BACKUP_PREFIX_WEEKLY = "backups/weekly/"
DAILY_RETENTION_DAYS = 7
WEEKLY_RETENTION_DAYS = 30


def _build_s3_client():
    kwargs: dict[str, Any] = {
        "region_name": getattr(settings, "AWS_S3_REGION_NAME", None) or "sa-east-1",
    }
    key_id = (getattr(settings, "AWS_ACCESS_KEY_ID", None) or "").strip()
    secret = (getattr(settings, "AWS_SECRET_ACCESS_KEY", None) or "").strip()
    if key_id and secret:
        kwargs["aws_access_key_id"] = key_id
        kwargs["aws_secret_access_key"] = secret
    return boto3.client("s3", **kwargs)


def _notify_backup_failure(exc: BaseException) -> None:
    recipient = (os.getenv("SUBSCRIPTION_NOTIFY_EMAIL") or "").strip()
    if not recipient:
        # TODO: Wire Django ADMINS or a dedicated ops email setting when available.
        return
    try:
        body = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        send_mail(
            subject="[Zentro] Database backup failed",
            message=body,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None) or None,
            recipient_list=[recipient],
            fail_silently=False,
        )
    except Exception:
        logger.exception("Could not send backup failure notification email")


def prune_database_backups_on_s3(s3_client, bucket: str) -> None:
    """Remove daily backups older than 7 days and weekly backups older than 30 days."""
    now = datetime.now(dt_timezone.utc)
    rules = [
        (BACKUP_PREFIX_DAILY, DAILY_RETENTION_DAYS),
        (BACKUP_PREFIX_WEEKLY, WEEKLY_RETENTION_DAYS),
    ]
    for prefix, max_days in rules:
        cutoff = now - timedelta(days=max_days)
        to_delete: list[str] = []
        paginator = s3_client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            for obj in page.get("Contents") or []:
                key = obj.get("Key")
                lm = obj.get("LastModified")
                if not key or not lm:
                    continue
                if lm < cutoff:
                    to_delete.append(key)
        for i in range(0, len(to_delete), 1000):
            batch = to_delete[i : i + 1000]
            if batch:
                s3_client.delete_objects(
                    Bucket=bucket,
                    Delete={"Objects": [{"Key": k} for k in batch], "Quiet": True},
                )
        if to_delete:
            logger.info(
                "Pruned %d S3 backup object(s) under %r (older than %d days)",
                len(to_delete),
                prefix,
                max_days,
            )


def _run_pg_dump_custom(out_path: str, db: dict[str, Any]) -> None:
    """Run pg_dump in PostgreSQL custom format (-F c), written to ``out_path`` (use pg_restore to load)."""
    name = (db.get("NAME") or "").strip()
    if not name:
        raise ValueError("DATABASES['default']['NAME'] is not configured")
    user = db.get("USER") or ""
    password = db.get("PASSWORD") or ""
    host = db.get("HOST") or "localhost"
    port = str(db.get("PORT") or "5432")

    pg_dump_bin = shutil.which("pg_dump")
    if not pg_dump_bin:
        raise FileNotFoundError(
            "pg_dump not found on PATH; install postgresql-client (or equivalent)"
        )

    cmd = [
        pg_dump_bin,
        "-h",
        host,
        "-p",
        port,
        "-U",
        str(user),
        "-d",
        str(name),
        "--no-owner",
        "-F",
        "c",
        "-f",
        out_path,
    ]
    env = {**os.environ, "PGPASSWORD": str(password)}
    opts = db.get("OPTIONS") or {}
    if opts.get("sslmode"):
        env["PGSSLMODE"] = str(opts["sslmode"])

    proc = subprocess.run(
        cmd,
        stderr=subprocess.PIPE,
        env=env,
        check=False,
    )
    if proc.returncode != 0:
        err = proc.stderr.decode(errors="replace") if proc.stderr else ""
        try:
            if os.path.isfile(out_path):
                os.remove(out_path)
        except OSError:
            pass
        raise RuntimeError(f"pg_dump failed (exit {proc.returncode}): {err}")


@shared_task(
    bind=True,
    soft_time_limit=7000,
    time_limit=7200,
    name="base.tasks.database_backup_task",
)
def database_backup_task(self, tier: str = "daily") -> dict[str, Any]:
    """
    Dump the default PostgreSQL database with pg_dump -F c (custom format), upload the .dump file
    to S3, then prune old backups. Restore locally with pg_restore, not psql.
    """
    tier = (tier or "daily").lower()
    if tier not in ("daily", "weekly"):
        raise ValueError("tier must be 'daily' or 'weekly'")

    prefix = BACKUP_PREFIX_DAILY if tier == "daily" else BACKUP_PREFIX_WEEKLY
    bucket = getattr(settings, "AWS_STORAGE_BUCKET_NAME", None) or ""
    if not bucket:
        raise ValueError("AWS_STORAGE_BUCKET_NAME is not configured")

    stamp = datetime.now(dt_timezone.utc).strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"backup_{stamp}.dump"
    s3_key = f"{prefix}{filename}"

    db = settings.DATABASES["default"]
    tmp_path = os.path.join(
        tempfile.gettempdir(),
        f"zentro_db_backup_{stamp}_{tier}.dump",
    )
    try:
        _run_pg_dump_custom(tmp_path, db)
        size = os.path.getsize(tmp_path)
        s3 = _build_s3_client()
        s3.upload_file(tmp_path, bucket, s3_key)
        logger.info(
            "Database backup uploaded: s3://%s/%s (%d bytes, tier=%s)",
            bucket,
            s3_key,
            size,
            tier,
        )
        prune_database_backups_on_s3(s3, bucket)
        return {"bucket": bucket, "key": s3_key, "bytes": size, "tier": tier}
    except Exception as exc:
        logger.exception("Database backup failed (tier=%s)", tier)
        _notify_backup_failure(exc)
        raise
    finally:
        try:
            if os.path.isfile(tmp_path):
                os.remove(tmp_path)
        except OSError:
            logger.warning("Could not remove temp backup file %s", tmp_path)
