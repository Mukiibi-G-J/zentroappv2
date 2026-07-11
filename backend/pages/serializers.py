from rest_framework import serializers
from .models import Page, PageControl, PageControlField, PageAction


class PageControlFieldSerializer(serializers.ModelSerializer):
    FieldId = serializers.IntegerField(source='field_id')
    PageId = serializers.IntegerField(source='page_id')
    PageControlId = serializers.IntegerField(source='page_control_id')
    PageControlFieldId = serializers.IntegerField(source='page_control_field_id')
    Name = serializers.CharField(source='name')
    Caption = serializers.CharField(source='caption')
    FieldType = serializers.CharField(source='field_type')
    Visible = serializers.BooleanField(source='visible')
    Editable = serializers.BooleanField(source='editable')
    PrimaryKey = serializers.BooleanField(source='primary_key')
    Required = serializers.BooleanField(source='required')
    TabIndex = serializers.IntegerField(source='tab_index')
    Tooltip = serializers.CharField(source='tooltip', allow_null=True)
    EnumValues = serializers.CharField(source='enum_values', allow_null=True)
    NoSeriesCode = serializers.CharField(source='no_series_code', allow_null=True)
    HasLookupPage = serializers.BooleanField(source='has_lookup_page')
    LookupPageId = serializers.SerializerMethodField()
    HasDrillDownPage = serializers.BooleanField(source='has_drill_down_page')
    DrillDownPageId = serializers.SerializerMethodField()
    HasTableRelation = serializers.BooleanField(source='has_table_relation')
    RelatedTable = serializers.CharField(source='related_table', allow_null=True)
    RelatedField = serializers.CharField(source='related_field', allow_null=True)
    RelatedDisplayField = serializers.CharField(source='related_display_field', allow_null=True)
    RelationContextField = serializers.CharField(source='relation_context_field', allow_null=True)
    RelationContextDefault = serializers.CharField(source='relation_context_default', allow_null=True)
    RelationLookupFooter = serializers.BooleanField(source='relation_lookup_footer')
    RelationPartControlName = serializers.CharField(
        source='relation_part_control_name', allow_null=True,
    )
    FreezeColumn = serializers.BooleanField(source='freeze_column')
    VisibleWhenField = serializers.CharField(source='visible_when_field', allow_null=True)
    VisibleWhenValues = serializers.CharField(source='visible_when_values', allow_null=True)
    ThresholdWarning = serializers.IntegerField(source='threshold_warning', allow_null=True)
    ThresholdDanger = serializers.IntegerField(source='threshold_danger', allow_null=True)

    class Meta:
        model = PageControlField
        fields = [
            'FieldId', 'PageId', 'PageControlId', 'PageControlFieldId',
            'Name', 'Caption', 'FieldType', 'Visible', 'Editable',
            'PrimaryKey', 'Required', 'TabIndex', 'Tooltip', 'EnumValues',
            'NoSeriesCode', 'HasLookupPage', 'LookupPageId', 'HasDrillDownPage',
            'DrillDownPageId', 'HasTableRelation', 'RelatedTable', 'RelatedField',
            'RelatedDisplayField', 'RelationContextField', 'RelationContextDefault',
            'RelationLookupFooter', 'RelationPartControlName',
            'FreezeColumn', 'VisibleWhenField', 'VisibleWhenValues',
            'ThresholdWarning', 'ThresholdDanger',
        ]

    def get_LookupPageId(self, obj):
        return obj.lookup_page_id

    def get_DrillDownPageId(self, obj):
        return obj.drill_down_page_id


class PageActionSerializer(serializers.ModelSerializer):
    ActionId = serializers.IntegerField(source='action_id')
    PageId = serializers.IntegerField(source='page_id')
    Name = serializers.CharField(source='name')
    Caption = serializers.CharField(source='caption')
    RequiresConfirmation = serializers.BooleanField(source='requires_confirmation')
    ConfirmationMessage = serializers.CharField(source='confirmation_message', allow_null=True)
    Tooltip = serializers.CharField(source='tooltip', allow_null=True)
    Visible = serializers.BooleanField(source='visible')
    ImageUrl = serializers.CharField(source='image_url', allow_null=True)
    ActionRelativeUrl = serializers.CharField(source='action_relative_url', allow_null=True)
    RibbonTab = serializers.CharField(source='ribbon_tab', allow_null=True)
    VisibleWhenField = serializers.CharField(source='visible_when_field', allow_null=True)
    VisibleWhenValues = serializers.CharField(source='visible_when_values', allow_null=True)
    ActionType = serializers.CharField(source='action_type')

    class Meta:
        model = PageAction
        fields = [
            'ActionId', 'PageId', 'Name', 'Caption', 'RequiresConfirmation',
            'ConfirmationMessage', 'Tooltip', 'Visible', 'ImageUrl',
            'ActionRelativeUrl', 'RibbonTab', 'VisibleWhenField', 'VisibleWhenValues',
            'ActionType',
        ]


