"""
Create or update the debug superuser defined in ``company.tasks`` (DEBUG_ADMIN_*)
inside a tenant schema — same bootstrap pattern as company signup (branch dimension + global_dimension_1).

Examples::

    python manage.py tenant_command create_debug_tenant_admin --schema=dejunctionbarandresturant

    python manage.py create_debug_tenant_admin --schema=dejunctionbarandresturant
"""

import os

from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, connection

try:
    from django_tenants.utils import get_public_schema_name, schema_context, schema_exists
except ImportError:
    get_public_schema_name = None
    schema_context = None
    schema_exists = None


class Command(BaseCommand):
    help = (
        "Create or update DEBUG_ADMIN user (from company.tasks) in a tenant schema."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--schema",
            type=str,
            default=None,
            help=(
                "Tenant schema name. With tenant_command, omit and the wrapper sets the schema."
            ),
        )
        parser.add_argument("--email", type=str, default=None, help="Admin email.")
        parser.add_argument(
            "--password", type=str, default=None, help="Admin password."
        )
        parser.add_argument(
            "--username", type=str, default=None, help="Admin username."
        )
        parser.add_argument(
            "--full-name", type=str, default=None, help="Admin full name."
        )
        parser.add_argument(
            "--phone", type=str, default=None, help="Admin phone number."
        )

    def handle(self, *args, **options):
        from authentication.models import CustomUser as User
        from dimension.setup import (
            DEFAULT_FIRST_BRANCH_CODE,
            DEFAULT_FIRST_BRANCH_DESCRIPTION,
            ensure_default_branch_dimension_and_gl_setup,
        )

        # Prefer explicit CLI args, then env vars, then safe local defaults.
        debug_admin_email = (
            options.get("email")
            or os.getenv("DEBUG_ADMIN_EMAIL")
            or "mukiibijoseph19@gmail.com"
        )
        debug_admin_password = (
            options.get("password")
            or os.getenv("DEBUG_ADMIN_PASSWORD")
            or "D@ur!c412"
        )
        debug_admin_username = (
            options.get("username") or os.getenv("DEBUG_ADMIN_USERNAME") or "debug_admin"
        )
        debug_admin_full_name = (
            options.get("full_name")
            or os.getenv("DEBUG_ADMIN_FULL_NAME")
            or "Debug Admin"
        )
        debug_admin_phone_number = (
            options.get("phone")
            or os.getenv("DEBUG_ADMIN_PHONE_NUMBER")
            or "+256750440865"
        )

        schema = options["schema"]
        if schema:
            if schema_context is None or schema_exists is None:
                raise CommandError(
                    "django-tenants is required for --schema. "
                    "Use: python manage.py tenant_command create_debug_tenant_admin --schema=..."
                )
            if not schema_exists(schema):
                raise CommandError(f"Schema does not exist: {schema!r}")
        else:
            if get_public_schema_name is None:
                raise CommandError(
                    "Pass --schema=... or run via tenant_command with --schema=..."
                )
            public = get_public_schema_name()
            if getattr(connection, "schema_name", None) == public:
                raise CommandError(
                    "Current schema is public. Run:\n"
                    "  python manage.py tenant_command create_debug_tenant_admin "
                    "--schema=dejunctionbarandresturant"
                )
            schema = connection.schema_name

        def run():
            branch_setup = ensure_default_branch_dimension_and_gl_setup(
                default_branch_value_code=DEFAULT_FIRST_BRANCH_CODE,
                default_branch_value_description=DEFAULT_FIRST_BRANCH_DESCRIPTION,
            )
            branch_value = branch_setup["default_branch_value"]

            user = User.objects.filter(email=debug_admin_email).first()
            if user:
                user.username = debug_admin_username
                user.full_name = debug_admin_full_name
                user.phone_number = debug_admin_phone_number
                user.set_password(debug_admin_password)
                user.is_superuser = True
                user.is_staff = True
                user.is_active = True
                user.is_verified = True
                user.global_dimension_1 = branch_value
                user.save()
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Updated existing user id={user.pk} email={user.email!r} in schema {schema!r}."
                    )
                )
                return

            try:
                user = User.objects.create_superuser(
                    email=debug_admin_email,
                    username=debug_admin_username,
                    full_name=debug_admin_full_name,
                    phone_number=debug_admin_phone_number,
                    password=debug_admin_password,
                )
            except IntegrityError as exc:
                raise CommandError(
                    "Could not create user (unique constraint). "
                    "Another row may already use this email, username, or phone_number. "
                    f"Details: {exc}"
                ) from exc

            user.is_staff = True
            user.is_verified = True
            user.is_active = True
            user.global_dimension_1 = branch_value
            user.save(
                update_fields=[
                    "is_staff",
                    "is_verified",
                    "is_active",
                    "global_dimension_1",
                ]
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f"Created user id={user.pk} email={user.email!r} in schema {schema!r}."
                )
            )

        if options["schema"]:
            with schema_context(schema):
                run()
        else:
            run()
