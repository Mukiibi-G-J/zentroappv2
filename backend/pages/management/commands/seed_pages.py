from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django_tenants.utils import schema_context, get_tenant_model, get_public_schema_name

from pages.schema_ddl import ensure_page_engine_schema


def _active_tenant_schema() -> str | None:
    """When invoked via `tenant_command`, the connection tenant is already set."""
    tenant = getattr(connection, 'tenant', None)
    schema_name = getattr(tenant, 'schema_name', None)
    if schema_name and schema_name != get_public_schema_name():
        return schema_name
    return None


def _run_for_schema(schema_name: str, stdout=None):
    from pages.seed import seed
    with schema_context(schema_name):
        with connection.cursor() as cur:
            ensure_page_engine_schema(cur)
        ids = seed()
    if stdout:
        stdout.write(
            f"  {schema_name}: list pages {ids['items_list_id']}/{ids['customers_list_id']}/"
            f"{ids['vendors_list_id']}/{ids.get('bank_accounts_list_id', '—')}/"
            f"{ids.get('users_list_id', '—')}/{ids.get('user_setup_list_id', '—')} "
            f"-> card pages {ids['items_card_id']}/{ids['customers_card_id']}/"
            f"{ids['vendors_card_id']}/{ids.get('bank_accounts_card_id', '—')}/"
            f"{ids.get('users_card_id', '—')} "
            f"(ledger lists {ids.get('customer_ledger_list_id')}/"
            f"{ids.get('vendor_ledger_list_id')}/{ids.get('item_ledger_list_id')}/"
            f"{ids.get('bank_ledger_list_id', '—')})"
        )
    return ids


class Command(BaseCommand):
    help = 'Create page engine tables and seed pages for one or all tenant schemas'

    def add_arguments(self, parser):
        parser.add_argument(
            '--schema',
            type=str,
            default=None,
            help='Target a single tenant schema (e.g. --schema primewise). Omit to run all tenants.',
        )

    def handle(self, *args, **options):
        target = options.get('schema') or _active_tenant_schema()

        if target:
            try:
                _run_for_schema(target, self.stdout)
                self.stdout.write(self.style.SUCCESS(f'Done — schema: {target}'))
            except Exception as e:
                raise CommandError(f'Failed for schema "{target}": {e}') from e
        else:
            TenantModel = get_tenant_model()
            tenants = list(TenantModel.objects.exclude(schema_name='public'))
            if not tenants:
                self.stdout.write(self.style.WARNING('No non-public tenants found.'))
                return
            errors = []
            for tenant in tenants:
                try:
                    _run_for_schema(tenant.schema_name, self.stdout)
                except Exception as e:
                    errors.append(f'{tenant.schema_name}: {e}')
                    self.stdout.write(self.style.ERROR(f'  ERR {tenant.schema_name}: {e}'))
            if errors:
                raise CommandError(f'{len(errors)} schema(s) failed.')
            self.stdout.write(self.style.SUCCESS(f'Done — {len(tenants)} schema(s) seeded.'))
