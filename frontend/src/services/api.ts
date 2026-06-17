/**
 * API client — comunicación con el backend FastAPI.
 *
 * En desarrollo usa el proxy de Vite (/api/v1 → localhost:8001).
 * En producción intenta usar VITE_API_URL; si falta y estamos en el frontend público
 * de Render, cae al backend público conocido para evitar depender de un proxy roto.
 */

const RENDER_FRONTEND_HOST = 'beconnect-frontend.onrender.com'
const RENDER_BACKEND_BASE = 'https://beexpand-fedeto-crm-email.onrender.com/api/v1'

function resolveApiBase(): string {
  const envBase = import.meta.env.VITE_API_URL?.trim()
  if (envBase) return envBase

  if (typeof window !== 'undefined' && window.location.hostname === RENDER_FRONTEND_HOST) {
    return RENDER_BACKEND_BASE
  }

  return '/api/v1'
}

const API_BASE = resolveApiBase()
const API_CONFIG_HINT = import.meta.env.DEV
  ? 'Verificá que el backend esté corriendo en http://localhost:8001 o definí VITE_API_URL=http://localhost:8001/api/v1.'
  : `Configurá VITE_API_URL con la URL pública del backend o usá ${RENDER_BACKEND_BASE}.`

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

  let res: Response
  try {
    res = await fetch(`${API_BASE}${path}`, {
      method,
      headers,
      body: body ? JSON.stringify(body) : undefined,
    })
  } catch {
    throw new Error(`No se pudo conectar con la API. ${API_CONFIG_HINT}`)
  }

  const contentType = res.headers.get('content-type')?.toLowerCase() || ''
  const isJson = contentType.includes('application/json')
  const isHtml = contentType.includes('text/html')

  if (isHtml) {
    throw new Error(
      `La ruta API ${API_BASE}${path} está devolviendo HTML en lugar de JSON. ${API_CONFIG_HINT}`,
    )
  }

  if (!res.ok) {
    if (isJson) {
      const error = await res.json().catch(() => ({ detail: res.statusText }))
      throw new Error(error.detail || `HTTP ${res.status}`)
    }

    const text = await res.text().catch(() => '')
    throw new Error(text || res.statusText || `HTTP ${res.status}`)
  }

  // 204 No Content
  if (res.status === 204) return undefined as T

  if (isJson) {
    return res.json()
  }

  throw new Error(
    `La API respondió sin JSON en ${API_BASE}${path}. ${API_CONFIG_HINT}`,
  )
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

// ── Reprocess ──

export interface ReprocessVote {
  agent: string
  category: string
  confidence: number
  reason?: string | null
}

export interface ReprocessResponse {
  status: string
  category: string
  confidence: number
  resolution: string
  votes: ReprocessVote[]
  processing_time_ms: number
  email_id: string
}

export async function reprocessEmail(emailId: string): Promise<ReprocessResponse> {
  return request<ReprocessResponse>('POST', `/emails/${emailId}/reprocess`)
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

// ── Settings ──

export interface ImapSettings {
  server: string
  port: number
  email: string
  password: string
  poll_interval_minutes: number
  folder_map: Record<string, string>
}

export interface ImapUpdate {
  server?: string
  port?: number
  email?: string
  password?: string
  poll_interval_minutes?: number
  folder_map?: Record<string, string>
}

export interface NotificationSettings {
  twilio_account_sid: string
  twilio_auth_token: string
  twilio_from_number: string
  twilio_to_number: string
  twilio_min_urgency: string
}

export interface NotificationUpdate {
  twilio_account_sid?: string
  twilio_auth_token?: string
  twilio_from_number?: string
  twilio_to_number?: string
  twilio_min_urgency?: string
}

export interface PasswordUpdate {
  current_password: string
  new_password: string
}

export interface TestImapRequest {
  server: string
  port: number
  email: string
  password: string
}

export interface TestImapResponse {
  success: boolean
  message: string
  folders: string[]
}

export interface TestWhatsAppResponse {
  success: boolean
  message: string
}

export interface SystemStatus {
  imap_configured: boolean
  whatsapp_configured: boolean
  openrouter_configured: boolean
  ollama_reachable: boolean
  crm_configured: boolean
  last_sync_at: string | null
  last_retrain_at: string | null
  last_retrain_accuracy: number | null
  uptime_seconds: number | null
  database: string
  version: string
}

export async function getImapSettings(): Promise<ImapSettings> {
  return request<ImapSettings>('GET', '/settings/imap')
}

export async function updateImapSettings(data: ImapUpdate): Promise<ImapSettings> {
  return request<ImapSettings>('PUT', '/settings/imap', data)
}

export async function getNotificationSettings(): Promise<NotificationSettings> {
  return request<NotificationSettings>('GET', '/settings/notifications')
}

export async function updateNotificationSettings(data: NotificationUpdate): Promise<NotificationSettings> {
  return request<NotificationSettings>('PUT', '/settings/notifications', data)
}

export async function changePassword(data: PasswordUpdate): Promise<void> {
  return request<void>('PUT', '/settings/password', data)
}

export async function testImapConnection(data: TestImapRequest): Promise<TestImapResponse> {
  return request<TestImapResponse>('POST', '/settings/test-imap', data)
}

export async function testWhatsApp(): Promise<TestWhatsAppResponse> {
  return request<TestWhatsAppResponse>('POST', '/settings/test-whatsapp')
}

export async function getSystemStatus(): Promise<SystemStatus> {
  return request<SystemStatus>('GET', '/settings/status')
}

// ── Invoices ──

export interface InvoiceResponse {
  id: string
  email_id: string
  filename: string
  file_size: number
  numero: string | null
  proveedor: string | null
  importe: number | null
  fecha: string | null
  vencimiento: string | null
  created_at: string | null
}

export interface InvoiceDetailResponse extends InvoiceResponse {
  file_path: string
  extracted_data: Record<string, unknown>
}

export interface InvoicesListResponse {
  total: number
  skip: number
  limit: number
  invoices: InvoiceResponse[]
}

export async function getInvoices(params?: {
  proveedor?: string
  fecha_from?: string
  fecha_to?: string
  skip?: number
  limit?: number
}): Promise<InvoicesListResponse> {
  const q = new URLSearchParams()
  if (params?.proveedor) q.set('proveedor', params.proveedor)
  if (params?.fecha_from) q.set('fecha_from', params.fecha_from)
  if (params?.fecha_to) q.set('fecha_to', params.fecha_to)
  if (params?.skip) q.set('skip', String(params.skip))
  if (params?.limit) q.set('limit', String(params.limit))
  return request<InvoicesListResponse>('GET', `/invoices?${q.toString()}`)
}

export async function getInvoice(id: string): Promise<InvoiceDetailResponse> {
  return request<InvoiceDetailResponse>('GET', `/invoices/${id}`)
}

export async function getEmailInvoices(emailId: string): Promise<{ email_id: string; total: number; invoices: InvoiceResponse[] }> {
  return request('GET', `/emails/${emailId}/invoices`)
}

export function getInvoiceDownloadUrl(id: string): string {
  const token = getToken()
  return `${API_BASE}/invoices/${id}/download?token=${token}`
}
