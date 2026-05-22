/**
 * API client — comunicación con el backend FastAPI.
 *
 * Todas las llamadas pasan por el proxy de Vite (/api → localhost:8000).
 * Los endpoints protegidos incluyen automáticamente el token JWT.
 */

const API_BASE = '/api/v1'

let _token: string | null = null

export function setToken(token: string | null) {
  _token = token
  if (token) {
    localStorage.setItem('auth_token', token)
  } else {
    localStorage.removeItem('auth_token')
  }
}

export function getToken(): string | null {
  if (!_token) {
    _token = localStorage.getItem('auth_token')
  }
  return _token
}

export function isAuthenticated(): boolean {
  return getToken() !== null
}

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  }
  const token = getToken()
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  })

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(error.detail || `HTTP ${res.status}`)
  }

  // 204 No Content
  if (res.status === 204) return undefined as T

  return res.json()
}

// ── Auth ──

export interface LoginRequest {
  username: string
  password: string
}

export interface TokenResponse {
  access_token: string
  token_type: string
}

export interface UserResponse {
  id: string
  username: string
  full_name: string | null
  role: string
  active: boolean
}

export async function login(data: LoginRequest): Promise<TokenResponse> {
  return request<TokenResponse>('POST', '/auth/login', data)
}

export async function getMe(): Promise<UserResponse> {
  return request<UserResponse>('GET', '/auth/me')
}

// ── Sync ──

export interface SyncResultItem {
  subject: string | null
  sender_name: string
  category: string | null
  confidence: number
  resolution: string | null
  routing: { departments: string[]; persons: string[] }
  summary: string | null
  urgency: string
  actions: { action: string; success: boolean; detail: string | null }[]
  error: string | null
}

export interface SyncResponse {
  connected: boolean
  fetched: number
  processed: number
  errors: number
  account_email: string
  results: SyncResultItem[]
  error?: string
}

export async function syncEmails(): Promise<SyncResponse> {
  return request<SyncResponse>('POST', '/emails/sync')
}

// ── Dashboard ──

export interface RecentEmailItem {
  id: string
  subject: string | null
  sender_name: string | null
  sender_email: string
  category: string | null
  confidence: number
  method: string
  summary: string | null
  received_at: string | null
  resolution: string | null          // consensus | majority | llm_judge | fallback
  departments: string[]              // Departamentos destino
  urgency: string                    // alta | media | baja
  action_required: string | null     // pago | soporte | consulta | ...
  reviewed: boolean                  // Revisado manualmente
}

export interface DashboardSummary {
  total_emails: number
  emails_today: number
  contacts_by_category: Record<string, number>
  opportunities_by_stage: Record<string, number>
  recent_emails: RecentEmailItem[]
  classification_by_method: Record<string, number>
}

export async function getDashboardSummary(): Promise<DashboardSummary> {
  return request<DashboardSummary>('GET', '/dashboard/summary')
}

export async function reviewEmail(emailId: string, category: string): Promise<RecentEmailItem> {
  return request<RecentEmailItem>('PATCH', `/emails/${emailId}/review`, { category })
}

// ── Retrain ──

export interface RetrainResponse {
  status: string
  accuracy: number | null
  f1_macro: number | null
  train_samples: number | null
  test_samples: number | null
  real_samples: number | null
  training_time_seconds: number | null
  detail: string | null
}

// ── CRM ──

export interface CrmSyncItem {
  email: string
  name: string
  crm_id: string | null
  action: string
  detail: string | null
}

export interface CrmSyncResponse {
  total: number
  created: number
  updated: number
  skipped: number
  errors: number
  results: CrmSyncItem[]
  connected: boolean
  detail: string | null
}

export async function syncCrm(): Promise<CrmSyncResponse> {
  return request<CrmSyncResponse>('POST', '/crm/sync')
}

export async function retrainModel(params?: {
  epochs?: number
  augment_multiplier?: number
  synthetic_count?: number
  learning_rate?: number
  real_only?: boolean
}): Promise<RetrainResponse> {
  return request<RetrainResponse>('POST', '/classification-history/retrain', params ?? {})
}

// ── Contacts ──

export interface ContactResponse {
  id: string
  name: string
  email: string
  company: string | null
  position: string | null
  category: string
  phone: string | null
  email_count: number
  first_email_at: string | null
  last_email_at: string | null
  created_at: string
}

export interface ContactsListResponse {
  items: ContactResponse[]
  total: number
  skip: number
  limit: number
}

export async function getContacts(params?: {
  category?: string
  search?: string
  skip?: number
  limit?: number
}): Promise<ContactsListResponse> {
  const q = new URLSearchParams()
  if (params?.category) q.set('category', params.category)
  if (params?.search) q.set('search', params.search)
  if (params?.skip) q.set('skip', String(params.skip))
  if (params?.limit) q.set('limit', String(params.limit))
  const qs = q.toString()
  return request<ContactsListResponse>('GET', `/contacts${qs ? '?' + qs : ''}`)
}

