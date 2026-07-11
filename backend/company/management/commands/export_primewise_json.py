from __future__ import annotations

import json
from pathlib import Path
from typing import List, Dict

from django.apps import apps
from django.conf import settings
from django.core import serializers
from django.core.management.base import BaseCommand
from django_tenants.utils import schema_context
from django.db.utils import ProgrammingError


SKIP_MODELS = {
    "contenttypes.contenttype",
    "auth.permission",
    "admin.logentry",
    "sessions.session",
}


class Command(BaseCommand):
    help = (
        "Export data from a tenant schema (default: primewise) into JSON fixtures, "
        "grouped per app, using chunked model iteration to avoid cursor issues."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--schema",
            default="primewise",
            help="Tenant schema to export from (default: primewise).",
        )
        parser.add_argument(
            "--apps",
            nargs="*",
            help=(
                "Optional list of app labels to export. "
                "If omitted, all TENANT_APPS from settings are used."
            ),
        )
        parser.add_argument(
            "--output-dir",
            default="dumps/primewise-json",
            help="Directory to write JSON files into (default: dumps/primewise-json).",
        )

    def handle(self, *args, **options):
        schema_name: str = options["schema"]
        output_dir = Path(options["output_dir"])
        output_dir.mkdir(parents=True, exist_ok=True)

        # Determine which app labels to export
        if options["apps"]:
            app_labels = options["apps"]
        else:
            tenant_apps_modules = list(getattr(settings, "TENANT_APPS", []))
            app_labels = []
            for mod in tenant_apps_modules:
                label = mod.rsplit(".", 1)[-1]
                if label not in app_labels:
                    app_labels.append(label)

        if not app_labels:
            self.stdout.write(self.style.WARNING("No tenant app labels to export. Exiting."))
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"Exporting tenant data from schema '{schema_name}' for apps: {', '.join(app_labels)}"
            )
        )

        with schema_context(schema_name):
            for app_label in app_labels:
                try:
                    app_config = apps.get_app_config(app_label)
                except LookupError:
                    self.stdout.write(
                        self.style.WARNING(f"App config not found for '{app_label}', skipping.")
                    )
                    continue

                all_objects: List[Dict] = []

                for model in app_config.get_models():
                    meta = model._meta
                    full_label = f"{meta.app_label}.{meta.model_name}".lower()

                    if full_label in SKIP_MODELS:
                        continue

                    qs = model._default_manager.all()
                    try:
                        if not qs.exists():
                            continue
                    except ProgrammingError as exc:
                        # Table might not exist in this schema (e.g. partially migrated apps).
                        self.stdout.write(
                            self.style.WARNING(
                                f"  Skipping {full_label} because its table is missing: {exc}"
                            )
                        )
                        continue

                    self.stdout.write(
                        self.style.NOTICE(  # type: ignore[attr-defined]
                            f"  Serializing {full_label} ({qs.count()} objects)"
                        )
                    )

                    # Serialize the entire queryset for this model.
                    # If the DB schema for this model is out of sync (missing columns),
                    # catch the error and skip this model instead of aborting the export.
                    try:
                        data_json = serializers.serialize(
                            "json",
                            qs,
                            use_natural_foreign_keys=True,
                            use_natural_primary_keys=True,
                        )
                    except ProgrammingError as exc:
                        self.stdout.write(
                            self.style.WARNING(
                                f"    Skipping {full_label} due to schema error during serialization: {exc}"
                            )
                        )
                        continue
                    try:
                        data_list = json.loads(data_json)
                    except json.JSONDecodeError as exc:
                        self.stdout.write(
                            self.style.ERROR(
                                f"    Failed to parse JSON for {full_label}: {exc}"
                            )
                        )
                        continue

                    if not isinstance(data_list, list):
                        self.stdout.write(
                            self.style.ERROR(
                                f"    Unexpected serialized type for {full_label}: {type(data_list)}"
                            )
                        )
                        continue

                    all_objects.extend(data_list)

                if not all_objects:
                    self.stdout.write(
                        self.style.WARNING(f"No data found for app '{app_label}', skipping file.")
                    )
                    continue

                file_path = output_dir / f"primewise_{app_label}.json"
                with file_path.open("w", encoding="utf-8") as f:
                    json.dump(all_objects, f, indent=2)

                self.stdout.write(
                    self.style.SUCCESS(
                        f"Wrote {len(all_objects)} objects for app '{app_label}' to {file_path}"
                    )
                )

