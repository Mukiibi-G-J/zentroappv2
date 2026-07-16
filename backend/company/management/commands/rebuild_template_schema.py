"""Rebuild the golden tenant template schema used for fast signup cloning."""

from __future__ import annotations

import logging

from django.core.management.base import BaseCommand

from company.template_rebuild_core import run_rebuild_template_schema

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Drop and recreate PostgreSQL schema _zentro_template using full tenant "
        "migrations, pre-seed baseline (pages engine, BC permissions, roles, "
        "JSON import, seeds), then remove the throwaway Company row (schema kept)."
    )

    def handle(self, *args, **options) -> None:
        run_rebuild_template_schema()
        logger.info("rebuild_template_schema management command finished")
