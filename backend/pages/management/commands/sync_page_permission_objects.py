from django.core.management.base import BaseCommand, CommandError
from django_tenants.utils import get_tenant_model, schema_context

from pages.permission_sync import sync_all_page_permission_objects


def _run(schema_name: str, stdout=None, style=None):
    with schema_context(schema_name):
        stats = sync_all_page_permission_objects()
    if stdout and style:
        stdout.write(
            style.SUCCESS(
                f'  {schema_name}: created={stats["created"]} updated={stats["updated"]} '
                f'skipped={stats["skipped"]}'
            )
        )
    return stats


class Command(BaseCommand):
    help = (
        'Sync page-engine Pages (with object_id) to base.Objects for BC-style '
        'permission set lines (run after seed_pages or migrate).'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--schema',
            type=str,
            default=None,
            help='Single tenant schema; omit to run all tenants.',
        )

    def handle(self, *args, **options):
        target = options.get('schema')
        if target:
            try:
                _run(target, self.stdout, self.style)
                self.stdout.write(self.style.SUCCESS(f'Done — schema: {target}'))
            except Exception as exc:
                raise CommandError(f'Failed for schema "{target}": {exc}') from exc
            return

        TenantModel = get_tenant_model()
        for tenant in TenantModel.objects.exclude(schema_name='public').order_by('schema_name'):
            try:
                _run(tenant.schema_name, self.stdout, self.style)
            except Exception as exc:
                self.stdout.write(
                    self.style.ERROR(f'  {tenant.schema_name}: {exc}')
                )
