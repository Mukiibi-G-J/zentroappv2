import atexit
import logging
import os

from django.apps import AppConfig
from django.db import connection
from django.db.models.signals import post_migrate
from django_tenants.utils import get_public_schema_name

logger = logging.getLogger(__name__)

_TENANT_MIGRATIONS_TOUCHED = False
_ATEXIT_REGISTERED = False


def _flush_template_rebuild_if_needed() -> None:
    global _TENANT_MIGRATIONS_TOUCHED
    if os.environ.get("DISABLE_TEMPLATE_REBUILD") == "1":
        return
    if not _TENANT_MIGRATIONS_TOUCHED:
        return
    try:
        from company.template_rebuild_core import run_rebuild_template_schema

        run_rebuild_template_schema()
    except Exception:
        logger.exception(
            "atexit template rebuild failed; run manage.py rebuild_template_schema manually"
        )
    finally:
        _TENANT_MIGRATIONS_TOUCHED = False


def _register_atexit_once() -> None:
    global _ATEXIT_REGISTERED
    if not _ATEXIT_REGISTERED:
        atexit.register(_flush_template_rebuild_if_needed)
        _ATEXIT_REGISTERED = True


def _on_post_migrate(sender, **kwargs) -> None:
    global _TENANT_MIGRATIONS_TOUCHED
    if os.environ.get("DISABLE_TEMPLATE_REBUILD") == "1":
        return
    plan = kwargs.get("plan")
    if not plan:
        return
    if connection.schema_name == get_public_schema_name():
        return
    _TENANT_MIGRATIONS_TOUCHED = True
    _register_atexit_once()


class CompanyConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "company"

    def ready(self) -> None:
        post_migrate.connect(
            _on_post_migrate,
            dispatch_uid="company.template_schema_post_migrate",
        )
