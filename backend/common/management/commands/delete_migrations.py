from django.core.management.base import BaseCommand
import os
import pathlib
from django.conf import settings


class Command(BaseCommand):
    help = 'Delete migration files starting with "00" from custom project apps only'

    def add_arguments(self, parser):
        parser.add_argument(
            "--exclude",
            nargs="+",
            help="List of apps to exclude from migration deletion",
            default=["admin"],
        )

    def handle(self, *args, **options):
        excluded_apps = options["exclude"]
        project_root = pathlib.Path().absolute()

        # Get the base directory where your custom apps are located
        base_dir = str(project_root)

        deleted_files = 0
        skipped_files = 0

        # List of your custom apps
        custom_apps = [
            "authentication",
            "base",
            "common",
            "financials",
            "items",
            "postings",
            "company",
            "sales",
            "config_packages",
            "customers",
            "settings",
            "setup",
            "purchases",
            "payments",
            "expenses",
            "reports",
            "resources",
            "production",
            "permissions",
            "prepayment",
            "bank_account",
            "hotel_management",
        ]

        for root, dirs, files in os.walk(project_root):
            if "migrations" in dirs:
                migration_dir = os.path.join(root, "migrations")
                app_name = os.path.basename(os.path.dirname(migration_dir))

                # Skip if not in custom apps list
                if app_name not in custom_apps:
                    self.stdout.write(
                        self.style.WARNING(
                            f"Skipping {app_name} as it is not a custom app"
                        )
                    )
                    continue

                if app_name in excluded_apps:
                    self.stdout.write(
                        self.style.WARNING(
                            f"Skipping {app_name} as it is in excluded apps"
                        )
                    )
                    continue

                for filename in os.listdir(migration_dir):
                    # Only delete files starting with "00" and are .py files
                    if (
                        filename.startswith("00")
                        and filename.endswith(".py")
                        and filename != "__init__.py"
                    ):
                        file_path = os.path.join(migration_dir, filename)
                        try:
                            # Delete the file instead of clearing it
                            os.remove(file_path)
                            deleted_files += 1
                            self.stdout.write(
                                self.style.SUCCESS(
                                    f"Deleted migration file: {file_path}"
                                )
                            )
                        except Exception as e:
                            skipped_files += 1
                            self.stdout.write(
                                self.style.ERROR(
                                    f"Error deleting {file_path}: {str(e)}"
                                )
                            )

        self.stdout.write(
            self.style.SUCCESS(
                f"\nCompleted! Deleted {deleted_files} migration files. "
                f"Skipped {skipped_files} files."
            )
        )
