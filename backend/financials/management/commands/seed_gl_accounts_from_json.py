from django.core.management.base import BaseCommand
from django.db import transaction
from django_tenants.utils import schema_context
import json
import os
from pathlib import Path

from financials.models import G_LAccount


@transaction.atomic
def seed_accounts_from_json(json_file_path: str) -> dict:
    """
    Read GL accounts from JSON export file and create/update accounts.
    
    Returns:
        dict: Summary with created, updated, exists, errors counts
    """
    # Read JSON file
    if not os.path.exists(json_file_path):
        raise FileNotFoundError(f"JSON file not found: {json_file_path}")
    
    with open(json_file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Extract GL accounts from the data structure
    accounts_data = data.get("data", {}).get("financials.G_LAccount", [])
    
    if not accounts_data:
        raise ValueError("No GL accounts found in JSON file")
    
    summary = {
        "created": 0,
        "updated": 0,
        "exists": 0,
        "errors": 0,
        "error_details": []
    }
    
    # Process each account
    for account_data in accounts_data:
        try:
            account_no = account_data.get("no")
            if not account_no:
                summary["errors"] += 1
                summary["error_details"].append({
                    "account": "Unknown",
                    "error": "Missing account number (no)"
                })
                continue
            
            # Prepare account data (exclude 'no' from defaults)
            account_fields = {
                "name": account_data.get("name", ""),
                "indentation": account_data.get("indentation", 0),
                "income_balance": account_data.get("income_balance"),
                "accountcategory": account_data.get("accountcategory"),
                "debit_credit": account_data.get("debit_credit"),
                "accounttype": account_data.get("accounttype"),
                "totaling": account_data.get("totaling"),
                "direct_posting": account_data.get("direct_posting", False),
                "blocked": account_data.get("blocked", False),
            }
            
            # Handle None values for totaling
            if account_fields["totaling"] is None:
                account_fields["totaling"] = None
            
            # Try to get existing account
            try:
                account = G_LAccount.objects.get(no=account_no)
                
                # Check if update is needed
                changed_fields = []
                for field_name, value in account_fields.items():
                    current_value = getattr(account, field_name)
                    if current_value != value:
                        setattr(account, field_name, value)
                        changed_fields.append(field_name)
                
                if changed_fields:
                    account.save(update_fields=changed_fields)
                    summary["updated"] += 1
                else:
                    summary["exists"] += 1
                    
            except G_LAccount.DoesNotExist:
                # Create new account
                G_LAccount.objects.create(no=account_no, **account_fields)
                summary["created"] += 1
                
        except Exception as e:
            summary["errors"] += 1
            account_name = account_data.get("name", "Unknown")
            account_no = account_data.get("no", "N/A")
            summary["error_details"].append({
                "account": f"{account_no} - {account_name}",
                "error": str(e)
            })
    
    return summary


class Command(BaseCommand):
    help = "Seed GL accounts from tenant export JSON file"

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            type=str,
            default="tenant_semuna_export_20250227_062346.json",
            help="Path to JSON export file (default: tenant_semuna_export_20250227_062346.json)",
        )
        parser.add_argument(
            "--schema",
            type=str,
            default="semuna",
            help="Schema name for tenant-specific operation (default: semuna)",
        )

    def handle(self, *args, **options):
        schema_name = options.get("schema", "semuna")
        json_file = options.get("file", "tenant_semuna_export_20250227_062346.json")
        
        # Resolve file path (try relative to project root, then absolute)
        if not os.path.isabs(json_file):
            # Try in zentro-backend directory (where the command is located)
            # __file__ is in: zentro-backend/financials/management/commands/seed_gl_accounts_from_json.py
            # So we go up 4 levels to get to zentro-backend
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
            self.style.SUCCESS(f"SEEDING GL ACCOUNTS FROM JSON FOR SCHEMA: {schema_name}")
        )
        self.stdout.write("=" * 80)
        self.stdout.write(f"JSON File: {json_file}\n")
        
        try:
            with schema_context(schema_name):
                summary = seed_accounts_from_json(json_file)
                
                # Display summary
                self.stdout.write("\n" + "-" * 80)
                self.stdout.write(self.style.SUCCESS("SEEDING SUMMARY"))
                self.stdout.write("-" * 80)
                self.stdout.write(f"  ✓ Created: {summary['created']} accounts")
                self.stdout.write(f"  ↻ Updated: {summary['updated']} accounts")
                self.stdout.write(f"  ⊙ Exists:  {summary['exists']} accounts")
                
                if summary["errors"] > 0:
                    self.stdout.write(
                        self.style.ERROR(f"  ✗ Errors:  {summary['errors']} accounts")
                    )
                    self.stdout.write("\n  Error Details:")
                    for error in summary["error_details"]:
                        self.stdout.write(
                            self.style.ERROR(f"    - {error['account']}: {error['error']}")
                        )
                
                total_processed = (
                    summary["created"] + summary["updated"] + summary["exists"] + summary["errors"]
                )
                self.stdout.write(f"\n  Total Processed: {total_processed} accounts")
                
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
                self.style.ERROR(f"✗ Error seeding accounts: {str(e)}")
            )
            raise

        self.stdout.write("\n" + "=" * 80)
        self.stdout.write(self.style.SUCCESS("GL ACCOUNTS SEEDING COMPLETED"))
        self.stdout.write("=" * 80 + "\n")

