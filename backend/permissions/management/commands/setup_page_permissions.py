"""
Management command to create default permission sets with page-engine permissions.

Page lines reference page names (e.g. ``ItemList`` → Zentro ID 10201).
Run ``seed_pages`` (or ``align_zentro_page_ids``) first so PageId == ObjectId.

Usage:
    python manage.py tenant_command setup_page_permissions --schema=hardwareworld
"""

from django.core.management.base import BaseCommand

from permissions.bc_permission_set_pages import BC_PERMISSION_SET_PAGES
from permissions.models import PermissionSet
from permissions.table_permissions import create_permission_lines


class Command(BaseCommand):
    help = 'Create default permission sets with Zentro page object permissions'

    def handle(self, *args, **options):
        self.stdout.write('\n' + '=' * 80)
        self.stdout.write(self.style.SUCCESS('SETTING UP PAGE PERMISSIONS'))
        self.stdout.write('=' * 80 + '\n')

        created_sets = 0
        updated_sets = 0
        created_lines = 0

        for code, name, description, page_permissions in BC_PERMISSION_SET_PAGES:
            perm_set, created = PermissionSet.objects.update_or_create(
                code=code,
                defaults={
                    'name': name,
                    'description': description,
                    'is_active': True,
                },
            )

            if created:
                created_sets += 1
                self.stdout.write(self.style.SUCCESS(f'\n[+] Created Permission Set: {code}'))
            else:
                updated_sets += 1
                self.stdout.write(self.style.WARNING(f'\n[~] Updated Permission Set: {code}'))

            perm_set.permissionsetline_set.all().delete()

            n = create_permission_lines(
                perm_set,
                page_permissions,
                object_type='Page',
                stdout=self.stdout,
                style=self.style,
            )
            created_lines += n

            for page_name, permissions in page_permissions:
                if not permissions:
                    continue
                perm_str = ' '.join(
                    label for flag, label in (
                        ('R' in permissions, 'Read'),
                        ('I' in permissions, 'Insert'),
                        ('M' in permissions, 'Modify'),
                        ('D' in permissions, 'Delete'),
                    ) if flag
                )
                self.stdout.write(f'    - {page_name}: {perm_str or "-"}')

        self.stdout.write('\n' + '=' * 80)
        self.stdout.write(self.style.SUCCESS('SUMMARY'))
        self.stdout.write('=' * 80)
        self.stdout.write(f'Permission sets created: {created_sets}')
        self.stdout.write(f'Permission sets updated: {updated_sets}')
        self.stdout.write(f'Permission lines created: {created_lines}')
        self.stdout.write(self.style.SUCCESS('\n[OK] Page permissions setup complete!'))
