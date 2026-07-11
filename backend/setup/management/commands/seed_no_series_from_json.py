from django.core.management.base import BaseCommand
from django.db import transaction
from django_tenants.utils import schema_context
from django.conf import settings
import json
import os
from pathlib import Path

from setup.models import NoSeries, NoSeriesLines


@transaction.atomic
def seed_no_series_from_json(json_file_path: str) -> dict:
    """
    Read number series from JSON file and create/update them.
    
    Returns:
        dict: Summary with created, updated, exists, errors counts
    """
    # Read JSON file
    if not os.path.exists(json_file_path):
        raise FileNotFoundError(f"JSON file not found: {json_file_path}")
    
    with open(json_file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Extract number series from the data structure
    series_data = data.get("no_series", [])
    
    if not series_data:
        raise ValueError("No number series found in JSON file")
    
    summary = {
        "created": 0,
        "updated": 0,
        "exists": 0,
        "errors": 0,
        "error_details": []
    }
    
    # Process each number series
    for series_info in series_data:
        try:
            code = series_info.get("code")
            if not code:
                summary["errors"] += 1
                summary["error_details"].append({
                    "series": "Unknown",
                    "error": "Missing code"
                })
                continue
            
            description = series_info.get("description", "")
            no_series_lines_data = series_info.get("no_series_lines", {})
            start_number = no_series_lines_data.get("start_number", "")
            increment_by = no_series_lines_data.get("increment_by", 1)
            
            # Create or update NoSeries
            no_series, ns_created = NoSeries.objects.get_or_create(
                code=code,
                defaults={"description": description}
            )
            
            if ns_created:
                summary["created"] += 1
            else:
                # Update description if it exists but is different
                if no_series.description != description:
                    no_series.description = description
                    no_series.save(update_fields=["description"])
                    summary["updated"] += 1
                else:
                    summary["exists"] += 1
            
            # Create or update NoSeriesLines
            no_series_line, line_created = NoSeriesLines.objects.get_or_create(
                no_series=no_series,
                defaults={
                    "start_number": start_number,
                    "increment_by": increment_by,
                }
            )
            
            if not line_created:
                # Update if fields are missing or different
                updated_fields = []
                if (
                    not no_series_line.start_number
                    or no_series_line.start_number != start_number
                ):
                    no_series_line.start_number = start_number
                    updated_fields.append("start_number")
                
                if (
                    not no_series_line.increment_by
                    or no_series_line.increment_by != increment_by
                ):
                    no_series_line.increment_by = increment_by
                    updated_fields.append("increment_by")
                
                if updated_fields:
                    no_series_line.save(update_fields=updated_fields)
                    summary["updated"] += 1
            else:
                summary["created"] += 1
                
        except Exception as e:
            summary["errors"] += 1
            series_code = series_info.get("code", "Unknown")
            summary["error_details"].append({
                "series": series_code,
                "error": str(e)
            })
    
    return summary


class Command(BaseCommand):
    help = "Seed number series from default_no_series.json file"

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            type=str,
            default="data/default_no_series.json",
            help="Path to JSON file (default: data/default_no_series.json)",
        )
        parser.add_argument(
            "--tenant",
            type=str,
            help="Tenant schema name (optional, defaults to current schema)",
        )

    def handle(self, *args, **options):
        json_file = options.get("file", "data/default_no_series.json")
        tenant_schema = options.get("tenant")

        # Resolve file path
        if not os.path.isabs(json_file):
            # Try relative to project root (zentro-backend)
            backend_path = Path(__file__).parent.parent.parent.parent / json_file
            if backend_path.exists():
                json_file = str(backend_path.resolve())
            else:
                # Try current working directory
                current_path = Path(json_file)
                if current_path.exists():
                    json_file = str(current_path.resolve())
                else:
                    # Try absolute path as-is
                    if not os.path.exists(json_file):
                        raise FileNotFoundError(
                            f"JSON file not found: {json_file}\n"
                            f"Tried:\n"
                            f"  - {backend_path}\n"
                            f"  - {current_path.resolve()}\n"
                            f"  - {json_file}"
                        )

        self.stdout.write("\n" + "=" * 80)
        self.stdout.write(
            self.style.SUCCESS("SEEDING NUMBER SERIES FROM JSON")
        )
        self.stdout.write("=" * 80)
        self.stdout.write(f"JSON File: {json_file}\n")

        def seed_series():
            summary = seed_no_series_from_json(json_file)
            
            # Display summary
            self.stdout.write("\n" + "-" * 80)
            self.stdout.write(self.style.SUCCESS("SEEDING SUMMARY"))
            self.stdout.write("-" * 80)
            self.stdout.write(f"  ✓ Created: {summary['created']} series/lines")
            self.stdout.write(f"  ↻ Updated: {summary['updated']} series/lines")
            self.stdout.write(f"  ⊙ Exists:  {summary['exists']} series/lines")
            
            if summary["errors"] > 0:
                self.stdout.write(
                    self.style.ERROR(f"  ✗ Errors:  {summary['errors']} series")
                )
                self.stdout.write("\n  Error Details:")
                for error in summary["error_details"]:
                    self.stdout.write(
                        self.style.ERROR(f"    - {error['series']}: {error['error']}")
                    )
            
            total_processed = (
                summary["created"] + summary["updated"] + summary["exists"] + summary["errors"]
            )
            self.stdout.write(f"\n  Total Processed: {total_processed} series")

        try:
            if tenant_schema:
                with schema_context(tenant_schema):
                    seed_series()
            else:
                seed_series()
        except FileNotFoundError as e:
            self.stdout.write(
                self.style.ERROR(f"✗ File not found: {str(e)}")
            )
            self.stdout.write("\n  Please ensure the JSON file exists and the path is correct.")
            raise
        except ValueError as e:
            self.stdout.write(
                self.style.ERROR(f"✗ Invalid JSON structure: {str(e)}")
            )
            raise
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"✗ Error seeding number series: {str(e)}")
            )
            raise

        self.stdout.write("\n" + "=" * 80)
        self.stdout.write(self.style.SUCCESS("NUMBER SERIES SEEDING COMPLETED"))
        self.stdout.write("=" * 80 + "\n")

