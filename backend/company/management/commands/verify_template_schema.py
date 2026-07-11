"""Verify _zentro_template exists and has no pending migrations (CI)."""

from __future__ import annotations

import logging
import sys

from django.core.management.base import BaseCommand
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django_tenants.utils import schema_context

from company.template_schema import TEMPLATE_SCHEMA_NAME, template_schema_exists

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Exit 0 if _zentro_template exists and tenant migrations are fully applied; "
        "exit 1 if missing or stale."
    )

    def handle(self, *args, **options) -> None:
        if not template_schema_exists():
            logger.error(
                "verify_template_schema: schema %r does not exist",
                TEMPLATE_SCHEMA_NAME,
            )
            sys.exit(1)

        with schema_context(TEMPLATE_SCHEMA_NAME):
            executor = MigrationExecutor(connection)
            plan = executor.migration_plan(executor.loader.graph.leaf_nodes())

        if plan:
            logger.error(
                "verify_template_schema: %d pending migration(s) on %r",
                len(plan),
                TEMPLATE_SCHEMA_NAME,
            )
            sys.exit(1)

        logger.info(
            "verify_template_schema: schema %r is present and up to date",
            TEMPLATE_SCHEMA_NAME,
        )
