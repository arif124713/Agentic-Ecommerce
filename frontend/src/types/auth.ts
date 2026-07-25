export interface AuthUser {
  public_id: string
  first_name: string
  last_name: string | null
  email: string
  email_verified_at: string | null
  mfa_enabled: boolean
  roles: string[]
  permissions: string[]
}

export interface RegisterPayload {
  first_name: string
  last_name?: string
  email: string
  password: string
  marketing_opt_in?: boolean
}

export interface LoginPayload {
  email: string
  password: string
  remember_me?: boolean
}

export interface Session {
  id: string
  device_label: string | null
  ip: string | null
  is_current: boolean
  created_at: string
  last_used_at: string | null
}
