"""
Parse Business Central ``.app`` symbol packages into ``base.Objects`` rows.

BC ``.app`` files are ZIP archives prefixed with a 40-byte NAVX header. Symbol
metadata lives in ``SymbolReference.json`` (developer packages). Runtime-only
packages (e.g. Microsoft Base Application) may omit that file — download symbols
via VS Code **AL: Download Symbols from Global Sources** first.
"""

from __future__ import annotations

import io
import json
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path

from pages.bc_page_ids import bc_page_object_id

# Microsoft Base Application package id (BC 14+)
BASE_APPLICATION_PACKAGE_IDS = {
    '437dbf0e-84ff-417a-965d-ed2bb9650972',
}

AL_OBJECT_RE = re.compile(
    r'^(table|page|report|codeunit|enum|query|xmlport)\s+(\d+)\s+"([^"]+)"',
    re.IGNORECASE | re.MULTILINE,
)

BC_OBJECT_TYPE_MAP = {
    'table': 'Table',
    'page': 'Page',
    'report': 'Report',
    'codeunit': 'Codeunit',
    'enum': 'Enum',
    'query': 'Query',
    'xmlport': 'XMLport',
}


@dataclass(frozen=True)
class BCObjectRow:
    object_type: str
    object_id: int
    object_name: str
    object_caption: str
    app_label: str
    object_subtype: str = 'Permanent'

    def as_objects_defaults(self) -> dict:
        return {
            'object_type': self.object_type,
            'object_caption': self.object_caption,
            'app_label': self.app_label,
            'object_subtype': self.object_subtype,
            'is_active': True,
            'requires_permission': self.object_type in ('Page', 'Table'),
            'related_model': '',
        }


def _sanitize_object_name(name: str) -> str:
    """BC permission object names: alphanumeric, no spaces."""
    return re.sub(r'[^A-Za-z0-9_]', '', name.replace(' ', ''))


def _unique_object_name(
    object_type: str,
    object_id: int,
    object_name: str,
    object_caption: str,
) -> str:
    """Ensure object_name is unique (base.Objects.object_name is globally unique)."""
    from base.models import Objects

    base = object_name or _sanitize_object_name(object_caption)
    if not Objects.objects.filter(object_name=base).exclude(object_id=object_id).exists():
        return base
    alt = f'{object_type}·{object_caption}'[:255]
    if not Objects.objects.filter(object_name=alt).exclude(object_id=object_id).exists():
        return alt
    return f'{object_type}·{object_id}'[:255]


def zentro_page_object_id(bc_page_id: int) -> int:
    return bc_page_object_id(bc_page_id)


def resolve_object_id(object_type: str, bc_id: int) -> int:
    """BC object IDs are stored as-is (scoped by object_type, like BC)."""
    return bc_id


def _caption_from_properties(properties: list | None) -> str:
    if not properties:
        return ''
    for prop in properties:
        if not isinstance(prop, dict):
            continue
        if prop.get('Name') != 'Caption':
            continue
        value = prop.get('Value')
        if isinstance(value, dict):
            return str(value.get('String') or value.get('value') or '')
        if value is not None:
            return str(value)
    return ''


def _iter_symbol_collections(symbol_data: dict) -> list[tuple[str, list]]:
    """Return (BC type key, items) pairs from SymbolReference.json layouts."""
    type_keys = (
        'Tables', 'Pages', 'Reports', 'Codeunits', 'Enums', 'Queries', 'Xmlports',
        'tables', 'pages', 'reports', 'codeunits', 'enums', 'queries', 'xmlports',
    )
    out: list[tuple[str, list]] = []
    for key in type_keys:
        items = symbol_data.get(key)
        if isinstance(items, list) and items:
            out.append((key.rstrip('s').capitalize() + 's', items))
    # Flat namespace layout: {"Objects": [{"Type": "Table", ...}]}
    objects = symbol_data.get('Objects') or symbol_data.get('objects')
    if isinstance(objects, list):
        grouped: dict[str, list] = {}
        for item in objects:
            if not isinstance(item, dict):
                continue
            raw_type = item.get('Type') or item.get('type') or ''
            key = raw_type.lower()
            grouped.setdefault(key, []).append(item)
        for key, items in grouped.items():
            out.append((key, items))
    return out


