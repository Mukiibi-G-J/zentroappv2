"""Resolve table-relation lookups from page field metadata + TableRelation rows."""

from pages.models import PageControlField, TableRelation


def _normalize_relation_context_value(context_field: str, value):
    """Map stored enum keys to TableRelation context_value labels when needed."""
    if not value:
        return value
    if context_field == 'bal_account_type':
        from financials.enums import BalacingAccountType, coerce_balancing_account_type

        key = coerce_balancing_account_type(value)
        if key:
            try:
                return BalacingAccountType[key].value
            except KeyError:
                pass
    if context_field in ('account_type', 'bal_account_type') and isinstance(value, str):
        from financials.enums import BalacingAccountType

        for tag in BalacingAccountType:
            if value == tag.name:
                return tag.value
    return value


def context_value_for_field(field: PageControlField, record_values=None):
    """Return the active context value for a context-sensitive relation field."""
    record_values = record_values or {}
    if not field.relation_context_field:
        return None
    value = record_values.get(field.relation_context_field)
    if value is None or value == '':
        value = field.relation_context_default or ''
    value = _normalize_relation_context_value(field.relation_context_field, value)
    return value or None


def resolve_table_relation(field: PageControlField, record_values=None):
    """
    Return (related_table, related_field, display_field) for a page field.
    Uses conditional TableRelation rows when relation_context_field is set.
    """
    source_table = field.page_control.source_table or field.page.source_table
    context_field = field.relation_context_field
    context_value = context_value_for_field(field, record_values)

    if context_field and not context_value:
        return None, None, None

    if context_field and context_value:
        rel = TableRelation.objects.filter(
            source_table=source_table,
            source_field=field.name,
            context_field=context_field,
            context_value=context_value,
        ).first()
        if rel:
            return rel.related_table, rel.related_field, rel.display_field

    rel = TableRelation.objects.filter(
        source_table=source_table,
        source_field=field.name,
        context_field='',
        context_value='',
    ).first()

    if rel:
        return rel.related_table, rel.related_field, rel.display_field

    if field.has_table_relation and field.related_table and field.related_field:
        return field.related_table, field.related_field, field.related_display_field

    return None, None, None