class PartPageSummarySerializer(serializers.ModelSerializer):
    """Shallow page serializer for Part controls — no nested Parts."""

    PageId = serializers.IntegerField(source='page_id')
    Name = serializers.CharField(source='name')
    SourceTable = serializers.CharField(source='source_table')
    PageType = serializers.CharField(source='page_type')
    InsertAllowed = serializers.BooleanField(source='insert_allowed')
    DeleteAllowed = serializers.BooleanField(source='delete_allowed')
    ModifyAllowed = serializers.BooleanField(source='modify_allowed')
    DesktopEnabled = serializers.BooleanField(source='desktop_enabled')
    PageControls = serializers.SerializerMethodField()
    PageActions = PageActionSerializer(source='page_actions', many=True, read_only=True)

    class Meta:
        model = Page
        fields = [
            'PageId', 'Name', 'SourceTable', 'PageType',
            'InsertAllowed', 'DeleteAllowed', 'ModifyAllowed',
            'DesktopEnabled',
            'PageControls', 'PageActions',
        ]

    def get_PageControls(self, obj):
        controls = obj.page_controls.prefetch_related('fields').all()
        return PageControlSerializer(controls, many=True).data


class PageControlSerializer(serializers.ModelSerializer):
    PageControlId = serializers.IntegerField(source='page_control_id')
    PageId = serializers.IntegerField(source='page_id')
    ControlType = serializers.CharField(source='control_type')
    Name = serializers.CharField(source='name')
    Caption = serializers.CharField(source='caption')
    SourceTable = serializers.CharField(source='source_table')
    ShowCaption = serializers.BooleanField(source='show_caption')
    Editable = serializers.BooleanField(source='editable')
    Visible = serializers.BooleanField(source='visible')
    TabIndex = serializers.IntegerField(source='tab_index')
    PartPageId = serializers.IntegerField(source='part_page_id', allow_null=True)
    LinkField = serializers.CharField(source='link_field', allow_blank=True)
    PartPage = PartPageSummarySerializer(source='part_page', read_only=True, allow_null=True)
    Fields = PageControlFieldSerializer(source='fields', many=True, read_only=True)
    # Cue / CueGroup / Headline fields
    CueSourceTable = serializers.CharField(source='cue_source_table', allow_blank=True)
    CueAggregate = serializers.CharField(source='cue_aggregate', allow_blank=True)
    CueFilterField = serializers.CharField(source='cue_filter_field', allow_blank=True)
    CueFilterValue = serializers.CharField(source='cue_filter_value', allow_blank=True)
    CueAggregateField = serializers.CharField(source='cue_aggregate_field', allow_blank=True)
    CueStyle = serializers.CharField(source='cue_style', allow_blank=True)
    DrillDownPageId = serializers.IntegerField(source='drill_down_page_id', allow_null=True)
    HeadlineTemplate = serializers.CharField(source='headline_template', allow_blank=True)
    MaxRecords = serializers.IntegerField(source='max_records')

    class Meta:
        model = PageControl
        fields = [
            'PageControlId', 'PageId', 'ControlType', 'Name', 'Caption',
            'SourceTable', 'ShowCaption', 'Editable', 'Visible', 'TabIndex',
            'PartPageId', 'LinkField', 'PartPage', 'Fields',
            'CueSourceTable', 'CueAggregate', 'CueFilterField', 'CueFilterValue',
            'CueAggregateField', 'CueStyle', 'DrillDownPageId', 'HeadlineTemplate',
            'MaxRecords',
        ]


class PageSerializer(serializers.ModelSerializer):
    PageId = serializers.IntegerField(source='page_id')
    ObjectId = serializers.IntegerField(source='object_id', allow_null=True)
    Name = serializers.CharField(source='name')
    Caption = serializers.CharField(source='caption')
    SourceTable = serializers.CharField(source='source_table')
    PageType = serializers.CharField(source='page_type')
    Editable = serializers.BooleanField(source='editable')
    InsertAllowed = serializers.BooleanField(source='insert_allowed')
    DeleteAllowed = serializers.BooleanField(source='delete_allowed')
    ModifyAllowed = serializers.BooleanField(source='modify_allowed')
    CardPageId = serializers.SerializerMethodField()
    HeaderPageId = serializers.SerializerMethodField()
    ContextFilterField = serializers.CharField(source='context_filter_field', allow_blank=True)
    ContextKeyField = serializers.CharField(source='context_key_field', allow_blank=True)
    DocumentType = serializers.CharField(source='document_type', allow_blank=True)
    ListExcludeField = serializers.CharField(source='list_exclude_field', allow_blank=True)
    ListExcludeValues = serializers.CharField(source='list_exclude_values', allow_blank=True)
    ListFilterField = serializers.CharField(source='list_filter_field', allow_blank=True)
    ListFilterValue = serializers.CharField(source='list_filter_value', allow_blank=True)
    TitleField = serializers.CharField(source='title_field', allow_blank=True)
    DesktopEnabled = serializers.BooleanField(source='desktop_enabled')
    PageControls = PageControlSerializer(source='page_controls', many=True, read_only=True)
    PageActions = PageActionSerializer(source='page_actions', many=True, read_only=True)

    class Meta:
        model = Page
        fields = [
            'PageId', 'ObjectId', 'Name', 'Caption', 'SourceTable', 'PageType',
            'Editable', 'InsertAllowed', 'DeleteAllowed', 'ModifyAllowed',
            'CardPageId', 'HeaderPageId', 'ContextFilterField', 'ContextKeyField',
            'DocumentType', 'ListExcludeField', 'ListExcludeValues',
            'ListFilterField', 'ListFilterValue', 'TitleField',
            'DesktopEnabled',
            'PageControls', 'PageActions',
        ]

    def get_CardPageId(self, obj):
        return obj.card_page_id

    def get_HeaderPageId(self, obj):
        return obj.header_page_id
