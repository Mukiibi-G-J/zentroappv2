"""
Ensure BRANCH + G/L global dimensions for a tenant.

If the tenant already has at least one BRANCH dimension value, **no new branch
row is created**. Otherwise creates one value: code from ``--description`` (slug),
or ``MAIN`` / ``Main`` if no description is given.

With django-tenants ``tenant_command``, ``--schema`` is consumed by the wrapper to
select the tenant; this command then runs on that connection and does not need
its own ``--schema``:

    python manage.py tenant_command populate_tenant_dimension_defaults --schema=demo1

Run directly (switches schema inside the command):

    python manage.py populate_tenant_dimension_defaults --schema=demo1
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import connection

try:
    from django_tenants.utils import get_public_schema_name, schema_context
except ImportError:
    get_public_schema_name = None
    schema_context = None


class Command(BaseCommand):
    help = (
        "Wire GeneralLedgerSetup to BRANCH and ensure global dimensions have values. "
        "Does not add a branch value if one already exists."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--schema",
            type=str,
            default=None,
            help=(
                "Tenant schema name. Optional when using tenant_command (wrapper "
                "already set the tenant). Required for direct: manage.py populate_tenant_dimension_defaults"
            ),
        )
        parser.add_argument(
            "--description",
            type=str,
            default="",
            help="Description when creating the first BRANCH value only (if none exist)",
        )

    def handle(self, *args, **options):
        schema = options["schema"]
        desc = (options.get("description") or "").strip() or None

        from dimension.setup import (
            ensure_default_branch_dimension_and_gl_setup,
            suggest_branch_value_code_from_label,
        )

        def run():
            code = suggest_branch_value_code_from_label(desc) if desc else None
            ensure_default_branch_dimension_and_gl_setup(
                default_branch_value_code=code,
                default_branch_value_description=desc,
            )

        if schema:
            if schema_context is None:
                raise CommandError(
                    "django-tenants is required to use --schema. "
                    "Use: python manage.py tenant_command populate_tenant_dimension_defaults --schema=..."
                )
            with schema_context(schema):
                run()
            label = schema
        else:
            if get_public_schema_name is None:
                raise CommandError("Pass --schema=... or run via tenant_command with --schema=...")
            public = get_public_schema_name()
            if getattr(connection, "schema_name", None) == public:
                raise CommandError(
                    "Current database schema is public. Select a tenant, e.g.:\n"
                    "  python manage.py tenant_command populate_tenant_dimension_defaults --schema=demo1"
                )
            run()
            label = getattr(connection, "schema_name", "tenant")

        self.stdout.write(
            self.style.SUCCESS(
                f"Dimension defaults ensured for schema {label!r}."
            )
        )
