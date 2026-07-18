'use client'

import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react'
import Select, {
  type GroupBase,
  type MenuListProps,
  type OptionProps,
  type SingleValue,
  type StylesConfig,
  components,
} from 'react-select'
import type { RelationOption } from '@/hooks/useRelationOptions'
import type { RelationMenuFooter } from '@/lib/relationMenuFooter'

interface Props {
  options: RelationOption[]
  value: string
  placeholder?: string
  autoFocus?: boolean
  initialInput?: string
  disabled?: boolean
  compact?: boolean
  isLoading?: boolean
  menuFooter?: RelationMenuFooter
  onChange: (value: string) => void
  onBlur?: () => void
  onMenuOpen?: () => void
  onKeyDown?: (e: React.KeyboardEvent) => void
  noOptionsMessage?: string
}

type SelectExtraProps = {
  menuFooter?: RelationMenuFooter
  closeMenu?: () => void
}

const RelationSelectMenuContext = createContext<SelectExtraProps>({})

function isItemUomOption(option: RelationOption): boolean {
  return option.quantityPerUnit != null && option.quantityPerUnit !== ''
}

function RelationMenuList(props: MenuListProps<RelationOption, false, GroupBase<RelationOption>>) {
  const flatOptions = props.options.filter(
    (o): o is RelationOption => 'value' in o && typeof o.value === 'string',
  )
  const showQty = flatOptions.some(isItemUomOption)
  const { menuFooter: footer, closeMenu } = useContext(RelationSelectMenuContext)
  const showFooter =
    footer &&
    (footer.onNew || footer.onShowDetails || footer.onSelectFromFullList)

  const runFooterAction = (action?: () => void) => {
    if (!action) return
    closeMenu?.()
    action()
  }

  return (
    <div>
      <div className="sticky top-0 z-10 flex border-b border-gray-200 bg-gray-50 px-3 py-2 text-xs font-semibold uppercase tracking-wide text-bodyText">
        <span className={showQty ? 'w-20' : 'w-28'}>{showQty ? 'Code' : 'No.'}</span>
        <span className="flex-1 min-w-0">{showQty ? 'Contains' : 'Name'}</span>
        {showQty ? (
          <span className="w-28 text-right shrink-0">Qty. per UOM</span>
        ) : null}
      </div>
      <div className="max-h-52 overflow-y-auto">{props.children}</div>
      {showFooter ? (
        <div className="sticky bottom-0 z-10 flex items-center justify-between gap-2 border-t border-gray-200 bg-[#eef6f7] px-3 py-2 text-xs">
          {footer.onNew ? (
            <button
              type="button"
              disabled={footer.newDisabled}
              className="font-medium text-s1 hover:underline disabled:cursor-not-allowed disabled:text-gray-400 disabled:no-underline"
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => runFooterAction(footer.onNew)}
            >
              + New
            </button>
          ) : (
            <span />
          )}
          <div className="flex items-center gap-4">
            {footer.onShowDetails ? (
              <button
                type="button"
                disabled={footer.showDetailsDisabled}
                className="text-bodyText hover:text-s1 hover:underline disabled:cursor-not-allowed disabled:text-gray-400 disabled:no-underline"
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => runFooterAction(footer.onShowDetails)}
              >
                Show details
              </button>
            ) : null}
            {footer.onSelectFromFullList ? (
              <button
                type="button"
                disabled={footer.fullListDisabled}
                className="font-medium text-s1 hover:underline disabled:cursor-not-allowed disabled:text-gray-400 disabled:no-underline"
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => runFooterAction(footer.onSelectFromFullList)}
              >
                Select from full list
              </button>
            ) : null}
          </div>
        </div>
      ) : null}
    </div>
  )
}

