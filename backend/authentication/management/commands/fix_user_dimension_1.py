"""
Fix CustomUser.dimension_1 (global_dimension_1) when it contains string codes like "Kyengera"
instead of integer DimensionValue IDs.

This can happen due to schema drift or data migration issues. The error manifests as:
  ValidationError: {'global_dimension_1': ['"Kyengera" value must be an integer.']}
  during admin login (when user.save(update_fields=['last_login']) triggers full_clean).

Usage:
  python manage.py tenant_command fix_user_dimension_1 --schema=semuna
  python manage.py tenant_command fix_user_dimension_1 --schema=semuna --dry-run
"""

from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = (
        "Fix user dimension_1 column when it contains DimensionValue codes (e.g. 'Kyengera') "
        "instead of integer IDs. Resolves codes to DimensionValue IDs and updates the column."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be fixed without making changes.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN - no changes will be made\n"))

        with connection.cursor() as cursor:
            # Get column type (filter by current schema for multi-tenant)
            cursor.execute(
                """
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_schema = current_schema()
                  AND table_name = 'authentication_customuser'
                  AND column_name = 'dimension_1'
                LIMIT 1
                """
            )
            row = cursor.fetchone()
            if not row:
                self.stdout.write(
                    self.style.ERROR(
                        "Column authentication_customuser.dimension_1 not found."
                    )
                )
                return

            col_type = row[1]
            self.stdout.write(f"Column dimension_1 type: {col_type}")

            # Find users where dimension_1 is non-null and not a valid integer FK.
            # When column is varchar/text, it may contain codes like "Kyengera".
            if col_type in ("character varying", "varchar", "text"):
                cursor.execute(
                    """
                    SELECT id, dimension_1::text
                    FROM authentication_customuser
                    WHERE dimension_1 IS NOT NULL
                      AND dimension_1::text !~ '^[0-9]+$'
                    """
                )
                rows = cursor.fetchall()
            else:
                # For bigint, string values shouldn't exist - but if ValidationError
                # occurs, schema may have drifted. Try casting to text and filtering.
                self.stdout.write(
                    self.style.WARNING(
                        "Column is numeric. Checking for non-numeric values (schema drift)."
                    )
                )
                try:
                    cursor.execute(
                        """
                        SELECT id, dimension_1::text
                        FROM authentication_customuser
                        WHERE dimension_1 IS NOT NULL
                        """
                    )
                    all_rows = cursor.fetchall()
                    rows = [
                        (r[0], r[1])
                        for r in all_rows
                        if r[1] is not None and not str(r[1]).strip().isdigit()
                    ]
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f"Could not query dimension_1: {e}")
                    )
                    return

            if not rows:
                self.stdout.write(
                    self.style.SUCCESS(
                        "No users with non-integer dimension_1 (string codes) found."
                    )
                )
                return

        self.stdout.write(f"Found {len(rows)} user(s) with non-integer dimension_1:")

        # Check if dimension_dimensionvalue has id column (migration 0003 may not have run)
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT column_name FROM information_schema.columns
                WHERE table_schema = current_schema()
                  AND table_name = 'dimension_dimensionvalue'
                  AND column_name = 'id'
                LIMIT 1
                """
            )
            has_id_column = cursor.fetchone() is not None

        if not has_id_column:
            self.stdout.write(
                self.style.ERROR(
                    "dimension_dimensionvalue has no 'id' column in this schema. "
                    "Run: python manage.py migrate_schemas --schema=<your_schema> dimension"
                )
            )
            return

        fixed = 0
        for user_id, dim_val in rows:
            code = str(dim_val).strip()
            self.stdout.write(f"  User id={user_id}, dimension_1={repr(dim_val)}")

            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id FROM dimension_dimensionvalue
                    WHERE code = %s
                    LIMIT 1
                    """,
                    [code],
                )
                row = cursor.fetchone()
            if row is None:
                self.stdout.write(
                    self.style.WARNING(
                        f"    DimensionValue with code '{code}' not found. "
                        "Setting dimension_1 to NULL."
                    )
                )
                new_val = None
            else:
                new_val = row[0]
                self.stdout.write(f"    -> Resolved to DimensionValue id={new_val} ({code})")

            if not dry_run:
                with connection.cursor() as c:
                    if new_val is None:
                        c.execute(
                            """
                            UPDATE authentication_customuser
                            SET dimension_1 = NULL
                            WHERE id = %s
                            """,
                            [user_id],
                        )
                    else:
                        c.execute(
                            """
                            UPDATE authentication_customuser
                            SET dimension_1 = %s
                            WHERE id = %s
                            """,
                            [new_val, user_id],
                        )
                fixed += 1

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"\nWould fix {len(rows)} user(s). Run without --dry-run to apply."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f"\nFixed {fixed} user(s). Login should work now.")
            )
