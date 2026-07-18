export type GlobalSearchResultKind = 'page' | 'record'

export interface GlobalSearchItem {
  id: string
  kind: GlobalSearchResultKind
  title: string
  description?: string
  categoryTitle: string
  pageName: string
  systemId?: string
  imageUrl?: string
  iconKey?: string
}

export interface GlobalSearchSection {
  title: string
  items: GlobalSearchItem[]
}

export interface ApiGlobalSearchRow {
  title: string
  description?: string
  icon?: string
  category?: string
  categoryTitle?: string
  pageName?: string
  systemId?: string
  url?: string
}

export interface ApiGlobalSearchSection {
  title: string
  data: ApiGlobalSearchRow[]
}
