const CURRENCY_SYMBOLS: Record<string, string> = {
  BDT: '৳',
  USD: '$',
  INR: '₹',
}

export function formatMoney(value: string | number, currency = 'BDT'): string {
  const amount = typeof value === 'string' ? Number(value) : value
  const symbol = CURRENCY_SYMBOLS[currency] ?? currency + ' '
  return `${symbol}${amount.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`
}

export function formatDiscount(percent: string | number): string {
  const value = typeof percent === 'string' ? Number(percent) : percent
  return `${Math.round(value)}% OFF`
}
