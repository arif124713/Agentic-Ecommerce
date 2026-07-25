import { describe, expect, it } from 'vitest'
import { formatDiscount, formatMoney } from './money'

describe('formatMoney', () => {
  it('formats INR with the rupee symbol and no decimals', () => {
    expect(formatMoney('1299.00', 'INR')).toBe('₹1,299')
  })

  it('formats BDT (the default) with the taka symbol', () => {
    expect(formatMoney(500)).toBe('৳500')
  })

  it('falls back to the currency code for an unknown currency', () => {
    expect(formatMoney('10', 'XYZ')).toBe('XYZ 10')
  })

  it('accepts numeric input as well as strings', () => {
    expect(formatMoney(2500, 'INR')).toBe('₹2,500')
  })

  it('rounds fractional amounts rather than truncating', () => {
    expect(formatMoney('99.6', 'INR')).toBe('₹100')
  })
})

describe('formatDiscount', () => {
  it('rounds to the nearest whole percent and appends OFF', () => {
    expect(formatDiscount('49.6')).toBe('50% OFF')
    expect(formatDiscount(33)).toBe('33% OFF')
  })

  it('rounds down when below the midpoint', () => {
    expect(formatDiscount('49.4')).toBe('49% OFF')
  })
})
