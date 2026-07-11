import pandas as pd
import logging
from celery import shared_task
from django.apps import apps
from django_tenants.utils import tenant_context
from .models import ConfigPackage, ConfigPackageTable
from .import_handlers import process_import_data

logger = logging.getLogger(__name__)


@shared_task(bind=True)
def import_tables_background(
    self,
    tenant_schema_name,
    excel_file_path,
    package_code,
    table_id,
    table_name,
    user_id=None,
):
    """
    Background task to import tables using the modular import handlers system
    """
    logger.info(
        f"DEBUG: Task - import_tables_background called with user_id: {user_id}"
    )
    try:
        # Update task state to STARTED
        self.update_state(
            state="STARTED",
            meta={
                "progress": 10,
                "message": "Starting import process...",
                "status": "started",
            },
        )

        # Get tenant and use schema context
        from django_tenants.utils import schema_context
        from company.models import Company

        logger.info(f"Starting import for schema: {tenant_schema_name}")

        # Use schema context directly
        with schema_context(tenant_schema_name):
            # Get tenant within the schema context
            try:
                tenant = Company.objects.get(schema_name=tenant_schema_name)
                logger.info(
                    f"Found tenant: {tenant.name} with schema: {tenant.schema_name}"
                )
            except Company.DoesNotExist:
                logger.error(
                    f"Company with schema_name '{tenant_schema_name}' does not exist"
                )
                raise ValueError(f"Tenant not found for schema: {tenant_schema_name}")
            except Exception as e:
                logger.error(f"Error getting tenant: {e}")
                raise ValueError(f"Error getting tenant: {str(e)}")

            # Look up the user within the tenant context
            user = None
            if user_id:
                from authentication.models import CustomUser

                try:
                    user = CustomUser.objects.get(id=user_id)
                    logger.info(f"DEBUG: Found user in tenant context: {user}")
                except CustomUser.DoesNotExist:
                    logger.error(f"DEBUG: User {user_id} not found in tenant context")
                    user = None

            # Update progress
            self.update_state(
                state="PROGRESS",
                meta={
                    "progress": 20,
                    "message": "Loading model and data...",
                    "status": "processing",
                },
            )

            # Get model class for the table
            model = None
            for app_config in apps.get_app_configs():
                try:
                    model_name = table_name.replace(" ", "")  # Remove spaces
                    model = apps.get_model(app_config.label, model_name)
                    break
                except LookupError:
                    continue

            if not model:
                raise ValueError(f"Model not found for table: {table_name}")

            # Get or create config package table
            config_package = ConfigPackage.objects.get(code=package_code)
            package_table, _ = ConfigPackageTable.objects.get_or_create(
                package_code=config_package,
                table_id=table_id,
                defaults={"table_name": table_name},
            )

            # Update progress
            self.update_state(
                state="PROGRESS",
                meta={
                    "progress": 30,
                    "message": "Reading Excel file...",
                    "status": "processing",
                },
            )

            # Read Excel file - get headers from row 4 and data starting from row 5
            df = pd.read_excel(excel_file_path, header=None)
            headers = df.iloc[3].fillna("").str.strip()
            data_df = df.iloc[4:]
            data_df.columns = headers

            # Update progress
            self.update_state(
                state="PROGRESS",
                meta={
                    "progress": 50,
                    "message": "Processing import data...",
                    "status": "processing",
                },
            )

            # Use the modular import system
            logger.info(f"DEBUG: About to call process_import_data with user: {user}")
            stats = process_import_data(model, tenant, package_table, data_df, user)

            # Update progress
            self.update_state(
                state="PROGRESS",
                meta={
                    "progress": 90,
                    "message": "Finalizing import...",
                    "status": "processing",
                },
            )

            # Prepare result message
            if stats["failed"] > 0:
                message = f"Import completed with {stats['failed']} errors. {stats['created']} records created, {stats['updated']} records updated."
            else:
                message = f"Import completed successfully. {stats['created']} records created, {stats['updated']} records updated."

            # Return success result
            return {
                "progress": 100,
                "message": message,
                "status": "completed",
                "success": stats["failed"] == 0,
                "statistics": stats,
            }

    except Exception as e:
        logger.error(
            f"Background import failed for tenant {tenant_schema_name}: {str(e)}"
        )

        # Return error result
        return {
            "progress": 100,
            "message": f"Import failed: {str(e)}",
            "status": "failed",
            "success": False,
            "error": str(e),
        }
    finally:
        # Clean up temporary file
        try:
            import os

            if os.path.exists(excel_file_path):
                os.unlink(excel_file_path)
                logger.info(f"Cleaned up temporary file: {excel_file_path}")
        except Exception as e:
            logger.error(f"Error cleaning up temporary file: {e}")
