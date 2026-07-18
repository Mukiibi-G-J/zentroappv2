'use client'

import { useEffect, useState } from 'react'
import PhoneInput, { type Country, parsePhoneNumber } from 'react-phone-number-input'
import 'react-phone-number-input/style.css'
import '@/styles/phone-input.css'
import SearchableCountrySelect from '@/components/shared/SearchableCountrySelect'
import { cn } from '@/lib/utils'

const E164_MAX_LEN = 16

export interface PhoneNumberPickerProps {
  value?: string
  onChange: (value: string | undefined) => void
  onCountryChange?: (country: Country | undefined) => void
  defaultCountry?: Country
  placeholder?: string
  disabled?: boolean
  className?: string
  error?: boolean
  id?: string
}

export function PhoneNumberPicker({
  value,
  onChange,
  onCountryChange,
  defaultCountry = 'UG',
  placeholder = 'Phone number',
  disabled = false,
  className = '',
  error = false,
  id,
}: PhoneNumberPickerProps) {
  const [internalValue, setInternalValue] = useState<string | undefined>(value)

  const inputStyle = {
    '--PhoneInput-color--focus': '#ffbf3f',
    '--PhoneInputCountrySelect-marginRight': '0',
    '--PhoneInputCountrySelectArrow-color': '#3b4a46',
    '--PhoneInputCountrySelectArrow-color--focus': '#ffbf3f',
    '--PhoneInput-color': error ? '#ef4444' : '#060b1e',
  } as React.CSSProperties

  useEffect(() => {
    if (value && value.length > E164_MAX_LEN) {
      const truncated = value.slice(0, E164_MAX_LEN)
      setInternalValue(truncated)
      onChange(truncated)
      return
    }
    setInternalValue(value)
    // eslint-disable-next-line react-hooks/exhaustive-deps -- sync from prop only
  }, [value])

  const handleChange = (newValue: string | undefined) => {
    if (!newValue) {
      setInternalValue(undefined)
      onChange(undefined)
      return
    }
    if (newValue.length > E164_MAX_LEN) return

    setInternalValue(newValue)
    onChange(newValue)

    try {
      const parsed = parsePhoneNumber(newValue)
      if (parsed?.country) {
        onCountryChange?.(parsed.country)
      }
    } catch {
      /* incomplete while typing */
    }
  }

  const handleCountryChange = (country: Country | undefined) => {
    onCountryChange?.(country)
  }

  return (
    <div className={cn('relative w-full', className)}>
      <PhoneInput
        value={internalValue}
        onChange={handleChange}
        onCountryChange={handleCountryChange}
        placeholder={placeholder}
        disabled={disabled}
        defaultCountry={defaultCountry}
        international
        countryCallingCodeEditable={false}
        countrySelectComponent={SearchableCountrySelect}
        className={cn('phone-input', error && 'phone-input-error')}
        style={inputStyle}
        numberInputProps={{
          id,
          maxLength: 24,
          autoComplete: 'tel',
        }}
      />
    </div>
  )
}

export { parsePhoneNumber }