def _normalize_type_key(key: str) -> str | None:
    mapping = {
        'tables': 'Table',
        'table': 'Table',
        'pages': 'Page',
        'page': 'Page',
        'reports': 'Report',
        'report': 'Report',
        'codeunits': 'Codeunit',
        'codeunit': 'Codeunit',
        'enums': 'Enum',
        'enum': 'Enum',
        'queries': 'Query',
        'query': 'Query',
        'xmlports': 'XMLport',
        'xmlport': 'XMLport',
    }
    return mapping.get(key.lower().rstrip('s') if key.lower().endswith('s') else key.lower()) or mapping.get(key.lower())


def _rows_from_symbol_item(
    collection_key: str,
    item: dict,
    *,
    app_label: str,
) -> BCObjectRow | None:
    object_type = _normalize_type_key(collection_key) or _normalize_type_key(
        str(item.get('Type') or item.get('type') or '')
    )
    if not object_type:
        return None

    bc_id = item.get('Id') or item.get('id') or item.get('ObjectId') or item.get('objectId')
    name = item.get('Name') or item.get('name') or ''
    if bc_id is None or not name:
        return None

    try:
        bc_id_int = int(bc_id)
    except (TypeError, ValueError):
        return None

    caption = (
        _caption_from_properties(item.get('Properties') or item.get('properties'))
        or str(item.get('Caption') or item.get('caption') or name)
    )
    object_id = resolve_object_id(object_type, bc_id_int)
    return BCObjectRow(
        object_type=object_type,
        object_id=object_id,
        object_name=_sanitize_object_name(str(name)),
        object_caption=str(caption)[:255],
        app_label=app_label,
    )


def parse_symbol_reference_json(
    symbol_data: dict,
    *,
    app_label: str = 'Base Application',
    package_name: str | None = None,
) -> list[BCObjectRow]:
    label = app_label
    if package_name and package_name != 'Base Application':
        label = package_name

    rows: list[BCObjectRow] = []
    seen: set[tuple[str, int]] = set()

    for collection_key, items in _iter_symbol_collections(symbol_data):
        for item in items:
            if not isinstance(item, dict):
                continue
            row = _rows_from_symbol_item(collection_key, item, app_label=label)
            if row is None:
                continue
            key = (row.object_type, row.object_id)
            if key in seen:
                continue
            seen.add(key)
            rows.append(row)

    return rows


def _read_zip_payload(app_path: Path) -> bytes:
    raw = app_path.read_bytes()
    if raw[:4] == b'NAVX':
        # 40-byte NAVX header, then ZIP (PK..)
        zip_start = raw.find(b'PK', 40)
        if zip_start == -1:
            raise ValueError(f'No ZIP payload found in {app_path}')
        return raw[zip_start:]
    return raw


def _manifest_package_name(zip_file: zipfile.ZipFile) -> str:
    for name in ('NavxManifest.xml', 'manifest.json', 'AppManifest.json'):
        try:
            text = zip_file.read(name).decode('utf-8', errors='ignore')
        except KeyError:
            continue
        if 'Base Application' in text:
            return 'Base Application'
        m = re.search(r'<Name>([^<]+)</Name>', text)
        if m:
            return m.group(1).strip()
        m = re.search(r'"name"\s*:\s*"([^"]+)"', text)
        if m:
            return m.group(1).strip()
    return 'Unknown'


def _is_base_application_package(app_path: Path, zip_file: zipfile.ZipFile) -> bool:
    name_lower = app_path.name.lower()
    if 'base application' in name_lower or 'baseapplication' in name_lower:
        return True
    try:
        manifest = zip_file.read('NavxManifest.xml').decode('utf-8', errors='ignore')
    except KeyError:
        return False
    return any(pid in manifest for pid in BASE_APPLICATION_PACKAGE_IDS)


