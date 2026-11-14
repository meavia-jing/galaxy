import axios, { type AxiosError, type AxiosInstance, type InternalAxiosRequestConfig } from 'axios'

export interface ApiError {
  code: string
  message: string
  fields?: Record<string, string>
}

export class ApiRequestError extends Error {
  code: string
  fields: Record<string, string>
  requestId: string

  constructor(error: ApiError, requestId = '') {
    super(error.message)
    this.name = 'ApiRequestError'
    this.code = error.code
    this.fields = error.fields ?? {}
    this.requestId = requestId
  }
}

let accessToken: string | null = null
let refreshing: Promise<string | null> | null = null

export function setAccessToken(token: string | null): void {
  accessToken = token
}

export function getAccessToken(): string | null {
  return accessToken
}

function readCookie(name: string): string {
  const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`))
  return match ? decodeURIComponent(match[1]) : ''
}

export const http: AxiosInstance = axios.create({
  baseURL: '/api/v1',
  timeout: 20000,
  withCredentials: true,
  headers: { 'Content-Type': 'application/json' },
})

http.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  if (accessToken) {
    config.headers.Authorization = `Bearer ${accessToken}`
  }
  const csrf = readCookie('csrftoken')
  if (csrf) {
    config.headers['X-CSRFToken'] = csrf
  }
  return config
})

interface Envelope<T> {
  data: T
  request_id: string
}

function unwrap<T>(payload: unknown): T {
  const envelope = payload as Envelope<T>
  if (envelope && typeof envelope === 'object' && 'data' in envelope) {
    return envelope.data
  }
  return payload as T
}

function toApiError(error: AxiosError): ApiRequestError {
  const body = error.response?.data as
    | { error?: ApiError; request_id?: string }
    | undefined
  if (body?.error) {
    return new ApiRequestError(body.error, body.request_id ?? '')
  }
  return new ApiRequestError({
    code: 'NETWORK_ERROR',
    message: error.response ? '请求失败，请稍后重试' : '网络异常，请检查后端服务是否启动',
  })
}

/** Single-flight refresh so concurrent 401s trigger only one refresh call. */
async function refreshAccessToken(): Promise<string | null> {
  if (!refreshing) {
    refreshing = axios
      .post<Envelope<{ access: string }>>('/api/v1/auth/refresh/', null, {
        withCredentials: true,
        headers: { 'X-CSRFToken': readCookie('csrftoken') },
      })
      .then((response) => {
        const token = unwrap<{ access: string }>(response.data).access
        accessToken = token
        return token
      })
      .catch(() => {
        accessToken = null
        return null
      })
      .finally(() => {
        refreshing = null
      })
  }
  return refreshing
}

export async function ensureCsrf(): Promise<void> {
  await axios.get('/api/v1/auth/csrf/', { withCredentials: true })
}

http.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const config = error.config as InternalAxiosRequestConfig & { _retried?: boolean }
    const status = error.response?.status
    const url = config?.url ?? ''
    if (status === 401 && config && !config._retried && !url.includes('/auth/')) {
      config._retried = true
      const token = await refreshAccessToken()
      if (token) {
        config.headers.Authorization = `Bearer ${token}`
        return http.request(config)
      }
    }
    return Promise.reject(toApiError(error))
  },
)

export async function apiGet<T>(url: string, params?: Record<string, unknown>): Promise<T> {
  const response = await http.get(url, { params })
  return unwrap<T>(response.data)
}

export async function apiPost<T>(url: string, body?: unknown): Promise<T> {
  const response = await http.post(url, body ?? {})
  return unwrap<T>(response.data)
}

export async function apiPatch<T>(url: string, body: unknown): Promise<T> {
  const response = await http.patch(url, body)
  return unwrap<T>(response.data)
}

export { refreshAccessToken }
