from django.core.management.base import BaseCommand
from django_tenants.utils import schema_context

from financials.services.chart_of_accounts import indent_chart_of_accounts


class Command(BaseCommand):
    help = 'Recompute G/L account indentation (Business Central style) for a tenant schema'

    def add_arguments(self, parser):
        parser.add_argument(
            '--schema',
            type=str,
            required=True,
            help='Tenant schema name (e.g. primewise)',
        )

    def handle(self, *args, **options):
        schema_name = options['schema']
        self.stdout.write(f'Indenting chart of accounts for schema: {schema_name}')

        with schema_context(schema_name):
            result = indent_chart_of_accounts()

        if result.errors:
            for message in result.errors:
                self.stdout.write(self.style.ERROR(message))

        self.stdout.write(
            self.style.SUCCESS(
                f'Updated indentation on {result.updated} account(s).',
            ),
        )
