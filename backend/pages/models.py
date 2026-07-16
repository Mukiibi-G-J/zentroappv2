from django.db import models


PAGE_TYPE_CHOICES = [
    ('List', 'List'),
    ('Card', 'Card'),
    ('Document', 'Document'),
    ('ListPart', 'ListPart'),
    ('Journal', 'Journal'),
    ('Worksheet', 'Worksheet'),
    ('RoleCenter', 'Role Center'),
    ('POS', 'Point of Sale'),
    ('Queue', 'Sync Queue'),
]

FIELD_TYPE_CHOICES = [
    ('Text', 'Text'),
    ('Integer', 'Integer'),
    ('Decimal', 'Decimal'),
    ('Boolean', 'Boolean'),
    ('Date', 'Date'),
    ('DateTime', 'DateTime'),
    ('Enum', 'Enum'),
    ('Option', 'Option'),
    ('Code', 'Code'),
    ('Image', 'Image'),
    ('File', 'File'),
    ('Password', 'Password'),
]

CONTROL_TYPE_CHOICES = [
    ('Group', 'Group'),
    ('SubPage', 'SubPage'),
    ('Repeater', 'Repeater'),
    ('FactBox', 'FactBox'),
    ('Part', 'Part'),
    ('CueGroup', 'Cue Group'),
    ('Cue', 'Cue'),
    ('HeadlineGroup', 'Headline Group'),
    ('Headline', 'Headline'),
]

CUE_AGGREGATE_CHOICES = [
    ('count', 'Count'),
    ('sum', 'Sum'),
    ('avg', 'Average'),
    ('max', 'Max'),
    ('min', 'Min'),
]

CUE_STYLE_CHOICES = [
    ('', 'Normal'),
    ('Favorable', 'Favorable (green)'),
    ('Unfavorable', 'Unfavorable (red)'),
    ('Ambiguous', 'Ambiguous (yellow)'),
    ('Subordinate', 'Subordinate (grey)'),
]


class Page(models.Model):
    page_id = models.AutoField(primary_key=True)
    object_id = models.IntegerField(
        null=True,
        blank=True,
        unique=True,
        db_index=True,
        help_text=(
            'Zentro page ID for permissions (same as page_id for registered pages, '
            'e.g. 10201 ItemList). Synced to base.Objects for permission set lines.'
        ),
    )
    name = models.CharField(max_length=200, unique=True)
    caption = models.CharField(max_length=200)
    source_table = models.CharField(max_length=200)
    page_type = models.CharField(max_length=20, choices=PAGE_TYPE_CHOICES, default='List')
    editable = models.BooleanField(default=True)
    insert_allowed = models.BooleanField(default=True)
    delete_allowed = models.BooleanField(default=True)
    modify_allowed = models.BooleanField(default=True)
    card_page = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='list_pages')
    header_page = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='sub_pages')
    context_filter_field = models.CharField(max_length=200, blank=True)
    context_key_field = models.CharField(max_length=200, blank=True)
    document_type = models.CharField(max_length=100, blank=True)
    list_exclude_field = models.CharField(max_length=200, blank=True)
    list_exclude_values = models.TextField(blank=True)
    list_filter_field = models.CharField(
        max_length=200,
        blank=True,
        help_text='When set with list_filter_value, list pages show only matching records (e.g. status=Posted).',
    )
    list_filter_value = models.CharField(
        max_length=200,
        blank=True,
        help_text='Value for list_filter_field (e.g. Posted, Open).',
    )
    title_field = models.CharField(max_length=200, blank=True)
    desktop_enabled = models.BooleanField(
        default=False,
        help_text='When true, this page is available in the Zentro Desktop Electron app.',
    )

    class Meta:
        db_table = 'page_engine_page'
        ordering = ['page_id']

    def __str__(self):
        return self.caption


class PageControl(models.Model):
    page_control_id = models.AutoField(primary_key=True)
    page = models.ForeignKey(Page, on_delete=models.CASCADE, related_name='page_controls')
    control_type = models.CharField(max_length=20, choices=CONTROL_TYPE_CHOICES, default='Repeater')
    name = models.CharField(max_length=200)
    caption = models.CharField(max_length=200)
    source_table = models.CharField(max_length=200)
    show_caption = models.BooleanField(default=True)
    editable = models.BooleanField(default=True)
    visible = models.BooleanField(default=True)
    tab_index = models.IntegerField(
        default=0,
        help_text='Display/ordering position of this control within its page',
    )
    parent_control = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='children',
        help_text='Parent CueGroup for Cue controls',
    )
    part_page = models.ForeignKey(
        'Page',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='used_as_part',
        help_text='For ControlType=Part: the sub-page to embed',
    )
    link_field = models.CharField(
        max_length=100,
        blank=True,
        default='',
        help_text='For ControlType=Part: field on sub-table that links to parent PK',
    )
    max_records = models.IntegerField(
        default=5,
        help_text='For RoleCenter Part controls: max rows to return',
    )
    # ── Cue / CueGroup / Headline fields ─────────────────────────────────────
    cue_source_table = models.CharField(
        max_length=100,
        blank=True,
        default='',
        help_text='Model to aggregate for this CueGroup/Cue/Headline',
    )
    cue_aggregate = models.CharField(
        max_length=20,
        blank=True,
        default='count',
        choices=CUE_AGGREGATE_CHOICES,
        help_text='Aggregation function for Cue value',
    )
    cue_filter_field = models.CharField(
        max_length=100,
        blank=True,
        default='',
        help_text='Field to filter on for this Cue (e.g. status)',
    )
    cue_filter_value = models.CharField(
        max_length=100,
        blank=True,
        default='',
        help_text='Value to filter by (e.g. Open)',
    )
    cue_aggregate_field = models.CharField(
        max_length=100,
        blank=True,
        default='',
        help_text='Field to sum/avg/max/min (blank = count rows)',
    )
    drill_down_page = models.ForeignKey(
        'Page',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='cue_drill_down_source',
        help_text='List page to open when user clicks this Cue tile',
    )
    cue_style = models.CharField(
        max_length=20,
        blank=True,
        default='',
        choices=CUE_STYLE_CHOICES,
        help_text='Visual style of the Cue tile',
    )
    headline_template = models.CharField(
        max_length=500,
        blank=True,
        default='',
        help_text=(
            'Template for Headline control. '
            'Use {value} for computed value, {period} for time period. '
            'Example: "The biggest sales order was {value}"'
        ),
    )

    class Meta:
        db_table = 'page_engine_control'
        ordering = ['tab_index', 'page_control_id']


