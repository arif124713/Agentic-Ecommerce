export interface Address {
  id: number
  label: string | null
  recipient_name: string
  phone: string
  division: string
  district: string | null
  city: string
  area: string | null
  postal_code: string | null
  street_line1: string
  street_line2: string | null
  landmark: string | null
  is_default_shipping: boolean
  is_default_billing: boolean
}

export type AddressInput = Omit<Address, 'id'>
