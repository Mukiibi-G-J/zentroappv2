"""
Assign UserPersonalization Role Centres from legacy Role / UserGroup access.

Usage::

    python manage.py tenant_command assign_application_profiles --schema=primewise --force
"""

from django.core.management.base import BaseCommand

from authentication.profile_assignment import assign_application_profiles


class Command(BaseCommand):
    help = 'Assign ApplicationProfile (Role Centre) from old roles/groups'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Overwrite existing personalization profiles',
        )
        parser.add_argument(
            '--only-missing',
            action='store_true',
            help='Only set users who have no profile yet',
        )

    def handle(self, *args, **options):
        stats = assign_application_profiles(
            only_missing=options['only_missing'],
            force=options['force'] or not options['only_missing'],
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"users={stats['users']} updated={stats['updated']} "
                f"skipped={stats['skipped']} unmapped={stats['unmapped']} "
                f"missing_profile={stats['missing_profile']}"
            )
        )
