'use client'

import { useEffect, useRef, useState } from 'react'
import { cn } from '@/lib/utils'

interface OtpInputProps {
  length: number
  onComplete: (otp: string) => void
  disabled?: boolean
}

export function OtpInput({ length, onComplete, disabled = false }: OtpInputProps) {
  const [otp, setOtp] = useState<string[]>(() => new Array(length).fill(''))
  const inputRefs = useRef<(HTMLInputElement | null)[]>([])

  useEffect(() => {
    inputRefs.current = inputRefs.current.slice(0, length)
  }, [length])

  const handleChange = (value: string, index: number) => {
    if (value && !/^\d$/.test(value)) return

    const next = [...otp]
    next[index] = value.slice(-1)
    setOtp(next)

    const joined = next.join('')
    if (joined.length === length) {
      onComplete(joined)
    }

    if (value && index < length - 1) {
      inputRefs.current[index + 1]?.focus()
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>, index: number) => {
    if (e.key === 'Backspace' && !otp[index] && index > 0) {
      inputRefs.current[index - 1]?.focus()
    }
  }

  const handlePaste = (e: React.ClipboardEvent<HTMLInputElement>) => {
    e.preventDefault()
    const pasted = e.clipboardData.getData('text').replace(/\D/g, '').slice(0, length)
    if (!pasted) return

    const next = pasted.split('').concat(new Array(length - pasted.length).fill(''))
    setOtp(next)
    if (pasted.length === length) {
      onComplete(pasted)
    }
    const focusIndex = Math.min(pasted.length, length - 1)
    inputRefs.current[focusIndex]?.focus()
  }

  return (
    <div className="flex justify-center gap-2">
      {otp.map((digit, index) => (
        <input
          key={index}
          ref={(el) => {
            inputRefs.current[index] = el
          }}
          type="text"
          inputMode="numeric"
          autoComplete={index === 0 ? 'one-time-code' : 'off'}
          maxLength={1}
          value={digit}
          disabled={disabled}
          autoFocus={index === 0}
          onChange={(e) => handleChange(e.target.value, index)}
          onKeyDown={(e) => handleKeyDown(e, index)}
          onPaste={handlePaste}
          className={cn(
            'h-12 w-11 rounded-xl border border-strokeColor text-center text-xl text-mainTextColor',
            'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-s2 focus-visible:ring-offset-2',
            'disabled:cursor-not-allowed disabled:bg-softBg disabled:opacity-60',
          )}
        />
      ))}
    </div>
  )
}
