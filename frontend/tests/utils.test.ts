import { cn } from '@/lib/utils'

describe('cn utility function', () => {
  it('should merge classes correctly', () => {
    const result = cn('px-4', 'py-2', 'bg-blue-500')
    expect(result).toBe('px-4 py-2 bg-blue-500')
  })

  it('should handle duplicate classes by using the last one', () => {
    const result = cn('bg-red-500', 'bg-blue-500')
    expect(result).toBe('bg-blue-500')
  })

  it('should handle conditional classes', () => {
    const isActive = true
    const isDisabled = false
    
    const result = cn(
      'base-class',
      isActive && 'active-class',
      isDisabled && 'disabled-class',
      !isDisabled && 'enabled-class'
    )
    
    expect(result).toBe('base-class active-class enabled-class')
  })

  it('should handle arrays of classes', () => {
    const result = cn(['px-4', 'py-2'], ['bg-blue-500', 'text-white'])
    expect(result).toBe('px-4 py-2 bg-blue-500 text-white')
  })

  it('should handle objects with conditional classes', () => {
    const result = cn({
      'base-class': true,
      'active-class': true,
      'disabled-class': false
    })
    
    expect(result).toBe('base-class active-class')
  })

  it('should merge conflicting Tailwind classes correctly', () => {
    // twMerge should handle conflicting classes by keeping the last one
    const result = cn('p-4', 'p-2', 'px-8')
    expect(result).toBe('p-2 px-8')
  })

  it('should handle empty inputs', () => {
    expect(cn()).toBe('')
    expect(cn('')).toBe('')
    expect(cn(null, undefined, false)).toBe('')
  })

  it('should handle mixed input types', () => {
    const result = cn(
      'base',
      ['array-class'],
      { 'object-class': true, 'false-class': false },
      true && 'conditional-class',
      null,
      undefined
    )
    
    expect(result).toBe('base array-class object-class conditional-class')
  })
})
