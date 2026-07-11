"""
Import Business Central Base Application objects into ``base.Objects``.

Populates the Permission Set **application_object** lookup (same role as BC
``AllObjWithCaption`` for pages/tables).

Usage
-----
1. Download symbols into the ROM AL project (once):

   VS Code → Command Palette → **AL: Download Symbols from Global Sources**

   This creates ``.alpackages`` under ``ROM_Budget_Monitoring``.

2. Import into a tenant::

    cd C:\\PROJECTS\\zentroapp-webV2\\backend
    .\\env\\Scripts\\activate
    python manage.py tenant_command populate_bc_base_application_objects ^
        --schema=primewise ^
        --symbols-dir=C:\\DEVELOPMENT\\HRP_DEV\\ROM_AL\\ROM_Budget_Monitoring\\.alpackages

3. Also sync Zentro page-engine pages (optional)::

    python manage.py tenant_command seed_pages --schema=primewise
"""

from __future__ import annotations

from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction

from base.bc_symbol_parser import collect_bc_objects, _unique_object_name
from base.models import ObjectType, Objects

DEFAULT_SYMBOLS_DIR = Path(
    r'C:\DEVELOPMENT\HRP_DEV\ROM_AL\ROM_Budget_Monitoring\.alpackages'
)
DEFAULT_AL_PROJECT = Path(
    r'C:\DEVELOPMENT\HRP_DEV\ROM_AL\ROM_Budget_Monitoring'
)


class Command(BaseCommand):
    help = (
        'Import BC Base Application objects (tables, pages, …) into base.Objects '
        'for Permission Set line lookups'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--symbols-dir',
            type=str,
            default=str(DEFAULT_SYMBOLS_DIR),
            help='Folder containing downloaded .app symbol packages',
        )
        parser.add_argument(
            '--al-project-dir',
            type=str,
            default=str(DEFAULT_AL_PROJECT),
            help='ROM AL project root — parses local table/page definitions as Custom objects',
        )
        parser.add_argument(
            '--skip-symbols',
            action='store_true',
            help='Only import objects declared in the AL project (no .app parsing)',
        )
        parser.add_argument(
            '--skip-al-project',
            action='store_true',
            help='Only import from .app symbol packages',
        )
        parser.add_argument(
            '--include-all-apps',
            action='store_true',
            help='Import every .app in symbols-dir, not only Base Application',
        )
        parser.add_argument(
            '--types',
            type=str,
            default='Table,Page,Report,Codeunit',
            help='Comma-separated object types to import (default: Table,Page,Report,Codeunit)',
        )
        parser.add_argument(
            '--json-file',
            type=str,
            default=str(
                Path(r'C:\DEVELOPMENT\HRP_DEV\ROM_AL\ROM_Budget_Monitoring\docs\base-application-objects.json')
            ),
            help='Import from exported base-application-objects.json',
        )
        parser.add_argument(
            '--json-only',
            action='store_true',
            help='Only import from --json-file (skip .app and AL project)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show counts only; do not write to the database',
        )

    def handle(self, *args, **options):
        json_only = options['json_only']
        json_file = Path(options['json_file']) if options.get('json_file') else None
        symbols_dir = None if options['skip_symbols'] or json_only else Path(options['symbols_dir'])
        al_project_dir = None if options['skip_al_project'] or json_only else Path(options['al_project_dir'])
        allowed_types = {t.strip() for t in options['types'].split(',') if t.strip()}

        if not json_only and symbols_dir and not symbols_dir.is_dir():
            self.stdout.write(
                self.style.WARNING(
                    f'Symbols folder not found: {symbols_dir}\n'
                    'Download BC symbols first:\n'
                    '  1. Open ROM_Budget_Monitoring in VS Code\n'
                    '  2. AL: Download Symbols from Global Sources\n'
                    f'  3. Re-run with --symbols-dir="{symbols_dir}"'
                )
            )

        rows = collect_bc_objects(
            symbols_dir=symbols_dir if symbols_dir and symbols_dir.is_dir() else None,
            al_project_dir=al_project_dir if al_project_dir and al_project_dir.is_dir() else None,
            base_application_only=not options['include_all_apps'],
            json_file=json_file if json_file and json_file.is_file() else None,
        )
        rows = [r for r in rows if r.object_type in allowed_types]

        if not rows:
            self.stdout.write(self.style.ERROR('No objects found to import.'))
            return

        by_type: dict[str, int] = {}
        for row in rows:
            by_type[row.object_type] = by_type.get(row.object_type, 0) + 1

        self.stdout.write(self.style.SUCCESS(f'Found {len(rows)} objects:'))
        for obj_type, count in sorted(by_type.items()):
            self.stdout.write(f'  {obj_type}: {count}')

        if options['dry_run']:
            return

        type_refs = self._ensure_object_types()
        created = updated = skipped = 0

        with transaction.atomic():
            for row in rows:
                type_ref = type_refs.get(row.object_type)
                existing = Objects.objects.filter(
                    object_type=row.object_type,
                    object_id=row.object_id,
                ).first()

                # Never overwrite Zentro custom page-engine rows (subtype Custom + related name)
                if existing and existing.object_subtype == 'Custom' and row.object_subtype == 'Permanent':
                    if existing.app_label not in ('Base Application', 'Unknown', ''):
                        skipped += 1
                        continue

                defaults = row.as_objects_defaults()
                defaults['object_type_ref'] = type_ref

                _, was_created = Objects.objects.update_or_create(
                    object_id=row.object_id,
                    defaults={
                        **defaults,
                        'object_name': _unique_object_name(
                            row.object_type,
                            row.object_id,
                            row.object_name,
                            row.object_caption,
                        ),
                    },
                )
                if was_created:
                    created += 1
                else:
                    updated += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'Done — created {created}, updated {updated}, skipped {skipped}'
            )
        )

    def _ensure_object_types(self) -> dict[str, ObjectType]:
        specs = [
            ('TABLE', 'Table', 'Database tables (BC table permissions)', 1),
            ('PAGE', 'Page', 'UI pages (BC page permissions)', 2),
            ('REPORT', 'Report', 'Reports', 3),
            ('CODEUNIT', 'Codeunit', 'Codeunits', 4),
            ('QUERY', 'Query', 'Queries', 5),
            ('XMLPORT', 'XMLport', 'XMLports', 6),
            ('ENUM', 'Enum', 'Enums', 7),
        ]
        out: dict[str, ObjectType] = {}
        for code, name, desc, sort_order in specs:
            obj_type, _ = ObjectType.objects.get_or_create(
                code=code,
                defaults={'name': name, 'description': desc, 'sort_order': sort_order},
            )
            out[name] = obj_type
        return out