export async function getContact(id: string): Promise<ContactResponse> {
  return request<ContactResponse>('GET', `/contacts/${id}`)
}

export async function updateContact(
  id: string,
  data: { category?: string },
): Promise<ContactResponse> {
  return request<ContactResponse>('PATCH', `/contacts/${id}`, data)
}

// ── Opportunities ──

export interface OpportunityResponse {
  id: string
  email_id: string | null
  contact_id: string
  title: string
  description: string | null
  stage: string
  value: number | null
  probability: number | null
  expected_close: string | null
  source: string | null
  notes: string | null
  created_at: string
  updated_at: string
}

export interface OpportunityCreate {
  contact_id: string
  title: string
  description?: string
  stage?: string
  value?: number
  probability?: number
  expected_close?: string
  notes?: string
}

export interface OpportunitiesListResponse {
  items: OpportunityResponse[]
  total: number
  skip: number
  limit: number
}

export async function getOpportunities(params?: {
  stage?: string
  skip?: number
  limit?: number
}): Promise<OpportunitiesListResponse> {
  const q = new URLSearchParams()
  if (params?.stage) q.set('stage', params.stage)
  if (params?.skip) q.set('skip', String(params.skip))
  if (params?.limit) q.set('limit', String(params.limit))
  const qs = q.toString()
  return request<OpportunitiesListResponse>(
    'GET',
    `/opportunities${qs ? '?' + qs : ''}`,
  )
}

export async function getOpportunity(id: string): Promise<OpportunityResponse> {
  return request<OpportunityResponse>('GET', `/opportunities/${id}`)
}

export async function createOpportunity(
  data: OpportunityCreate,
): Promise<OpportunityResponse> {
  return request<OpportunityResponse>('POST', '/opportunities', data)
}

export async function updateOpportunity(
  id: string,
  data: OpportunityCreate,
): Promise<OpportunityResponse> {
  return request<OpportunityResponse>('PUT', `/opportunities/${id}`, data)
}

export async function deleteOpportunity(id: string): Promise<void> {
  return request<void>('DELETE', `/opportunities/${id}`)
}

// ── Time Series & Forecasting ──

export interface TimeSeriesPoint {
  date: string
  value: number
}

export interface CategoryTimeSeriesPoint {
  date: string
  category: string
  value: number
}

export interface ForecastByCategory {
  category: string
  predicted_count: number
  trend: string  // increasing | decreasing | stable
}

export interface ForecastDailyPoint {
  date: string
  category: string
  predicted_count: number
}

export interface ForecastData {
  days: number  // 30 | 60 | 90
  total: number
  by_category: ForecastByCategory[]
  daily_projections: ForecastDailyPoint[]
  method: string
}

export interface TimeSeriesResponse {
  volume: TimeSeriesPoint[]
  by_category: CategoryTimeSeriesPoint[]
  avg_confidence: TimeSeriesPoint[]
  contacts_cumulative: TimeSeriesPoint[]
  volume_forecast: TimeSeriesPoint[]
  by_category_forecast: CategoryTimeSeriesPoint[]
  avg_confidence_forecast: TimeSeriesPoint[]
  contacts_forecast: TimeSeriesPoint[]
  forecasts: ForecastData[]
}

// ── Email Detail ──

export interface ClassificationHistoryItem {
  id: string
  email_id: string
  category: string
  confidence: number
  method: string
  details: Record<string, unknown> | null
  reviewed: boolean
  reviewed_by: string | null
  reviewed_at: string | null
  created_at: string | null
}

export interface EmailDetail {
  id: string
  account_id: string
  subject: string | null
  body_plain: string | null
  body_html: string | null
  sender_email: string
  sender_name: string | null
  recipients: { email: string; name: string | null }[] | null
  has_attachments: boolean
  attachments: { filename: string; type: string; size: number }[] | null
  received_at: string | null
  processed_at: string | null
  category: string | null
  relevance: string | null
  status: string | null
  summary: string | null
  extra_data: Record<string, unknown> | null
  created_at: string
  classification_history: ClassificationHistoryItem[]
}

export async function getEmail(id: string): Promise<EmailDetail> {
  return request<EmailDetail>('GET', `/emails/${id}`)
}

export async function getTimeSeries(
  period: string = '30d',
): Promise<TimeSeriesResponse> {
  return request<TimeSeriesResponse>('GET', `/dashboard/timeseries?period=${period}`)
}

// ── Chat ──

export interface ChatRequest {
  message: string
  conversation_id?: string | null
}

export interface ChatResponse {
  response: string
  conversation_id: string
}

export async function sendChatMessage(data: ChatRequest): Promise<ChatResponse> {
  return request<ChatResponse>('POST', '/chat', data)
}
