"""Verify _zentro_template exists, has no pending migrations, and is pre-seeded (CI)."""

from __future__ import annotations

import logging
import sys

from django.core.management.base import BaseCommand
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django_tenants.utils import schema_context

from company.template_schema import TEMPLATE_SCHEMA_NAME, template_schema_exists
from company.tenant_baseline import tenant_has_baseline_data

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Exit 0 if _zentro_template exists, tenant migrations are fully applied, "
        "and baseline data (pages/roles/permissions/no-series) is present; "
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
            has_baseline = tenant_has_baseline_data()

        if plan:
            logger.error(
                "verify_template_schema: %d pending migration(s) on %r",
                len(plan),
                TEMPLATE_SCHEMA_NAME,
            )
            sys.exit(1)

        if not has_baseline:
            logger.error(
                "verify_template_schema: schema %r exists but baseline data is missing "
                "(roles/pages/permission sets/no-series). Re-run rebuild_template_schema.",
                TEMPLATE_SCHEMA_NAME,
            )
            sys.exit(1)

        logger.info(
            "verify_template_schema: schema %r is present, migrated, and pre-seeded",
            TEMPLATE_SCHEMA_NAME,
        )
