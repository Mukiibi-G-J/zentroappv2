from django.core.management.base import BaseCommand
from django.db import connection, transaction
from company.models import Company, Domain


class Command(BaseCommand):
    help = "Safely delete a company and its schema"

    def add_arguments(self, parser):
        parser.add_argument(
            "--id",
            type=int,
            help="Company ID to delete",
        )
        parser.add_argument(
            "--schema",
            type=str,
            help="Company schema name to delete",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Force deletion without confirmation",
        )

    def handle(self, *args, **options):
        company_id = options.get("id")
        schema_name = options.get("schema")
        force = options.get("force")

        if not company_id and not schema_name:
            self.stdout.write(
                self.style.ERROR("Please provide either --id or --schema")
            )
            return

        try:
            # Find the company
            if company_id:
                company = Company.objects.get(id=company_id)
            else:
                company = Company.objects.get(schema_name=schema_name)

            self.stdout.write(f"\nCompany found:")
            self.stdout.write(f"  ID: {company.id}")
            self.stdout.write(f"  Name: {company.name}")
            self.stdout.write(f"  Schema: {company.schema_name}")
            self.stdout.write(f"  Domain: {company.domain_url}")

            # Confirm deletion
            if not force:
                confirm = input(
                    "\nAre you sure you want to delete this company? (yes/no): "
                )
                if confirm.lower() != "yes":
                    self.stdout.write(self.style.WARNING("Deletion cancelled."))
                    return

            self.stdout.write(self.style.WARNING("\nStarting deletion process..."))

            company_id = company.id
            company_name = company.name
            company_schema = company.schema_name

            # Step 1: Delete all domains associated with this company
            self.stdout.write("  1. Deleting domains...")
            domains = Domain.objects.filter(tenant=company)
            domain_count = domains.count()
            domains.delete()
            self.stdout.write(
                self.style.SUCCESS(f"     ✓ Deleted {domain_count} domain(s)")
            )

            # Step 2: Drop the schema (this deletes all tenant-specific data)
            self.stdout.write(f'  2. Dropping schema "{company_schema}"...')
            with connection.cursor() as cursor:
                # Drop the schema directly - PostgreSQL will handle connections
                cursor.execute(f'DROP SCHEMA IF EXISTS "{company_schema}" CASCADE;')

            self.stdout.write(self.style.SUCCESS(f"     ✓ Schema dropped"))

            # Step 3: Delete related records in public schema that reference the company
            self.stdout.write("  3. Deleting related records in public schema...")
            with connection.cursor() as cursor:
                # Get all tables in public schema that have foreign keys to company_company
                cursor.execute(
                    """
                    SELECT DISTINCT
                        con.conrelid::regclass AS table_name,
                        att.attname AS column_name
                    FROM pg_constraint con
                    JOIN pg_attribute att ON att.attrelid = con.conrelid 
                        AND att.attnum = ANY(con.conkey)
                    WHERE con.contype = 'f'
                      AND con.confrelid = 'public.company_company'::regclass
                      AND pg_catalog.pg_table_is_visible(con.conrelid);
                """
                )

                related_tables = cursor.fetchall()

                for table_name, column_name in related_tables:
                    # Remove schema prefix if present
                    table_name = str(table_name).replace("public.", "").replace('"', "")
                    column_name = str(column_name)

                    try:
                        cursor.execute(
                            f'DELETE FROM "{table_name}" WHERE "{column_name}" = %s;',
                            [company_id],
                        )
                        deleted_count = cursor.rowcount
                        if deleted_count > 0:
                            self.stdout.write(
                                f"     - Deleted {deleted_count} record(s) from {table_name}"
                            )
                    except Exception as e:
                        self.stdout.write(
                            self.style.WARNING(
                                f"     - Could not delete from {table_name}: {str(e)}"
                            )
                        )

            self.stdout.write(self.style.SUCCESS(f"     ✓ Related records cleaned"))

            # Step 4: Delete the company record
            self.stdout.write("  4. Deleting company record...")
            try:
                company.delete()
                self.stdout.write(self.style.SUCCESS(f"     ✓ Company record deleted"))
            except Exception as e:
                # If normal deletion fails due to orphaned constraints, use direct SQL with triggers disabled
                error_msg = str(e)
                if (
                    "cache lookup failed for constraint" in error_msg
                    or "could not find trigger" in error_msg
                ):
                    self.stdout.write(
                        self.style.WARNING(
                            f"     - Normal deletion failed: {error_msg}"
                        )
                    )
                    self.stdout.write(
                        "     - Attempting deletion with triggers disabled..."
                    )

                    with connection.cursor() as cursor:
                        # Temporarily disable triggers to bypass orphaned constraint issues
                        # (only works for roles allowed to set session_replication_role)
                        try:
                            cursor.execute("SET session_replication_role = replica;")
                            cursor.execute(
                                "DELETE FROM company_company WHERE id = %s;",
                                [company_id],
                            )
                            cursor.execute("SET session_replication_role = DEFAULT;")
                        except Exception as inner:
                            if (
                                "permission denied" in str(inner).lower()
                                or "session_replication_role" in str(inner).lower()
                            ):
                                raise RuntimeError(
                                    "Deletion fallback needs session_replication_role=replica, "
                                    "which this database user is not allowed to set. "
                                    "Fix company/orphan rows manually or use a superuser connection."
                                ) from inner
                            raise

                    self.stdout.write(
                        self.style.SUCCESS(
                            f"     ✓ Company record deleted (via direct SQL)"
                        )
                    )
                else:
                    # Re-raise if it's a different error
                    raise

            self.stdout.write(
                self.style.SUCCESS(
                    f'\n✓ Successfully deleted company "{company_name}"!'
                )
            )

        except Company.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(
                    "Company not found with the provided ID or schema name."
                )
            )
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"\n✗ Error during deletion: {str(e)}"))
            self.stdout.write(
                self.style.WARNING("\nYou may need to manually clean up the database.")
            )
