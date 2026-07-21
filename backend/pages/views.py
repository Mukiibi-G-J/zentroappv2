from django.apps import apps
from django.core.exceptions import FieldDoesNotExist, ValidationError
from django.db import models as django_models, transaction
from django.db.utils import DataError, IntegrityError, ProgrammingError
from decimal import Decimal
from datetime import date, datetime
import re
import uuid
import urllib.parse

from django.db.models import Sum, Avg, Max, Min, Value, OuterRef, Subquery, Q
from django.db.models.functions import TruncMonth, Coalesce
from django.utils import timezone
from django_tenants.utils import schema_context
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from authentication.authentication import JWTAuthenticationWithRevocationChecks as JWTAuthentication

from authentication.session_context import serialize_rc_nav_items
from permissions.table_permissions import (
    check_source_table_permission,
    permission_denied_message,
)
from .models import Page, PageControl, PageControlField, PageAction
from .relation_resolver import context_value_for_field, resolve_table_relation
from .serializers import PageSerializer
from .user_page_service import (
    create_user_for_page,
    get_user_by_page_id,
    serialize_user_field,
    soft_delete_user,
    update_user_for_page,
    user_effective_permission_sets,
    users_queryset,
)

_DUPLICATE_KEY_RE = re.compile(
    r'Key \((?P<field>[^)]+)\)=\((?P<value>[^)]+)\) already exists',
    re.IGNORECASE,
)

_SOURCE_TABLE_LABELS = {
    'UnitOfMeasure': 'Unit of measure',
    'ItemCategory': 'Item category',
    'Item': 'Item',
    'Customer': 'Customer',
    'Vendor': 'Vendor',
    'Resource': 'Resource',
}


def _enforce_source_table_permission(request, source_table: str, permission_type: str):
    """Return a 403 Response when table-data permission is denied, else None."""
    allowed, reason = check_source_table_permission(
        request.user, source_table or '', permission_type,
    )
    if allowed:
        return None
    return Response(
        {
            'error': permission_denied_message(
                source_table or '', permission_type, reason,
            ),
        },
        status=status.HTTP_403_FORBIDDEN,
    )


def _friendly_db_error_message(exc, source_table=None):
    """Turn raw database errors into user-facing page data messages."""
    err = str(exc)
    if isinstance(exc, IntegrityError) and (
        'not-null constraint' in err.lower() or 'violates not-null' in err.lower()
    ):
        if 'column "code"' in err.lower() or "column 'code'" in err.lower():
            label = _SOURCE_TABLE_LABELS.get(source_table or '', 'Record')
            return f'{label} requires a Code before it can be saved.'
        col_match = re.search(
            r'column "(?P<col>[^"]+)"|column \'(?P<col2>[^\']+)\'',
            err,
            re.IGNORECASE,
        )
        col = (col_match.group('col') or col_match.group('col2') or '').strip() if col_match else ''
        col_labels = {
            'vendor_id': 'Vendor',
            'vendor': 'Vendor',
            'customer_id': 'Customer',
            'customer': 'Customer',
            'global_dimension_1_id': 'Branch',
            'dimension_set_id': 'Dimension Set',
            'payment_method_id': 'Payment Method',
            'invoice_no': 'No.',
        }
        if col in col_labels:
            return f'{col_labels[col]} is required before creating the record.'
        if col:
            return f'{col.replace("_", " ").strip()} is required before creating the record.'
        return 'A required field is missing.'
    if isinstance(exc, IntegrityError) and 'unique constraint' in err.lower():
        match = _DUPLICATE_KEY_RE.search(err)
        if match:
            field = match.group('field')
            value = match.group('value')
            if source_table == 'UnitOfMeasure' or 'unitofmeasure' in err.lower():
                return f'Unit of measure "{value}" already exists. Enter a different code.'
            label = _SOURCE_TABLE_LABELS.get(source_table or '', 'Record')
            if field == 'code':
                return f'{label} with code "{value}" already exists.'
            return f'A record with {field} "{value}" already exists.'
        if 'system_id' in err.lower():
            return 'A record with this system ID already exists.'
        return 'This record already exists.'
    return err


def _merge_create_defaults_from_current_values(defaults: dict, model, record_values: dict) -> dict:
    """Carry values typed before the first save (e.g. Description before Code)."""
    if not record_values:
        return defaults
    skip = {'SystemId', 'system_id', 'id', 'indentation', 'SystemCreatedAt', 'SystemModifiedAt'}
    for key, raw in record_values.items():
        if key in defaults or key in skip:
            continue
        if not _model_has_direct_field(model, key):
            continue
        if raw is None or raw == '':
            continue
        defaults[key] = raw
    return defaults


def _validate_page_primary_keys_for_create(page: Page, defaults: dict) -> str | None:
    """
    Require user-entered primary keys on Card create only (e.g. Item Category Code).

    Documents / worksheets assign No. via number series in model.save() — never block those.
    Also skip read-only / No. Series PK fields on cards.
    """
    page_type = (getattr(page, 'page_type', None) or '').strip()
    if page_type and page_type != 'Card':
        return None
    pk_fields = PageControlField.objects.filter(page=page, primary_key=True)
    for pcf in pk_fields:
        if not pcf.editable or (pcf.no_series_code or '').strip():
            continue
        val = defaults.get(pcf.name)
        if val is None or (isinstance(val, str) and not val.strip()):
            caption = (pcf.caption or pcf.name or 'Code').strip()
            return f'Enter {caption} before creating the record.'
    return None


def _page_data_error_response(exc, source_table=None):
    if isinstance(exc, IntegrityError):
        return Response(
            {'error': _friendly_db_error_message(exc, source_table)},
            status=status.HTTP_409_CONFLICT,
        )
    if isinstance(exc, (ValueError, ValidationError)):
        if isinstance(exc, ValidationError):
            if getattr(exc, 'error_dict', None):
                for errors in exc.error_dict.values():
                    if errors:
                        message = str(errors[0])
                        break
                else:
                    message = exc.messages[0] if exc.messages else str(exc)
            elif exc.messages:
                message = exc.messages[0]
            else:
                message = str(exc)
        else:
            message = str(exc)
        return Response({'error': message}, status=status.HTTP_400_BAD_REQUEST)
    return Response(
        {'error': _friendly_db_error_message(exc, source_table)},
        status=status.HTTP_400_BAD_REQUEST,
    )


def _serialize_relation_row(model, obj, related_field, display_field):
    value = getattr(obj, related_field, None)
    if value is None:
        return None
    if model.__name__ == 'ItemUnitOfMeasure':
        uom = getattr(obj, 'unit_of_measure', None)
        code = getattr(uom, 'code', '') if uom else ''
        name = getattr(uom, 'description', '') if uom else ''
        qty = obj.quantity_per_unit
        if qty is None or qty == '':
            qty = 1
        qty_str = str(qty)
        # Name column: prefer description; otherwise show how many base units this UOM contains
        display_name = (name or '').strip() or f'{qty_str} per {code}'.strip()
        return {
            'Value': str(value),
            'Caption': f'{code} — {display_name}'.strip(' —') if display_name else code,
            'Code': code,
            'Name': display_name,
            'QuantityPerUnit': qty_str,
        }
    if model.__name__ == 'Objects':
        object_name = getattr(obj, 'object_name', '') or ''
        object_caption = getattr(obj, 'object_caption', '') or ''
        display_name = object_name or object_caption
        return {
            'Value': str(value),
            'Caption': display_name,
            'Code': str(value),
            'Name': display_name,
        }
    if model.__name__ == 'ItemCategory':
        level = int(getattr(obj, 'level', 0) or 0)
        code = str(value)
        caption = getattr(obj, display_field, None) if display_field else None
        display_name = str(caption) if caption is not None else code
        return {
            'Value': code,
            'Caption': display_name,
            'Code': code,
            'Name': display_name,
            'Indentation': level,
        }
    caption = getattr(obj, display_field, None) if display_field else None
    return {
        'Value': str(value),
        'Caption': str(caption) if caption is not None else None,
    }


def _scoped_relation_lookup_qs(model, record_values):
    select_related = ['unit_of_measure'] if model.__name__ == 'ItemUnitOfMeasure' else []
    qs = model.objects.select_related(*select_related)
    if model.__name__ == 'ItemUnitOfMeasure':
        item_no = record_values.get('no') or record_values.get('item')
        if item_no:
            qs = qs.filter(item__no=item_no)
    return qs


def _lookup_relation_object(model, related_field, display_field, current_val, record_values):
    """Resolve a relation row when the stored value may be a PK or a display key."""
    qs = _scoped_relation_lookup_qs(model, record_values)
    if related_field in ('id', 'pk') and str(current_val).isdigit():
        obj = qs.filter(pk=current_val).first()
        if obj is not None:
            return obj
    if related_field in ('id', 'pk') and display_field:
        obj = qs.filter(**{display_field: current_val}).first()
        if obj is not None:
            return obj
    lookup_field = related_field if related_field in {f.name for f in model._meta.get_fields()} else 'pk'
    return qs.filter(**{lookup_field: current_val}).first()


def _relation_row_matches_current(row, current_str, related_field, display_field):
    """True when current_str is already represented in relation results."""
    if row.get('Value') == current_str:
        return True
    if row.get('Code') == current_str:
        return True
    if row.get('Caption') == current_str:
        return True
    if display_field and related_field in ('id', 'pk'):
        caption = row.get('Caption') or ''
        if caption.startswith(f'{current_str} —') or caption == current_str:
            return True
    return False


def _append_current_relation_value(results, model, field, related_field, display_field, record_values):
    current_val = record_values.get(field.name)
    if current_val is None or current_val == '':
        return results
    current_str = str(current_val)
    if any(
        _relation_row_matches_current(r, current_str, related_field, display_field)
        for r in results
    ):
        return results
    obj = _lookup_relation_object(model, related_field, display_field, current_val, record_values)
    if obj is None:
        return results
    row = _serialize_relation_row(model, obj, related_field, display_field)
    if not row:
        return results
    if any(r.get('Value') == row.get('Value') for r in results):
        return results
    return [row, *results]


