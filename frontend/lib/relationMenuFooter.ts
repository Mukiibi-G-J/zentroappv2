/** Business Central–style lookup footer actions (+ New, Show details, Select from full list). */
export interface RelationMenuFooter {
  onNew?: () => void
  onShowDetails?: () => void
  onSelectFromFullList?: () => void
  newDisabled?: boolean
  showDetailsDisabled?: boolean
  fullListDisabled?: boolean
}