function RelationOptionRow(props: OptionProps<RelationOption, false>) {
  const { data } = props
  const showQty = isItemUomOption(data)
  return (
    <components.Option {...props}>
      <div className="flex items-center gap-3 text-sm">
        <span className={`${showQty ? 'w-20' : 'w-28'} font-medium text-mainTextColor truncate`}>
          {showQty ? (data.code || data.value) : data.value}
        </span>
        {showQty ? (
          <>
            <span className="flex-1 min-w-0 truncate text-bodyText">{data.name || data.caption || '—'}</span>
            <span className="w-28 text-right shrink-0 tabular-nums text-bodyText">
              {data.quantityPerUnit}
            </span>
          </>
        ) : data.name || data.caption ? (
          <span className="flex-1 truncate text-bodyText">{data.name || data.caption}</span>
        ) : null}
      </div>
    </components.Option>
  )
}

function buildSelectStyles(compact: boolean, wideMenu: boolean): StylesConfig<RelationOption, false> {
  return {
  control: (base, state) => ({
    ...base,
    minHeight: compact ? 32 : 34,
    backgroundColor: state.isDisabled ? '#f9fafb' : '#ffffff',
    borderColor: state.isFocused ? '#0d9488' : '#e5e7eb',
    boxShadow: state.isFocused ? '0 0 0 2px rgba(13, 148, 136, 0.2)' : 'none',
    borderRadius: 8,
    fontSize: 14,
    '&:hover': { borderColor: state.isFocused ? '#0d9488' : '#d1d5db' },
  }),
  valueContainer: (base) => ({ ...base, padding: '0 8px' }),
  singleValue: (base, state) => ({ ...base, color: state.isDisabled ? '#9ca3af' : '#060b1e' }),
  input: (base) => ({ ...base, margin: 0, padding: 0, color: '#060b1e' }),
  menuPortal: (base) => ({ ...base, zIndex: 99999 }),
  menu: (base) => ({
    ...base,
    zIndex: 99999,
    minWidth: wideMenu ? 360 : 280,
    maxWidth: 'min(480px, calc(100vw - 24px))',
    borderRadius: 8,
    overflow: 'hidden',
    boxShadow: '0 8px 24px rgba(0,0,0,0.15)',
  }),
  option: (base, state) => ({
    ...base,
    backgroundColor: state.isSelected ? '#0d9488' : state.isFocused ? '#f0fdfa' : 'white',
    color: state.isSelected ? 'white' : '#1f2937',
    cursor: 'pointer',
  }),
  indicatorSeparator: () => ({ display: 'none' }),
  dropdownIndicator: (base, state) => ({
    ...base,
    color: state.isFocused ? '#0d9488' : '#9ca3af',
    padding: '0 6px',
  }),
  }
}

function optionMatchesValue(option: RelationOption, value: string): boolean {
  return (
    option.value === value
    || option.code === value
    || option.label === value
    || option.name === value
    || (option.caption != null && option.caption === value)
    || (option.name != null && option.name.startsWith(`${value} —`))
  )
}

function dedupeOptions(options: RelationOption[]): RelationOption[] {
  const seen = new Set<string>()
  return options.filter((option) => {
    if (seen.has(option.value)) return false
    seen.add(option.value)
    return true
  })
}

