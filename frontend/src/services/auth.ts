import axios from 'axios'
import { apiClient } from './apiClient'
import type { Envelope } from '@/types/catalog'
import type { AuthUser, LoginPayload, MfaEnableResult, MfaSetup, RegisterPayload, Session } from '@/types/auth'

export async function registerAccount(payload: RegisterPayload): Promise<void> {
  await apiClient.post('/auth/register', payload)
}

export async function login(payload: LoginPayload): Promise<AuthUser> {
  const { data } = await apiClient.post<Envelope<AuthUser>>('/auth/login', payload)
  return data.data
}

export async function logout(): Promise<void> {
  await apiClient.post('/auth/logout')
}

export async function logoutAll(): Promise<void> {
  await apiClient.post('/auth/logout-all')
}

export async function getCurrentUser(): Promise<AuthUser | null> {
  try {
    const { data } = await apiClient.get<Envelope<AuthUser>>('/auth/me')
    return data.data
  } catch (error) {
    if (axios.isAxiosError(error) && error.response?.status === 401) {
      return null
    }
    throw error
  }
}

export async function verifyEmail(token: string): Promise<void> {
  await apiClient.post('/auth/email/verify', { token })
}

export async function resendVerification(email: string): Promise<void> {
  await apiClient.post('/auth/email/resend', { email })
}

export async function forgotPassword(email: string): Promise<void> {
  await apiClient.post('/auth/password/forgot', { email })
}

export async function resetPassword(token: string, password: string): Promise<void> {
  await apiClient.post('/auth/password/reset', { token, password })
}

export async function mfaSetup(): Promise<MfaSetup> {
  const { data } = await apiClient.post<Envelope<MfaSetup>>('/auth/mfa/setup')
  return data.data
}

export async function mfaEnable(code: string): Promise<MfaEnableResult> {
  const { data } = await apiClient.post<Envelope<MfaEnableResult>>('/auth/mfa/enable', { code })
  return data.data
}

export async function mfaDisable(password: string, code: string): Promise<void> {
  await apiClient.post('/auth/mfa/disable', { password, code })
}

export async function mfaLoginVerify(
  challengeToken: string,
  factor: { code: string } | { recovery_code: string },
): Promise<AuthUser> {
  const { data } = await apiClient.post<Envelope<AuthUser>>('/auth/mfa/login-verify', {
    challenge_token: challengeToken,
    ...factor,
  })
  return data.data
}

export async function listSessions(): Promise<Session[]> {
  const { data } = await apiClient.get<Envelope<Session[]>>('/auth/sessions')
  return data.data
}

export async function revokeSession(id: string): Promise<void> {
  await apiClient.delete(`/auth/sessions/${id}`)
}
