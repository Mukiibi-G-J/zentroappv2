from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Iterable, List, Dict

from django.conf import settings
from django.core.management import BaseCommand, call_command
from django.db import connection
from django_tenants.utils import get_public_schema_name

from company.models import Company


DEFAULT_EXCLUDES: List[str] = [
    "contenttypes",
    "auth.Permission",
    "admin.LogEntry",
    "sessions.Session",
]


def _run_dumpdata_for_schema(
    schema_name: str,
    app_labels: Iterable[str],
    excludes: Iterable[str],
    indent: int | None,
) -> List[Dict]:
    """
    Run Django's dumpdata for the given schema and app labels, returning a list
    of deserialized objects (dicts) suitable for JSON fixtures.
    """
    # Switch schema on the current connection
    connection.set_schema(schema_name)

    # Use an in-memory buffer to capture dumpdata JSON output
    buf = io.StringIO()

    # Build dumpdata arguments: app labels only; exclusions via --exclude
    dump_kwargs = {
        "stdout": buf,
        "indent": indent,
        "format": "json",
    }

    for ex in excludes:
        dump_kwargs.setdefault("exclude", [])
        dump_kwargs["exclude"].append(ex)

    # Call dumpdata; this will honour the current schema on the connection
    call_command("dumpdata", *app_labels, **dump_kwargs)

    raw = buf.getvalue().strip()
    if not raw:
        return []

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Failed to parse dumpdata JSON for schema {schema_name}: {exc}") from exc

    # dumpdata returns a list of objects
    if not isinstance(data, list):
        raise RuntimeError(f"Unexpected dumpdata output for schema {schema_name}: expected list, got {type(data)}")

    return data


class Command(BaseCommand):
    help = (
        "Export data from specified schemas (public and tenant schemas) into "
        "Django JSON fixtures, excluding migration and system tables."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--schemas",
            nargs="+",
            help=(
                "Schema names to export (e.g. public primewise). "
                "If omitted, defaults to: public and all tenant schemas."
            ),
        )
        parser.add_argument(
            "-o",
            "--output",
            required=True,
            help=(
                "Output path. If --split is given, treated as a directory. "
                "Otherwise, a single JSON file is written to this path."
            ),
        )
        parser.add_argument(
            "--exclude",
            nargs="*",
            default=[],
            help=(
                "Additional app labels or app.model paths to exclude. "
                "Defaults already exclude contenttypes, auth.Permission, "
                "admin.LogEntry and sessions.Session."
            ),
        )
        parser.add_argument(
            "--indent",
            type=int,
            default=2,
            help="JSON indent for readability (default: 2).",
        )
        parser.add_argument(
            "--split",
            action="store_true",
            help=(
                "Write one fixture file per schema (e.g. dump_public.json, dump_primewise.json) "
                "instead of a single combined JSON file."
            ),
        )

    def handle(self, *args, **options):
        # Resolve schemas
        schema_names: List[str]
        if options["schemas"]:
            schema_names = options["schemas"]
        else:
            # Default: public + all tenant schemas from Company
            public_schema = get_public_schema_name()
            tenant_schemas = list(
                Company.objects.exclude(schema_name=public_schema).values_list("schema_name", flat=True)
            )
            schema_names = [public_schema] + tenant_schemas

        if not schema_names:
            self.stdout.write(self.style.WARNING("No schemas to export. Exiting."))
            return

        # Build excludes list
        excludes = list(DEFAULT_EXCLUDES)
        for ex in options["exclude"] or []:
            if ex not in excludes:
                excludes.append(ex)

        indent = options.get("indent")
        split = options["split"]
        output = options["output"]

        # Determine app labels for public vs tenant schemas.
        # SHARED_APPS / TENANT_APPS contain dotted module paths; dumpdata expects
        # Django app labels (usually the last segment, e.g. 'django.contrib.admin' -> 'admin').
        shared_apps_modules = list(getattr(settings, "SHARED_APPS", []))
        tenant_apps_modules = list(getattr(settings, "TENANT_APPS", []))

        def to_app_labels(modules: List[str]) -> List[str]:
            labels: List[str] = []
            for mod in modules:
                # e.g. "django.contrib.admin" -> "admin"
                #      "company" -> "company"
                label = mod.rsplit(".", 1)[-1]
                if label not in labels:
                    labels.append(label)
            return labels

        shared_apps = to_app_labels(shared_apps_modules)
        tenant_apps = to_app_labels(tenant_apps_modules)
        public_schema_name = get_public_schema_name()

        # Normalise output path
        output_path = Path(output)

        if split:
            # Ensure directory exists
            output_dir = output_path
            output_dir.mkdir(parents=True, exist_ok=True)
        else:
            output_dir = output_path.parent
            output_dir.mkdir(parents=True, exist_ok=True)

        combined: Dict[str, List[Dict]] = {}

        for schema in schema_names:
            is_public = schema == public_schema_name or schema == "public"
            app_labels = shared_apps if is_public else tenant_apps

            if not app_labels:
                self.stdout.write(
                    self.style.WARNING(f"No app labels configured for schema {schema}; skipping.")
                )
                continue

            self.stdout.write(self.style.NOTICE(f"Exporting schema '{schema}' ..."))  # type: ignore[attr-defined]

            data = _run_dumpdata_for_schema(
                schema_name=schema,
                app_labels=app_labels,
                excludes=excludes,
                indent=indent,
            )

            if split:
                # Each schema gets its own fixture file
                safe_schema = schema.replace("-", "_")
                file_path = output_dir / f"dump_{safe_schema}.json"
                with file_path.open("w", encoding="utf-8") as f:
                    json.dump(data, f, indent=indent)
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Wrote {len(data)} objects for schema '{schema}' to {file_path}"
                    )
                )
            else:
                combined[schema] = data
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Collected {len(data)} objects for schema '{schema}'"
                    )
                )

        if not split:
            with output_path.open("w", encoding="utf-8") as f:
                json.dump(combined, f, indent=indent)
            self.stdout.write(
                self.style.SUCCESS(
                    f"Wrote combined export for {len(combined)} schema(s) to {output_path}"
                )
            )

