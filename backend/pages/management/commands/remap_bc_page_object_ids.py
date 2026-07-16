"""
LEGACY — prefer ``align_zentro_page_ids`` (PageId == ObjectId, Zentro 10xxx).

Older tenants used offset object IDs. Current scheme is ``ZENTRO_PAGE_REGISTRY``.

Usage (legacy only)::

    python manage.py tenant_command remap_bc_page_object_ids --schema=primewise
"""

from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction

from pages.bc_page_ids import (
    BC_PAGE_REGISTRY,
    ZENTRO_CUSTOM_PAGE_REGISTRY,
    resolve_page_object_id,
)
from pages.models import Page
from pages.permission_sync import apply_object_id_from_registry, sync_all_page_permission_objects


LEGACY_BC_OFFSET = 1000
LEGACY_CUSTOM_BASE = 15_000
NEW_CUSTOM_BASE = 50_000


class Command(BaseCommand):
    help = 'LEGACY: remap old offset object_ids (prefer align_zentro_page_ids)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--sync',
            action='store_true',
            default=True,
            help='Run sync_page_permission_objects after remap (default: on)',
        )
        parser.add_argument(
            '--delete-legacy-objects',
            action='store_true',
            default=False,
            help='Delete old base.Objects rows after remap (only safe when no other tenant references them)',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        from base.models import Objects
        from permissions.models import PermissionSetLine

        delete_legacy = options['delete_legacy_objects']
        pages_updated = 0
        objects_remapped = 0
        lines_repointed = 0
        stale_deleted = 0

        # 1) Update page_engine Page.object_id from registry
        for page in Page.objects.all():
            before = page.object_id
            apply_object_id_from_registry(page)
            if page.object_id != before:
                pages_updated += 1

        # 2) BC pages: 1000+bc -> bc
        for _name, (bc_id, _module) in BC_PAGE_REGISTRY.items():
            old_id = LEGACY_BC_OFFSET + bc_id
            new_id = bc_id
            objects_remapped, lines_repointed, stale_deleted = self._migrate_object_id(
                Objects,
                PermissionSetLine,
                old_id=old_id,
                new_id=new_id,
                object_type='Page',
                delete_legacy=delete_legacy,
                objects_remapped=objects_remapped,
                lines_repointed=lines_repointed,
                stale_deleted=stale_deleted,
            )

        # 3) Custom pages: 15xxx -> 50xxx
        for _name, (new_id, _module) in ZENTRO_CUSTOM_PAGE_REGISTRY.items():
            old_id = new_id - (NEW_CUSTOM_BASE - LEGACY_CUSTOM_BASE)
            if old_id < LEGACY_CUSTOM_BASE:
                continue
            objects_remapped, lines_repointed, stale_deleted = self._migrate_object_id(
                Objects,
                PermissionSetLine,
                old_id=old_id,
                new_id=new_id,
                object_type='Page',
                delete_legacy=delete_legacy,
                objects_remapped=objects_remapped,
                lines_repointed=lines_repointed,
                stale_deleted=stale_deleted,
            )

        # 4) Legacy Zentro module-band page IDs (10xxx) — retire if replaced
        for page in Page.objects.exclude(object_id__isnull=True):
            legacy = Objects.objects.filter(
                object_type='Page',
                object_id__gte=10_000,
                object_id__lt=15_000,
                object_name=page.name,
            ).exclude(object_id=page.object_id)
            for stale in legacy:
                target = Objects.objects.filter(
                    object_type='Page',
                    object_id=page.object_id,
                ).first()
                if target:
                    n = PermissionSetLine.objects.filter(application_object=stale).update(
                        application_object=target,
                    )
                    lines_repointed += n
                if delete_legacy and not PermissionSetLine.objects.filter(
                    application_object=stale,
                ).exists():
                    stale.delete()
                    stale_deleted += 1

        if options['sync']:
            stats = sync_all_page_permission_objects()
            self.stdout.write(f'Sync: {stats}')

        self.stdout.write(
            self.style.SUCCESS(
                f'Done — pages_updated={pages_updated}, objects_remapped={objects_remapped}, '
                f'lines_repointed={lines_repointed}, stale_deleted={stale_deleted}'
            )
        )

    def _migrate_object_id(
        self,
        Objects,
        PermissionSetLine,
        *,
        old_id,
        new_id,
        object_type,
        delete_legacy,
        objects_remapped,
        lines_repointed,
        stale_deleted,
    ):
        if old_id == new_id:
            return objects_remapped, lines_repointed, stale_deleted

        old_obj = Objects.objects.filter(object_type=object_type, object_id=old_id).first()
        new_obj = Objects.objects.filter(object_type=object_type, object_id=new_id).first()

        if not old_obj:
            return objects_remapped, lines_repointed, stale_deleted

        if new_obj and new_obj.pk != old_obj.pk:
            n = PermissionSetLine.objects.filter(application_object=old_obj).update(
                application_object=new_obj,
            )
            lines_repointed += n
            if delete_legacy and not PermissionSetLine.objects.filter(
                application_object=old_obj,
            ).exists():
                old_obj.delete()
                stale_deleted += 1
        elif not new_obj:
            field_names = [
                f.name
                for f in Objects._meta.fields
                if f.name not in ('object_id', 'created_at', 'updated_at', 'system_id')
            ]
            clone_data = {name: getattr(old_obj, name) for name in field_names}
            # object_name is globally unique — free the name before creating the new PK row.
            old_obj.object_name = f'__migrating__{old_obj.pk}__{old_obj.object_name}'[:255]
            old_obj.save(update_fields=['object_name'])
            new_obj, _ = Objects.objects.update_or_create(
                object_id=new_id,
                defaults=clone_data,
            )
            n = PermissionSetLine.objects.filter(application_object=old_obj).update(
                application_object=new_obj,
            )
            lines_repointed += n
            if delete_legacy and old_obj.pk != new_obj.pk and not PermissionSetLine.objects.filter(
                application_object=old_obj,
            ).exists():
                old_obj.delete()
                stale_deleted += 1
            objects_remapped += 1
        else:
            objects_remapped += 1

        return objects_remapped, lines_repointed, stale_deleted