export default function SearchableRelationSelect({
  options,
  value,
  placeholder = 'Search…',
  autoFocus = false,
  initialInput,
  disabled = false,
  compact = false,
  isLoading = false,
  menuFooter,
  onChange,
  onBlur,
  onMenuOpen,
  onKeyDown,
  noOptionsMessage = 'No matches',
}: Props) {
  const menuOpenRef = useRef(false)
  const [menuIsOpen, setMenuIsOpen] = useState(false)
  const [inputValue, setInputValue] = useState('')

  useEffect(() => {
    if (!autoFocus) return
    if (initialInput != null && initialInput !== '') {
      setInputValue(initialInput)
      setMenuIsOpen(true)
    }
  }, [autoFocus, initialInput])

  // After a value is committed, clear the search text so the selected key shows — not the filter string.
  useEffect(() => {
    if (!menuIsOpen) setInputValue('')
  }, [value, menuIsOpen])

  const allOptions = (() => {
    const unique = dedupeOptions(options)
    if (!value || unique.some((o) => optionMatchesValue(o, value))) return unique
    if (isLoading) return unique
    return [{ value, label: value, caption: '' }, ...unique]
  })()

  const selected = allOptions.find((o) => optionMatchesValue(o, value)) ?? null
  const showQtyColumn = options.some(isItemUomOption)
  const waitingForLabel = isLoading && !!value && !options.some((o) => optionMatchesValue(o, value))

  const filterOption = useCallback(
    (option: { label: string; value: string; data: RelationOption }, input: string) => {
      const q = input.trim().toLowerCase()
      if (!q) return true
      const caption = option.data.caption?.toLowerCase() ?? ''
      const code = option.data.code?.toLowerCase() ?? ''
      const name = option.data.name?.toLowerCase() ?? ''
      const qty = option.data.quantityPerUnit?.toLowerCase() ?? ''
      return (
        option.value.toLowerCase().includes(q) ||
        caption.includes(q) ||
        code.includes(q) ||
        name.includes(q) ||
        qty.includes(q) ||
        option.label.toLowerCase().includes(q)
      )
    },
    [],
  )

  const resolveTypedValue = useCallback(
    (typed: string): string | null => {
      const q = typed.trim()
      if (!q) return null
      const match = allOptions.find(
        (o) =>
          o.value.toLowerCase() === q.toLowerCase()
          || o.label.toLowerCase() === q.toLowerCase()
          || (o.code?.toLowerCase() === q.toLowerCase())
          || (o.name?.toLowerCase() === q.toLowerCase())
          || (o.caption?.toLowerCase() === q.toLowerCase())
          || (o.name?.toLowerCase().includes(q.toLowerCase()))
          || (o.caption?.toLowerCase().includes(q.toLowerCase())),
      )
      return match?.value ?? null
    },
    [allOptions],
  )

  const handleChange = (option: SingleValue<RelationOption>) => {
    setInputValue('')
    setMenuIsOpen(false)
    onChange(option?.value ?? '')
  }

  const handleBlur = () => {
    setTimeout(() => {
      if (menuOpenRef.current) return
      const resolved = resolveTypedValue(inputValue)
      if (resolved != null && resolved !== value) {
        setInputValue('')
        onChange(resolved)
      }
      onBlur?.()
    }, 200)
  }

  return (
    <RelationSelectMenuContext.Provider
      value={{
        menuFooter,
        closeMenu: () => setMenuIsOpen(false),
      }}
    >
      <Select<RelationOption, false, GroupBase<RelationOption>>
        options={allOptions}
        value={waitingForLabel ? null : selected}
        onChange={handleChange}
        onBlur={handleBlur}
        inputValue={inputValue}
        onInputChange={(next, meta) => {
          if (meta.action === 'input-change') {
            setInputValue(next)
          } else {
            setInputValue('')
          }
        }}
        menuIsOpen={menuIsOpen}
        onMenuOpen={() => {
          menuOpenRef.current = true
          setMenuIsOpen(true)
          onMenuOpen?.()
        }}
        onMenuClose={() => {
          menuOpenRef.current = false
          setMenuIsOpen(false)
        }}
        filterOption={filterOption}
        isSearchable
        isClearable
        isDisabled={disabled || isLoading}
        isLoading={isLoading}
        autoFocus={autoFocus}
        openMenuOnFocus
        menuPortalTarget={typeof document !== 'undefined' ? document.body : null}
        menuPosition="fixed"
        menuPlacement="auto"
        menuShouldScrollIntoView={false}
        placeholder={waitingForLabel ? 'Loading…' : placeholder}
        noOptionsMessage={() => noOptionsMessage}
        components={{ MenuList: RelationMenuList, Option: RelationOptionRow }}
        formatOptionLabel={(option, { context }) => {
          if (context !== 'value') return undefined
          if (isItemUomOption(option)) {
            const code = option.code || option.label
            const qty = option.quantityPerUnit
            return qty ? `${code} (${qty})` : code
          }
          if (
            option.caption &&
            option.code &&
            (option.code === 'Page' || option.code === 'Table')
          ) {
            return option.caption
          }
          return option.code || option.label || option.value
        }}
        classNamePrefix="relation-select"
        styles={buildSelectStyles(compact, showQtyColumn)}
      />
    </RelationSelectMenuContext.Provider>
  )
}
