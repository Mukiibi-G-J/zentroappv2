from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

from django.core.management import BaseCommand
from django.core import serializers
from django.db import connection, transaction
from django_tenants.utils import get_public_schema_name


class Command(BaseCommand):
    help = (
        "Load JSON fixtures into specific schemas (public and tenant schemas). "
        "Supports either a combined JSON file keyed by schema name or a directory "
        "containing per-schema files like dump_public.json, dump_primewise.json."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "-i",
            "--input",
            required=True,
            help=(
                "Path to a combined JSON file or a directory containing per-schema "
                "fixture files (e.g. dump_public.json, dump_primewise.json)."
            ),
        )
        parser.add_argument(
            "--schemas",
            nargs="*",
            help=(
                "Optional list of schema names to load. "
                "If omitted, all schemas present in the input are loaded."
            ),
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Parse fixtures and show counts but do not write to the database.",
        )

    def handle(self, *args, **options):
        input_path = Path(options["input"])
        specified_schemas = options.get("schemas") or []
        dry_run = options["dry_run"]

        if not input_path.exists():
            raise SystemExit(f"Input path does not exist: {input_path}")

        if input_path.is_dir():
            schema_to_file = self._discover_per_schema_files(input_path)
            data_by_schema = self._load_per_schema_files(schema_to_file)
        else:
            data_by_schema = self._load_combined_file(input_path)

        if not data_by_schema:
            self.stdout.write(self.style.WARNING("No schema data found in input. Nothing to do."))
            return

        # Filter to specified schemas if provided
        if specified_schemas:
            data_by_schema = {
                schema: data
                for schema, data in data_by_schema.items()
                if schema in specified_schemas
            }

        if not data_by_schema:
            self.stdout.write(
                self.style.WARNING("No matching schemas to load after applying filters.")
            )
            return

        for schema, objects in data_by_schema.items():
            if not isinstance(objects, list):
                self.stdout.write(
                    self.style.ERROR(
                        f"Expected a list of fixture objects for schema '{schema}', "
                        f"got {type(objects)} instead."
                    )
                )
                continue

            if not objects:
                self.stdout.write(
                    self.style.WARNING(f"No objects to load for schema '{schema}'; skipping.")
                )
                continue

            self._load_for_schema(schema, objects, dry_run=dry_run)

    def _discover_per_schema_files(self, directory: Path) -> Dict[str, Path]:
        """
        Discover per-schema fixture files in a directory.
        Expected naming: dump_<schema>.json (e.g. dump_public.json, dump_primewise.json).
        """
        mapping: Dict[str, Path] = {}
        for path in directory.glob("dump_*.json"):
            name = path.stem  # e.g. "dump_public"
            _, _, schema = name.partition("dump_")
            if not schema:
                continue
            mapping[schema] = path
        return mapping

    def _load_per_schema_files(self, mapping: Dict[str, Path]) -> Dict[str, List[dict]]:
        data_by_schema: Dict[str, List[dict]] = {}
        for schema, path in mapping.items():
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            data_by_schema[schema] = data
        return data_by_schema

    def _load_combined_file(self, path: Path) -> Dict[str, List[dict]]:
        """
        Load a single combined JSON file of the form:
        {
          "public": [...],
          "primewise": [...]
        }
        """
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, dict):
            raise SystemExit(
                f"Combined input file must be a JSON object keyed by schema name; "
                f"got {type(data)} instead."
            )

        result: Dict[str, List[dict]] = {}
        for schema, objects in data.items():
            if isinstance(objects, list):
                result[schema] = objects
        return result

    def _load_for_schema(self, schema_name: str, objects: List[dict], dry_run: bool) -> None:
        """
        Load a list of fixture-style objects into a specific schema using
        Django's serializers. Runs inside a transaction per schema.
        """
        # Switch schema
        connection.set_schema(schema_name)

        # Re-encode objects as JSON that Django's serializers can consume
        json_string = json.dumps(objects)

        # Parse fixtures
        try:
            deserialized = list(serializers.deserialize("json", json_string))
        except Exception as exc:
            self.stdout.write(
                self.style.ERROR(
                    f"Failed to deserialize fixtures for schema '{schema_name}': {exc}"
                )
            )
            return

        total = len(deserialized)
        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"[DRY RUN] Would load {total} object(s) into schema '{schema_name}'."
                )
            )
            return

        self.stdout.write(
            self.style.NOTICE(  # type: ignore[attr-defined]
                f"Loading {total} object(s) into schema '{schema_name}' ..."
            )
        )

        with transaction.atomic():
            for obj in deserialized:
                obj.save()

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully loaded {total} object(s) into schema '{schema_name}'."
            )
        )

