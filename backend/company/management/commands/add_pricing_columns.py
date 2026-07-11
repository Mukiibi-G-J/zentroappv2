"""Add included_modules to company_pricing if missing (fix for faked migrations)."""
from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = "Add included_modules column to company_pricing if missing"

    def handle(self, *args, **options):
        with connection.cursor() as c:
            c.execute("""
                SELECT column_name FROM information_schema.columns
                WHERE table_schema='public' AND table_name='company_pricing' AND column_name='included_modules'
            """)
            if c.fetchone():
                self.stdout.write(self.style.SUCCESS("included_modules already exists"))
            else:
                c.execute("ALTER TABLE company_pricing ADD COLUMN included_modules jsonb DEFAULT '[]'::jsonb")
                self.stdout.write(self.style.SUCCESS("Added included_modules to company_pricing"))

            c.execute("""
                SELECT column_name FROM information_schema.columns
                WHERE table_schema='public' AND table_name='company_company' AND column_name='module_overrides'
            """)
            if c.fetchone():
                self.stdout.write(self.style.SUCCESS("module_overrides already exists"))
            else:
                c.execute("ALTER TABLE company_company ADD COLUMN module_overrides jsonb DEFAULT '[]'::jsonb")
                self.stdout.write(self.style.SUCCESS("Added module_overrides to company_company"))

            c.execute("""
                SELECT column_name FROM information_schema.columns
                WHERE table_schema='public' AND table_name='company_company' AND column_name='user_limit_override'
            """)
            if c.fetchone():
                self.stdout.write(self.style.SUCCESS("user_limit_override already exists"))
            else:
                c.execute("ALTER TABLE company_company ADD COLUMN user_limit_override integer NULL")
                self.stdout.write(self.style.SUCCESS("Added user_limit_override to company_company"))

            c.execute("""
                SELECT column_name FROM information_schema.columns
                WHERE table_schema='public' AND table_name='company_subscription' AND column_name='extra_users_purchased'
            """)
            if c.fetchone():
                self.stdout.write(self.style.SUCCESS("extra_users_purchased already exists"))
            else:
                c.execute("ALTER TABLE company_subscription ADD COLUMN extra_users_purchased integer NOT NULL DEFAULT 0")
                self.stdout.write(self.style.SUCCESS("Added extra_users_purchased to company_subscription"))
        self.stdout.write(self.style.SUCCESS("Done."))
