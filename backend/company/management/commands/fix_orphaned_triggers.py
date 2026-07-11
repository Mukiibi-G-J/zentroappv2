from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = "Fix orphaned PostgreSQL triggers that cause deletion errors"

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING("Checking for orphaned triggers..."))

        with connection.cursor() as cursor:
            # Find all orphaned triggers (triggers that reference non-existent functions)
            cursor.execute(
                """
                SELECT 
                    t.tgname AS trigger_name,
                    c.relname AS table_name,
                    n.nspname AS schema_name,
                    t.oid AS trigger_oid
                FROM pg_trigger t
                JOIN pg_class c ON t.tgrelid = c.oid
                JOIN pg_namespace n ON c.relnamespace = n.oid
                WHERE NOT t.tgisinternal
                AND NOT EXISTS (
                    SELECT 1 
                    FROM pg_proc p 
                    WHERE p.oid = t.tgfoid
                )
                ORDER BY n.nspname, c.relname, t.tgname;
            """
            )

            orphaned_triggers = cursor.fetchall()

            if not orphaned_triggers:
                self.stdout.write(self.style.SUCCESS("No orphaned triggers found!"))
                return

            self.stdout.write(
                self.style.WARNING(
                    f"Found {len(orphaned_triggers)} orphaned trigger(s)"
                )
            )

            # Drop each orphaned trigger
            for trigger_name, table_name, schema_name, trigger_oid in orphaned_triggers:
                try:
                    self.stdout.write(
                        f"  Dropping trigger {trigger_name} on {schema_name}.{table_name} (OID: {trigger_oid})"
                    )

                    # Drop the trigger
                    cursor.execute(
                        f"""
                        DROP TRIGGER IF EXISTS "{trigger_name}" ON "{schema_name}"."{table_name}" CASCADE;
                    """
                    )

                    self.stdout.write(self.style.SUCCESS(f"    ✓ Dropped successfully"))
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"    ✗ Error: {str(e)}"))

            # Commit the changes
            connection.commit()

            self.stdout.write(
                self.style.SUCCESS("\nOrphaned triggers cleanup completed!")
            )
            self.stdout.write("You can now try deleting the company again.")
