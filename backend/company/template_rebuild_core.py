"""Programmatic rebuild of the golden tenant template schema (no management command wrapper)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from django.db import connection
from django_tenants.utils import schema_context

from company.template_schema import TEMPLATE_SCHEMA_NAME

logger = logging.getLogger(__name__)

TEMPLATE_COMPANY_NAME = "__zentro_template__"
TEMPLATE_COMPANY_EMAIL = "template@zentro.invalid"
TEMPLATE_DOMAIN_URL = "__zentro_template__.localhost"
TEMPLATE_ADDRESS = "Template"
TEMPLATE_PHONE = "+000000000"


def _remove_template_company_row(Company) -> None:
    """Delete any leftover public ``Company`` row for the template schema (schema kept)."""
    existing = Company.objects.filter(schema_name=TEMPLATE_SCHEMA_NAME).first()
    if not existing:
        return
    existing.auto_drop_schema = False
    existing.delete()


def run_rebuild_template_schema() -> None:
    """
    Drop ``_zentro_template``, create it via full django-tenants migrations,
    seed tenant-generic baseline (pages engine, BC permissions, JSON import, …),
    then remove the throwaway ``Company`` row while keeping the schema.
    """
    from company.models import Company

    with schema_context("public"):
        with connection.cursor() as cursor:
            cursor.execute(
                f'DROP SCHEMA IF EXISTS {connection.ops.quote_name(TEMPLATE_SCHEMA_NAME)} CASCADE'
            )

        _remove_template_company_row(Company)

        company = Company(
            name=TEMPLATE_COMPANY_NAME,
            domain_url=TEMPLATE_DOMAIN_URL,
            schema_name=TEMPLATE_SCHEMA_NAME,
            address=TEMPLATE_ADDRESS,
            phone=TEMPLATE_PHONE,
            email=TEMPLATE_COMPANY_EMAIL,
            onboarding_data={},
        )
        company.auto_create_schema = True
        company.save()

    # Baseline must run with the schema present (outside public-only block).
    # Includes pages engine, BC permission objects, roles, JSON import, seeds.
    from company.tenant_baseline import run_tenant_baseline_bootstrap

    logger.info(
        "template_rebuild: seeding baseline into %s (roles, pages, permissions, data)",
        TEMPLATE_SCHEMA_NAME,
    )
    run_tenant_baseline_bootstrap(TEMPLATE_SCHEMA_NAME, ensure_branch=True)

    with schema_context("public"):
        from company.models import Company

        company = Company.objects.filter(schema_name=TEMPLATE_SCHEMA_NAME).first()
        if company:
            company.auto_drop_schema = False
            company.delete()
        else:
            _remove_template_company_row(Company)

    ts = datetime.now(timezone.utc).isoformat()
    logger.info(
        "template_rebuild: golden schema %s rebuilt and pre-seeded successfully at %s",
        TEMPLATE_SCHEMA_NAME,
        ts,
    )