def parse_app_file(
    app_path: Path,
    *,
    base_application_only: bool = True,
) -> list[BCObjectRow]:
    """Extract object rows from one ``.app`` symbol package."""
    app_path = Path(app_path)
    payload = _read_zip_payload(app_path)
    with zipfile.ZipFile(io.BytesIO(payload)) as zf:
        if base_application_only and not _is_base_application_package(app_path, zf):
            return []
        try:
            symbol_bytes = zf.read('SymbolReference.json')
        except KeyError as exc:
            raise ValueError(
                f'{app_path.name} has no SymbolReference.json. '
                'Download developer symbols (AL: Download Symbols from Global Sources) '
                'instead of runtime .app from DVD.'
            ) from exc
        symbol_data = json.loads(symbol_bytes.decode('utf-8'))
        package_name = _manifest_package_name(zf)
        app_label = 'Base Application' if _is_base_application_package(app_path, zf) else package_name
        return parse_symbol_reference_json(symbol_data, app_label=app_label, package_name=package_name)


def discover_app_files(symbols_dir: Path) -> list[Path]:
    symbols_dir = Path(symbols_dir)
    if not symbols_dir.is_dir():
        return []
    return sorted(symbols_dir.glob('*.app'))


def parse_al_project_objects(
    project_root: Path,
    *,
    app_label: str = 'Budget Monitoring',
) -> list[BCObjectRow]:
    """Parse ``table`` / ``page`` / … declarations from local ``.al`` sources."""
    project_root = Path(project_root)
    rows: list[BCObjectRow] = []
    seen: set[tuple[str, int]] = set()

    for al_file in project_root.rglob('*.al'):
        if '.alpackages' in al_file.parts:
            continue
        try:
            text = al_file.read_text(encoding='utf-8', errors='ignore')
        except OSError:
            continue
        for match in AL_OBJECT_RE.finditer(text):
            raw_type, raw_id, caption = match.groups()
            object_type = BC_OBJECT_TYPE_MAP[raw_type.lower()]
            bc_id = int(raw_id)
            object_id = resolve_object_id(object_type, bc_id)
            key = (object_type, object_id)
            if key in seen:
                continue
            seen.add(key)
            rows.append(
                BCObjectRow(
                    object_type=object_type,
                    object_id=object_id,
                    object_name=_sanitize_object_name(caption),
                    object_caption=caption[:255],
                    app_label=app_label,
                    object_subtype='Custom',
                )
            )
    return rows


def collect_bc_objects(
    *,
    symbols_dir: Path | None = None,
    al_project_dir: Path | None = None,
    base_application_only: bool = True,
    json_file: Path | None = None,
) -> list[BCObjectRow]:
    rows: list[BCObjectRow] = []
    seen: set[tuple[str, int]] = set()

    def _add(batch: list[BCObjectRow]) -> None:
        for row in batch:
            key = (row.object_type, row.object_id)
            if key in seen:
                continue
            seen.add(key)
            rows.append(row)

    if json_file:
        _add(parse_bc_objects_json_file(json_file))

    if symbols_dir:
        for app_file in discover_app_files(symbols_dir):
            try:
                _add(parse_app_file(app_file, base_application_only=base_application_only))
            except ValueError:
                continue

    if al_project_dir:
        _add(parse_al_project_objects(al_project_dir))

    return rows


def parse_bc_objects_json_file(json_path: Path) -> list[BCObjectRow]:
    """
    Load BC objects from ``base-application-objects.json`` export.

    JSON shape: ``{"objects": [{"object_type", "object_id", "object_name", "object_caption", "application"}, ...]}``
    """
    json_path = Path(json_path)
    data = json.loads(json_path.read_text(encoding='utf-8'))
    items = data.get('objects') or []
    rows: list[BCObjectRow] = []
    seen: set[tuple[str, int]] = set()

    for item in items:
        if not isinstance(item, dict):
            continue
        object_type = str(item.get('object_type') or '').strip()
        if object_type not in ('Table', 'Page', 'Report', 'Codeunit', 'Query', 'XMLport', 'Enum'):
            continue
        try:
            bc_id = int(item['object_id'])
        except (KeyError, TypeError, ValueError):
            continue
        name = str(item.get('object_name') or '').strip()
        if not name:
            continue
        caption = str(item.get('object_caption') or name)[:255]
        app_label = str(item.get('application') or 'Base Application')
        key = (object_type, bc_id)
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            BCObjectRow(
                object_type=object_type,
                object_id=bc_id,
                object_name=_sanitize_object_name(name),
                object_caption=caption,
                app_label=app_label,
                object_subtype='Permanent',
            )
        )
    return rows
