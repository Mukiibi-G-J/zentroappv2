import type { DataRecord } from './pagedata'

export interface PageControlField {
  FieldId: number
  PageId: number
  PageControlId: number
  PageControlFieldId: number
  Name: string
  Caption: string
  FieldType: 'Text' | 'Integer' | 'Decimal' | 'Boolean' | 'Date' | 'DateTime' | 'Enum' | 'Option' | 'Code' | 'Image' | 'File' | 'Password'
  Visible: boolean
  Editable: boolean
  PrimaryKey: boolean
  Required: boolean
  TabIndex: number
  Tooltip?: string | null
  EnumValues?: string | null
  NoSeriesCode?: string | null
  HasLookupPage?: boolean
  LookupPageId?: number | null
  HasDrillDownPage?: boolean
  DrillDownPageId?: number | null
  HasTableRelation?: boolean
  RelatedTable?: string | null
  RelatedField?: string | null
  RelatedDisplayField?: string | null
  RelationContextField?: string | null
  RelationContextDefault?: string | null
  RelationLookupFooter?: boolean
  RelationPartControlName?: string | null
  FreezeColumn?: boolean
  VisibleWhenField?: string | null
  VisibleWhenValues?: string | null
  ThresholdWarning?: number | null
  ThresholdDanger?: number | null
}

export interface PageAction {
  ActionId: number
  PageId: number
  Name: string
  Caption: string
  ActionType?: string
  RequiresConfirmation: boolean
  ConfirmationMessage?: string | null
  Tooltip?: string | null
  Visible: boolean
  ImageUrl?: string | null
  ActionRelativeUrl?: string | null
  RibbonTab?: string
  /** When set, actions with the same RibbonGroup on a tab render as one dropdown. */
  RibbonGroup?: string | null
  VisibleWhenField?: string | null
  VisibleWhenValues?: string | null
}

export interface TableRelationValue {
  Value: string
  Caption: string | null
  Code?: string | null
  Name?: string | null
  QuantityPerUnit?: string | null
}

export interface PageActionResponse {
  Successful: boolean
  Command: 'MESSAGE' | 'REFRESH' | 'NONE' | 'PREVIEW' | 'DOWNLOAD' | 'NAVIGATE' | 'OPEN_UNAPPLY'
  Content?: unknown
  Message?: string
}

export interface PageControl {
  PageControlId: number
  PageId: number
  ControlType: 'Group' | 'SubPage' | 'Repeater' | 'FactBox' | 'Part' | 'CueGroup' | 'Cue' | 'HeadlineGroup' | 'Headline'
  Name: string
  Caption: string
  SourceTable: string
  ShowCaption: boolean
  Editable: boolean
  Visible: boolean
  TabIndex: number
  PartPageId?: number | null
  LinkField?: string
  PartPage?: PartSummary | null
  Fields: PageControlField[]
  // Cue / CueGroup / Headline
  CueSourceTable?: string
  CueAggregate?: string
  CueFilterField?: string
  CueFilterValue?: string
  CueAggregateField?: string
  CueStyle?: string
  DrillDownPageId?: number | null
  HeadlineTemplate?: string
  MaxRecords?: number
}

export interface PartSummary {
  PageId: number
  Name: string
  SourceTable: string
  PageType: string
  InsertAllowed: boolean
  DeleteAllowed: boolean
  ModifyAllowed: boolean
  PageControls: PageControl[]
  PageActions?: PageAction[]
}

export interface Page {
  PageId: number
  /** Business Central page object ID when mapped (e.g. 31 = Item List). */
  ObjectId?: number | null
  Name: string
  Caption: string
  SourceTable: string
  PageType: 'List' | 'Card' | 'Document' | 'ListPart' | 'Journal' | 'Worksheet' | 'RoleCenter' | 'POS'
  Editable: boolean
  InsertAllowed: boolean
  DeleteAllowed: boolean
  ModifyAllowed: boolean
  CardPageId: number | null
  HeaderPageId?: number | null
  ContextFilterField?: string
  ContextKeyField?: string
  DocumentType?: string
  ListExcludeField?: string
  ListExcludeValues?: string
  ListFilterField?: string
  ListFilterValue?: string
  TitleField?: string
  /** When true, page is available in Zentro Desktop (backend `desktop_enabled`). */
  DesktopEnabled?: boolean
  PageControls: PageControl[]
  PageActions?: PageAction[]
}

// ── Role Centre types ──────────────────────────────────────────────────────────

export interface CueData {
  Name?: string
  ControlId: number
  Caption: string
  Value: number | null
  FormattedValue?: string | null
  CueStyle: string
  DrillDownPageId: number | null
  DrillDownQuery?: string | null
  LinkCaption?: string
  ThresholdWarning: number | null
  ThresholdDanger: number | null
}

export interface ChartPoint {
  Label: string
  Value: number
  FormattedValue?: string
  Year?: number
  Month?: number
}

export interface BrickCard {
  Title: string
  Subtitle: string
  ListPageId: number | null
  CardPageId: number | null
  SystemId: string
}

export interface HeadlineItem {
  ControlId: number
  Title: string
  Text: string
  DrillDownPageId?: number | null
  DrillDownQuery?: string
}

export interface RoleCentreReportAction {
  Name: string
  Description: string
  SystemId: string
  PeriodType?: string
}

export interface RoleCentreSection {
  ControlId: number
  ControlType: 'Headline' | 'CueGroup' | 'Part' | 'Brick' | 'Assistance' | 'Reports'
  Caption: string
  LayoutStyle?: 'NormalCues' | 'StandardCues'
  // Headline (BC HeadlinePart — one or more rotating lines)
  Value?: string
  Headlines?: HeadlineItem[]
  // CueGroup
  Cues?: CueData[]
  // Part / Assistance list
  PartPageId?: number
  Rows?: DataRecord[]
  // Brick
  Bricks?: {
    Items: BrickCard[]
    Customers: BrickCard[]
  }
  // Assistance
  ChartCaption?: string
  ChartSubtitle?: string
  ChartTotalFormatted?: string
  ChartPoints?: ChartPoint[]
  ListCaption?: string
  // Reports quick actions
  ListPageId?: number | null
  OverviewPageId?: number | null
  Reports?: RoleCentreReportAction[]
}

export interface RoleCentreNavItem {
  Name: string
  Caption: string
  ImageUrl: string
  TargetPageName: string
}

export interface RoleCentreData {
  PageId: number
  Name: string
  Caption: string
  Sections: RoleCentreSection[]
  NavItems?: RoleCentreNavItem[]
}

export interface ListCuesData {
  PageId: number
  Name: string
  CueGroups: RoleCentreSection[]
}
