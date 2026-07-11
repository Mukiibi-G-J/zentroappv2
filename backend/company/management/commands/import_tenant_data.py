import json

from django.core.management.base import BaseCommand

from company.tenant_import import run_tenant_data_import


class Command(BaseCommand):
    help = "Import tenant data from JSON file"

    def add_arguments(self, parser):
        parser.add_argument("schema_name", type=str)
        parser.add_argument("file_path", type=str)

    def handle(self, *args, **options):
        schema_name = options["schema_name"]
        file_path = options["file_path"]

        if isinstance(file_path, dict):
            file_path = str(file_path.get("path", ""))
        else:
            file_path = str(file_path)

        with open(file_path, "r") as f:
            data = json.load(f)

        run_tenant_data_import(
            schema_name, data, self.stdout, self.stderr, self.style
        )