class TableRelationsView(APIView):
    """POST /api/pages/relations/ — lookup values for table-relation fields."""

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        page_id = request.data.get('PageId')
        control_id = request.data.get('PageControlId')
        field_id = request.data.get('PageControlFieldId')

        if not all([page_id, control_id, field_id]):
            return Response(
                {'error': 'PageId, PageControlId and PageControlFieldId are required'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        schema = _get_schema(request)
        if not schema:
            return Response({'error': 'No tenant in token'}, status=status.HTTP_400_BAD_REQUEST)

        record_values = request.data.get('CurrentRecordValues') or {}

        with schema_context(schema):
            try:
                field = PageControlField.objects.select_related('page', 'page_control').get(
                    pk=field_id,
                    page_id=page_id,
                    page_control_id=control_id,
                )
            except PageControlField.DoesNotExist:
                return Response({'error': 'Field not found'}, status=status.HTTP_404_NOT_FOUND)

            related_table, related_field, display_field = resolve_table_relation(
                field, record_values,
            )
            if not related_table or not related_field:
                return Response([])

            source_table = field.page_control.source_table or field.page.source_table

            model = _get_model(related_table)
            if model is None:
                return Response(
                    {'error': f'Model not found for table: {related_table}'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            order_field = related_field
            if order_field not in {f.name for f in model._meta.get_fields()}:
                order_field = 'pk'

            qs = model.objects.all()
            if field.relation_context_field:
                ctx_val = context_value_for_field(field, record_values)
                if not ctx_val:
                    return Response([])
            if model.__name__ == 'Objects':
                qs = model.objects.filter(
                    object_type__in=['Page', 'Table'],
                    requires_permission=True,
                    is_active=True,
                )
                if field.relation_context_field == 'object_type':
                    ctx_val = context_value_for_field(field, record_values)
                    if ctx_val:
                        qs = qs.filter(object_type=ctx_val)
            if model.__name__ == 'ItemUnitOfMeasure':
                item_no = record_values.get('no') or record_values.get('item')
                if item_no:
                    qs = qs.filter(item__no=item_no)
                else:
                    return Response([])

            if model.__name__ == 'ApplicationProfile':
                from utils.page_access import filter_application_profiles_for_user
                from utils.page_modules import filter_application_profiles_by_enabled_modules

                qs = filter_application_profiles_by_enabled_modules(
                    qs, _get_request_enabled_modules(request, schema),
                )

                target_user = request.user
                if source_table == 'UserPersonalization':
                    # user_id is serialized as username (Code), not numeric PK.
                    target_user_ref = record_values.get('user_id')
                    if target_user_ref:
                        from authentication.models import CustomUser

                        ref = str(target_user_ref).strip()
                        resolved = CustomUser.objects.filter(username=ref).first()
                        if resolved is None and ref.isdigit():
                            resolved = CustomUser.objects.filter(pk=int(ref)).first()
                        if resolved is None:
                            resolved = CustomUser.objects.filter(system_id=ref).first()
                        target_user = resolved or request.user

                current_profile_id = None
                role_code = record_values.get('role')
                if role_code:
                    from authentication.models import ApplicationProfile

                    current = ApplicationProfile.objects.filter(code=role_code).first()
                    if current:
                        current_profile_id = current.pk
                elif source_table == 'UserPersonalization' and target_user:
                    from authentication.models import UserPersonalization

                    pers = UserPersonalization.objects.filter(user=target_user).first()
                    if pers and pers.role_id:
                        current_profile_id = pers.role_id

                qs = filter_application_profiles_for_user(
                    qs,
                    target_user,
                    current_profile_id=current_profile_id,
                )

            qs = _filter_payment_method_relation_qs(
                qs,
                source_table=source_table,
                field_name=field.name,
                record_values=record_values,
            )
            qs = _filter_sales_item_relation_qs(
                qs,
                source_table=source_table,
                model=model,
                request=request,
            )

            results = []
            select_related = ['unit_of_measure'] if model.__name__ == 'ItemUnitOfMeasure' else []
            if model.__name__ == 'ItemCategory':
                relation_qs = qs.select_related(*select_related).order_by('tree_id', 'lft')
            else:
                relation_qs = qs.select_related(*select_related).order_by(order_field)
            for obj in relation_qs:
                row = _serialize_relation_row(model, obj, related_field, display_field)
                if row:
                    results.append(row)

            results = _append_current_relation_value(
                results, model, field, related_field, display_field, record_values,
            )
            if (
                model.__name__ == 'PaymentMethod'
                and source_table == 'PurchaseInvoice'
                and field.name == 'payment_method'
                and _is_general_vendor(vendor_no=record_values.get('vendor'))
            ):
                results = [row for row in results if row.get('Value') != 'NOT_PAID']

        return Response(results)


# ── Page config endpoints ──────────────────────────────────────────────────────
MODEL_REGISTRY: dict[str, tuple[str, str]] = {
    'Item': ('items', 'Item'),
    'Customer': ('sales', 'Customer'),
    'Vendor': ('purchases', 'Vendor'),
    'CustomerLedgerEntry': ('sales', 'CustomerLedgerEntry'),
    'VendorLedger': ('purchases', 'VendorLedger'),
    'DetailedVendorLedgerEntry': ('purchases', 'DetailedVendorLedgerEntry'),
    'DetailedCustomerLedgerEntry': ('sales', 'DetailedCustomerLedgerEntry'),
    'ItemLedgerEntries': ('items', 'ItemLedgerEntries'),
    'BankAccount': ('bank_account', 'BankAccount'),
    'BankAccountLedgerEntry': ('bank_account', 'BankAccountLedgerEntry'),
    'BankAccountPostingGroup': ('bank_account', 'BankAccountPostingGroup'),
    'UserSetup': ('authentication', 'UserSetup'),
    'UserPersonalization': ('authentication', 'UserPersonalization'),
    'ApplicationProfile': ('authentication', 'ApplicationProfile'),
    'CustomUser': ('authentication', 'CustomUser'),
    'SalesOrder': ('sales', 'SalesOrder'),
    'SalesOrderLine': ('sales', 'SalesOrderLine'),
    'SalesInvoice': ('sales', 'SalesInvoice'),
    'SalesInvoiceLine': ('sales', 'SalesInvoiceLine'),
    'PostedSalesInvoice': ('sales', 'PostedSalesInvoice'),
    'PostedSalesInvoiceLine': ('sales', 'PostedSalesInvoiceLine'),
    'SalesCreditMemo': ('sales', 'SalesCreditMemo'),
    'SalesCreditMemoLine': ('sales', 'SalesCreditMemoLine'),
    'PurchaseInvoice': ('purchases', 'PurchaseInvoice'),
    'PurchaseInvoiceLine': ('purchases', 'PurchaseInvoiceLine'),
    'PostedPurchaseInvoice': ('purchases', 'PostedPurchaseInvoice'),
    'PostedPurchaseInvoiceLine': ('purchases', 'PostedPurchaseInvoiceLine'),
    'PurchaseCreditMemo': ('purchases', 'PurchaseCreditMemo'),
    'PurchaseCreditMemoLine': ('purchases', 'PurchaseCreditMemoLine'),
    'Expense': ('expenses', 'Expense'),
    'ExpenseType': ('expenses', 'ExpenseType'),
    'PaymentJournal': ('payments', 'PaymentJournal'),
    'PaymentLine': ('payments', 'PaymentLine'),
    'CashReceiptJournalBatch': ('payments', 'CashReceiptJournalBatch'),
    'CashReceiptJournalLine': ('payments', 'CashReceiptJournalLine'),
    'GeneralJournalBatch': ('financials', 'GeneralJournalBatch'),
    'GeneralJournalLine': ('financials', 'GeneralJournalLine'),
    'PaymentMethod': ('financials', 'PaymentMethod'),
    'G_LAccount': ('financials', 'G_LAccount'),
    'GeneralLedgerEntry': ('financials', 'GeneralLedgerEntry'),
    # Setup models
    'NoSeries': ('setup', 'NoSeries'),
    'NoSeriesLines': ('setup', 'NoSeriesLines'),
    'InventorySetup': ('setup', 'InventorySetup'),
    'ManufacturingSetup': ('setup', 'ManufacturingSetup'),
    'CompanyInformation': ('setup', 'CompanyInformation'),
    'CompanySubscription': ('setup', 'CompanySubscription'),
    'CompanyBillingHistory': ('setup', 'CompanyBillingHistory'),
    'CompanyPaymentMethod': ('setup', 'CompanyPaymentMethod'),
    'GeneralLedgerSetup': ('financials', 'GeneralLedgerSetup'),
    'FinancialReport': ('financials', 'FinancialReport'),
    'FinancialReportRowGroup': ('financials', 'FinancialReportRowGroup'),
    'FinancialReportColumnGroup': ('financials', 'FinancialReportColumnGroup'),
    'FinancialReportRowLine': ('financials', 'FinancialReportRowLine'),
    'FinancialReportColumnLine': ('financials', 'FinancialReportColumnLine'),
    'GeneralPostingSetup': ('postings', 'GeneralPostingSetup'),
    'GeneralBusinessPostingGroup': ('postings', 'GeneralBusinessPostingGroup'),
    'GeneralProductPostingGroup': ('postings', 'GeneralProductPostingGroup'),
    'Dimension': ('dimension', 'Dimension'),
    'DimensionValue': ('dimension', 'DimensionValue'),
    'ItemJournal': ('items', 'ItemJournal'),
    'Location': ('items', 'Location'),
    'UnitOfMeasure': ('items', 'UnitOfMeasure'),
    'ItemUnitOfMeasure': ('items', 'ItemUnitOfMeasure'),
    'ItemCategory': ('items', 'ItemCategory'),
    'ItemTrackingCodes': ('items', 'ItemTrackingCodes'),
    'TrackingSpecification': ('items', 'TrackingSpecification'),
    # Restaurant module
    'Floor': ('restaurant_management', 'Floor'),
    'Table': ('restaurant_management', 'Table'),
    'Reservation': ('restaurant_management', 'Reservation'),
    'MenuCategory': ('restaurant_management', 'MenuCategory'),
    'MenuItem': ('restaurant_management', 'MenuItem'),
    'Menu': ('restaurant_management', 'Menu'),
    'RestaurantOrder': ('restaurant_management', 'RestaurantOrder'),
    'RestaurantOrderItem': ('restaurant_management', 'RestaurantOrderItem'),
    # Security / user management
    'PermissionSet': ('permissions', 'PermissionSet'),
    'PermissionSetLine': ('permissions', 'PermissionSetLine'),
    'UserPermissionSets': ('permissions', 'PermissionSet'),
    'UserGroup': ('authentication', 'UserGroup'),
    'Objects': ('base', 'Objects'),
    'Role': ('authentication', 'Role'),
}

SETUP_SOURCE_TABLES = frozenset({
    'GeneralLedgerSetup',
    'InventorySetup',
    'ManufacturingSetup',
    'CompanyInformation',
    'CompanySubscription',
})

USER_PERSONALIZATION_SOURCE_TABLE = 'UserPersonalization'

_LIST_QUERY_PARAMS = frozenset({
    'PageId', 'ControlId', 'search', 'limit', 'offset', 'parent_system_id',
    'sort', 'order',
    # BC-style card record navigator
    'neighbors', 'SystemId',
})

# Query params passed to list API but not ORM fields on every model.
_LIST_VIRTUAL_FILTER_KEYS = frozenset({
    'ledger_user_id',
    'applied_to_entry_id',
    'vendor_ledger_entry_id',
    'customer_ledger_entry_id',
})

# Date scope params mapped to posting_date range lookups (not plain model fields).
_LIST_DATE_SCOPE_KEYS = frozenset({'posting_date', 'posting_date_from', 'posting_date_to'})


def _get_model(source_table: str):
    entry = MODEL_REGISTRY.get(source_table)
    if not entry:
        return None
    try:
        return apps.get_model(*entry)
    except LookupError:
        return None


def _audit_user_name(user) -> str:
    full_name = getattr(user, 'full_name', None) or ''
    if full_name:
        return full_name
    if hasattr(user, 'get_full_name'):
        full_name = user.get_full_name() or ''
        if full_name:
            return full_name
    return user.username or user.email or ''


def _audit_update_fields(model) -> list[str]:
    fields: list[str] = []
    if hasattr(model, 'modified_by'):
        fields.append('modified_by')
    if hasattr(model, 'updated_at'):
        fields.append('updated_at')
    return fields


def _apply_audit_on_create(defaults: dict, model, user) -> dict:
    if user is None:
        return defaults
    try:
        created_by_field = model._meta.get_field('created_by')
    except FieldDoesNotExist:
        return defaults

    if isinstance(created_by_field, django_models.ForeignKey):
        defaults.setdefault('created_by', user)
    else:
        defaults.setdefault('created_by', _audit_user_name(user))

    try:
        modified_by_field = model._meta.get_field('modified_by')
    except FieldDoesNotExist:
        return defaults

    if isinstance(modified_by_field, django_models.ForeignKey):
        defaults.setdefault('modified_by', user)
    else:
        defaults.setdefault('modified_by', _audit_user_name(user))
    return defaults


def _resolve_list_page_for_create(card_page: Page, list_page_id) -> Page | None:
    if list_page_id:
        try:
            list_page = Page.objects.get(pk=int(list_page_id))
        except (Page.DoesNotExist, ValueError, TypeError):
            list_page = None
        else:
            if list_page.card_page_id == card_page.page_id:
                return list_page
    # Only auto-resolve when a single filtered list shares this card (e.g. one list per card).
    # ItemJournalCard has two lists (operational vs opening_balance) — ListPageId is required.
    qs = Page.objects.filter(
        card_page=card_page,
        list_filter_field__gt='',
        list_filter_value__gt='',
    )
    if qs.count() == 1:
        return qs.first()
    return None


def _resolve_payload_fk_writes(page: Page, control: PageControl, payload: dict, model=None) -> dict:
    """Resolve table-relation code values to FK instances on multi-field create."""
    if not payload:
        return payload
    if model is None:
        model = _get_model(page.source_table)
    relation_fields = control.fields.filter(
        has_table_relation=True,
        name__in=list(payload.keys()),
    )
    for field in relation_fields:
        if field.name not in payload:
            continue
        if field.name == 'no' and model and model.__name__ == 'PurchaseInvoiceLine':
            continue
        resolved_name, resolved_value = _resolve_fk_write(
            page, field.name, payload[field.name], record_values=payload, model=model,
        )
        payload[resolved_name] = resolved_value
    return payload


def _apply_drill_down_context(payload: dict, page: Page, model) -> dict:
    """Attach parent FK from list drill-down context (e.g. item__no → item)."""
    ctx_field = (page.context_filter_field or '').strip()
    if not ctx_field or '__' not in ctx_field:
        return payload
    value = payload.pop(ctx_field, None)
    if value is None or value == '':
        return payload
    fk_name, lookup = ctx_field.split('__', 1)
    if payload.get(fk_name):
        return payload
    try:
        fk_field = model._meta.get_field(fk_name)
        related_model = fk_field.remote_field.model
    except Exception:
        return payload
    related_obj = related_model.objects.filter(**{lookup: value}).first()
    if related_obj is not None:
        payload[fk_name] = related_obj
    return payload


def _apply_list_page_create_defaults(
    card_page: Page, defaults: dict, request, list_page_id=None,
) -> dict:
    list_page = _resolve_list_page_for_create(card_page, list_page_id)
    if list_page and list_page.list_filter_field:
        filter_val = _list_filter_create_default(list_page.list_filter_value)
        defaults.setdefault(list_page.list_filter_field, filter_val)
    return defaults


def _resolve_branch_location_for_request(request):
    """Default items.Location for the active branch (restaurant floors, journals, etc.)."""
    from items.models import Location

    try:
        from dimension.branch_filter import get_branch_for_request

        dimension = get_branch_for_request(request) or getattr(
            request.user, 'global_dimension_1', None,
        )
    except Exception:
        dimension = getattr(request.user, 'global_dimension_1', None)

    branch_code = getattr(dimension, 'code', '') or ''
    if branch_code:
        location = Location.objects.filter(code__iexact=branch_code).first()
        if location:
            return location
    return Location.objects.order_by('code').first()


def _apply_floor_create_defaults(defaults: dict, request) -> dict:
    if defaults.get('location') or defaults.get('location_id'):
        return defaults
    location = _resolve_branch_location_for_request(request)
    if location:
        defaults.setdefault('location', location)
    return defaults


def _apply_item_journal_create_defaults(defaults: dict, request) -> dict:
    from django.utils import timezone
    from items.enums import EntryType

    defaults.setdefault('user', request.user)
    defaults.setdefault('entry_type', EntryType.PositiveAdjustment.name)
    defaults.setdefault('date', timezone.now().date())

    try:
        from dimension.models import get_posting_dimension_payload
        from financials.models import GeneralLedgerSetup

        dimension = None
        try:
            from dimension.branch_filter import get_branch_for_request

            dimension = get_branch_for_request(request) or getattr(
                request.user, 'global_dimension_1', None,
            )
        except Exception:
            dimension = getattr(request.user, 'global_dimension_1', None)

        location = _resolve_branch_location_for_request(request)
        if location:
            defaults.setdefault('location_code', location)

        gl = GeneralLedgerSetup.objects.first()
        g1 = dimension
        g2 = getattr(request.user, 'global_dimension_2', None)
        dim_payload = get_posting_dimension_payload(
            global_dimension_1=g1,
            global_dimension_2=g2,
            gl_setup=gl,
        )
        defaults.setdefault(
            'global_dimension_1',
            dim_payload.get('global_dimension_1') or g1,
        )
        defaults.setdefault(
            'global_dimension_2',
            dim_payload.get('global_dimension_2') or g2,
        )
        defaults.setdefault('dimension_set', dim_payload.get('dimension_set'))
    except Exception:
        pass

    return defaults


def _apply_audit_on_update(obj, user, field_name: str) -> list[str]:
    update_fields = [field_name]
    if hasattr(obj, 'modified_by'):
        obj.modified_by = _audit_user_name(user)
        update_fields.append('modified_by')
    update_fields.extend(
        f for f in _audit_update_fields(obj.__class__)
        if f not in update_fields and f != field_name
    )
    return update_fields


def _model_has_item_and_description(model) -> bool:
    field_names = {
        f.name for f in model._meta.get_fields()
        if getattr(f, 'concrete', False) and not getattr(f, 'many_to_many', False)
    }
    return 'item' in field_names and 'description' in field_names


def _description_from_item(item) -> str:
    if item is None:
        return ''
    return (getattr(item, 'item_name', None) or '').strip()


def _default_item_unit_of_measure(item):
    if item is None:
        return None
    iuom = getattr(item, 'purchase_unit_of_measure', None)
    if iuom:
        return iuom
    from items.models import ItemUnitOfMeasure

    return (
        ItemUnitOfMeasure.objects.filter(item=item, default=True).first()
        or ItemUnitOfMeasure.objects.filter(item=item).order_by('id').first()
    )


def _purchase_unit_cost_from_item(item) -> Decimal | None:
    """Buying price for purchase lines; None when the item has no cost."""
    if item is None:
        return None
    cost = getattr(item, 'unit_cost', None)
    if cost is None or cost == '':
        cost = getattr(item, 'unit_price', None)
    if cost is None or cost == '':
        return None
    cost = Decimal(str(cost))
    return cost if cost > 0 else None


def _sales_unit_price_from_item(item) -> Decimal | None:
    """Selling price for sales lines; None when the item has no unit price."""
    if item is None:
        return None
    price = getattr(item, 'unit_price', None)
    if price is None or price == '':
        return None
    price = Decimal(str(price))
    return price if price >= 0 else None


def _apply_sales_line_item_price_defaults(payload: dict) -> dict:
    """Qty default + unit price from item card when an item is on a sales line."""
    line_type = payload.get('type') or 'item'
    if line_type != 'item':
        return payload
    item = payload.get('item')
    if not item:
        return payload
    if not payload.get('quantity'):
        payload['quantity'] = 1
    price = _sales_unit_price_from_item(item)
    if price is not None:
        payload['unit_price'] = price
    elif not payload.get('unit_price'):
        payload['unit_price'] = 0
    return payload


def _apply_purchase_invoice_line_item_defaults(payload: dict) -> dict:
    """Description, UOM, qty=1, and unit cost when an item is on a purchase line."""
    line_type = payload.get('type') or 'item'
    if line_type != 'item':
        return payload
    payload = _apply_item_line_defaults_to_payload(payload)
    item = payload.get('item')
    if not item:
        return payload
    if not payload.get('quantity'):
        payload['quantity'] = 1
    cost = _purchase_unit_cost_from_item(item)
    if cost is not None:
        payload['unit_cost'] = cost
    elif not payload.get('unit_cost'):
        payload['unit_cost'] = 0
    return payload


def _apply_item_line_defaults_to_payload(payload: dict, model=None) -> dict:
    """Description + purchase UOM when an item is set on document line create."""
    item = payload.get('item')
    if not item:
        return payload
    payload['description'] = _description_from_item(item)
    iuom = _default_item_unit_of_measure(item)
    if not iuom:
        return payload
    field_names = None
    if model is not None:
        field_names = {
            f.name for f in model._meta.get_fields()
            if getattr(f, 'concrete', False) and not getattr(f, 'many_to_many', False)
        }
    if field_names is None or 'item_unit_of_measure' in field_names:
        payload['item_unit_of_measure'] = iuom
    if field_names is None or 'unit_of_measure' in field_names:
        payload['unit_of_measure'] = iuom.unit_of_measure
    return payload


def _description_from_account(account_type: str | None, account_no: str | None) -> str | None:
    """Resolve display name for journal line account type + no."""
    if not account_type or not account_no:
        return None

    from payments.enums import AccountType

    model = None
    if account_type == AccountType.VENDOR.value:
        from purchases.models import Vendor
        model = Vendor
    elif account_type == AccountType.CUSTOMER.value:
        from sales.models import Customer
        model = Customer
    elif account_type in (AccountType.GL.value, 'G/L Account'):
        from financials.models import G_LAccount
        model = G_LAccount
    elif account_type in ('Bank Account', 'Bank_Account'):
        from bank_account.models import BankAccount
        model = BankAccount
    else:
        return None

    obj = model.objects.filter(no=account_no).first()
    if obj is None:
        return None
    return getattr(obj, 'name', None) or str(account_no)


def _sync_line_description_from_account(obj) -> list[str]:
    """When account_no/type changes on a journal line, copy account name into description."""
    if type(obj).__name__ not in (
        'PaymentLine',
        'CashReceiptJournalLine',
        'GeneralJournalLine',
    ):
        return []
    description = _description_from_account(
        getattr(obj, 'account_type', None),
        getattr(obj, 'account_no', None),
    )
    if not description or obj.description == description:
        return []
    obj.description = description
    return ['description']


def _sync_account_driven_line_fields(obj) -> list[str]:
    return _sync_line_description_from_account(obj)


def _apply_account_line_defaults(payload: dict) -> dict:
    """Default description when account_no is set on journal line create."""
    account_no = payload.get('account_no')
    if account_no and not payload.get('description'):
        description = _description_from_account(
            payload.get('account_type'),
            account_no if isinstance(account_no, str) else str(account_no),
        )
        if description:
            payload['description'] = description
    return payload


def _sync_line_description_from_item(obj) -> list[str]:
    """When item changes on a document line, copy item_name into description."""
    if not _model_has_item_and_description(obj.__class__):
        return []
    description = _description_from_item(getattr(obj, 'item', None))
    if not description or obj.description == description:
        return []
    obj.description = description
    return ['description']


def _sync_line_item_unit_of_measure(obj) -> list[str]:
    """When item changes, default purchase/item UOM on the line."""
    if not hasattr(obj, 'item_unit_of_measure'):
        return []
    iuom = _default_item_unit_of_measure(getattr(obj, 'item', None))
    if not iuom:
        return []
    extra: list[str] = []
    if obj.item_unit_of_measure_id != iuom.pk:
        obj.item_unit_of_measure = iuom
        extra.append('item_unit_of_measure')
    if hasattr(obj, 'unit_of_measure_id') and obj.unit_of_measure_id != iuom.unit_of_measure_id:
        obj.unit_of_measure = iuom.unit_of_measure
        extra.append('unit_of_measure')
    return extra


def _sync_purchase_invoice_line_from_item(obj) -> list[str]:
    """When item changes on a purchase invoice line, default qty and unit cost."""
    if type(obj).__name__ != 'PurchaseInvoiceLine':
        return []
    item = getattr(obj, 'item', None)
    if not item:
        return []
    extra: list[str] = []
    if obj.quantity != 1:
        obj.quantity = 1
        extra.append('quantity')
    cost = _purchase_unit_cost_from_item(item)
    if cost is not None:
        if obj.unit_cost != cost:
            obj.unit_cost = cost
            extra.append('unit_cost')
    elif obj.unit_cost:
        obj.unit_cost = Decimal('0')
        extra.append('unit_cost')
    return extra


def _sync_sales_line_from_item(obj) -> list[str]:
    """When item changes on a sales line, stamp qty (if empty) and unit price from item."""
    if type(obj).__name__ not in ('SalesInvoiceLine', 'SalesOrderLine'):
        return []
    item = getattr(obj, 'item', None)
    if not item:
        return []
    extra: list[str] = []
    if not obj.quantity:
        obj.quantity = 1
        extra.append('quantity')
    price = _sales_unit_price_from_item(item)
    if price is not None:
        if obj.unit_price != price:
            obj.unit_price = price
            extra.append('unit_price')
    elif obj.unit_price:
        obj.unit_price = Decimal('0')
        extra.append('unit_price')
    return extra


def _sync_purchase_line_type_switch(obj) -> list[str]:
    """Clear wrong FKs when purchase line type changes."""
    if type(obj).__name__ != 'PurchaseInvoiceLine':
        return []
    extra: list[str] = []
    line_type = getattr(obj, 'type', 'item') or 'item'
    if line_type == 'resource':
        if obj.item_id is not None:
            obj.item_id = None
            extra.append('item')
        if obj.gl_account_id is not None:
            obj.gl_account_id = None
            extra.append('gl_account')
        for field in ('item_unit_of_measure', 'unit_of_measure', 'location_code'):
            if getattr(obj, f'{field}_id', None) is not None:
                setattr(obj, field, None)
                extra.append(field)
    elif line_type == 'gl_account':
        if obj.item_id is not None:
            obj.item_id = None
            extra.append('item')
        if obj.resource_id is not None:
            obj.resource_id = None
            extra.append('resource')
        for field in ('item_unit_of_measure', 'unit_of_measure', 'location_code'):
            if getattr(obj, f'{field}_id', None) is not None:
                setattr(obj, field, None)
                extra.append(field)
    elif line_type == 'item':
        if obj.resource_id is not None:
            obj.resource_id = None
            extra.append('resource')
        if obj.gl_account_id is not None:
            obj.gl_account_id = None
            extra.append('gl_account')
    return extra


def _sync_resource_driven_purchase_line_fields(obj) -> list[str]:
    if type(obj).__name__ != 'PurchaseInvoiceLine':
        return []
    if getattr(obj, 'type', 'item') != 'resource' or not obj.resource_id:
        return []
    extra: list[str] = []
    if not obj.description and obj.resource:
        obj.description = obj.resource.name
        extra.append('description')
    cost = getattr(obj.resource, 'direct_unit_cost', None) or getattr(obj.resource, 'unit_cost', None)
    if cost is not None and not obj.unit_cost:
        obj.unit_cost = cost
        extra.append('unit_cost')
    return extra


def _serialize_purchase_line_no(obj) -> str | None:
    """BC-style unified No. from item / resource / G/L account FK."""
    line_type = getattr(obj, 'type', 'item') or 'item'
    if line_type == 'resource':
        resource = getattr(obj, 'resource', None)
        return getattr(resource, 'code', None) if resource else None
    if line_type == 'gl_account':
        gl_account = getattr(obj, 'gl_account', None)
        return getattr(gl_account, 'no', None) if gl_account else None
    item = getattr(obj, 'item', None)
    return getattr(item, 'no', None) if item else None


def _lookup_purchase_line_no_target(line_type: str, code_value):
    """Resolve No. code to (fk_attr, model_instance) for purchase lines."""
    if code_value is None or code_value == '':
        return None, None
    code_value = str(code_value).strip()
    if line_type == 'resource':
        model = _get_model('Resource')
        if model is None:
            raise ValueError('Resource model is not available.')
        obj = model.objects.filter(code=code_value).first()
        if obj is None:
            raise ValueError(f'Resource "{code_value}" was not found.')
        return 'resource', obj
    if line_type == 'gl_account':
        model = _get_model('G_LAccount')
        if model is None:
            raise ValueError('G/L Account model is not available.')
        obj = model.objects.filter(no=code_value).first()
        if obj is None:
            raise ValueError(f'G/L Account "{code_value}" was not found.')
        return 'gl_account', obj
    model = _get_model('Item')
    if model is None:
        raise ValueError('Item model is not available.')
    obj = model.objects.filter(no=code_value).first()
    if obj is None:
        raise ValueError(f'Item "{code_value}" was not found.')
    return 'item', obj


def _assign_purchase_line_no(obj, value, record_values=None) -> list[str]:
    """Map unified No. write to item / resource / gl_account FK columns."""
    record_values = record_values or {}
    line_type = record_values.get('type')
    if line_type is None or line_type == '':
        line_type = getattr(obj, 'type', 'item') or 'item'
    if line_type != getattr(obj, 'type', 'item'):
        obj.type = line_type
    extra: list[str] = ['type']
    extra.extend(_sync_purchase_line_type_switch(obj))

    if value is None or value == '':
        for attr in ('item', 'resource', 'gl_account'):
            if getattr(obj, f'{attr}_id', None) is not None:
                setattr(obj, attr, None)
                extra.append(attr)
        return list(dict.fromkeys(extra))

    fk_attr, related = _lookup_purchase_line_no_target(line_type, value)
    for attr in ('item', 'resource', 'gl_account'):
        if attr == fk_attr:
            setattr(obj, attr, related)
            extra.append(attr)
        elif getattr(obj, f'{attr}_id', None) is not None:
            setattr(obj, attr, None)
            extra.append(attr)
    return list(dict.fromkeys(extra))


def _apply_purchase_line_no_field_update(obj, value, record_values=None) -> list[str]:
    if type(obj).__name__ != 'PurchaseInvoiceLine':
        return []
    extra = _assign_purchase_line_no(obj, value, record_values)
    line_type = getattr(obj, 'type', 'item') or 'item'
    if line_type == 'item':
        extra.extend(_sync_item_driven_line_fields(obj))
    elif line_type == 'resource':
        extra.extend(_sync_resource_driven_purchase_line_fields(obj))
    return list(dict.fromkeys(extra))


def _purchase_line_no_create_defaults(value, record_values: dict) -> dict:
    """Build model defaults when the first persisted field on a new line is No."""
    line_type = record_values.get('type') or 'item'
    defaults: dict = {'type': line_type}
    fk_attr, related = _lookup_purchase_line_no_target(line_type, value)
    if not fk_attr:
        return defaults
    defaults[fk_attr] = related
    for attr in ('item', 'resource', 'gl_account'):
        if attr != fk_attr:
            defaults[attr] = None
    return defaults


def _sync_item_driven_line_fields(obj) -> list[str]:
    extra: list[str] = []
    for part in (
        _sync_line_description_from_item(obj),
        _sync_line_item_unit_of_measure(obj),
        _sync_purchase_invoice_line_from_item(obj),
        _sync_sales_line_from_item(obj),
    ):
        for field_name in part:
            if field_name not in extra:
                extra.append(field_name)
    return extra


def _rename_model_primary_key(model, pk_name: str, old_pk, new_pk, user) -> None:
    """Rename a non-auto PK in place and cascade the key to direct FK references."""
    update_kwargs = {pk_name: new_pk}
    if hasattr(model, 'modified_by'):
        update_kwargs['modified_by'] = _audit_user_name(user)
    if hasattr(model, 'updated_at'):
        update_kwargs['updated_at'] = timezone.now()

    with transaction.atomic():
        for rel in model._meta.related_objects:
            fk = rel.field
            if not isinstance(fk, django_models.ForeignKey):
                continue
            if fk.remote_field.model is not model:
                continue
            rel_model = rel.related_model
            rel_model.objects.filter(**{fk.name: old_pk}).update(**{fk.name: new_pk})
        rows = model.objects.filter(**{pk_name: old_pk}).update(**update_kwargs)
    if rows != 1:
        raise ValueError(
            f'A record with code "{new_pk}" already exists. Enter a different code.'
        )


def _save_page_field_update(obj, user, field_name: str, *, previous_pk=None, extra_fields=None) -> None:
    """Persist one field. PK renames use queryset.update to avoid duplicate inserts."""
    pk_name = obj._meta.pk.name
    if field_name == pk_name:
        new_pk = getattr(obj, pk_name)
        old_pk = previous_pk if previous_pk is not None else new_pk
        if str(old_pk) != str(new_pk):
            _rename_model_primary_key(obj.__class__, pk_name, old_pk, new_pk, user)
            obj._state.adding = False
            return
        if hasattr(obj, 'modified_by'):
            obj.modified_by = _audit_user_name(user)
        obj.save()
        return
    update_fields = _apply_audit_on_update(obj, user, field_name)
    if extra_fields:
        for extra in extra_fields:
            if extra not in update_fields:
                update_fields.append(extra)
    obj.save(update_fields=update_fields)


def _save_nested_related_field_update(obj, field_name: str, value) -> None:
    """Persist dotted lookup fields (e.g. user__can_switch_branch on UserSetup)."""
    parts = field_name.split('__')
    if len(parts) < 2:
        raise ValueError(f'Invalid field: {field_name}')

    current = obj
    for part in parts[:-1]:
        current = getattr(current, part, None)
        if current is None:
            raise ValueError(f'Cannot update {field_name}: related record is missing')

    leaf = parts[-1]
    try:
        current._meta.get_field(leaf)
    except FieldDoesNotExist as exc:
        raise ValueError(f'Invalid field: {field_name}') from exc

    setattr(current, leaf, value)
    current.save(update_fields=[leaf])


def _model_has_direct_field(model, field_name: str) -> bool:
    try:
        model._meta.get_field(field_name)
        return True
    except FieldDoesNotExist:
        return False


def _user_owns_personalization(obj, user) -> bool:
    return getattr(obj, 'user_id', None) == user.pk


def _can_access_personalization(request, obj, permission_type: str = 'read') -> bool:
    """Own record, or admin with User Settings page permission."""
    if obj is None:
        return False
    user = request.user
    if _user_owns_personalization(obj, user):
        return True
    if getattr(user, 'is_superuser', False):
        return True
    from permissions.services.super_permission_set import user_has_super_permission
    if user_has_super_permission(user):
        return True
    from pages.bc_page_ids import resolve_page_object_id
    for page_name in ('UserSettingsCard', 'UserSettingsList'):
        oid = resolve_page_object_id(page_name)
        if oid is None:
            continue
        allowed, _ = user.check_object_permission(oid, permission_type)
        if allowed:
            return True
    return False


def _search_lookups(model, field_name: str) -> list[str]:
    """Build ORM icontains lookups; FK Code fields search the related key column."""
    try:
        field = model._meta.get_field(field_name)
    except django_models.FieldDoesNotExist:
        return [f'{field_name}__icontains']
    if isinstance(field, django_models.ForeignKey):
        related_name = getattr(field.target_field, 'name', 'pk')
        return [f'{field_name}__{related_name}__icontains']
    return [f'{field_name}__icontains']


def _resolve_field_value(obj, attr: str):
    """Resolve model fields, FK ids, dotted lookups, and @property values."""
    if '__' in attr:
        value = obj
        for part in attr.split('__'):
            if value is None:
                return None
            value = getattr(value, part, None)
        return value

    if hasattr(obj, attr):
        value = getattr(obj, attr)
        if value is None:
            value = getattr(obj, f'{attr}_id', None)
        elif hasattr(value, 'code') and not isinstance(value, (str, int, float, bool)):
            return value.code
        return value

    return getattr(obj, f'{attr}_id', None)


def _normalize_serialized_value(value):
    if value is None:
        return None
    if hasattr(value, 'url'):
        return value.url
    if hasattr(value, 'isoformat'):
        return value.isoformat()
    if isinstance(value, (str, int, float, bool)):
        return value
    if hasattr(value, '__str__'):
        return str(value)
    return value


def _serialize_branch_aware_computed_value(obj, field_name: str, request):
    """Branch-scoped balance/inventory for page-engine lists (matches REST serializers)."""
    model_name = obj.__class__.__name__

    if field_name == 'balance':
        if model_name == 'Customer':
            from sales.serializers import CustomerSerializer
            return CustomerSerializer(context={'request': request}).get_balance(obj)
        if model_name == 'Vendor':
            from purchases.serializers import VendorSerializer
            return VendorSerializer(context={'request': request}).get_balance(obj)
        if model_name == 'BankAccount':
            from bank_account.serializers import BankAccountSerializer
            return BankAccountSerializer(context={'request': request}).get_balance(obj)
        if model_name == 'G_LAccount':
            from django.db.models import Sum
            from financials.models import GeneralLedgerEntry, GeneralLedgerSetup
            from dimension.branch_filter import filter_queryset_by_branch

            qs = GeneralLedgerEntry.objects.filter(gl_account=obj)
            gl_setup = GeneralLedgerSetup.objects.first()
            if gl_setup and getattr(gl_setup, 'enable_multiple_branches', False):
                qs = filter_queryset_by_branch(
                    qs, request.user, model_class=GeneralLedgerEntry, request=request,
                )
            return qs.aggregate(total=Sum('amount'))['total'] or 0.0

    if field_name == 'inventory' and model_name == 'Item':
        from items.serializers import ItemSerializer
        return ItemSerializer(context={'request': request}).get_inventory(obj)

    if field_name == 'unit_cost' and model_name == 'Item':
        from authentication.models import UserSetup
        from items.serializers import ItemSerializer

        try:
            user_setup = UserSetup.objects.select_related('user').get(user=request.user)
            if not user_setup.can_see_buying_price:
                return None
        except UserSetup.DoesNotExist:
            pass
        return ItemSerializer(context={'request': request}).get_unit_cost(obj)

    if model_name == 'SalesInvoice':
        from sales.serializers import SalesInvoiceSerializer

        serializer = SalesInvoiceSerializer(context={'request': request})
        if field_name == 'total_amount':
            if hasattr(obj, 'computed_total_amount'):
                return float(obj.computed_total_amount or 0)
            return serializer.get_total_amount(obj)
        if field_name == 'user_name':
            if hasattr(obj, 'user_name') and obj.user_name:
                return obj.user_name
            return serializer.get_user_name(obj)

    if model_name == 'PostedSalesInvoice':
        if field_name == 'total_amount':
            if hasattr(obj, 'computed_total_amount'):
                return float(obj.computed_total_amount or 0)
            from django.db.models import Sum
            total = (
                obj.posted_sales_invoice_lines.aggregate(s=Sum('amount')).get('s') or 0
            )
            return float(total)
        if field_name == 'user_name':
            if hasattr(obj, 'user_name') and obj.user_name:
                return obj.user_name
            return ''

    if model_name == 'SalesCreditMemo' and field_name == 'total_amount':
        from django.db.models import Sum

        if hasattr(obj, '_prefetched_objects_cache') and 'lines' in obj._prefetched_objects_cache:
            return float(sum(line.amount or 0 for line in obj.lines.all()))
        total = obj.lines.aggregate(s=Sum('amount')).get('s') or 0
        return float(total)

    if model_name == 'PurchaseInvoice' and field_name == 'total_amount':
        from purchases.serializers import PurchaseInvoiceSerializer

        return PurchaseInvoiceSerializer(context={'request': request}).get_total_amount(obj)

    if model_name == 'GeneralJournalLine' and field_name in ('account_name', 'bal_account_name'):
        return getattr(obj, field_name, '') or ''

    return None


def _uses_branch_aware_computed(obj, field_name: str) -> bool:
    model_name = obj.__class__.__name__
    if field_name == 'balance' and model_name in ('Customer', 'Vendor', 'BankAccount', 'G_LAccount'):
        return True
    if field_name == 'inventory' and model_name == 'Item':
        return True
    if field_name == 'unit_cost' and model_name == 'Item':
        return True
    return (
        (model_name == 'SalesInvoice' and field_name in ('total_amount', 'user_name'))
        or (model_name == 'PostedSalesInvoice' and field_name in ('total_amount', 'user_name'))
        or (model_name == 'SalesCreditMemo' and field_name == 'total_amount')
        or (model_name == 'PurchaseInvoice' and field_name == 'total_amount')
    )


def _uses_general_journal_computed(obj, field_name: str) -> bool:
    return obj.__class__.__name__ == 'GeneralJournalLine' and field_name in (
        'account_name',
        'bal_account_name',
    )


def _serialize_field_value(obj, field: PageControlField, request=None):
    """Serialize one page field; FK table-relation fields return the related key (no/code)."""
    if obj.__class__.__name__ == 'UserPersonalization' and field.name == 'user_id':
        user = getattr(obj, 'user', None)
        return _normalize_serialized_value(getattr(user, 'username', None) if user else None)
    if obj.__class__.__name__ == 'PaymentMethod':
        if field.name == 'bal_account_no':
            return _normalize_serialized_value(_serialize_payment_method_bal_account_no(obj))
        if field.name == 'bal_account_type':
            return _normalize_serialized_value(
                _payment_method_bal_type_display(getattr(obj, 'bal_account_type', None)),
            )
    if request is not None and _uses_branch_aware_computed(obj, field.name):
        return _normalize_serialized_value(
            _serialize_branch_aware_computed_value(obj, field.name, request),
        )
    if _uses_general_journal_computed(obj, field.name):
        return _normalize_serialized_value(getattr(obj, field.name, '') or '')
    rel = getattr(obj, field.name, None)
    if (
        obj.__class__.__name__ == 'PermissionSetLine'
        and field.name == 'application_object'
        and rel is not None
    ):
        obj_type = getattr(rel, 'object_type', '') or ''
        name = getattr(rel, 'object_name', '') or ''
        return f'{obj_type} · {name}' if obj_type and name else name or obj_type
    if field.has_table_relation and field.related_field and rel is not None:
        if (
            field.related_display_field
            and field.related_field in ('id', 'pk')
        ):
            display = _resolve_field_value(rel, field.related_display_field)
            if display is not None and display != '':
                return display
        key = getattr(rel, field.related_field, None)
        if key is not None and key != '':
            return key
    if obj.__class__.__name__ == 'CustomUser':
        return _normalize_serialized_value(serialize_user_field(obj, field.name))
    if obj.__class__.__name__ == 'PermissionSet' and field.name == 'via_user_groups':
        return _normalize_serialized_value(getattr(obj, '_via_user_groups', '') or '')
    if obj.__class__.__name__ in ('PurchaseInvoiceLine', 'PostedPurchaseInvoiceLine') and field.name == 'no':
        return _normalize_serialized_value(_serialize_purchase_line_no(obj))
    return _normalize_serialized_value(_resolve_field_value(obj, field.name))


def _serialize_record(obj, fields: list[PageControlField], request=None) -> dict:
    row: dict = {'SystemId': str(getattr(obj, 'system_id', obj.pk))}
    for field in fields:
        row[field.name] = _serialize_field_value(obj, field, request)
    if obj.__class__.__name__ == 'G_LAccount':
        row['indentation'] = getattr(obj, 'indentation', 0) or 0
    if obj.__class__.__name__ == 'ItemCategory':
        row['indentation'] = int(getattr(obj, 'level', 0) or 0)
        # parent_id is the related category code (to_field='code').
        row.setdefault('parent', getattr(obj, 'parent_id', None) or '')
    if obj.__class__.__name__ == 'CustomUser':
        row['id'] = obj.pk
    if obj.__class__.__name__ == 'ItemUnitOfMeasure':
        row['id'] = obj.pk
    if obj.__class__.__name__ in (
        'PurchaseInvoiceLine',
        'SalesInvoiceLine',
        'SalesOrderLine',
        'PurchaseInvoice',
        'SalesInvoice',
        'PostedSalesInvoice',
        'PostedSalesInvoiceLine',
        'SalesCreditMemo',
        'SalesCreditMemoLine',
        'PostedPurchaseInvoiceLine',
        'PostedPurchaseInvoice',
        'TrackingSpecification',
        'ItemLedgerEntries',
    ):
        row['id'] = obj.pk
    if obj.__class__.__name__ == 'PermissionSetLine':
        app_obj = getattr(obj, 'application_object', None)
        if app_obj is not None:
            row['object_type'] = app_obj.object_type
            row['object_id'] = app_obj.object_id
            row['object_name'] = app_obj.object_name
        else:
            row.setdefault('object_type', '')
            row.setdefault('object_id', None)
            row.setdefault('object_name', '')
    if obj.__class__.__name__ == 'FinancialReport':
        for extra in ('start_date', 'end_date', 'period_type'):
            if extra not in row:
                row[extra] = _normalize_serialized_value(getattr(obj, extra, None))
    if obj.__class__.__name__ == 'PostedSalesInvoice':
        linked_sid = getattr(obj, 'sales_invoice_system_id', None)
        if linked_sid:
            row['sales_invoice_system_id'] = str(linked_sid)
    return row


def _resolve_filter_field(model, lookup_key: str):
    """Resolve the target model field for an ORM lookup key (e.g. customer__no, open)."""
    parts = lookup_key.split('__')
    opts = model._meta
    for i, part in enumerate(parts):
        try:
            field = opts.get_field(part)
        except FieldDoesNotExist:
            return None
        if i == len(parts) - 1:
            return field
        if not getattr(field, 'is_relation', False) or not field.related_model:
            return None
        opts = field.related_model._meta
    return None


def _coerce_filter_value(model, lookup_key: str, value: str):
    """Coerce query-string filter values to types expected by the target model field."""
    field = _resolve_filter_field(model, lookup_key)
    if field is None:
        return value
    if isinstance(field, django_models.BooleanField):
        return _parse_cue_filter_value(value.strip())
    return value


# Computed list columns that sort via ORM annotation (not stored model fields).
_COMPUTED_LIST_SORT_PATHS: dict[str, dict[str, str]] = {
    'VendorLedger': {
        'remaining_amount': 'detailed_entries__amount',
    },
    'CustomerLedgerEntry': {
        'remaining_amount': 'sales_detailed_entries__amount',
    },
}


def _allowed_list_sort_fields(control, model) -> set[str]:
    """Field names the user may sort by on a list page."""
    if control is None:
        return set()
    allowed: set[str] = set()
    computed = _COMPUTED_LIST_SORT_PATHS.get(model.__name__, {})
    for field in _serialization_fields(control):
        name = field.name
        if _resolve_list_sort_lookup(model, name):
            allowed.add(name)
        elif name in computed:
            allowed.add(name)
    return allowed


def _resolve_list_sort_lookup(model, field_name: str) -> str | None:
    try:
        model._meta.get_field(field_name)
        return field_name
    except FieldDoesNotExist:
        pass
    fk_name = f'{field_name}_id'
    try:
        model._meta.get_field(fk_name)
        return fk_name
    except FieldDoesNotExist:
        return None


def _computed_sort_annotation_name(sort_field: str) -> str:
    """Annotation alias that cannot clash with model @property names."""
    return f'_sort_{sort_field}'


def _annotate_computed_list_sort(qs, model, sort_field: str):
    """Annotate queryset so computed list columns can be ordered in SQL."""
    path = _COMPUTED_LIST_SORT_PATHS.get(model.__name__, {}).get(sort_field)
    if not path:
        return qs, None
    annotation_name = _computed_sort_annotation_name(sort_field)
    return qs.annotate(
        **{
            annotation_name: Coalesce(
                Sum(path),
                Value(0),
                output_field=django_models.DecimalField(max_digits=15, decimal_places=2),
            )
        }
    ), annotation_name


def _apply_user_list_sort(qs, model, control, sort_field: str | None, order: str | None):
    """Apply user-chosen column sort (replaces default list ordering)."""
    if not sort_field or not control:
        return qs
    allowed = _allowed_list_sort_fields(control, model)
    if sort_field not in allowed:
        return qs
    lookup = _resolve_list_sort_lookup(model, sort_field)
    if not lookup:
        qs, lookup = _annotate_computed_list_sort(qs, model, sort_field)
        if not lookup:
            return qs
    descending = (order or 'asc').strip().lower() == 'desc'
    prefix = '-' if descending else ''
    return qs.order_by(f'{prefix}{lookup}')


def _extract_list_filters(request, model) -> dict:
    """Map extra query params to ORM filters (drill-down context)."""
    filters: dict = {}
    for key, value in request.query_params.items():
        if key in _LIST_QUERY_PARAMS or not value:
            continue
        if key.startswith('cf_'):
            continue
        if key in _LIST_VIRTUAL_FILTER_KEYS:
            filters[key] = value
            continue
        if key in _LIST_DATE_SCOPE_KEYS and hasattr(model, 'posting_date'):
            filters[key] = value
            continue
        if '__' in key or hasattr(model, key) or hasattr(model, f'{key}_id'):
            filters[key] = _coerce_filter_value(model, key, value)
    return filters


def _apply_posting_date_scope(qs, filters: dict[str, str]):
    """Apply posting_date / posting_date_from / posting_date_to and remove from filters dict."""
    posting_date = filters.pop('posting_date', None)
    posting_date_from = filters.pop('posting_date_from', None)
    posting_date_to = filters.pop('posting_date_to', None)
    if posting_date:
        qs = qs.filter(posting_date=posting_date)
    if posting_date_from:
        qs = qs.filter(posting_date__gte=posting_date_from)
    if posting_date_to:
        qs = qs.filter(posting_date__lte=posting_date_to)
    return qs


def _apply_sales_invoice_virtual_filters(qs, filters: dict[str, str]):
    """Apply SalesInvoice filters that are not plain model fields (ledger salesperson)."""
    ledger_user_id = filters.get('ledger_user_id')
    if not ledger_user_id:
        return qs
    try:
        user_id = int(ledger_user_id)
    except (TypeError, ValueError):
        return qs

    from django.db.models import IntegerField, OuterRef, Subquery
    from sales.models import CustomerLedgerEntry

    ledger_user_subquery = (
        CustomerLedgerEntry.objects.filter(document_no=OuterRef('invoice_no'))
        .order_by('-id')
        .values('user_id')[:1]
    )
    return qs.annotate(
        ledger_user_id=Subquery(ledger_user_subquery, output_field=IntegerField()),
    ).filter(ledger_user_id=user_id)


def _apply_posted_sales_invoice_virtual_filters(qs, filters: dict[str, str]):
    """Apply PostedSalesInvoice virtual filters (ledger salesperson via linked SalesInvoice)."""
    ledger_user_id = filters.get('ledger_user_id')
    if not ledger_user_id:
        return qs
    try:
        user_id = int(ledger_user_id)
    except (TypeError, ValueError):
        return qs

    return qs.filter(ledger_user_id=user_id)


def _apply_applied_entries_filter(qs, source_table: str, entry_id: str):
    """BC page 62 Applied Vendor/Customer Entries filter."""
    from financials.ledger_application import (
        collect_applied_customer_ledger_entry_ids,
        collect_applied_vendor_ledger_entry_ids,
    )

    try:
        eid = int(entry_id)
    except (TypeError, ValueError):
        return qs.none()

    if source_table == 'VendorLedger':
        linked_ids = collect_applied_vendor_ledger_entry_ids(eid)
    elif source_table == 'CustomerLedgerEntry':
        linked_ids = collect_applied_customer_ledger_entry_ids(eid)
    else:
        return qs.none()

    return qs.filter(id__in=linked_ids).distinct()


def _apply_detailed_ledger_entry_filter(qs, source_table: str, entry_id: str):
    """BC Detailed Vendor/Customer Ledg. Entries RunPageLink filter."""
    try:
        eid = int(entry_id)
    except (TypeError, ValueError):
        return qs.none()

    if source_table == 'DetailedVendorLedgerEntry':
        from purchases.models import VendorLedger

        vendor_id = (
            VendorLedger.objects.filter(pk=eid).values_list('vendor_id', flat=True).first()
        )
        qs = qs.filter(vendor_ledger_entry_id=eid)
        if vendor_id:
            qs = qs.filter(vendor_id=vendor_id)
        return qs.order_by('posting_date', 'entry_no')

    if source_table == 'DetailedCustomerLedgerEntry':
        from sales.models import CustomerLedgerEntry

        customer_id = (
            CustomerLedgerEntry.objects.filter(pk=eid)
            .values_list('customer_id', flat=True)
            .first()
        )
        qs = qs.filter(customer_ledger_entry_id=eid)
        if customer_id:
            qs = qs.filter(customer_id=customer_id)
        return qs.order_by('posting_date', 'entry_no')

    return qs


def _find_part_link_for_sub_page(sub_page: Page):
    return PageControl.objects.filter(
        control_type='Part',
        part_page=sub_page,
    ).exclude(link_field='').first()


def _record_status_value(obj) -> str | None:
    if obj is None:
        return None
    raw = getattr(obj, 'status', None)
    if raw is None:
        return None
    if hasattr(raw, 'value'):
        return str(raw.value)
    return str(raw)


def _record_is_posted(obj) -> bool:
    return _record_status_value(obj) == 'Posted'


def _restaurant_order_is_closed(obj) -> bool:
    if obj is None:
        return False
    if obj.__class__.__name__ not in ('RestaurantOrder', 'RestaurantOrderItem'):
        return False
    if obj.__class__.__name__ == 'RestaurantOrderItem':
        obj = getattr(obj, 'order', None)
    if obj is None:
        return False
    try:
        from restaurant_management.order_guards import order_is_closed

        return order_is_closed(obj)
    except Exception:
        status_val = _record_status_value(obj)
        if status_val == 'completed':
            return True
        return bool(getattr(obj, 'sales_invoice_id', None))


def _parent_record_for_line(obj):
    """Resolve document header from a line row (sales invoice line, etc.)."""
    if obj is None:
        return None
    for attr in (
        'sales_invoice',
        'purchase_invoice',
        'sales_order',
        'purchase_order',
        'credit_memo',
        'payment_journal',
        'item_journal',
        'expense',
        'document',
        'header',
        'order',
    ):
        parent = getattr(obj, attr, None)
        if parent is not None:
            return parent
    return None


def _record_is_read_only(obj) -> bool:
    if obj.__class__.__name__ in (
        'PostedPurchaseInvoice',
        'PostedPurchaseInvoiceLine',
        'PostedSalesInvoice',
        'PostedSalesInvoiceLine',
    ):
        return True
    if _record_is_posted(obj):
        return True
    if _restaurant_order_is_closed(obj):
        return True
    parent = _parent_record_for_line(obj)
    if _record_is_posted(parent):
        return True
    if _restaurant_order_is_closed(parent):
        return True
    return False


def _posted_read_only_response():
    return Response(
        {'error': 'Posted documents cannot be modified'},
        status=status.HTTP_403_FORBIDDEN,
    )


def _resolve_purchase_invoice_no_for_vendor_invoice(vendor_invoice_no: str) -> str | None:
    from purchases.models import PurchaseInvoice

    if not vendor_invoice_no:
        return None
    return (
        PurchaseInvoice.objects.filter(
            vendor_invoice_no=vendor_invoice_no,
            status='Posted',
        )
        .values_list('invoice_no', flat=True)
        .first()
    )


def _apply_posted_purchase_item_tracking_filters(qs, filters: dict):
    """BC 6511 — item ledger rows for a posted purchase line (document_no + item)."""
    from items.enums import EntryType

    vendor_invoice_no = filters.pop('vendor_invoice_no', None)
    item_no = filters.pop('item', None) or filters.pop('item__no', None)
    if vendor_invoice_no:
        document_no = _resolve_purchase_invoice_no_for_vendor_invoice(vendor_invoice_no)
        if document_no:
            qs = qs.filter(document_no=document_no)
        else:
            qs = qs.none()
    if item_no:
        qs = qs.filter(item__no=item_no)
    qs = qs.filter(entry_type=EntryType.Purchase.name)
    if filters:
        qs = qs.filter(**filters)
    return qs


def _apply_part_parent_filter(qs, link_field: str, parent_system_id: str):
    if not link_field or not parent_system_id:
        return qs
    return qs.filter(**{link_field: parent_system_id})


def _filter_item_unit_of_measure_qs(qs, obj=None, record_values: dict | None = None):
    if obj is not None:
        item = getattr(obj, 'item', None)
        if item is not None:
            return qs.filter(item=item)
        item_id = getattr(obj, 'item_id', None)
        if item_id:
            return qs.filter(item_id=item_id)
    if record_values:
        item_no = record_values.get('no') or record_values.get('item')
        if item_no:
            return qs.filter(item__no=item_no)
    return qs


def _merge_fk_record_values(
    pcf: PageControlField | None,
    obj=None,
    record_values: dict | None = None,
    field_name: str | None = None,
    field_value=None,
) -> dict:
    """Merge request payload + existing record for context-sensitive relations."""
    merged = dict(record_values or {})
    if field_name is not None:
        merged[field_name] = field_value
    if pcf and pcf.relation_context_field and obj is not None:
        ctx = pcf.relation_context_field
        if merged.get(ctx) in (None, ''):
            merged[ctx] = getattr(obj, ctx, None)
    return merged


def _fk_write_target_value(model, field_name: str, related_obj, related_field: str, raw_value):
    """Return FK instance for FK fields, or the related code for CharField storage."""
    if model is None or related_obj is None:
        return related_obj
    try:
        model_field = model._meta.get_field(field_name)
    except FieldDoesNotExist:
        return related_obj
    if model_field.is_relation and not model_field.many_to_many:
        return related_obj
    if related_field:
        return getattr(related_obj, related_field, raw_value)
    return raw_value


def _resolve_fk_write(
    page: Page,
    field_name: str,
    value,
    obj=None,
    record_values: dict | None = None,
    model=None,
):
    """Resolve a string code value to a FK object when the field has a table relation."""
    if value is None or value == '':
        return field_name, None
    # Already resolved (e.g. create path resolved vendor, then re-walks defaults).
    # Re-filtering with a model instance uses str(obj) like "VENDOR-000022 - Name" and fails.
    if isinstance(value, django_models.Model):
        return field_name, value
    pcf = PageControlField.objects.filter(
        page=page, name=field_name, has_table_relation=True
    ).first()
    if not pcf:
        return field_name, value

    merged_values = _merge_fk_record_values(
        pcf, obj=obj, record_values=record_values, field_name=field_name, field_value=value,
    )
    related_table, related_field, display_field = resolve_table_relation(pcf, merged_values)
    if not related_table or not related_field:
        related_table = pcf.related_table
        related_field = pcf.related_field
        display_field = pcf.related_display_field
    if not related_table or not related_field:
        return field_name, value

    related_model = _get_model(related_table)
    if related_model is None:
        return field_name, value

    if model is None:
        model = obj.__class__ if obj is not None else _get_model(page.source_table)

    qs = related_model.objects.all()
    related_obj = None
    if related_field in ('id', 'pk') and str(value).isdigit():
        related_obj = qs.filter(pk=value).first()
    elif related_field in ('id', 'pk') and display_field:
        lookup = {display_field: value}
        scoped_qs = qs
        if related_table == 'ItemUnitOfMeasure':
            scoped_qs = _filter_item_unit_of_measure_qs(
                qs, obj=obj, record_values=merged_values,
            )
        related_obj = scoped_qs.filter(**lookup).first()
    if related_obj is None:
        related_obj = qs.filter(**{related_field: value}).first()
    if related_obj is not None:
        return field_name, _fk_write_target_value(
            model, field_name, related_obj, related_field, value,
        )
    raise ValueError(
        f'No matching {related_table} record found for "{value}".',
    )


def _payment_method_bal_type_key(bal_account_type: str | None) -> str | None:
    from financials.enums import coerce_balancing_account_type
    return coerce_balancing_account_type(bal_account_type)


def _payment_method_is_bank_type(bal_account_type: str | None) -> bool:
    from financials.enums import BalacingAccountType
    return _payment_method_bal_type_key(bal_account_type) == BalacingAccountType.Bank_Account.name


def _payment_method_bal_type_display(bal_account_type: str | None) -> str | None:
    from financials.enums import BalacingAccountType
    key = _payment_method_bal_type_key(bal_account_type)
    if not key:
        return bal_account_type
    try:
        return BalacingAccountType[key].value
    except KeyError:
        return bal_account_type


def _coerce_payment_method_bal_type_write(value) -> str:
    from financials.enums import BalacingAccountType, coerce_balancing_account_type
    return coerce_balancing_account_type(value) or BalacingAccountType.GLAccount.name


def _resolve_payment_method_account_fk(bal_account_type: str | None, account_no):
    """BC-style unified Bal. Account No. → (gl_fk, bank_fk)."""
    if account_no is None or account_no == '':
        return None, None
    if _payment_method_is_bank_type(bal_account_type):
        bank_model = _get_model('BankAccount')
        if bank_model is None:
            raise ValueError('Bank account model is not available.')
        bank_obj = bank_model.objects.filter(no=account_no).first()
        if bank_obj is None:
            raise ValueError(f'Bank account "{account_no}" was not found.')
        return None, bank_obj
    gl_model = _get_model('G_LAccount')
    if gl_model is None:
        raise ValueError('G/L account model is not available.')
    gl_obj = gl_model.objects.filter(no=account_no).first()
    if gl_obj is None:
        raise ValueError(f'G/L account "{account_no}" was not found.')
    return gl_obj, None


def _assign_payment_method_unified_bal_account(obj, bal_account_type, account_no) -> None:
    gl_obj, bank_obj = _resolve_payment_method_account_fk(bal_account_type, account_no)
    obj.bal_account_no = gl_obj
    obj.bal_bank_account_no = bank_obj


def _serialize_payment_method_bal_account_no(obj) -> str | None:
    if _payment_method_is_bank_type(getattr(obj, 'bal_account_type', None)):
        bank = getattr(obj, 'bal_bank_account_no', None)
        return getattr(bank, 'no', None) if bank else None
    gl = getattr(obj, 'bal_account_no', None)
    return getattr(gl, 'no', None) if gl else None


def _normalize_payment_method_payload(payload: dict) -> dict:
    """Map unified bal_account_no writes to the correct FK columns."""
    if 'bal_account_type' in payload:
        payload['bal_account_type'] = _coerce_payment_method_bal_type_write(
            payload['bal_account_type'],
        )
    if 'bal_account_no' not in payload and 'bal_bank_account_no' not in payload:
        return payload
    raw = payload.pop('bal_account_no', None)
    payload.pop('bal_bank_account_no', None)
    bal_type = payload.get('bal_account_type')
    gl_obj, bank_obj = _resolve_payment_method_account_fk(bal_type, raw)
    payload['bal_account_no'] = gl_obj
    payload['bal_bank_account_no'] = bank_obj
    return payload


def _apply_payment_method_field_update(obj, field_name: str, value, record_values=None):
    """
    BC-style Payment Method field writes.
    Returns list of model fields to persist, or None if not handled.
    """
    record_values = record_values or {}
    if field_name == 'bal_account_type':
        obj.bal_account_type = _coerce_payment_method_bal_type_write(value)
        obj.bal_account_no = None
        obj.bal_bank_account_no = None
        return ['bal_account_type', 'bal_account_no', 'bal_bank_account_no']
    if field_name == 'bal_account_no':
        bal_type = record_values.get('bal_account_type') or obj.bal_account_type
        _assign_payment_method_unified_bal_account(obj, bal_type, value)
        return ['bal_account_no', 'bal_bank_account_no']
    return None


def _save_payment_method_fields(obj, user, field_names: list[str]) -> None:
    update_fields: list[str] = []
    for field_name in field_names:
        update_fields.extend(_apply_audit_on_update(obj, user, field_name))
    obj.save(update_fields=list(dict.fromkeys(update_fields)))


_ITEM_MANUAL_COST_TYPES = frozenset({'Service', 'Non-Inventory'})


def _coerce_item_manual_unit_cost(value):
    from decimal import Decimal, InvalidOperation

    if value in (None, ''):
        return Decimal('0.00')
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError('Invalid buying price.') from exc


def _item_type_for_cost_write(obj, model, system_id: str | None = None) -> str | None:
    if obj is not None:
        return getattr(obj, 'type', None)
    if model.__name__ != 'Item' or not system_id:
        return None
    partial = model.objects.filter(system_id=system_id).only('type').first()
    return getattr(partial, 'type', None) if partial else None


def _apply_item_field_update(obj, field_name: str, value, *, model=None, system_id=None):
    """
    Item card virtual fields (unit_cost is a computed @property on the model).
    Returns list of model fields to persist, [] to skip, or None if not handled.
    """
    model_name = obj.__class__.__name__ if obj is not None else (model.__name__ if model else '')
    if model_name != 'Item' or field_name != 'unit_cost':
        return None

    item_type = _item_type_for_cost_write(obj, obj.__class__ if obj is not None else model, system_id)
    if item_type not in _ITEM_MANUAL_COST_TYPES:
        return []

    obj.manual_unit_cost = _coerce_item_manual_unit_cost(value)
    return ['manual_unit_cost']


def _resolve_part_data_control(control: PageControl, page: Page):
    """Resolve Part control to the sub-page Repeater used for list data."""
    if control.control_type != 'Part':
        return control, page
    if not control.part_page_id:
        return None, page
    sub_page = control.part_page
    sub_control = sub_page.page_controls.filter(control_type='Repeater').first()
    if not sub_control:
        sub_control = sub_page.page_controls.first()
    return sub_control, sub_page


def _inject_part_parent_link(payload: dict, page: Page, parent_system_id: str | None) -> dict:
    parent_system_id = parent_system_id or payload.pop('parent_system_id', None)
    if not parent_system_id:
        return payload

    part_link = _find_part_link_for_sub_page(page)
    if not part_link or not part_link.link_field:
        return payload

    link = part_link.link_field
    payload = {k: v for k, v in payload.items() if k not in ('parent_system_id',)}

    if '__' in link:
        fk_field = link.split('__')[0]
        parent_model = _get_model(part_link.page.source_table)
        if parent_model is None:
            return payload
        parent_obj = PageDataRecordView()._get_obj(parent_model, parent_system_id)
        if parent_obj is not None:
            payload[fk_field] = parent_obj
    else:
        payload[link] = parent_system_id

    return payload


def _apply_sales_order_line_defaults(payload: dict, request) -> dict:
    from dimension.models import get_merged_line_dimensions

    if not (payload.get('global_dimension_1') and payload.get('dimension_set')):
        sales_order = payload.get('sales_order')
        if sales_order is None and payload.get('sales_order_id'):
            from sales.models import SalesOrder
            sales_order = SalesOrder.objects.filter(pk=payload['sales_order_id']).first()

        customer_no = None
        if sales_order and getattr(sales_order, 'customer', None):
            customer_no = getattr(sales_order.customer, 'no', None)

        item = payload.get('item')
        dims = get_merged_line_dimensions(
            customer_no=customer_no,
            item=item,
            request_user=getattr(request, 'user', None),
            line_data=payload,
        )
        if dims.get('global_dimension_1') and not payload.get('global_dimension_1'):
            payload['global_dimension_1'] = dims['global_dimension_1']
        if dims.get('dimension_set') and not payload.get('dimension_set'):
            payload['dimension_set'] = dims['dimension_set']
    if not payload.get('type'):
        payload['type'] = 'item'
    if not payload.get('quantity'):
        payload['quantity'] = 0
    payload = _apply_item_line_defaults_to_payload(payload)
    return _apply_sales_line_item_price_defaults(payload)


GENERAL_VENDOR_NO = 'VENDOR-000001'


def _is_general_vendor(vendor=None, vendor_no: str | None = None) -> bool:
    """True for the system general vendor or any vendor whose no/name contains 'general'."""
    if vendor is not None:
        no = (getattr(vendor, 'no', None) or '').strip().lower()
        name = (getattr(vendor, 'name', None) or '').strip().lower()
        if no == GENERAL_VENDOR_NO.lower():
            return True
        return 'general' in no or 'general' in name
    if vendor_no:
        normalized = str(vendor_no).strip().lower()
        if normalized == GENERAL_VENDOR_NO.lower():
            return True
        return 'general' in normalized
    return False


def _payment_method_prefers_cash_default():
    from financials.models import PaymentMethod

    cash = (
        PaymentMethod.objects.exclude(code='NOT_PAID')
        .filter(bal_account_no__isnull=False)
        .order_by('code')
        .first()
    )
    if cash:
        return cash
    return PaymentMethod.objects.exclude(code='NOT_PAID').order_by('code').first()


def _filter_payment_method_relation_qs(qs, *, source_table: str | None, field_name: str | None, record_values: dict):
    if source_table != 'PurchaseInvoice' or field_name != 'payment_method':
        return qs
    vendor_no = record_values.get('vendor')
    if not _is_general_vendor(vendor_no=vendor_no):
        return qs
    return qs.exclude(code='NOT_PAID')


_SALES_LINE_ITEM_SOURCE_TABLES = frozenset({
    'SalesInvoiceLine',
    'SalesOrderLine',
})


def _item_on_hand_for_sales(item, request) -> Decimal | None:
    """Branch-aware on-hand qty for Inventory items; None for Service / Non-Inventory."""
    from items.enums import InventoryType
    from items.models import ItemLedgerEntries

    if getattr(item, 'type', None) in (
        InventoryType.Service.value,
        InventoryType.NonInventory.value,
    ):
        return None

    ile = ItemLedgerEntries.objects.filter(item=item)
    try:
        from financials.models import GeneralLedgerSetup

        gl_setup = GeneralLedgerSetup.objects.first()
        if gl_setup and getattr(gl_setup, 'enable_multiple_branches', False) and request:
            from dimension.branch_filter import get_branch_for_request

            branch = None
            try:
                branch = get_branch_for_request(request)
            except Exception:
                branch = None
            if not branch:
                branch = getattr(getattr(request, 'user', None), 'global_dimension_1', None)
            if branch:
                ile = ile.filter(global_dimension_1=branch)
    except Exception:
        pass
    return ile.aggregate(total=Sum('remaining_quantity'))['total'] or 0


def _validate_sales_line_item_in_stock(item, request, *, previous_item=None) -> None:
    """Block assigning blocked or out-of-stock inventory items on sales lines."""
    if item is None:
        return
    if previous_item is not None and getattr(previous_item, 'pk', None) == getattr(item, 'pk', None):
        return
    name = getattr(item, 'item_name', None) or getattr(item, 'no', 'Item')
    if getattr(item, 'blocked', False):
        raise ValueError(f'{name} is blocked and cannot be sold.')
    on_hand = _item_on_hand_for_sales(item, request)
    if on_hand is not None and on_hand <= 0:
        raise ValueError(f'{name} is out of stock and cannot be selected.')


def _filter_sales_item_relation_qs(qs, *, source_table: str | None, model, request):
    """Hide blocked / out-of-stock Inventory items from sales line Item pickers."""
    if model.__name__ != 'Item':
        return qs
    if source_table not in _SALES_LINE_ITEM_SOURCE_TABLES:
        return qs

    from items.enums import InventoryType
    from items.models import ItemLedgerEntries

    qs = qs.filter(blocked=False)

    ile_qs = ItemLedgerEntries.objects.filter(item=OuterRef('pk'))
    try:
        from financials.models import GeneralLedgerSetup

        gl_setup = GeneralLedgerSetup.objects.first()
        if gl_setup and getattr(gl_setup, 'enable_multiple_branches', False) and request:
            from dimension.branch_filter import get_branch_for_request

            branch = get_branch_for_request(request)
            if not branch:
                branch = getattr(request.user, 'global_dimension_1', None)
            if branch:
                ile_qs = ile_qs.filter(global_dimension_1=branch)
    except Exception:
        pass

    on_hand = (
        ile_qs.values('item')
        .annotate(total=Sum('remaining_quantity'))
        .values('total')
    )
    on_hand_field = django_models.DecimalField(max_digits=28, decimal_places=5)
    qs = qs.annotate(
        _sales_on_hand=Coalesce(
            Subquery(on_hand, output_field=on_hand_field),
            Value(0, output_field=on_hand_field),
        ),
    )
    non_stock = [
        InventoryType.Service.value,
        InventoryType.NonInventory.value,
    ]
    return qs.filter(
        Q(type__in=non_stock) | Q(_sales_on_hand__gt=0),
    )


def _validate_purchase_invoice_payment_method(vendor, payment_method) -> None:
    if payment_method is None:
        return
    from financials.models import PaymentMethod

    pm = payment_method
    if isinstance(payment_method, (str, int)):
        lookup = {'code': payment_method} if isinstance(payment_method, str) else {'pk': payment_method}
        pm = PaymentMethod.objects.filter(**lookup).first()
    if pm and getattr(pm, 'code', None) == 'NOT_PAID' and _is_general_vendor(vendor):
        raise ValueError(
            "General vendor cannot have 'Not Paid Yet' as payment method. "
            'Please select a different payment method.',
        )


def _default_purchase_invoice_payment_method(vendor=None):
    from financials.models import PaymentMethod

    if _is_general_vendor(vendor):
        return _payment_method_prefers_cash_default()

    if vendor is not None and getattr(vendor, 'payment_method', None):
        return vendor.payment_method
    return PaymentMethod.objects.filter(code='NOT_PAID').first() or PaymentMethod.objects.order_by('id').first()


def _apply_purchase_invoice_payment_method_defaults(defaults: dict) -> dict:
    if defaults.get('payment_method') is not None:
        return defaults
    vendor = defaults.get('vendor')
    payment_method = _default_purchase_invoice_payment_method(vendor)
    if payment_method is not None:
        defaults['payment_method'] = payment_method
    return defaults


def _sync_purchase_invoice_payment_method_from_vendor(obj, user) -> None:
    if obj.__class__.__name__ != 'PurchaseInvoice':
        return
    vendor = getattr(obj, 'vendor', None)
    if _is_general_vendor(vendor):
        if obj.payment_method and obj.payment_method.code == 'NOT_PAID':
            replacement = _payment_method_prefers_cash_default()
            if replacement and obj.payment_method_id != replacement.pk:
                obj.payment_method = replacement
                _save_page_field_update(obj, user, 'payment_method')
        return
    vendor_pm = getattr(vendor, 'payment_method', None) if vendor else None
    if vendor_pm is None:
        return
    if obj.payment_method_id == vendor_pm.pk:
        return
    obj.payment_method = vendor_pm
    _save_page_field_update(obj, user, 'payment_method')


def _apply_invoice_header_defaults(model, defaults: dict, request) -> dict:
    """Stamp branch/dimension defaults when creating invoice headers via dynamic pages."""
    from dimension.branch_filter import get_branch_for_request
    from dimension.utils import get_first_branch_dimension_value

    if defaults.get('global_dimension_1') is None:
        branch = get_branch_for_request(request) if request else None
        if not branch and request and getattr(request, 'user', None):
            branch = getattr(request.user, 'global_dimension_1', None)
        if not branch:
            branch = get_first_branch_dimension_value()
        if branch:
            defaults['global_dimension_1'] = branch

    if model.__name__ == 'PurchaseInvoice':
        defaults = _apply_purchase_invoice_payment_method_defaults(defaults)

    if defaults.get('dimension_set') is None:
        if model.__name__ == 'PurchaseInvoice':
            from dimension.models import get_posting_dimension_payload

            payload = get_posting_dimension_payload(
                global_dimension_1=defaults.get('global_dimension_1'),
                global_dimension_2=defaults.get('global_dimension_2'),
                dimension_set=None,
            )
            if payload.get('dimension_set') is not None:
                defaults['dimension_set'] = payload['dimension_set']
            if payload.get('global_dimension_1') is not None:
                defaults['global_dimension_1'] = payload['global_dimension_1']
            if payload.get('global_dimension_2') is not None:
                defaults['global_dimension_2'] = payload['global_dimension_2']
        elif model.__name__ == 'SalesInvoice' and defaults.get('global_dimension_1') is not None:
            try:
                from financials.models import GeneralLedgerSetup
                from dimension.models import get_or_create_dimension_set

                gl_setup = GeneralLedgerSetup.objects.first()
                if gl_setup and getattr(gl_setup, 'global_dimension_1_id', None):
                    defaults['dimension_set'] = get_or_create_dimension_set(
                        {gl_setup.global_dimension_1: defaults['global_dimension_1']}
                    )
            except Exception:
                pass

    return defaults


def _apply_sales_invoice_line_defaults(payload: dict, request) -> dict:
    from dimension.models import get_merged_line_dimensions

    if not (payload.get('global_dimension_1') and payload.get('dimension_set')):
        sales_invoice = payload.get('sales_invoice')
        if sales_invoice is None and payload.get('sales_invoice_id'):
            from sales.models import SalesInvoice
            sales_invoice = SalesInvoice.objects.filter(pk=payload['sales_invoice_id']).first()

        customer_no = None
        if sales_invoice and getattr(sales_invoice, 'customer', None):
            customer_no = getattr(sales_invoice.customer, 'no', None)

        item = payload.get('item')
        dims = get_merged_line_dimensions(
            customer_no=customer_no,
            item=item,
            request_user=getattr(request, 'user', None),
            line_data=payload,
            header_dimensions=sales_invoice,
        )
        if dims.get('global_dimension_1') and not payload.get('global_dimension_1'):
            payload['global_dimension_1'] = dims['global_dimension_1']
        if dims.get('dimension_set') and not payload.get('dimension_set'):
            payload['dimension_set'] = dims['dimension_set']
    if not payload.get('type'):
        payload['type'] = 'item'
    if not payload.get('quantity'):
        payload['quantity'] = 0
    payload = _apply_item_line_defaults_to_payload(payload)
    return _apply_sales_line_item_price_defaults(payload)


def _apply_purchase_invoice_line_defaults(payload: dict, request) -> dict:
    line_type = payload.get('type') or 'item'
    payload.setdefault('type', line_type)

    if payload.get('global_dimension_1') and payload.get('dimension_set'):
        if line_type == 'item' and not payload.get('location_code'):
            loc = _resolve_branch_location_for_request(request)
            if loc:
                payload['location_code'] = loc
        if line_type == 'item':
            return _apply_purchase_invoice_line_item_defaults(payload)
        if line_type == 'resource' and payload.get('resource') and not payload.get('description'):
            from resources.models import Resource
            resource = payload['resource']
            if not isinstance(resource, Resource):
                resource = Resource.objects.filter(pk=resource).first() if str(resource).isdigit() else Resource.objects.filter(code=resource).first()
            if resource:
                payload['description'] = resource.name
        return payload

    from dimension.models import get_merged_line_dimensions

    purchase_invoice = payload.get('purchase_invoice')
    if purchase_invoice is None and payload.get('purchase_invoice_id'):
        from purchases.models import PurchaseInvoice
        purchase_invoice = PurchaseInvoice.objects.filter(pk=payload['purchase_invoice_id']).first()

    # Empty Add Line must stay blank — never auto-pick the first Item as a placeholder.
    if line_type == 'item' and not payload.get('location_code'):
        loc = _resolve_branch_location_for_request(request)
        if loc:
            payload['location_code'] = loc

    vendor_no = None
    if purchase_invoice and getattr(purchase_invoice, 'vendor', None):
        vendor_no = getattr(purchase_invoice.vendor, 'no', None)

    item = payload.get('item') if line_type == 'item' else None
    resource = payload.get('resource') if line_type == 'resource' else None
    dims = get_merged_line_dimensions(
        vendor_no=vendor_no,
        item=item,
        resource=resource,
        request_user=getattr(request, 'user', None),
        line_data=payload,
        header_dimensions=purchase_invoice,
    )
    if dims.get('global_dimension_1') and not payload.get('global_dimension_1'):
        payload['global_dimension_1'] = dims['global_dimension_1']
    if dims.get('dimension_set') and not payload.get('dimension_set'):
        payload['dimension_set'] = dims['dimension_set']
    if line_type == 'item':
        return _apply_purchase_invoice_line_item_defaults(payload)
    if not payload.get('quantity'):
        payload['quantity'] = 1
    return payload


def _apply_tracking_specification_defaults(payload: dict, request) -> dict:
    from purchases.models import PurchaseInvoiceLine

    line_id = payload.get('purchase_invoice_line') or payload.get('purchase_invoice_line_id')
    if line_id:
        line = (
            PurchaseInvoiceLine.objects.select_related(
                'purchase_invoice',
                'item',
                'item_unit_of_measure',
                'location_code',
            )
            .filter(pk=line_id)
            .first()
        )
        if line:
            # Always overwrite — never keep a stale/wrong item from the client.
            payload['purchase_invoice'] = line.purchase_invoice
            payload['purchase_invoice_line'] = line
            if line.item_id:
                payload['item'] = line.item
            if line.location_code_id:
                payload['location_code'] = line.location_code
    if not payload.get('location_code'):
        location = _resolve_branch_location_for_request(request)
        if location:
            payload['location_code'] = location
    if not payload.get('quantity_base'):
        payload['quantity_base'] = 1
    if payload.get('description') is None:
        payload['description'] = ''
    if request and getattr(request, 'user', None) and not payload.get('user'):
        payload['user'] = request.user
    return payload


def _normalize_create_payload(payload: dict, model) -> dict:
    """Map page-engine field names to ORM and drop keys that are not model fields."""
    out = dict(payload)
    if 'SystemId' in out:
        system_id = out.pop('SystemId')
        if system_id and 'system_id' not in out:
            out['system_id'] = system_id

    valid = {f.name for f in model._meta.get_fields() if f.concrete and not f.many_to_many}
    valid |= {
        f'{f.name}_id'
        for f in model._meta.fields
        if getattr(f, 'is_relation', False)
    }
    return {k: v for k, v in out.items() if k in valid}


def _apply_sequential_line_no_default(payload: dict, model, parent_field: str) -> dict:
    """Assign next line_no (BC-style increments of 10000) when creating document lines."""
    if payload.get('line_no') is not None:
        return payload

    parent = payload.get(parent_field)
    parent_id = payload.get(f'{parent_field}_id')
    filter_kwargs = {}
    if parent is not None:
        filter_kwargs[parent_field] = parent
    elif parent_id is not None:
        filter_kwargs[f'{parent_field}_id'] = parent_id
    else:
        payload.setdefault('line_no', 10000)
        return payload

    max_line = model.objects.filter(**filter_kwargs).aggregate(m=Max('line_no'))['m'] or 0
    payload['line_no'] = max_line + 10000
    if not payload.get('row_no'):
        payload['row_no'] = str(payload['line_no'])
    return payload


def _apply_financial_report_row_line_defaults(payload: dict) -> dict:
    from financials import enums as fin_enums

    payload.setdefault('row_type', fin_enums.FinancialReportRowType.Posting.value)
    payload.setdefault('row_amount_basis', fin_enums.FinancialReportColumnType.Net_Change.value)
    payload.setdefault('totaling_type', fin_enums.FinancialReportTotalingType.Posting_Accounts.value)
    payload.setdefault('amount_type', fin_enums.FinancialReportAmountType.Net_Amount.value)
    payload.setdefault('show', fin_enums.FinancialReportShowLine.Yes.value)
    return payload


def _apply_line_defaults(payload: dict, request, model) -> dict:
    model_name = model.__name__
    if model_name == 'SalesOrderLine':
        return _apply_sales_order_line_defaults(payload, request)
    if model_name == 'SalesInvoiceLine':
        return _apply_sales_invoice_line_defaults(payload, request)
    if model_name == 'PurchaseInvoiceLine':
        return _apply_purchase_invoice_line_defaults(payload, request)
    if model_name == 'TrackingSpecification':
        return _apply_tracking_specification_defaults(payload, request)
    if model_name == 'ItemUnitOfMeasure':
        payload.setdefault('quantity_per_unit', 1)
    if model_name in ('GeneralJournalLine', 'CashReceiptJournalLine'):
        payload.setdefault('status', 'Open')
        batch_name = payload.get('batch_name')
        if batch_name:
            payload['batch_name'] = str(batch_name).strip().upper()
    if model_name == 'GeneralJournalLine':
        payload.setdefault('document_type', 'Payment')
    if model_name in ('PaymentLine', 'CashReceiptJournalLine', 'GeneralJournalLine'):
        payload = _apply_account_line_defaults(payload)
    if model_name == 'FinancialReportRowLine':
        payload = _apply_sequential_line_no_default(payload, model, 'row_group')
        payload = _apply_financial_report_row_line_defaults(payload)
    if model_name == 'FinancialReportColumnLine':
        payload = _apply_sequential_line_no_default(payload, model, 'column_group')
    return payload


def _get_schema(request) -> str | None:
    """Extract tenant schema from JWT token claim."""
    auth = getattr(request, 'auth', None)
    if auth is None:
        return None
    try:
        return auth.get('schema_name') or auth['schema_name']
    except (KeyError, AttributeError, TypeError):
        return None


def _get_request_enabled_modules(request, schema: str | None = None) -> list[str]:
    """Resolve tenant enabled_modules from middleware, request.tenant, or schema."""
    enabled = getattr(request, 'enabled_modules', None)
    if enabled:
        return list(enabled)

    tenant = getattr(request, 'tenant', None)
    if tenant is not None and hasattr(tenant, 'enabled_modules'):
        return list(tenant.enabled_modules or [])

    if schema:
        try:
            from company.models import Company

            company = Company.objects.get(schema_name=schema)
            return list(company.enabled_modules or [])
        except Exception:
            pass
    return []


def _resolve_card_control(page: Page, control_id=None):
    """First Group control, else first control — same resolution as GET record."""
    if control_id:
        return page.page_controls.filter(pk=control_id).first()
    return page.page_controls.filter(control_type='Group').first() or page.page_controls.first()


def _serialization_fields(control: PageControl) -> list[PageControlField]:
    """Visible page fields plus hidden primary-key fields (needed for apply/actions)."""
    visible = list(control.fields.filter(visible=True).order_by('tab_index'))
    visible_names = {f.name for f in visible}
    hidden_pk = control.fields.filter(primary_key=True).exclude(
        name__in=visible_names,
    ).order_by('tab_index')
    return sorted([*visible, *hidden_pk], key=lambda f: f.tab_index)


def _record_fields_for_page(page: Page, control=None) -> list:
    """Card pages serialize all Group fields; other pages use one control."""
    if page.page_type == 'Card':
        qs = (
            PageControlField.objects.filter(
                page=page,
                page_control__control_type='Group',
                visible=True,
            )
            .select_related('page_control')
            .order_by('page_control__tab_index', 'tab_index', 'page_control_field_id')
        )
        seen: set[str] = set()
        fields: list[PageControlField] = []
        for field in qs:
            if field.name in seen:
                continue
            seen.add(field.name)
            fields.append(field)
        if fields:
            return fields
    if control is not None:
        return _serialization_fields(control)
    fallback = _resolve_card_control(page)
    if fallback:
        return _serialization_fields(fallback)
    return []


def _serialize_page_record(page: Page, obj, control_id=None, request=None) -> dict:
    control = None if page.page_type == 'Card' else _resolve_card_control(page, control_id)
    fields = _record_fields_for_page(page, control)
    if not fields:
        return {'SystemId': str(getattr(obj, 'system_id', obj.pk))}
    return _serialize_record(obj, fields, request)


# ── Page action handlers ───────────────────────────────────────────────────────

def block_item(record, request):
    record.blocked = True
    record.save(update_fields=['blocked'])
    return record


def block_customer(record, request):
    if not hasattr(record, 'blocked'):
        raise ValueError('Customer does not support block action')
    record.blocked = True
    record.save(update_fields=['blocked'])
    return record


def _format_preview_account(obj):
    from payments.posting_preview import format_preview_account
    return format_preview_account(obj)


def _append_preview_ledger_rows(rows, entries, ledger_type, account_key, line_no):
    from payments.posting_preview import append_preview_ledger_rows
    return append_preview_ledger_rows(rows, entries, ledger_type, account_key, line_no)


def _build_payment_journal_preview_content(payment_journal, entries):
    from payments.posting_preview import build_posting_preview_content
    return build_posting_preview_content(
        entries,
        message=f'Preview posting for payment {payment_journal.document_no}',
        batch_name=payment_journal.document_no,
    )


def preview_payment_journal(record, request):
    import uuid

    from payments.admin import PaymentJournalProcessor
    from payments.posting_prepare import prepare_payment_journal_for_posting

    receipt_no = (
        f"RCP-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
    )

    prepare_payment_journal_for_posting(record)
    record.refresh_from_db()

    record.full_clean()
    record.clean()

    processor = PaymentJournalProcessor(record, request, receipt_no)
    entries = processor.process()

    if isinstance(entries, dict) and entries.get('success') is False:
        raise ValueError(entries.get('message', 'Preview failed'))

    has_rows = any(
        entries.get(key)
        for key in (
            'gl_entries',
            'vendor_entries',
            'customer_entries',
            'detailed_vendor_entries',
            'detailed_customer_entries',
            'bank_account_entries',
        )
    )
    if not has_rows:
        raise ValueError('Preview returned no entries')

    content = _build_payment_journal_preview_content(record, entries)
    return {'command': 'PREVIEW', 'content': content}


def _ensure_purchase_invoice_vendor_invoice_no(invoice):
    """Auto-fill vendor invoice no. when empty (lay users may not have a vendor bill number)."""
    from purchases.invoice_numbers import ensure_purchase_invoice_vendor_invoice_no

    ensure_purchase_invoice_vendor_invoice_no(invoice)


def _validate_purchase_invoice_for_posting(invoice):
    """Shared validation before preview/post (mirrors PurchaseInvoiceAdmin.preview_posting)."""
    _ensure_purchase_invoice_vendor_invoice_no(invoice)
    invoice.full_clean()
    invoice.clean()
    is_valid, errors = invoice.validate_all_tracking_specifications()
    if not is_valid:
        raise ValueError('; '.join(errors))
    for line in invoice.lines.all():
        line.full_clean()
        line.clean()


def preview_purchase_invoice(record, request):
    from purchases.admin import PurchaseInvoiceProcessor
    from payments.posting_preview import (
        build_posting_preview_content,
        processor_entries_have_rows,
    )

    _validate_purchase_invoice_for_posting(record)

    receipt_no = (
        f"RCP-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
    )
    processor = PurchaseInvoiceProcessor(record, request, receipt_no)
    entries = processor.process()

    if isinstance(entries, dict) and entries.get('success') is False:
        raise ValueError(entries.get('message', 'Preview failed'))

    if not processor_entries_have_rows(entries):
        raise ValueError('Preview returned no entries')

    content = build_posting_preview_content(
        entries,
        message=f'Preview posting for purchase invoice {record.invoice_no}',
        batch_name=record.invoice_no,
    )
    return {'command': 'PREVIEW', 'content': content}


def post_purchase_invoice(record, request):
    from authentication.models import UserSetup
    from purchases.admin import PurchaseInvoicePostingProcessor

    if record.status == 'Posted':
        raise ValueError('This purchase invoice has already been posted.')

    user_setup = UserSetup.get_or_create_for_user(request.user)
    today = timezone.now().date()

    if record.document_date and record.document_date < today:
        if not user_setup.can_post_previous_dates:
            raise ValueError(
                f'Document date ({record.document_date}) is in the past. '
                'You do not have permission to post purchases for previous dates.'
            )

    if record.posting_date and record.posting_date < today:
        if not user_setup.can_post_previous_dates:
            raise ValueError(
                f'Posting date ({record.posting_date}) is in the past. '
                'You do not have permission to post purchases for previous dates.'
            )

    is_valid, errors = record.validate_all_tracking_specifications()
    if not is_valid:
        raise ValueError('; '.join(errors))

    _ensure_purchase_invoice_vendor_invoice_no(record)

    receipt_no = (
        f"RCP-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
    )
    processor = PurchaseInvoicePostingProcessor(record, request, receipt_no)

    with transaction.atomic():
        result = processor.post()
        if not result.get('success'):
            raise ValueError(result.get('message', 'Unknown error during posting'))

    record.refresh_from_db()
    return record


def _resolve_sales_invoice_for_credit_memo(credit_memo):
    from sales.models import SalesInvoice

    posted_invoice = credit_memo.original_invoice
    if not posted_invoice:
        raise ValueError('Credit memo is not linked to an original posted invoice.')

    customer_invoice_no = getattr(posted_invoice, 'customer_invoice_no', None)
    sales_invoice = None
    if customer_invoice_no:
        sales_invoice = SalesInvoice.objects.filter(
            customer_invoice_no=customer_invoice_no,
            customer=posted_invoice.customer,
            status='Posted',
        ).first()
    if not sales_invoice:
        sales_invoice = SalesInvoice.objects.filter(
            customer=posted_invoice.customer,
            document_date=posted_invoice.document_date,
            status='Posted',
        ).first()
    if not sales_invoice:
        raise ValueError(
            f'Could not find original Sales Invoice for credit memo {credit_memo.credit_memo_no}.',
        )
    return sales_invoice


def _credit_memo_reversal_wrapper(sales_invoice):
    from sales.models import SalesCreditMemo

    class ReversalInvoiceWrapper:
        def __init__(self, invoice):
            self.no = invoice.invoice_no
            self.customer = invoice.customer
            self.document_date = invoice.document_date
            self.posting_date = invoice.posting_date
            self.vat_date = getattr(invoice, 'vat_date', None)
            self.due_date = getattr(invoice, 'due_date', None)
            self.customer_invoice_no = getattr(invoice, 'customer_invoice_no', None)
            self.status = invoice.status
            self.reversed = False
            self.posted_sales_invoice_lines = invoice.lines
            self.credit_memos = SalesCreditMemo.objects.none()

    return ReversalInvoiceWrapper(sales_invoice)


def _validate_sales_invoice_for_posting(invoice):
    """Shared validation before preview/post (mirrors SalesInvoiceAdmin.preview_posting)."""
    if invoice.status == 'Posted':
        raise ValueError('This sales invoice has already been posted.')
    if not invoice.payment_method:
        raise ValueError(
            f'Invoice {invoice.invoice_no} does not have a payment method set. '
            'Choose how you paid before posting.',
        )
    invoice.full_clean()
    invoice.clean()
    for line in invoice.lines.all():
        line.full_clean()
        line.clean()


def _sales_invoice_insufficient_inventory_message(entries) -> str | None:
    insufficient_items = []
    for item_preview in entries.get('inventory_reduction_preview', []):
        reduction = item_preview.get('reduction_info') or {}
        if not reduction.get('insufficient_inventory'):
            continue
        item = item_preview.get('item')
        item_name = getattr(item, 'item_name', None) or str(item)
        insufficient_items.append(
            {
                'item': item_name,
                'shortage': reduction.get('remaining_after_reduction'),
                'requested': item_preview.get('quantity_to_reduce'),
            },
        )
    if not insufficient_items:
        return None
    lines = [
        'Cannot post invoice due to insufficient inventory:',
    ]
    for item in insufficient_items:
        lines.append(
            f"• {item['item']}: Requested {item['requested']:.2f} units, "
            f"Shortage: {item['shortage']:.2f} units",
        )
    return '\n'.join(lines)


def preview_sales_invoice(record, request):
    from payments.posting_preview import (
        build_posting_preview_content,
        processor_entries_have_rows,
    )
    from sales.admin import SalesInvoiceProcessor

    _validate_sales_invoice_for_posting(record)

    receipt_no = (
        f"RCP-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
    )
    processor = SalesInvoiceProcessor(record, request, receipt_no)
    entries = processor.process()

    if isinstance(entries, dict) and entries.get('success') is False:
        raise ValueError(entries.get('message', 'Preview failed'))

    if not processor_entries_have_rows(entries):
        raise ValueError('Preview returned no entries')

    content = build_posting_preview_content(
        entries,
        message=f'Preview posting for sales invoice {record.invoice_no}',
        batch_name=record.invoice_no,
    )
    return {'command': 'PREVIEW', 'content': content}


def post_sales_invoice(record, request):
    from sales.admin import SalesInvoicePostingProcessor, SalesInvoiceProcessor

    _validate_sales_invoice_for_posting(record)

    receipt_no = (
        f"RCP-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
    )
    preview_processor = SalesInvoiceProcessor(record, request, receipt_no)
    entries = preview_processor.process()

    if isinstance(entries, dict) and entries.get('success') is False:
        raise ValueError(entries.get('message', 'Unknown error during posting'))

    inventory_error = _sales_invoice_insufficient_inventory_message(entries)
    if inventory_error:
        raise ValueError(inventory_error)

    processor = SalesInvoicePostingProcessor(record, request, receipt_no)
    with transaction.atomic():
        result = processor.post()
        if not result.get('success'):
            raise ValueError(result.get('message', 'Unknown error during posting'))

    record.refresh_from_db()
    return record


def preview_sales_credit_memo(record, request):
    from payments.posting_preview import (
        build_posting_preview_content,
        processor_entries_have_rows,
    )
    from sales.admin import SalesInvoiceReversalProcessor

    if record.status == 'Posted':
        raise ValueError('This credit memo has already been posted.')
    if not record.original_invoice:
        raise ValueError('Credit memo is not linked to an original posted invoice.')

    sales_invoice = _resolve_sales_invoice_for_credit_memo(record)
    wrapper = _credit_memo_reversal_wrapper(sales_invoice)
    processor = SalesInvoiceReversalProcessor(wrapper, request)
    entries = processor.process()

    if isinstance(entries, dict) and entries.get('success') is False:
        raise ValueError(entries.get('message', 'Preview failed'))
    if not processor_entries_have_rows(entries):
        raise ValueError('Preview returned no entries')

    content = build_posting_preview_content(
        entries,
        message=f'Preview posting for credit memo {record.credit_memo_no}',
        batch_name=record.credit_memo_no,
    )
    return {'command': 'PREVIEW', 'content': content}


def post_sales_credit_memo(record, request):
    from sales.admin import SalesCreditMemoPostingProcessor

    if record.status == 'Posted':
        raise ValueError('This credit memo has already been posted.')
    if not record.original_invoice:
        raise ValueError('Credit memo is not linked to an original posted invoice.')

    processor = SalesCreditMemoPostingProcessor(record, request)
    with transaction.atomic():
        result = processor.post()
        if not result.get('success'):
            raise ValueError(result.get('message', 'Unknown error during posting'))

    record.refresh_from_db()
    return record


def create_corrective_sales_credit_memo_action(record, request):
    """BC Create Corrective Credit Memo — opens Draft CM for manual edit/post."""
    from sales.views import create_corrective_sales_credit_memo

    result = create_corrective_sales_credit_memo(record, request)
    credit_memo = result['credit_memo']
    created = result.get('created', True)
    no = getattr(credit_memo, 'credit_memo_no', None) or getattr(credit_memo, 'no', '')
    message = (
        f'Credit memo {no} created. Adjust quantities or lines, then Post.'
        if created
        else f'Opening existing draft credit memo {no}.'
    )
    return {
        'command': 'NAVIGATE',
        'content': {
            'PageName': result['page_name'],
            'SystemId': str(credit_memo.system_id),
            'Message': message,
        },
    }


def create_corrective_purchase_credit_memo_action(record, request):
    """BC Create Corrective Credit Memo — opens Open CM for manual edit/post."""
    from purchases.views import create_corrective_purchase_credit_memo

    result = create_corrective_purchase_credit_memo(record, request)
    credit_memo = result['credit_memo']
    created = result.get('created', True)
    no = getattr(credit_memo, 'no', '') or ''
    message = (
        f'Credit memo {no} created. Adjust quantities or lines, then Post.'
        if created
        else f'Opening existing open credit memo {no}.'
    )
    return {
        'command': 'NAVIGATE',
        'content': {
            'PageName': result['page_name'],
            'SystemId': str(credit_memo.system_id),
            'Message': message,
        },
    }


def find_entries_posted_purchase_invoice(record, request):
    """BC Page 344 Find Entries — related ledgers for a posted purchase invoice."""
    from pages.find_entries import build_find_entries_for_posted_purchase

    content = build_find_entries_for_posted_purchase(record)
    ledger_rows = [
        r for r in (content.get('RelatedEntries') or [])
        if r.get('TableKey') != 'source_document'
    ]
    if not ledger_rows:
        raise ValueError('No related ledger entries found for this document.')
    return {'command': 'PREVIEW', 'content': content}


def find_entries_posted_sales_invoice(record, request):
    """BC Page 344 Find Entries — related ledgers for a posted sales invoice."""
    from pages.find_entries import build_find_entries_for_posted_sales

    content = build_find_entries_for_posted_sales(record)
    ledger_rows = [
        r for r in (content.get('RelatedEntries') or [])
        if r.get('TableKey') != 'source_document'
    ]
    if not ledger_rows:
        raise ValueError('No related ledger entries found for this document.')
    return {'command': 'PREVIEW', 'content': content}


def post_purchase_credit_memo(record, request):
    from purchases.admin import PurchaseCreditMemoPostingProcessor
    import uuid

    if record.status == 'Posted':
        raise ValueError('This credit memo has already been posted.')
    if not record.original_posted_invoice_id and not record.original_invoice_no:
        raise ValueError('Credit memo is not linked to an original posted invoice.')

    receipt_no = (
        f"RCP-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
    )
    processor = PurchaseCreditMemoPostingProcessor(record, request, receipt_no)
    with transaction.atomic():
        result = processor.post()
        if not result.get('success'):
            raise ValueError(result.get('message', 'Unknown error during posting'))

    record.refresh_from_db()
    return record


def post_payment_journal(record, request):
    import uuid

    from django.db import transaction

    from payments.admin import PaymentJournalPostingProcessor
    from payments.enums import PaymentStatus
    from payments.posting_prepare import prepare_payment_journal_for_posting

    if record.status == PaymentStatus.POSTED.value:
        raise ValueError('This payment journal has already been posted.')

    receipt_no = (
        f"RCP-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
    )

    prepare_payment_journal_for_posting(record)
    record.refresh_from_db()

    record.full_clean()
    record.clean()

    processor = PaymentJournalPostingProcessor(record, request, receipt_no)
    with transaction.atomic():
        result = processor.post()
        if not result.get('success'):
            raise ValueError(result.get('message', 'Unknown error during posting'))
        record.status = PaymentStatus.POSTED.value
        record.save(update_fields=['status', 'updated_at'])

    record.refresh_from_db()
    return record


def post_item_journal(record, request):
    from items.posting import ItemJournalFinalPoster

    preview_data = _run_item_journal_preview(record, request)
    poster = ItemJournalFinalPoster(preview_data, record, request.user)
    poster.post_to_tables()
    record.refresh_from_db()
    return record


def _run_item_journal_preview(record, request):
    """Shared validation + preview processor for item journals."""
    from common.enums import Status
    from items.admin import ItemJournalPreviewProcessor

    if record.status == Status.Posted.value:
        raise ValueError('This journal has already been posted.')

    receipt_no = f"RCP-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"

    from django.contrib.messages.storage.base import BaseStorage
    from django.contrib.messages import constants

    class ValidationMessageStorage(BaseStorage):
        def __init__(self, request):
            super().__init__(request)
            self.validation_errors = []

        def add(self, level, message, extra_tags=''):
            if level == constants.ERROR:
                self.validation_errors.append(message)

        def _get(self, *args, **kwargs):
            return [], True

        def _store(self, messages, response, *args, **kwargs):
            return []

    original_messages = getattr(request, '_messages', None)
    validation_storage = ValidationMessageStorage(request)
    request._messages = validation_storage
    try:
        previewer = ItemJournalPreviewProcessor(
            record, request, receipt_no=receipt_no,
        )
        preview_data = previewer.process()
    finally:
        if original_messages is not None:
            request._messages = original_messages
        elif hasattr(request, '_messages'):
            delattr(request, '_messages')

    if not preview_data or (
        isinstance(preview_data, dict) and not any(preview_data.values())
    ):
        errors = validation_storage.validation_errors or ['Journal failed validation.']
        raise ValueError('; '.join(str(e) for e in errors))
    return preview_data


def preview_item_journal(record, request):
    from payments.posting_preview import build_posting_preview_content

    preview_data = _run_item_journal_preview(record, request)
    content = build_posting_preview_content(
        preview_data,
        message=f'Preview posting for journal {record.document_no}',
        batch_name=record.document_no,
    )
    # Item journals may only produce item/value entries; still show GL when present.
    if not content.get('Entries') and not content.get('RelatedEntries'):
        # Fallback flat rows from item ledger preview so the dialog is never empty
        rows = []
        for i, entry in enumerate(preview_data.get('item_entries') or [], start=1):
            amount = float(entry.get('total') or 0)
            rows.append({
                'Line': i,
                'Side': 'Debit' if amount >= 0 else 'Credit',
                'LedgerType': 'Item',
                'Account': str(entry.get('item') or 'Item'),
                'Amount': abs(amount),
            })
        for i, entry in enumerate(preview_data.get('gl_entries') or [], start=len(rows) + 1):
            amount = float(entry.get('amount') or 0)
            gl = entry.get('gl_account')
            account = getattr(gl, 'no', None) or str(gl or 'G/L')
            rows.append({
                'Line': i,
                'Side': 'Debit' if amount >= 0 else 'Credit',
                'LedgerType': 'G/L',
                'Account': account,
                'Amount': abs(amount),
            })
        content['Entries'] = rows
        if not rows:
            raise ValueError('Preview returned no entries')
    return {'command': 'PREVIEW', 'content': content}


def preview_general_journal_batch_handler(_record, request):
    batch_name = request.data.get('BatchName') or request.data.get('batchName')
    if not batch_name:
        raise ValueError('BatchName is required for general journal actions.')
    from financials.services.general_journal_posting import preview_general_journal_batch

    return preview_general_journal_batch(str(batch_name), request)


def post_general_journal_batch_handler(_record, request):
    batch_name = request.data.get('BatchName') or request.data.get('batchName')
    if not batch_name:
        raise ValueError('BatchName is required for general journal actions.')
    from financials.services.general_journal_posting import post_general_journal_batch

    return post_general_journal_batch(str(batch_name), request)


def _parse_financial_report_dates(request, record=None) -> tuple[date, date]:
    start_raw = request.data.get('StartDate') or request.data.get('startDate')
    end_raw = request.data.get('EndDate') or request.data.get('endDate')
    if record is not None:
        if not start_raw and getattr(record, 'start_date', None):
            start_raw = record.start_date.isoformat()
        if not end_raw and getattr(record, 'end_date', None):
            end_raw = record.end_date.isoformat()
    if not start_raw or not end_raw:
        raise ValueError('Start date and end date are required.')
    try:
        start = datetime.strptime(str(start_raw)[:10], '%Y-%m-%d').date()
        end = datetime.strptime(str(end_raw)[:10], '%Y-%m-%d').date()
    except ValueError as exc:
        raise ValueError('Invalid date format. Use YYYY-MM-DD.') from exc
    if start > end:
        raise ValueError('Start date must be on or before end date.')
    return start, end


def recalculate_financial_report_handler(_record, request):
    report_name = request.data.get('BatchName') or request.data.get('batchName')
    if not report_name:
        raise ValueError('BatchName is required for financial report actions.')
    start_date, end_date = _parse_financial_report_dates(request)
    from financials.services.financial_report_service import generate_financial_report

    data = generate_financial_report(str(report_name), start_date, end_date)
    return {
        'command': 'REFRESH',
        'content': {
            'FinancialReport': data,
            'Message': 'Report recalculated',
        },
    }


def print_financial_report_handler(_record, request):
    import base64
    import re

    report_name = request.data.get('BatchName') or request.data.get('batchName')
    if not report_name:
        raise ValueError('BatchName is required for financial report actions.')
    export_format = (request.data.get('Format') or request.data.get('format') or '').lower()
    if export_format not in ('pdf', 'excel'):
        raise ValueError('Format must be pdf or excel.')
    start_date, end_date = _parse_financial_report_dates(request)
    from financials.services.financial_report_service import (
        FinancialReportService,
        generate_financial_report,
    )

    data = generate_financial_report(str(report_name), start_date, end_date)
    if export_format == 'pdf':
        file_bytes = FinancialReportService.generate_pdf(data)
        mime_type = 'application/pdf'
        extension = 'pdf'
    else:
        file_bytes = FinancialReportService.generate_excel(data)
        mime_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        extension = 'xlsx'

    safe_name = re.sub(r'[^\w\-]+', '-', str(report_name)).strip('-') or 'financial-report'
    filename = f"{safe_name}-{data.get('end_date') or end_date.isoformat()}.{extension}"
    return {
        'command': 'DOWNLOAD',
        'content': {
            'FileName': filename,
            'MimeType': mime_type,
            'FileBase64': base64.b64encode(file_bytes).decode('ascii'),
        },
    }


def _financial_report_name_from_record(record) -> str:
    return str(getattr(record, 'name', '') or getattr(record, 'pk', '')).strip()


def recalculate_financial_report_record_handler(record, request):
    report_name = _financial_report_name_from_record(record)
    if not report_name:
        raise ValueError('Financial report name is required.')
    request.data['BatchName'] = report_name
    request.data['batchName'] = report_name
    start_date, end_date = _parse_financial_report_dates(request, record)
    request.data['StartDate'] = start_date.isoformat()
    request.data['EndDate'] = end_date.isoformat()
    return recalculate_financial_report_handler(record, request)


def print_financial_report_record_handler(record, request):
    report_name = _financial_report_name_from_record(record)
    if not report_name:
        raise ValueError('Financial report name is required.')
    request.data['BatchName'] = report_name
    request.data['batchName'] = report_name
    start_date, end_date = _parse_financial_report_dates(request, record)
    request.data['StartDate'] = start_date.isoformat()
    request.data['EndDate'] = end_date.isoformat()
    return print_financial_report_handler(record, request)


ACTION_HANDLERS = {
    ('Item', 'block'): block_item,
    ('Customer', 'block'): block_customer,
    ('ItemJournal', 'post_item_journal'): post_item_journal,
    ('ItemJournal', 'preview_item_journal'): preview_item_journal,
    ('PaymentJournal', 'preview_payment_journal'): preview_payment_journal,
    ('PaymentJournal', 'post_payment_journal'): post_payment_journal,
    ('PurchaseInvoice', 'preview_purchase_invoice'): preview_purchase_invoice,
    ('PurchaseInvoice', 'post_purchase_invoice'): post_purchase_invoice,
    ('PostedPurchaseInvoice', 'create_corrective_credit_memo'): create_corrective_purchase_credit_memo_action,
    ('PostedPurchaseInvoice', 'reverse_transactions'): create_corrective_purchase_credit_memo_action,
    ('PostedPurchaseInvoice', 'find_entries'): find_entries_posted_purchase_invoice,
    ('SalesInvoice', 'preview_sales_invoice'): preview_sales_invoice,
    ('SalesInvoice', 'post_sales_invoice'): post_sales_invoice,
    ('SalesInvoice', 'create_corrective_credit_memo'): create_corrective_sales_credit_memo_action,
    ('SalesInvoice', 'reverse_transactions'): create_corrective_sales_credit_memo_action,
    ('PostedSalesInvoice', 'create_corrective_credit_memo'): create_corrective_sales_credit_memo_action,
    ('PostedSalesInvoice', 'reverse_transactions'): create_corrective_sales_credit_memo_action,
    ('PostedSalesInvoice', 'find_entries'): find_entries_posted_sales_invoice,
    ('SalesCreditMemo', 'preview_credit_memo'): preview_sales_credit_memo,
    ('SalesCreditMemo', 'post_credit_memo'): post_sales_credit_memo,
    ('PurchaseCreditMemo', 'post_credit_memo'): post_purchase_credit_memo,
    ('GeneralJournalLine', 'preview_general_journal'): preview_general_journal_batch_handler,
    ('GeneralJournalLine', 'post_general_journal'): post_general_journal_batch_handler,
    ('FinancialReportRowLine', 'recalculate_financial_report'): recalculate_financial_report_handler,
    ('FinancialReportRowLine', 'print_financial_report'): print_financial_report_handler,
    ('FinancialReport', 'recalculate_financial_report'): recalculate_financial_report_record_handler,
    ('FinancialReport', 'print_financial_report'): print_financial_report_record_handler,
}


WORKSHEET_BATCH_ACTIONS = frozenset({
    'preview_general_journal',
    'post_general_journal',
    'recalculate_financial_report',
    'print_financial_report',
})


# ── Page config endpoints ──────────────────────────────────────────────────────

class PagesListView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        schema = _get_schema(request)
        if not schema:
            return Response({'error': 'No tenant in token'}, status=status.HTTP_400_BAD_REQUEST)
        with schema_context(schema):
            pages = Page.objects.prefetch_related(
                'page_controls__fields',
                'page_controls__part_page__page_controls__fields',
                'page_controls__part_page__page_actions',
                'page_actions',
            ).all()
            data = PageSerializer(pages, many=True).data
        return Response(data)


class PageDetailView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        page_id = request.query_params.get('PageId')
        if not page_id:
            return Response({'error': 'PageId is required'}, status=status.HTTP_400_BAD_REQUEST)
        schema = _get_schema(request)
        if not schema:
            return Response({'error': 'No tenant in token'}, status=status.HTTP_400_BAD_REQUEST)
        with schema_context(schema):
            try:
                page = Page.objects.prefetch_related(
                    'page_controls__fields',
                    'page_controls__part_page__page_controls__fields',
                    'page_controls__part_page__page_actions',
                    'page_actions',
                ).get(pk=page_id)
                data = PageSerializer(page).data
            except Page.DoesNotExist:
                return Response({'error': 'Page not found'}, status=status.HTTP_404_NOT_FOUND)
        return Response(data)


def _resolve_permission_set_line_object(record_values: dict, object_id_value=None):
    """Resolve Objects row from page-engine Type + Object ID virtual fields."""
    from base.models import Objects

    object_type = record_values.get('object_type') or 'Page'
    raw_id = object_id_value if object_id_value is not None else record_values.get('object_id')
    if raw_id is None or raw_id == '':
        return None
    try:
        object_id = int(raw_id)
    except (TypeError, ValueError) as exc:
        raise ValueError('Object ID must be a number.') from exc

    app_obj = Objects.objects.filter(
        object_type=object_type,
        object_id=object_id,
        requires_permission=True,
        is_active=True,
    ).first()
    if app_obj is None:
        raise ValueError(
            f'No {object_type} object found with ID {object_id}.',
        )
    return app_obj


def _apply_permission_set_line_create_payload(payload: dict) -> dict:
    """Map virtual object_type/object_id fields to application_object FK."""
    if payload.get('application_object') or payload.get('application_object_id'):
        payload.pop('object_type', None)
        payload.pop('object_id', None)
        payload.pop('object_name', None)
        return payload

    record_values = {
        'object_type': payload.pop('object_type', None) or 'Page',
        'object_id': payload.pop('object_id', None),
    }
    payload.pop('object_name', None)
    app_obj = _resolve_permission_set_line_object(record_values)
    if app_obj is None:
        raise ValueError(
            'Select Type and Object ID before saving this permission line.',
        )
    payload['application_object'] = app_obj
    return payload


# ── Page data endpoints ────────────────────────────────────────────────────────

class PageDataView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        page_id = request.query_params.get('PageId')
        control_id = request.query_params.get('ControlId')
        search = request.query_params.get('search', '').strip()
        try:
            limit = int(request.query_params.get('limit', 100))
        except (TypeError, ValueError):
            limit = 100
        try:
            offset = int(request.query_params.get('offset', 0))
        except (TypeError, ValueError):
            offset = 0

        schema = _get_schema(request)
        if not schema:
            return Response({'error': 'No tenant in token'}, status=status.HTTP_400_BAD_REQUEST)

        with schema_context(schema):
            try:
                page = Page.objects.get(pk=page_id)
            except Page.DoesNotExist:
                return Response({'error': 'Page not found'}, status=status.HTTP_404_NOT_FOUND)

            part_link_control = None
            parent_system_id = request.query_params.get('parent_system_id', '').strip()

            if control_id:
                try:
                    control = page.page_controls.get(pk=control_id)
                except PageControl.DoesNotExist:
                    return Response({'error': 'Control not found'}, status=status.HTTP_404_NOT_FOUND)
            else:
                control = page.page_controls.filter(
                    control_type__in=['Repeater', 'Group']
                ).first()

            if control and control.control_type == 'Part':
                part_link_control = control
                control, page = _resolve_part_data_control(control, page)
                if control is None:
                    return Response({'error': 'Part control has no sub-page repeater'}, status=status.HTTP_404_NOT_FOUND)

            if not control:
                return Response([])

            source_table = control.source_table or page.source_table
            model = _get_model(source_table)
            if model is None:
                return Response(
                    {'error': f'Model not found for source table: {source_table}'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            denied = _enforce_source_table_permission(request, source_table, 'read')
            if denied is not None:
                return denied
            fields = _serialization_fields(control)
            if source_table == 'UserPermissionSets':
                if not parent_system_id:
                    return Response([])
                user = get_user_by_page_id(parent_system_id)
                if user is None:
                    return Response([])
                data = []
                for perm_set, group_codes in user_effective_permission_sets(user):
                    perm_set._via_user_groups = ', '.join(group_codes)
                    data.append(_serialize_record(perm_set, fields, request))
                return Response(data)
            if source_table == 'CompanyBillingHistory':
                from setup.company_sync import sync_company_billing_history
                sync_company_billing_history()
            elif source_table == 'CompanyPaymentMethod':
                from setup.company_sync import sync_company_payment_methods
                sync_company_payment_methods()

            if source_table == 'CustomUser':
                qs = users_queryset()
            elif source_table == 'PermissionSet':
                qs = model.objects.all().order_by('code')
            elif source_table == 'PermissionSetLine':
                qs = model.objects.select_related(
                    'application_object', 'permissionset',
                ).order_by('application_object__object_id')
            elif source_table == 'UserGroup':
                qs = model.objects.select_related('default_profile').order_by('code')
            elif source_table == 'Objects':
                if page.name in ('PermissionSetLinesSubform', 'ApplicationObjectsList'):
                    qs = model.objects.filter(
                        object_type__in=['Page', 'Table'],
                        requires_permission=True,
                        is_active=True,
                    ).order_by('object_type', 'object_id')
                else:
                    qs = model.objects.filter(
                        object_type='Page', requires_permission=True, is_active=True,
                    ).order_by('object_id')
            else:
                qs = model.objects.all()

            if source_table == 'UserSetup':
                qs = qs.select_related('user').order_by('user__full_name', 'user__username')
            elif source_table == USER_PERSONALIZATION_SOURCE_TABLE:
                qs = (
                    qs.select_related('user', 'role')
                    .filter(user__is_active=True, user__terminated=False)
                    .exclude(user__username='debug_admin')
                    .order_by('user__username')
                )
            elif source_table == 'BankAccount':
                qs = qs.order_by('no')
            elif source_table == 'G_LAccount':
                qs = qs.order_by('no')
            elif source_table == 'ItemCategory':
                qs = qs.select_related('parent').order_by('tree_id', 'lft')
            elif source_table == 'Dimension':
                qs = qs.order_by('code')
            elif source_table == 'DimensionValue':
                qs = qs.select_related('dimension_code').order_by('dimension_code__code', 'code')
            elif source_table == 'CompanyBillingHistory':
                qs = qs.order_by('-billing_date', '-id')
            elif source_table == 'CompanyPaymentMethod':
                qs = qs.order_by('-is_primary', 'holder_name')
            elif source_table == 'PaymentMethod':
                qs = qs.select_related('bal_account_no', 'bal_bank_account_no').order_by('code')
            elif source_table == 'BankAccountLedgerEntry':
                qs = qs.select_related('bank_account_no')
            elif source_table == 'SalesOrderLine':
                qs = qs.select_related('item', 'sales_order').order_by('id')
            elif source_table == 'SalesOrder':
                qs = qs.select_related('customer').order_by('-order_date', '-id')
            elif source_table == 'SalesInvoiceLine':
                qs = qs.select_related('item', 'sales_invoice').order_by('id')
            elif source_table == 'SalesInvoice':
                from django.db.models import CharField, OuterRef, Subquery
                from sales.models import CustomerLedgerEntry
                from sales.views import SalesViewSet

                qs = qs.select_related('customer').prefetch_related('lines').order_by(
                    '-document_date', '-id',
                )
                qs = SalesViewSet._with_invoice_totals(qs)
                ledger_user_name = (
                    CustomerLedgerEntry.objects.filter(
                        customer_id=OuterRef('customer_id'),
                        document_no=OuterRef('invoice_no'),
                    )
                    .order_by('-id')
                    .values('user__full_name')[:1]
                )
                qs = qs.annotate(
                    user_name=Subquery(ledger_user_name, output_field=CharField()),
                )
            elif source_table == 'PostedSalesInvoice':
                from sales.views import SalesViewSet

                qs = qs.select_related('customer', 'payment_method').order_by(
                    '-posting_date', '-id',
                )
                qs = SalesViewSet._with_posted_sales_invoice_totals(qs)
                qs = SalesViewSet._annotate_posted_sales_invoice_ledger_links(qs)
            elif source_table == 'PostedSalesInvoiceLine':
                qs = qs.select_related(
                    'item', 'posted_sales_invoice', 'resource',
                ).order_by('id')
            elif source_table == 'SalesCreditMemo':
                qs = qs.select_related(
                    'customer', 'original_invoice',
                ).prefetch_related('lines').order_by('-posting_date', '-id')
            elif source_table == 'SalesCreditMemoLine':
                qs = qs.select_related(
                    'item', 'credit_memo', 'location_code',
                ).order_by('id')
            elif source_table == 'PurchaseCreditMemo':
                qs = qs.select_related('vendor', 'original_posted_invoice').order_by(
                    '-posting_date', '-id',
                )
            elif source_table == 'PurchaseCreditMemoLine':
                qs = qs.select_related(
                    'item', 'credit_memo', 'location_code',
                ).order_by('id')
            elif source_table == 'PurchaseInvoiceLine':
                qs = qs.select_related(
                    'item',
                    'resource',
                    'gl_account',
                    'purchase_invoice',
                    'item_unit_of_measure__unit_of_measure',
                    'location_code',
                ).order_by('id')
            elif source_table == 'PostedPurchaseInvoiceLine':
                qs = qs.select_related(
                    'item',
                    'resource',
                    'gl_account',
                    'posted_purchase_invoice',
                    'item_unit_of_measure__unit_of_measure',
                    'location_code',
                ).order_by('id')
            elif source_table == 'TrackingSpecification':
                qs = qs.select_related(
                    'item',
                    'purchase_invoice',
                    'purchase_invoice_line',
                    'location_code',
                ).order_by('id')
            elif source_table == 'PurchaseInvoice':
                qs = qs.select_related('vendor').order_by('-posting_date', '-id')
            elif source_table == 'PostedPurchaseInvoice':
                from purchases.views import PurchaseViewSet

                qs = qs.select_related('vendor').order_by('-posting_date', '-id')
                qs = PurchaseViewSet._annotate_posted_purchase_invoice_closed(qs)
            elif source_table == 'ItemLedgerEntries':
                qs = qs.select_related('item', 'location').order_by('id')
            elif source_table == 'RestaurantOrder':
                qs = qs.select_related(
                    'table', 'customer', 'waiter', 'global_dimension_1',
                ).order_by('-created_at', '-id')
            elif source_table == 'RestaurantOrderItem':
                qs = qs.select_related('order', 'item').order_by('id')
            elif source_table == 'Reservation':
                qs = qs.select_related('customer', 'table', 'waiter').order_by(
                    '-reservation_date',
                )
            elif source_table == 'Table':
                qs = qs.select_related('floor', 'section').order_by(
                    'floor', 'table_number',
                )
            elif source_table == 'MenuItem':
                qs = qs.select_related('item', 'category', 'menu').order_by('id')
            elif source_table == 'ItemJournal':
                qs = (
                    qs.select_related('item', 'user', 'location_code')
                    .filter(
                        django_models.Q(journal_template__type='item')
                        | django_models.Q(journal_template__isnull=True)
                    )
                    .order_by('-date', '-created_at')
                )

            list_filters = _extract_list_filters(request, model)
            if list_filters:
                virtual_filters = {
                    k: list_filters[k]
                    for k in _LIST_VIRTUAL_FILTER_KEYS
                    if k in list_filters
                }
                orm_filters = {
                    k: v for k, v in list_filters.items()
                    if k not in _LIST_VIRTUAL_FILTER_KEYS
                    and k not in _LIST_DATE_SCOPE_KEYS
                }
                date_scope = {
                    k: list_filters[k]
                    for k in _LIST_DATE_SCOPE_KEYS
                    if k in list_filters
                }
                if date_scope:
                    qs = _apply_posting_date_scope(qs, date_scope)
                if orm_filters:
                    if source_table == 'ItemLedgerEntries' and (
                        'vendor_invoice_no' in orm_filters or 'item' in orm_filters
                    ):
                        qs = _apply_posted_purchase_item_tracking_filters(
                            qs, dict(orm_filters),
                        )
                    else:
                        qs = qs.filter(**orm_filters)
                if virtual_filters:
                    if source_table == 'SalesInvoice':
                        qs = _apply_sales_invoice_virtual_filters(qs, virtual_filters)
                    elif source_table == 'PostedSalesInvoice':
                        qs = _apply_posted_sales_invoice_virtual_filters(qs, virtual_filters)
                    applied_entry_id = virtual_filters.get('applied_to_entry_id')
                    if applied_entry_id and source_table in (
                        'VendorLedger',
                        'CustomerLedgerEntry',
                    ):
                        qs = _apply_applied_entries_filter(
                            qs, source_table, applied_entry_id
                        )
                    vendor_detail_id = virtual_filters.get('vendor_ledger_entry_id')
                    if vendor_detail_id and source_table == 'DetailedVendorLedgerEntry':
                        qs = _apply_detailed_ledger_entry_filter(
                            qs, source_table, vendor_detail_id
                        )
                    customer_detail_id = virtual_filters.get('customer_ledger_entry_id')
                    if customer_detail_id and source_table == 'DetailedCustomerLedgerEntry':
                        qs = _apply_detailed_ledger_entry_filter(
                            qs, source_table, customer_detail_id
                        )

            qs = _apply_page_list_scope(page, qs)

            if parent_system_id:
                link_field = ''
                if part_link_control and part_link_control.link_field:
                    link_field = part_link_control.link_field
                else:
                    sub_page_link = _find_part_link_for_sub_page(page)
                    if sub_page_link:
                        link_field = sub_page_link.link_field
                if link_field:
                    qs = _apply_part_parent_filter(qs, link_field, parent_system_id)

            if search:
                text_fields = [
                    f.name for f in fields
                    if f.field_type in ('Text', 'Code') and hasattr(model, f.name)
                ]
                if source_table == 'UserSetup':
                    text_fields.extend(['user__full_name', 'user__email', 'user__username'])
                elif source_table == 'CustomUser':
                    text_fields.extend(['full_name', 'email', 'username', 'phone_number'])
                elif source_table == 'PostedSalesInvoice':
                    text_fields.extend(['customer__name', 'no', 'customer_invoice_no'])
                if text_fields:
                    q = django_models.Q()
                    for fname in text_fields[:5]:
                        for lookup in _search_lookups(model, fname):
                            q |= django_models.Q(**{lookup: search})
                    qs = qs.filter(q)

            if page.source_table == 'BankAccountLedgerEntry':
                qs = qs.order_by('-posting_date', '-entry_no')
            elif page.source_table in ('CustomerLedgerEntry', 'VendorLedger', 'ItemLedgerEntries'):
                qs = qs.order_by('-posting_date', '-id')
            elif page.source_table == 'DetailedVendorLedgerEntry':
                qs = qs.select_related('vendor').order_by('posting_date', 'entry_no')
            elif page.source_table == 'DetailedCustomerLedgerEntry':
                qs = qs.select_related('customer').order_by('posting_date', 'entry_no')
            elif page.source_table == 'GeneralLedgerEntry':
                qs = qs.select_related('gl_account').order_by('-posting_date', '-id')

            if not parent_system_id:
                qs = _apply_request_branch_filter(
                    qs, request, source_table=source_table, model=model,
                )

            sort_field = (request.query_params.get('sort') or '').strip()
            sort_order = (request.query_params.get('order') or 'asc').strip()
            qs = _apply_user_list_sort(qs, model, control, sort_field, sort_order)

            # BC-style prev/next: return neighboring SystemIds without serializing rows.
            neighbors_for = (request.query_params.get('SystemId') or '').strip()
            if request.query_params.get('neighbors') == '1' and neighbors_for:
                if hasattr(model, 'system_id'):
                    ordered_ids = [
                        str(sid)
                        for sid in qs.values_list('system_id', flat=True)[:5000]
                    ]
                else:
                    ordered_ids = [
                        str(pk) for pk in qs.values_list('pk', flat=True)[:5000]
                    ]
                try:
                    idx = ordered_ids.index(neighbors_for)
                except ValueError:
                    return Response(
                        {'previousSystemId': None, 'nextSystemId': None}
                    )
                return Response(
                    {
                        'previousSystemId': (
                            ordered_ids[idx - 1] if idx > 0 else None
                        ),
                        'nextSystemId': (
                            ordered_ids[idx + 1]
                            if idx < len(ordered_ids) - 1
                            else None
                        ),
                    }
                )

            qs = qs[offset:offset + limit]
            data = [_serialize_record(obj, fields, request) for obj in qs]

        return Response(data)

    def post(self, request):
        page_id = request.data.get('PageId')
        control_id = request.data.get('ControlId')
        schema = _get_schema(request)
        if not schema:
            return Response({'error': 'No tenant in token'}, status=status.HTTP_400_BAD_REQUEST)

        with schema_context(schema):
            try:
                page = Page.objects.get(pk=page_id)
                control = page.page_controls.get(pk=control_id)
            except (Page.DoesNotExist, PageControl.DoesNotExist):
                return Response({'error': 'Page or control not found'}, status=status.HTTP_404_NOT_FOUND)

            source_table = control.source_table or page.source_table
            model = _get_model(source_table)
            if model is None:
                return Response({'error': 'Model not found'}, status=status.HTTP_400_BAD_REQUEST)

            denied = _enforce_source_table_permission(request, source_table, 'insert')
            if denied is not None:
                return denied

            if not page.insert_allowed:
                return Response({'error': 'Insert is not allowed on this page'}, status=status.HTTP_403_FORBIDDEN)

            parent_system_id = request.data.get('parent_system_id')
            if parent_system_id:
                part_link = _find_part_link_for_sub_page(page)
                if part_link and part_link.page_id:
                    parent_model = _get_model(part_link.page.source_table)
                    if parent_model is not None:
                        parent_obj = PageDataRecordView()._get_obj(
                            parent_model, parent_system_id,
                        )
                        if parent_obj is not None and _record_is_read_only(parent_obj):
                            return _posted_read_only_response()

            payload = {
                k: v for k, v in request.data.items()
                if k not in ('PageId', 'ControlId', 'parent_system_id')
            }
            payload = _inject_part_parent_link(payload, page, parent_system_id)
            payload = _apply_drill_down_context(payload, page, model)
            if model.__name__ == 'PermissionSetLine':
                try:
                    payload = _apply_permission_set_line_create_payload(payload)
                except ValueError as e:
                    return _page_data_error_response(e, source_table=source_table)
            payload = _resolve_payload_fk_writes(page, control, payload)
            if model.__name__ == 'PaymentMethod':
                payload = _normalize_payment_method_payload(payload)
            payload = _normalize_create_payload(payload, model)
            payload = _apply_line_defaults(payload, request, model)
            try:
                obj = model.objects.create(**payload)
                fields = list(control.fields.all())
                data = _serialize_record(obj, fields, request)
            except (ValueError, IntegrityError) as e:
                return _page_data_error_response(e, source_table=source_table)
            except Exception as e:
                return _page_data_error_response(e, source_table=source_table)

        return Response(data, status=status.HTTP_201_CREATED)


class PageDataRecordView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def _get_obj(self, model, system_id):
        if model.__name__ == 'CustomUser':
            return get_user_by_page_id(system_id)
        base_qs = model.objects.all()
        if model.__name__ in ('UserSetup', 'UserPersonalization'):
            base_qs = base_qs.select_related('user')
        if hasattr(model, 'system_id'):
            obj = base_qs.filter(system_id=system_id).first()
            if obj is not None:
                return obj
            # Document routes sometimes pass the open-document SystemId after posting.
            if model.__name__ == 'PostedSalesInvoice':
                return self._resolve_posted_sales_invoice(base_qs, system_id)
            if model.__name__ == 'PostedPurchaseInvoice':
                return self._resolve_posted_purchase_invoice(base_qs, system_id)
            return None
        return base_qs.filter(pk=system_id).first()

    @staticmethod
    def _resolve_posted_sales_invoice(base_qs, system_id):
        from sales.models import SalesInvoice

        si = SalesInvoice.objects.filter(system_id=system_id).only(
            'customer_invoice_no', 'customer_id',
        ).first()
        if si is None or not si.customer_invoice_no:
            return None
        qs = base_qs.filter(customer_invoice_no=si.customer_invoice_no)
        if si.customer_id:
            qs = qs.filter(customer_id=si.customer_id)
        return qs.order_by('-id').first()

    @staticmethod
    def _resolve_posted_purchase_invoice(base_qs, system_id):
        from purchases.models import PurchaseInvoice

        pi = PurchaseInvoice.objects.filter(system_id=system_id).first()
        if pi is None:
            return None
        # Prefer vendor invoice no / document link fields when present
        for lookup in (
            {'vendor_invoice_no': getattr(pi, 'vendor_invoice_no', None)},
            {'no': getattr(pi, 'no', None)},
        ):
            key, val = next(iter(lookup.items()))
            if not val:
                continue
            if not hasattr(base_qs.model, key):
                continue
            qs = base_qs.filter(**{key: val})
            vendor_id = getattr(pi, 'vendor_id', None)
            if vendor_id and hasattr(base_qs.model, 'vendor_id'):
                qs = qs.filter(vendor_id=vendor_id)
            found = qs.order_by('-id').first()
            if found is not None:
                return found
        return None

    def get(self, request, system_id: str):
        page_id = request.query_params.get('PageId')
        control_id = request.query_params.get('ControlId')
        schema = _get_schema(request)
        if not schema:
            return Response({'error': 'No tenant in token'}, status=status.HTTP_400_BAD_REQUEST)

        with schema_context(schema):
            try:
                page = Page.objects.get(pk=page_id)
            except Page.DoesNotExist:
                return Response({'error': 'Page not found'}, status=status.HTTP_404_NOT_FOUND)

            control = None
            if control_id and page.page_type != 'Card':
                try:
                    control = page.page_controls.get(pk=control_id)
                except PageControl.DoesNotExist:
                    return Response({'error': 'Control not found'}, status=status.HTTP_404_NOT_FOUND)
            elif page.page_type != 'Card':
                control = page.page_controls.filter(control_type='Group').first() \
                          or page.page_controls.first()
                if not control:
                    return Response({'error': 'No control found'}, status=status.HTTP_404_NOT_FOUND)

            source_table = (control.source_table if control else None) or page.source_table
            model = _get_model(source_table)
            if model is None:
                return Response(
                    {'error': f'Model not found for source table: {source_table}'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            denied = _enforce_source_table_permission(request, source_table, 'read')
            if denied is not None:
                return denied

            if page.source_table == 'CompanyInformation':
                obj = model.sync_from_public_company()
            elif page.source_table == 'CompanySubscription':
                obj = model.sync_from_public()
            else:
                obj = self._get_obj(model, system_id)
            if obj is None:
                return Response({'error': 'Record not found'}, status=status.HTTP_404_NOT_FOUND)

            if page.source_table == USER_PERSONALIZATION_SOURCE_TABLE and not _can_access_personalization(request, obj, 'read'):
                return Response({'error': 'Record not found'}, status=status.HTTP_404_NOT_FOUND)

            if model.__name__ == 'PurchaseInvoice' and not _record_is_read_only(obj):
                _sync_purchase_invoice_payment_method_from_vendor(obj, request.user)
                if hasattr(obj, 'refresh_from_db'):
                    obj.refresh_from_db()

            fields = _record_fields_for_page(page, control)
            data = _serialize_record(obj, fields, request)

        return Response(data)

    def patch(self, request, system_id: str):
        page_id = request.data.get('PageId')
        field_name = request.data.get('field')
        value = request.data.get('value')
        schema = _get_schema(request)
        if not schema:
            return Response({'error': 'No tenant in token'}, status=status.HTTP_400_BAD_REQUEST)

        with schema_context(schema):
            try:
                page = Page.objects.get(pk=page_id)
            except Page.DoesNotExist:
                return Response({'error': 'Page not found'}, status=status.HTTP_404_NOT_FOUND)

            model = _get_model(page.source_table)
            if model is None:
                return Response({'error': 'Model not found'}, status=status.HTTP_400_BAD_REQUEST)

            if not field_name:
                return Response({'error': 'field is required'}, status=status.HTTP_400_BAD_REQUEST)

            source_table = page.source_table
            perm_type = 'insert' if self._get_obj(model, system_id) is None else 'modify'
            denied = _enforce_source_table_permission(request, source_table, perm_type)
            if denied is not None:
                return denied

            if page.source_table in (
                'CompanySubscription',
                'CompanyBillingHistory',
                'CompanyPaymentMethod',
            ):
                return Response({'error': 'This record is read-only'}, status=status.HTTP_403_FORBIDDEN)

            if page.source_table == 'CompanyInformation':
                obj = model.sync_from_public_company()
            elif page.source_table == 'CompanySubscription':
                obj = model.sync_from_public()
            else:
                obj = self._get_obj(model, system_id)
            created = False

            if page.source_table == USER_PERSONALIZATION_SOURCE_TABLE:
                if obj is not None and not _can_access_personalization(request, obj, perm_type):
                    return Response({'error': 'Record not found'}, status=status.HTTP_404_NOT_FOUND)

            try:
                fk_record_values = request.data.get('CurrentRecordValues') or {}
                if page.source_table == 'CustomUser':
                    if obj is None:
                        if not page.insert_allowed:
                            return Response({'error': 'Record not found'}, status=status.HTTP_404_NOT_FOUND)
                        obj, created = create_user_for_page(system_id, field_name, value)
                    else:
                        obj, created = update_user_for_page(obj, field_name, value)
                elif obj is None:
                    if not page.insert_allowed:
                        return Response({'error': 'Record not found'}, status=status.HTTP_404_NOT_FOUND)
                    if not hasattr(model, field_name) and not (
                        model.__name__ == 'Item' and field_name == 'unit_cost'
                    ) and not (
                        model.__name__ == 'PurchaseInvoiceLine' and field_name == 'no'
                    ) and not (
                        '__' in field_name and _model_has_direct_field(
                            model, field_name.split('__')[0],
                        )
                    ):
                        return Response(
                            {'error': f'Invalid field: {field_name}'},
                            status=status.HTTP_400_BAD_REQUEST,
                        )
                    if model.__name__ == 'PurchaseInvoiceLine' and field_name == 'no':
                        # Clearing No. must not invent a new line (would hit NOT NULL on type/FKs).
                        if value is None or value == '':
                            return Response(
                                {'error': 'Record not found'},
                                status=status.HTTP_404_NOT_FOUND,
                            )
                        defaults = _purchase_line_no_create_defaults(value, fk_record_values)
                        defaults = _apply_purchase_invoice_line_defaults(defaults, request)
                    else:
                        field_name, value = _resolve_fk_write(
                            page, field_name, value, obj=obj,
                            record_values=fk_record_values, model=model,
                        )
                        defaults = {field_name: value}
                    if (
                        model.__name__ == 'PurchaseInvoiceLine'
                        and field_name == 'type'
                        and (value is None or value == '')
                    ):
                        return Response(
                            {'error': 'Type is required.'},
                            status=status.HTTP_400_BAD_REQUEST,
                        )
                    defaults = _merge_create_defaults_from_current_values(
                        defaults, model, fk_record_values,
                    )
                    pk_error = _validate_page_primary_keys_for_create(page, defaults)
                    if pk_error:
                        return Response({'error': pk_error}, status=status.HTTP_400_BAD_REQUEST)
                    # Resolve any relation values merged from the client (e.g. parent category).
                    for key in list(defaults.keys()):
                        try:
                            resolved_name, resolved_value = _resolve_fk_write(
                                page, key, defaults[key], obj=None,
                                record_values={**fk_record_values, **defaults},
                                model=model,
                            )
                        except ValueError as e:
                            return _page_data_error_response(e, source_table=source_table)
                        if resolved_name != key:
                            defaults.pop(key, None)
                        defaults[resolved_name] = resolved_value
                    if field_name == 'item' and _model_has_item_and_description(model):
                        defaults = _apply_item_line_defaults_to_payload(defaults, model=model)
                        if model.__name__ in ('SalesInvoiceLine', 'SalesOrderLine'):
                            defaults = _apply_sales_line_item_price_defaults(defaults)
                        if model.__name__ in _SALES_LINE_ITEM_SOURCE_TABLES:
                            _validate_sales_line_item_in_stock(
                                defaults.get('item', value), request,
                            )
                    if model.__name__ in (
                        'PaymentLine', 'CashReceiptJournalLine', 'GeneralJournalLine',
                    ):
                        merged = {**fk_record_values, **defaults}
                        merged = _apply_account_line_defaults(merged)
                        if merged.get('description'):
                            defaults['description'] = merged['description']
                    skip_orm_create = False
                    if model.__name__ == 'Item' and field_name == 'unit_cost':
                        item_type = _item_type_for_cost_write(None, model, system_id)
                        if item_type not in _ITEM_MANUAL_COST_TYPES:
                            obj = model.objects.filter(system_id=system_id).first()
                            created = False
                            skip_orm_create = True
                        else:
                            defaults = {
                                'manual_unit_cost': _coerce_item_manual_unit_cost(value),
                            }
                    if not skip_orm_create:
                        if model.__name__ in ('SalesInvoice', 'PurchaseInvoice', 'RestaurantOrder'):
                            defaults = _apply_invoice_header_defaults(model, defaults, request)
                        if model.__name__ == 'RestaurantOrder' and request and getattr(request, 'user', None):
                            defaults.setdefault('waiter', request.user)
                        list_page_id = request.data.get('ListPageId')
                        defaults = _apply_list_page_create_defaults(
                            page, defaults, request, list_page_id,
                        )
                        if page.source_table == 'ItemJournal':
                            defaults = _apply_item_journal_create_defaults(defaults, request)
                            if not defaults.get('item') and not defaults.get('item_id'):
                                return Response(
                                    {'error': 'Item is required to create an item journal.'},
                                    status=status.HTTP_400_BAD_REQUEST,
                                )
                        if model.__name__ == 'Floor':
                            defaults = _apply_floor_create_defaults(defaults, request)
                        defaults = _apply_audit_on_create(defaults, model, request.user)
                        if page.source_table == USER_PERSONALIZATION_SOURCE_TABLE:
                            defaults['user'] = request.user
                        obj, created = model.objects.update_or_create(
                            system_id=system_id,
                            defaults=defaults,
                        )
                else:
                    if _record_is_read_only(obj):
                        return _posted_read_only_response()
                    if model.__name__ == 'PaymentMethod':
                        pm_fields = _apply_payment_method_field_update(
                            obj, field_name, value, fk_record_values,
                        )
                        if pm_fields is not None:
                            _save_payment_method_fields(obj, request.user, pm_fields)
                        else:
                            field_name, value = _resolve_fk_write(
                                page, field_name, value, obj=obj,
                                record_values=fk_record_values, model=model,
                            )
                            setattr(obj, field_name, value)
                            _save_page_field_update(
                                obj, request.user, field_name, previous_pk=None,
                            )
                    elif model.__name__ == 'PermissionSetLine' and field_name in (
                        'object_type', 'object_id', 'object_name',
                    ):
                        if field_name == 'object_name':
                            pass
                        elif field_name == 'object_type':
                            if obj.application_object_id:
                                current_type = obj.application_object.object_type
                                if str(value) != str(current_type):
                                    obj.application_object = None
                                    obj.save(update_fields=['application_object'])
                        else:
                            merged = {**fk_record_values, 'object_id': value}
                            app_obj = _resolve_permission_set_line_object(
                                merged, object_id_value=value,
                            )
                            obj.application_object = app_obj
                            obj.save(update_fields=['application_object'])
                    elif model.__name__ == 'Item':
                        item_fields = _apply_item_field_update(
                            obj, field_name, value, system_id=system_id,
                        )
                        if item_fields is not None:
                            if item_fields:
                                _save_page_field_update(
                                    obj, request.user, item_fields[0], previous_pk=None,
                                )
                        else:
                            field_name, value = _resolve_fk_write(
                                page, field_name, value, obj=obj,
                                record_values=fk_record_values, model=model,
                            )
                            previous_pk = (
                                getattr(obj, obj._meta.pk.name)
                                if field_name == obj._meta.pk.name
                                else None
                            )
                            setattr(obj, field_name, value)
                            _save_page_field_update(
                                obj, request.user, field_name, previous_pk=previous_pk,
                            )
                    elif model.__name__ == 'PurchaseInvoiceLine' and field_name == 'no':
                        extra_fields = _apply_purchase_line_no_field_update(
                            obj, value, fk_record_values,
                        )
                        _save_page_field_update(
                            obj, request.user, extra_fields[0] if extra_fields else 'type',
                            extra_fields=extra_fields[1:] if len(extra_fields) > 1 else None,
                        )
                    else:
                        field_name, value = _resolve_fk_write(
                            page, field_name, value, obj=obj,
                            record_values=fk_record_values, model=model,
                        )
                        if '__' in field_name and not _model_has_direct_field(model, field_name):
                            _save_nested_related_field_update(obj, field_name, value)
                        else:
                            previous_pk = (
                                getattr(obj, obj._meta.pk.name)
                                if field_name == obj._meta.pk.name
                                else None
                            )
                            if (
                                model.__name__ == 'PurchaseInvoice'
                                and field_name == 'payment_method'
                            ):
                                _validate_purchase_invoice_payment_method(
                                    getattr(obj, 'vendor', None), value,
                                )
                            if (
                                field_name == 'item'
                                and model.__name__ in _SALES_LINE_ITEM_SOURCE_TABLES
                            ):
                                _validate_sales_line_item_in_stock(
                                    value,
                                    request,
                                    previous_item=getattr(obj, 'item', None),
                                )
                            setattr(obj, field_name, value)
                            extra_fields = None
                            if field_name == 'item':
                                extra_fields = _sync_item_driven_line_fields(obj)
                            elif field_name == 'type':
                                if value is None or value == '':
                                    return Response(
                                        {'error': 'Type is required.'},
                                        status=status.HTTP_400_BAD_REQUEST,
                                    )
                                extra_fields = _sync_purchase_line_type_switch(obj)
                            elif field_name == 'resource':
                                extra_fields = _sync_resource_driven_purchase_line_fields(obj)
                            elif field_name in ('account_no', 'account_type'):
                                extra_fields = _sync_account_driven_line_fields(obj)
                            _save_page_field_update(
                                obj, request.user, field_name, previous_pk=previous_pk,
                                extra_fields=extra_fields,
                            )
                            if field_name == 'vendor' and model.__name__ == 'PurchaseInvoice':
                                _sync_purchase_invoice_payment_method_from_vendor(obj, request.user)
            except ValidationError as e:
                return _page_data_error_response(e, source_table=page.source_table)
            except ValueError as e:
                return _page_data_error_response(e, source_table=page.source_table)
            except IntegrityError as e:
                return _page_data_error_response(e, source_table=page.source_table)
            except Exception as e:
                return _page_data_error_response(e, source_table=page.source_table)

            if obj is None:
                return Response(
                    {'ok': True, 'Created': False, 'record': {'SystemId': system_id}},
                )

            if hasattr(obj, 'refresh_from_db'):
                obj.refresh_from_db()

            record_data = _serialize_page_record(page, obj, request=request)

        return Response({'ok': True, 'Created': created, 'record': record_data})

    def delete(self, request, system_id: str):
        page_id = request.query_params.get('PageId')
        schema = _get_schema(request)
        if not schema:
            return Response({'error': 'No tenant in token'}, status=status.HTTP_400_BAD_REQUEST)

        with schema_context(schema):
            try:
                page = Page.objects.get(pk=page_id)
            except Page.DoesNotExist:
                return Response({'error': 'Page not found'}, status=status.HTTP_404_NOT_FOUND)

            model = _get_model(page.source_table)
            if model is None:
                return Response({'error': 'Model not found'}, status=status.HTTP_400_BAD_REQUEST)

            denied = _enforce_source_table_permission(request, page.source_table, 'delete')
            if denied is not None:
                return denied

            if not page.delete_allowed:
                return Response({'error': 'Delete not allowed on this page'}, status=status.HTTP_403_FORBIDDEN)

            obj = self._get_obj(model, system_id)
            if obj is None:
                return Response({'error': 'Record not found'}, status=status.HTTP_404_NOT_FOUND)

            if _record_is_read_only(obj):
                return _posted_read_only_response()

            try:
                if page.source_table == 'CustomUser':
                    soft_delete_user(obj)
                else:
                    obj.delete()
            except ProgrammingError as e:
                if 'does not exist' in str(e):
                    return Response(
                        {
                            'error': (
                                'Database schema is out of date for this company. '
                                'Run tenant migrations (migrate_schemas) and try again.'
                            ),
                        },
                        status=status.HTTP_503_SERVICE_UNAVAILABLE,
                    )
                raise
            except DataError as e:
                err = str(e)
                if 'base_unit_id' in err or 'invalid input syntax for type bigint' in err:
                    return Response(
                        {
                            'error': (
                                'Database schema is out of date for unit-of-measure links. '
                                'Run tenant migrations (migrate_schemas) and try again.'
                            ),
                        },
                        status=status.HTTP_503_SERVICE_UNAVAILABLE,
                    )
                raise
            except django_models.ProtectedError:
                return Response(
                    {'error': 'This record cannot be deleted because other records depend on it.'},
                    status=status.HTTP_409_CONFLICT,
                )

        return Response(status=status.HTTP_204_NO_CONTENT)


class PageActionView(APIView):
    """
    POST /api/pages/action/
    Invoke a PageAction on a specific record.
    Equivalent to BC's action trigger OnAction().
    """

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        page_id = request.data.get('PageId')
        action_id = request.data.get('ActionId')
        system_id = request.data.get('SystemId')
        batch_name = request.data.get('BatchName') or request.data.get('batchName')

        if not page_id or not action_id:
            return Response(
                {'error': 'PageId and ActionId are required'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        schema = _get_schema(request)
        if not schema:
            return Response({'error': 'No tenant in token'}, status=status.HTTP_400_BAD_REQUEST)

        with schema_context(schema):
            try:
                page = Page.objects.get(pk=page_id)
            except Page.DoesNotExist:
                return Response({'error': 'Page not found'}, status=status.HTTP_404_NOT_FOUND)

            action = PageAction.objects.filter(page=page, name=action_id).first()
            if action is None:
                try:
                    action = PageAction.objects.get(page=page, action_id=int(action_id))
                except (PageAction.DoesNotExist, ValueError, TypeError):
                    return Response({'error': 'Action not found'}, status=status.HTTP_404_NOT_FOUND)

            handler_key = (page.source_table, str(action_id).lower())
            handler = ACTION_HANDLERS.get(handler_key)
            if handler is None:
                handler_key = (page.source_table, action.name.lower())
                handler = ACTION_HANDLERS.get(handler_key)
            if handler is None:
                return Response(
                    {'error': f'No handler for action {action_id} on {page.source_table}'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            is_worksheet_batch = (
                page.page_type == 'Worksheet'
                and batch_name
                and action.name in WORKSHEET_BATCH_ACTIONS
            )

            if is_worksheet_batch:
                try:
                    result = handler(None, request)
                except Exception as e:
                    return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            else:
                if not system_id:
                    return Response(
                        {'error': 'SystemId is required'},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                model = _get_model(page.source_table)
                if model is None:
                    return Response({'error': 'Model not found'}, status=status.HTTP_400_BAD_REQUEST)

                record_view = PageDataRecordView()
                obj = record_view._get_obj(model, system_id)
                if obj is None:
                    return Response({'error': 'Record not found'}, status=status.HTTP_404_NOT_FOUND)

                try:
                    result = handler(obj, request)
                except PermissionError as e:
                    return Response(
                        {'error': str(e)},
                        status=status.HTTP_403_FORBIDDEN,
                    )
                except ValueError as e:
                    return Response(
                        {'error': str(e)},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                except Exception as e:
                    return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            if isinstance(result, dict) and result.get('command') == 'DOWNLOAD':
                return Response({
                    'Successful': True,
                    'Command': 'DOWNLOAD',
                    'Content': result.get('content'),
                })

            if isinstance(result, dict) and result.get('command') == 'PREVIEW':
                return Response({
                    'Successful': True,
                    'Command': 'PREVIEW',
                    'Content': result.get('content'),
                })

            if isinstance(result, dict) and result.get('command') == 'NAVIGATE':
                content = result.get('content') or {}
                return Response({
                    'Successful': True,
                    'Command': 'NAVIGATE',
                    'Content': content,
                    'Message': content.get('Message', 'Opening document'),
                })

            if isinstance(result, dict) and result.get('command') == 'REFRESH':
                content = result.get('content') or {}
                return Response({
                    'Successful': True,
                    'Command': 'REFRESH',
                    'Content': content,
                    'Message': content.get('Message', 'Completed'),
                })

            if is_worksheet_batch:
                return Response({
                    'Successful': True,
                    'Command': 'REFRESH',
                    'Content': result if isinstance(result, dict) else {},
                })

            record_data = _serialize_page_record(page, result, request=request)

        return Response({
            'ok': True,
            'ActionId': action.name,
            'record': record_data,
        })


# ── Role Centre helpers ────────────────────────────────────────────────────────

def _rc_layout_style(control: PageControl) -> str:
    if control.name == 'RCKeyTotals':
        return 'NormalCues'
    if control.name == 'RCSalesActivities':
        return 'StandardCues'
    return 'StandardCues'


def _parse_cue_filter_value(raw: str):
    if raw in ('True', 'true', '1'):
        return True
    if raw in ('False', 'false', '0'):
        return False
    return raw


def _parse_list_filter_values(raw: str) -> list:
    """Split comma-separated list filter values (e.g. 'Open,Draft')."""
    return [_parse_cue_filter_value(v.strip()) for v in raw.split(',') if v.strip()]


def _list_filter_create_default(raw: str):
    """Default field value when creating from a filtered list page."""
    values = _parse_list_filter_values(raw)
    return values[0] if values else _parse_cue_filter_value(raw)


def _apply_page_list_scope(page: Page, qs):
    """Apply page-engine list include/exclude filters configured on the Page record."""
    if page.list_filter_field and page.list_filter_value:
        try:
            values = _parse_list_filter_values(page.list_filter_value)
            if len(values) > 1:
                qs = qs.filter(**{f'{page.list_filter_field}__in': values})
            elif len(values) == 1:
                qs = qs.filter(**{page.list_filter_field: values[0]})
        except Exception:
            pass
    if page.list_exclude_field and page.list_exclude_values:
        excluded = [
            v.strip() for v in page.list_exclude_values.split(',') if v.strip()
        ]
        if excluded:
            qs = qs.exclude(**{f'{page.list_exclude_field}__in': excluded})
    return qs


# Admin/setup tables: not scoped by session branch in the page engine.
_PAGE_ENGINE_BRANCH_FILTER_SKIP = frozenset({
    'CustomUser',
    'UserSetup',
    'UserPersonalization',
    'Dimension',
    'DimensionValue',
    'CompanyInformation',
    'CompanySubscription',
    'CompanyBillingHistory',
    'CompanyPaymentMethod',
    'GeneralLedgerSetup',
    'InventorySetup',
    'SalesReceivable',
    'ApplicationProfile',
    'NoSeries',
    'PaymentMethod',
    'ExpenseType',
})


def _apply_request_branch_filter(qs, request, source_table=None, model=None):
    """Scope queryset to X-Branch-Id / user.global_dimension_1 (legacy REST parity)."""
    if source_table and source_table in _PAGE_ENGINE_BRANCH_FILTER_SKIP:
        return qs
    user = getattr(request, 'user', None)
    if not user or not getattr(user, 'is_authenticated', False):
        return qs
    from dimension.branch_filter import filter_queryset_by_branch

    model_class = model or getattr(qs, 'model', None)
    return filter_queryset_by_branch(qs, user, model_class=model_class, request=request)


def _format_cue_display_value(value, aggregate: str) -> str | None:
    if value is None:
        return None
    if aggregate in ('sum', 'avg', 'max', 'min'):
        try:
            return f'UGX {float(value):,.0f}'
        except (TypeError, ValueError):
            return str(value)
    if isinstance(value, float) and not float(value).is_integer():
        return f'{float(value):,.1f}'
    if isinstance(value, (int, float, Decimal)):
        return f'{int(value):,}'
    return str(value)


def _compute_inventory_value(request):
    """
    Inventory value = G/L 2110 (Resale Items) balance — same source as Sales dashboard stock_value.
    """
    from dimension.branch_filter import branch_scope_is_all, get_branch_for_request
    from reports.services.inventory_value_movement_service import (
        InventoryValueMovementService,
    )

    branch = None
    if request and not branch_scope_is_all(request):
        branch = get_branch_for_request(request)
        if not branch:
            user = getattr(request, 'user', None)
            branch = getattr(user, 'global_dimension_1', None) if user else None

    return InventoryValueMovementService.get_sales_dashboard_stock_balance(branch)


def _compute_this_month_revenue(request) -> float:
    """Sum of posted sales invoice line revenue for the current calendar month."""
    line_model = _get_model('SalesInvoiceLine')
    if line_model is None:
        return 0.0

    today = timezone.now().date()
    month_start = today.replace(day=1)

    line_total = django_models.ExpressionWrapper(
        django_models.F('quantity') * django_models.F('unit_price')
        - django_models.F('line_discount_amount'),
        output_field=django_models.DecimalField(max_digits=18, decimal_places=2),
    )
    line_qs = line_model.objects.filter(
        sales_invoice__status='Posted',
        sales_invoice__posting_date__gte=month_start,
    )
    line_qs = _apply_request_branch_filter(
        line_qs, request, source_table='SalesInvoiceLine', model=line_model,
    )
    total = line_qs.aggregate(total=Sum(line_total))['total']
    return float(total or 0)


def _compute_overdue_receivables(request) -> float:
    """Sum remaining amount on open customer ledger entries past due date."""
    model = _get_model('CustomerLedgerEntry')
    if model is None:
        return 0.0

    today = timezone.now().date()
    qs = model.objects.filter(
        open=True,
        due_date__isnull=False,
        due_date__lt=today,
    )
    qs = _apply_request_branch_filter(
        qs, request, source_table='CustomerLedgerEntry', model=model,
    )
    total = qs.aggregate(total=Sum('sales_detailed_entries__amount'))['total']
    return float(total or 0)


def _serialize_cue_data(cue: PageControl, *, layout_style: str, request=None) -> dict:
    value = _compute_cue_value(cue, request=request)
    if cue.name == 'RCCueDelayedOrders':
        value = _compute_delayed_orders_count(request)
    elif cue.name == 'RCCueAvgDaysDelayed':
        value = _compute_avg_days_delayed(request)
    elif cue.name == 'RCCueTotalRevenue':
        value = _compute_this_month_revenue(request)
    elif cue.name == 'RCCueOverdueReceivables':
        value = _compute_overdue_receivables(request)
    elif cue.name in ('RCCueTodaySales', 'PostedCueToday'):
        value = _compute_today_posted_sales(request)
    elif cue.name == 'RCCueInventoryValue':
        value = _compute_inventory_value(request)

    first_field = cue.fields.first()
    aggregate = cue.cue_aggregate or 'count'
    formatted = _format_cue_display_value(value, aggregate)
    money_cues = (
        'RCCueTodaySales',
        'PostedCueToday',
        'RCCueTotalRevenue',
        'RCCueOverdueReceivables',
        'RCCueReceivables',
    )
    if cue.name in money_cues and value is not None:
        try:
            formatted = f'UGX {float(value):,.0f}'
        except (TypeError, ValueError):
            pass

    drill_down_query = ''
    if cue.name in ('RCCueTodaySales', 'PostedCueToday'):
        drill_down_query = 'posting_date=__today__&filterLabel=Today\'s sales'
    elif cue.name == 'RCCueTotalRevenue':
        drill_down_query = (
            'posting_date_from=__month_start__&posting_date_to=__month_end__'
            '&filterLabel=This month'
        )
    elif cue.name == 'RCCueOverdueReceivables':
        drill_down_query = (
            'open=True&due_date_to=__yesterday__'
            '&filterLabel=Overdue receivables'
        )

    caption = cue.caption or ''
    if cue.name == 'RCCueTotalRevenue':
        caption = 'Sales This Month'

    return {
        'Name': cue.name,
        'ControlId': cue.page_control_id,
        'Caption': caption,
        'Value': value,
        'FormattedValue': formatted,
        'CueStyle': cue.cue_style or '',
        'DrillDownPageId': cue.drill_down_page_id,
        'DrillDownQuery': drill_down_query,
        'LinkCaption': cue.headline_template or '',
        'ThresholdWarning': first_field.threshold_warning if first_field else None,
        'ThresholdDanger': first_field.threshold_danger if first_field else None,
        'LayoutStyle': layout_style,
    }


def _compute_delayed_orders_count(request) -> int:
    model = _get_model('SalesOrder')
    if model is None:
        return 0
    today = timezone.now().date()
    qs = model.objects.filter(
        status='Open',
        expected_delivery_date__lt=today,
        expected_delivery_date__isnull=False,
    )
    qs = _apply_request_branch_filter(qs, request, source_table='SalesOrder', model=model)
    return qs.count()


def _compute_avg_days_delayed(request):
    model = _get_model('SalesOrder')
    if model is None:
        return 0
    today = timezone.now().date()
    qs = model.objects.filter(
        status='Open',
        expected_delivery_date__lt=today,
        expected_delivery_date__isnull=False,
    )
    qs = _apply_request_branch_filter(qs, request, source_table='SalesOrder', model=model)
    count = qs.count()
    if not count:
        return 0
    total_days = sum((today - order.expected_delivery_date).days for order in qs)
    return round(total_days / count, 1)


def _compute_today_posted_sales(request) -> float:
    """Sum of posted sales invoice totals for today (branch-scoped)."""
    from decimal import Decimal

    from django.db.models import DecimalField, Sum, Value
    from django.db.models.functions import Coalesce
    from sales.views import SalesViewSet

    model = _get_model('SalesInvoice')
    if model is None:
        return 0.0
    today = timezone.now().date()
    qs = model.objects.filter(status='Posted', posting_date=today)
    qs = _apply_request_branch_filter(qs, request, source_table='SalesInvoice', model=model)
    qs = SalesViewSet._with_invoice_totals(qs)
    total = qs.aggregate(
        total=Coalesce(
            Sum('computed_total_amount'),
            Value(Decimal('0.00'), output_field=DecimalField(max_digits=18, decimal_places=2)),
        ),
    )['total']
    return float(total or 0)


def _serialize_salesperson_today_cues(request, drill_down_page: Page) -> list[dict]:
    """Dynamic cue tiles: today's posted sales total per salesperson (ledger user)."""
    from decimal import Decimal

    from django.db.models import IntegerField, OuterRef, Subquery
    from sales.models import CustomerLedgerEntry, SalesInvoice
    from sales.views import SalesViewSet

    model = _get_model('SalesInvoice')
    if model is None or drill_down_page is None:
        return []

    today = timezone.now().date()
    qs = model.objects.filter(status='Posted', posting_date=today)
    qs = _apply_request_branch_filter(qs, request, source_table='SalesInvoice', model=model)
    qs = SalesViewSet._with_invoice_totals(qs)

    invoice_numbers = list(qs.values_list('invoice_no', flat=True))
    if not invoice_numbers:
        return []

    ledger_user_map: dict[str, object] = {}
    ledger_entries = (
        CustomerLedgerEntry.objects.filter(document_no__in=invoice_numbers)
        .select_related('user')
        .order_by('document_no', '-id')
    )
    for entry in ledger_entries:
        if entry.document_no not in ledger_user_map and entry.user_id:
            ledger_user_map[entry.document_no] = entry.user

    user_totals: dict[int, dict] = {}
    for invoice in qs.values('invoice_no', 'computed_total_amount'):
        invoice_no = invoice['invoice_no']
        user = ledger_user_map.get(invoice_no)
        user_id = user.id if user else 0
        user_name = (
            getattr(user, 'full_name', None)
            or getattr(user, 'username', None)
            or 'Unknown'
        )
        if user_id not in user_totals:
            user_totals[user_id] = {
                'user_id': user_id,
                'user_name': user_name,
                'total_sales': Decimal('0'),
            }
        user_totals[user_id]['total_sales'] += Decimal(
            str(invoice['computed_total_amount'] or 0),
        )

    ranked = sorted(
        user_totals.values(),
        key=lambda row: row['total_sales'],
        reverse=True,
    )[:8]

    cues: list[dict] = []
    for row in ranked:
        user_id = row['user_id']
        user_name = row['user_name']
        total = float(row['total_sales'])
        if user_id <= 0:
            caption = 'Unassigned'
        else:
            caption = user_name
        safe_label = urllib.parse.quote(f"Sales by {user_name}")
        safe_name = urllib.parse.quote(str(user_name))
        drill_query = (
            f'posting_date=__today__&ctx2Field=ledger_user_id&ctx2={user_id}'
            f'&filterLabel={safe_label}&ctxLabel={safe_name}'
        )
        cues.append({
            'Name': f'PostedCueSalesPerson_{user_id}',
            'ControlId': -(user_id or 0) - 10000,
            'Caption': caption,
            'Value': total,
            'FormattedValue': f'UGX {total:,.0f}',
            'CueStyle': 'Subordinate',
            'DrillDownPageId': drill_down_page.page_id,
            'DrillDownQuery': drill_query,
            'LinkCaption': '',
            'ThresholdWarning': None,
            'ThresholdDanger': None,
            'LayoutStyle': 'StandardCues',
        })
    return cues


def _serialize_list_cue_groups(page: Page, request) -> list[dict]:
    """Cue groups configured on a List page (BC-style list cues)."""
    groups: list[dict] = []
    for control in page.page_controls.filter(
        control_type='CueGroup',
        parent_control=None,
    ).order_by('tab_index', 'page_control_id'):
        layout_style = 'StandardCues'
        child_cues = control.children.filter(control_type='Cue').order_by(
            'tab_index', 'page_control_id',
        )
        cues = [
            _serialize_cue_data(cue, layout_style=layout_style, request=request)
            for cue in child_cues
        ]
        groups.append({
            'ControlId': control.page_control_id,
            'Caption': control.caption,
            'LayoutStyle': layout_style,
            'Cues': cues,
        })

    return groups


def _month_chart_label(year: int, month: int) -> str:
    month_labels = [
        'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
        'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
    ]
    return f"{month_labels[month - 1]} '{year % 100:02d}"


def _format_chart_currency(value: float) -> str:
    try:
        amount = float(value or 0)
    except (TypeError, ValueError):
        amount = 0.0
    if amount >= 1_000_000:
        return f'UGX {amount / 1_000_000:.1f}M'
    if amount >= 1_000:
        return f'UGX {amount / 1_000:.0f}K'
    return f'UGX {amount:,.0f}'


def _compute_revenue_chart(request) -> dict:
    """Last 6 calendar months of posted sales invoice revenue (excludes open orders)."""
    line_model = _get_model('SalesInvoiceLine')
    if line_model is None:
        return {'Points': [], 'Subtitle': '', 'TotalFormatted': 'UGX 0'}

    today = timezone.now().date()
    start = today.replace(day=1)
    months: list[tuple[int, int]] = []
    for offset in range(5, -1, -1):
        month = start.month - offset
        year = start.year
        while month <= 0:
            month += 12
            year -= 1
        months.append((year, month))

    earliest_year, earliest_month = months[0]
    range_start = today.replace(year=earliest_year, month=earliest_month, day=1)

    line_total = django_models.ExpressionWrapper(
        django_models.F('quantity') * django_models.F('unit_price')
        - django_models.F('line_discount_amount'),
        output_field=django_models.DecimalField(max_digits=18, decimal_places=2),
    )
    line_qs = line_model.objects.filter(
        sales_invoice__status='Posted',
        sales_invoice__posting_date__gte=range_start,
    )
    line_qs = _apply_request_branch_filter(
        line_qs, request, source_table='SalesInvoiceLine', model=line_model,
    )
    rows = (
        line_qs
        .annotate(month=TruncMonth('sales_invoice__posting_date'))
        .values('month')
        .annotate(total=Sum(line_total))
        .order_by('month')
    )
    totals_by_month = {
        (row['month'].year, row['month'].month): float(row['total'] or 0)
        for row in rows
        if row['month'] is not None
    }

    points = []
    running_total = 0.0
    for year, month in months:
        value = totals_by_month.get((year, month), 0)
        running_total += value
        points.append({
            'Label': _month_chart_label(year, month),
            'Value': value,
            'FormattedValue': _format_chart_currency(value),
            'Year': year,
            'Month': month,
        })

    return {
        'Points': points,
        'Subtitle': 'Posted sales invoices · last 6 months',
        'TotalFormatted': _format_chart_currency(running_total),
    }


def _compute_brick_items() -> dict:
    item_model = _get_model('Item')
    customer_model = _get_model('Customer')
    item_page = Page.objects.filter(name='ItemList').first()
    customer_page = Page.objects.filter(name='CustomerList').first()
    item_card = Page.objects.filter(name='ItemCard').first()
    customer_card = Page.objects.filter(name='CustomerCard').first()

    items = []
    if item_model is not None:
        for obj in item_model.objects.filter(blocked=False).order_by('-unit_price')[:3]:
            items.append({
                'Title': obj.item_name,
                'Subtitle': str(obj.no),
                'ListPageId': item_page.page_id if item_page else None,
                'CardPageId': item_card.page_id if item_card else None,
                'SystemId': str(obj.system_id),
            })

    customers = []
    if customer_model is not None:
        for obj in customer_model.objects.all().order_by('name')[:3]:
            customers.append({
                'Title': obj.name,
                'Subtitle': str(obj.no),
                'ListPageId': customer_page.page_id if customer_page else None,
                'CardPageId': customer_card.page_id if customer_card else None,
                'SystemId': str(obj.system_id),
            })

    return {'Items': items, 'Customers': customers}


def _compute_aggregate(control: PageControl, qs):
    """Apply aggregation function from control settings to a queryset."""
    aggregate = control.cue_aggregate or 'count'
    agg_field = control.cue_aggregate_field or ''
    if aggregate == 'count':
        return qs.count()
    if not agg_field:
        return None
    if aggregate == 'sum':
        return qs.aggregate(v=Sum(agg_field))['v'] or 0
    if aggregate == 'avg':
        return qs.aggregate(v=Avg(agg_field))['v'] or 0
    if aggregate == 'max':
        return qs.aggregate(v=Max(agg_field))['v'] or 0
    if aggregate == 'min':
        return qs.aggregate(v=Min(agg_field))['v'] or 0
    return None


def _compute_cue_value(control: PageControl, request=None):
    """Compute the aggregate value for a Cue or Headline control."""
    model = _get_model(control.cue_source_table)
    if model is None:
        return None
    qs = model.objects.all()
    if control.cue_filter_field and control.cue_filter_value:
        try:
            filter_val = _parse_cue_filter_value(control.cue_filter_value)
            qs = qs.filter(**{control.cue_filter_field: filter_val})
        except Exception:
            return None
    if request is not None:
        qs = _apply_request_branch_filter(
            qs, request, source_table=control.cue_source_table, model=model,
        )
    return _compute_aggregate(control, qs)


def _headline_uses_today_sales(control: PageControl) -> bool:
    if control.cue_source_table != 'SalesInvoice':
        return False
    name = (control.name or '').lower()
    template = (control.headline_template or '').lower()
    return 'today' in name or 'today' in template


def _compute_headline_value(control: PageControl, request=None):
    if _headline_uses_today_sales(control):
        return _compute_today_posted_sales(request)
    if control.name == 'RCHeadlineRevenue':
        return _compute_this_month_revenue(request)
    if control.name == 'RCCueTotalRevenue':
        chart = _compute_revenue_chart(request)
        return sum(point.get('Value', 0) for point in chart.get('Points', []))
    if control.name == 'RCHeadlineOverdue':
        return _compute_overdue_receivables(request)
    if not control.cue_source_table:
        return None
    return _compute_cue_value(control, request=request)


def _render_headline_text(control: PageControl, request=None) -> str:
    template = (control.headline_template or '').strip()
    if not template:
        return control.caption or ''
    value = _compute_headline_value(control, request)
    if value is None:
        return template
    if isinstance(value, (int, float)):
        if control.cue_aggregate in ('sum', 'avg', 'max', 'min') or _headline_uses_today_sales(control):
            formatted = f'UGX {value:,.0f}'
        elif isinstance(value, float) and not float(value).is_integer():
            formatted = f'{float(value):,.1f}'
        else:
            formatted = f'{int(value):,}'
    else:
        formatted = str(value)
    try:
        return template.format(value=formatted, period='this month')
    except (KeyError, IndexError):
        return template


def _serialize_headline_item(control: PageControl, request=None) -> dict:
    drill_down_query = ''
    if _headline_uses_today_sales(control):
        drill_down_query = "posting_date=__today__&filterLabel=Today's sales"
    elif control.name == 'RCHeadlineRevenue':
        drill_down_query = (
            'posting_date_from=__month_start__&posting_date_to=__month_end__'
            '&filterLabel=This month'
        )
    elif control.name == 'RCHeadlineOverdue':
        drill_down_query = (
            'open=True&due_date_to=__yesterday__'
            '&filterLabel=Overdue receivables'
        )
    return {
        'ControlId': control.page_control_id,
        'Title': control.caption or '',
        'Text': _render_headline_text(control, request),
        'DrillDownPageId': control.drill_down_page_id,
        'DrillDownQuery': drill_down_query,
    }


def _build_headline_section(group_control: PageControl, items: list[dict]) -> dict:
    return {
        'ControlId': group_control.page_control_id,
        'ControlType': 'Headline',
        'Caption': group_control.caption or '',
        'Headlines': items,
        'Value': items[0]['Text'] if items else '',
    }


def _compute_headline(control: PageControl, request=None) -> str:
    """Render the headline template with the computed aggregate value."""
    return _render_headline_text(control, request)


def _get_part_rows(control: PageControl, request=None) -> list:
    """Return the last max_records rows from a Part control's sub-page."""
    if not control.part_page_id:
        return []
    part_page = control.part_page
    sub_control = part_page.page_controls.filter(
        control_type__in=['Repeater', 'Group']
    ).first()
    if not sub_control:
        return []
    source_table = sub_control.source_table or part_page.source_table
    model = _get_model(source_table)
    if model is None:
        return []
    fields = list(sub_control.fields.filter(visible=True).order_by('tab_index'))
    max_rec = control.max_records or 5
    try:
        qs = model.objects.all().order_by('-pk')
        qs = _apply_page_list_scope(part_page, qs)
        if request is not None:
            qs = _apply_request_branch_filter(
                qs, request, source_table=source_table, model=model,
            )
        qs = list(qs[:max_rec])
    except Exception:
        return []
    return [_serialize_record(obj, fields, request) for obj in qs]


# ── Role Centre view ───────────────────────────────────────────────────────────

class RoleCentreView(APIView):
    """GET /api/pages/rolecentre/?PageId= — aggregate Cue data for a RoleCenter page."""

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        page_id = request.query_params.get('PageId')
        if not page_id:
            return Response({'error': 'PageId is required'}, status=status.HTTP_400_BAD_REQUEST)

        schema = _get_schema(request)
        if not schema:
            return Response({'error': 'No tenant in token'}, status=status.HTTP_400_BAD_REQUEST)

        with schema_context(schema):
            try:
                page = Page.objects.prefetch_related(
                    'page_controls__fields',
                    'page_controls__children__fields',
                    'page_controls__part_page__page_controls__fields',
                    'page_controls__drill_down_page',
                    'page_actions',
                ).get(pk=page_id)
            except Page.DoesNotExist:
                return Response({'error': 'Page not found'}, status=status.HTTP_404_NOT_FOUND)

            if page.page_type != 'RoleCenter':
                return Response(
                    {'error': f'Page {page_id} is not a RoleCenter (got {page.page_type})'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            sections = []
            # Only top-level controls (parent_control=None) define sections
            top_controls = page.page_controls.filter(
                parent_control=None,
            ).order_by('tab_index', 'page_control_id')

            assistance_part = top_controls.filter(name='RCRecentSalesOrders').first()
            assistance_headline = top_controls.filter(name='RCBusinessAssistance').first()

            for control in top_controls:
                if control.name == 'RCRecentSalesOrders' and assistance_headline:
                    continue

                if control.name == 'RCReports':
                    from financials.models import FinancialReport

                    fr_list = Page.objects.filter(name='FinancialReportList').first()
                    fr_overview = Page.objects.filter(name='FinancialReportOverview').first()
                    report_rows = []
                    for report in FinancialReport.objects.order_by('name'):
                        report_rows.append({
                            'Name': report.name,
                            'Description': report.description or report.name,
                            'SystemId': str(report.system_id),
                            'PeriodType': report.period_type or 'Month',
                        })
                    sections.append({
                        'ControlId': control.page_control_id,
                        'ControlType': 'Reports',
                        'Caption': control.caption or 'Reports',
                        'ListPageId': fr_list.page_id if fr_list else None,
                        'OverviewPageId': fr_overview.page_id if fr_overview else None,
                        'Reports': report_rows,
                    })
                    continue

                if control.name == 'RCQuickAccess':
                    sections.append({
                        'ControlId': control.page_control_id,
                        'ControlType': 'Brick',
                        'Caption': control.caption or 'Quick Access — Top Items and Customers',
                        'Bricks': _compute_brick_items(),
                    })
                    continue

                if control.name == 'RCBusinessAssistance':
                    part_control = assistance_part
                    rows = _get_part_rows(part_control, request) if part_control else []
                    revenue_chart = _compute_revenue_chart(request)
                    sections.append({
                        'ControlId': control.page_control_id,
                        'ControlType': 'Assistance',
                        'Caption': control.caption or 'Business Assistance',
                        'ChartCaption': 'Revenue by month',
                        'ChartSubtitle': revenue_chart.get('Subtitle', ''),
                        'ChartTotalFormatted': revenue_chart.get('TotalFormatted', 'UGX 0'),
                        'ChartPoints': revenue_chart.get('Points', []),
                        'ListCaption': part_control.caption if part_control else 'Recent Sales Orders',
                        'PartPageId': part_control.part_page_id if part_control else None,
                        'Rows': rows,
                    })
                    continue

                if control.control_type == 'HeadlineGroup':
                    child_headlines = control.children.filter(
                        control_type='Headline',
                        visible=True,
                    ).order_by('tab_index', 'page_control_id')
                    items = [
                        _serialize_headline_item(headline, request)
                        for headline in child_headlines
                    ]
                    if items:
                        sections.append(_build_headline_section(control, items))
                    continue

                if control.control_type == 'Headline':
                    sections.append(
                        _build_headline_section(
                            control,
                            [_serialize_headline_item(control, request)],
                        )
                    )
                    continue

                elif control.control_type == 'CueGroup':
                    layout_style = _rc_layout_style(control)
                    child_cues = control.children.filter(
                        control_type='Cue',
                    ).order_by('tab_index', 'page_control_id')
                    cues = [
                        _serialize_cue_data(cue, layout_style=layout_style, request=request)
                        for cue in child_cues
                    ]
                    sections.append({
                        'ControlId': control.page_control_id,
                        'ControlType': 'CueGroup',
                        'Caption': control.caption,
                        'LayoutStyle': layout_style,
                        'Cues': cues,
                    })

                elif control.control_type == 'Part' and control.part_page_id:
                    rows = _get_part_rows(control, request)
                    sections.append({
                        'ControlId': control.page_control_id,
                        'ControlType': 'Part',
                        'Caption': control.caption,
                        'PartPageId': control.part_page_id,
                        'Rows': rows,
                    })

        return Response({
            'PageId': page.page_id,
            'Name': page.name,
            'Caption': page.caption,
            'Sections': sections,
            'NavItems': [
                {
                    'Name': item['name'],
                    'Caption': item['caption'],
                    'ImageUrl': item['imageUrl'],
                    'TargetPageName': item['targetPageName'],
                }
                for item in serialize_rc_nav_items(page)
            ],
        })


class ListCuesView(APIView):
    """GET /api/pages/list-cues/?PageId= — cue tiles for List pages."""

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        page_id = request.query_params.get('PageId')
        if not page_id:
            return Response({'error': 'PageId is required'}, status=status.HTTP_400_BAD_REQUEST)

        schema = _get_schema(request)
        if not schema:
            return Response({'error': 'No tenant in token'}, status=status.HTTP_400_BAD_REQUEST)

        with schema_context(schema):
            try:
                page = Page.objects.get(pk=page_id)
            except Page.DoesNotExist:
                return Response({'error': 'Page not found'}, status=status.HTTP_404_NOT_FOUND)

            if page.page_type != 'List':
                return Response({'CueGroups': []})

            groups = _serialize_list_cue_groups(page, request)
            response_payload = {
                'PageId': page.page_id,
                'Name': page.name,
                'CueGroups': groups,
            }

        return Response(response_payload)


class SetupSoloView(APIView):
    """GET /api/pages/setup-solo/?PageId= — singleton setup row for card navigation."""

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        page_id = request.query_params.get('PageId')
        if not page_id:
            return Response({'error': 'PageId is required'}, status=status.HTTP_400_BAD_REQUEST)

        schema = _get_schema(request)
        if not schema:
            return Response({'error': 'No tenant in token'}, status=status.HTTP_400_BAD_REQUEST)

        with schema_context(schema):
            try:
                page = Page.objects.get(pk=page_id)
            except Page.DoesNotExist:
                return Response({'error': 'Page not found'}, status=status.HTTP_404_NOT_FOUND)

            if page.source_table not in SETUP_SOURCE_TABLES and page.source_table != USER_PERSONALIZATION_SOURCE_TABLE:
                return Response({'error': 'Not a singleton setup page'}, status=status.HTTP_400_BAD_REQUEST)

            if page.page_type != 'Card':
                return Response({'error': 'Page is not a Card page'}, status=status.HTTP_400_BAD_REQUEST)

            model = _get_model(page.source_table)
            if model is None:
                return Response({'error': 'Model not found'}, status=status.HTTP_400_BAD_REQUEST)

            if page.source_table == USER_PERSONALIZATION_SOURCE_TABLE:
                obj = model.get_or_create_for_user(request.user)
            elif page.source_table == 'CompanyInformation':
                obj = model.sync_from_public_company()
            elif page.source_table == 'CompanySubscription':
                obj = model.sync_from_public()
            else:
                obj = model.get_solo() if hasattr(model, 'get_solo') else model.objects.first()
            if obj is None:
                return Response(
                    {'error': f'{page.caption} has not been initialized for this company.'},
                    status=status.HTTP_404_NOT_FOUND,
                )

        return Response({'SystemId': str(obj.system_id)})