class PageControlField(models.Model):
    page_control_field_id = models.AutoField(primary_key=True)
    page_control = models.ForeignKey(PageControl, on_delete=models.CASCADE, related_name='fields')
    page = models.ForeignKey(Page, on_delete=models.CASCADE, related_name='fields')
    field_id = models.IntegerField(default=0)
    name = models.CharField(max_length=200)
    caption = models.CharField(max_length=200)
    field_type = models.CharField(max_length=20, choices=FIELD_TYPE_CHOICES, default='Text')
    visible = models.BooleanField(default=True)
    editable = models.BooleanField(default=True)
    primary_key = models.BooleanField(default=False)
    required = models.BooleanField(default=False)
    tab_index = models.IntegerField(default=0)
    tooltip = models.CharField(max_length=500, blank=True, null=True)
    enum_values = models.TextField(blank=True, null=True)
    no_series_code = models.CharField(max_length=50, blank=True, null=True)
    has_lookup_page = models.BooleanField(default=False)
    lookup_page = models.ForeignKey(Page, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    has_drill_down_page = models.BooleanField(default=False)
    drill_down_page = models.ForeignKey(Page, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    has_table_relation = models.BooleanField(default=False)
    related_table = models.CharField(max_length=200, blank=True, null=True)
    related_field = models.CharField(max_length=200, blank=True, null=True)
    related_display_field = models.CharField(max_length=200, blank=True, null=True)
    relation_context_field = models.CharField(max_length=200, blank=True, null=True)
    relation_context_default = models.CharField(max_length=200, blank=True, null=True)
    relation_lookup_footer = models.BooleanField(
        default=False,
        help_text='Show BC-style relation menu footer (+ New, Show details, Select from full list).',
    )
    relation_part_control_name = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        help_text='PageControl name of the Part to scroll to / add lines on for relation footer actions.',
    )
    freeze_column = models.BooleanField(default=False)
    visible_when_field = models.CharField(max_length=200, blank=True, null=True)
    visible_when_values = models.TextField(blank=True, null=True)
    threshold_warning = models.IntegerField(
        null=True,
        blank=True,
        help_text='Value at which Cue turns yellow (warning)',
    )
    threshold_danger = models.IntegerField(
        null=True,
        blank=True,
        help_text='Value at which Cue turns red (danger)',
    )

    class Meta:
        db_table = 'page_engine_field'
        ordering = ['tab_index', 'page_control_field_id']


class TableRelation(models.Model):
    """Conditional table relation: source field → related table, optionally filtered by context."""

    source_table = models.CharField(max_length=200)
    source_field = models.CharField(max_length=200)
    related_table = models.CharField(max_length=200)
    related_field = models.CharField(max_length=200)
    display_field = models.CharField(max_length=200)
    context_field = models.CharField(
        max_length=200,
        blank=True,
        help_text='When set with context_value, this row applies only for that context.',
    )
    context_value = models.CharField(max_length=200, blank=True)

    class Meta:
        db_table = 'page_engine_table_relation'
        unique_together = ('source_table', 'source_field', 'context_field', 'context_value')

    def __str__(self):
        return f'{self.source_table}.{self.source_field} → {self.related_table}'


class PageAction(models.Model):
    ACTION_TYPE_CHOICES = [
        ('Ribbon', 'Ribbon'),
        ('NavItem', 'Nav Item'),
    ]

    action_id = models.AutoField(primary_key=True)
    page = models.ForeignKey(Page, on_delete=models.CASCADE, related_name='page_actions')
    name = models.CharField(max_length=200)
    caption = models.CharField(max_length=200)
    action_type = models.CharField(
        max_length=20,
        choices=ACTION_TYPE_CHOICES,
        default='Ribbon',
        help_text='Ribbon = card/worksheet actions; NavItem = Role Centre sidebar links',
    )
    requires_confirmation = models.BooleanField(default=False)
    confirmation_message = models.TextField(blank=True, null=True)
    tooltip = models.CharField(max_length=500, blank=True, null=True)
    visible = models.BooleanField(default=True)
    image_url = models.CharField(max_length=500, blank=True, null=True)
    action_relative_url = models.CharField(max_length=500, blank=True, null=True)
    ribbon_tab = models.CharField(max_length=100, blank=True, null=True)
    visible_when_field = models.CharField(max_length=200, blank=True, null=True)
    visible_when_values = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'page_engine_action'
        ordering = ['action_id']
