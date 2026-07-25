import axios from 'axios'

export const apiClient = axios.create({
  baseURL: '/api/v1',
  withCredentials: true,
})

function readCookie(name: string): string | undefined {
  const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`))
  return match ? decodeURIComponent(match[1]) : undefined
}

apiClient.interceptors.request.use((config) => {
  config.headers['X-Request-ID'] = crypto.randomUUID()
  if (config.method && config.method.toUpperCase() !== 'GET') {
    const csrfToken = readCookie('csrf_token')
    if (csrfToken) config.headers['X-CSRF-Token'] = csrfToken
  }
  return config
})

export interface ApiErrorPayload {
  error: {
    code: string
    message: string
    details: { field: string; issue: string }[]
    request_id: string
  }
}

export function getApiErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const payload = error.response?.data as ApiErrorPayload | undefined
    if (payload?.error?.message) return payload.error.message
  }
  return 'Something went wrong. Please try again.'
}
