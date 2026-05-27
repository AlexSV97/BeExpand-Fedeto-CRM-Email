/**
 * Ajustes del sistema — 4 pestañas:
 *   1. Buzones (IMAP)
 *   2. Notificaciones (Telegram)
 *   3. Cuenta (contraseña)
 *   4. Estado del Sistema (solo lectura)
 */

import { useEffect, useState, useCallback } from 'react'
import { motion } from 'framer-motion'
import {
  getImapSettings,
  updateImapSettings,
  getNotificationSettings,
  updateNotificationSettings,
  changePassword,
  testImapConnection,
  testTelegram,
  getSystemStatus,
  type ImapUpdate,
  type NotificationUpdate,
  type SystemStatus,
  type TestImapResponse,
  type TestTelegramResponse,
} from '../services/api'

// ── Tabs ──

const TABS = [
  { key: 'imap', label: 'Buzones', icon: MailIcon },
  { key: 'notifications', label: 'Notificaciones', icon: BellIcon },
  { key: 'account', label: 'Cuenta', icon: UserIcon },
  { key: 'status', label: 'Estado del Sistema', icon: ActivityIcon },
]

// ── Iconos inline ──

function MailIcon() {
  return (
    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
    </svg>
  )
}

function BellIcon() {
  return (
    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0a3 3 0 11-6 0" />
    </svg>
  )
}

function UserIcon() {
  return (
    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
    </svg>
  )
}

function ActivityIcon() {
  return (
    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
    </svg>
  )
}

// ── Componentes de formulario reutilizables ──

function Input({ label, value, onChange, type = 'text', placeholder, className = '' }: {
  label: string
  value: string
  onChange: (v: string) => void
  type?: string
  placeholder?: string
  className?: string
}) {
  return (
    <div className={className}>
      <label className="block text-xs font-semibold text-muted-foreground mb-1.5">{label}</label>
      <input
        type={type}
        value={value}
        onChange={e => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full px-3.5 py-2.5 bg-card border border-border rounded-xl text-sm text-foreground
          outline-none focus:ring-2 focus:ring-chart-1/40 focus:border-chart-1/50
          placeholder:text-muted-foreground/40 transition-all"
      />
    </div>
  )
}

function Select({ label, value, onChange, options }: {
  label: string
  value: string
  onChange: (v: string) => void
  options: { value: string; label: string }[]
}) {
  return (
    <div>
      <label className="block text-xs font-semibold text-muted-foreground mb-1.5">{label}</label>
      <select
        value={value}
        onChange={e => onChange(e.target.value)}
        className="w-full px-3.5 py-2.5 bg-card border border-border rounded-xl text-sm text-foreground
          outline-none focus:ring-2 focus:ring-chart-1/40 focus:border-chart-1/50 transition-all"
      >
        {options.map(o => (
          <option key={o.value} value={o.value} className="text-foreground bg-card">{o.label}</option>
        ))}
      </select>
    </div>
  )
}

function Feedback({ message, type }: { message: string | null; type: 'success' | 'error' | 'info' | null }) {
  if (!message || !type) return null
  const colors: Record<string, string> = {
    success: 'bg-chart-2/10 border-chart-2/20 text-chart-2',
    error: 'bg-destructive/10 border-destructive/20 text-destructive',
    info: 'bg-chart-1/10 border-chart-1/20 text-chart-1',
  }
  return (
    <motion.div
      initial={{ opacity: 0, y: -8 }}
      animate={{ opacity: 1, y: 0 }}
      className={`p-3 rounded-xl border text-xs ${colors[type]}`}
    >
      {message}
    </motion.div>
  )
}

function SectionCard({ title, description, children }: { title: string; description?: string; children: React.ReactNode }) {
  return (
    <div className="bg-card rounded-2xl border border-border/50 shadow-sm p-6">
      <h3 className="text-base font-semibold text-foreground mb-1">{title}</h3>
      {description && <p className="text-xs text-muted-foreground mb-5">{description}</p>}
      {children}
    </div>
  )
}

function StatusBadge({ ok, label }: { ok: boolean; label: string }) {
  return (
    <div className="flex items-center gap-2.5 px-4 py-3 rounded-xl bg-secondary/30 border border-border/30">
      <span className={`w-2.5 h-2.5 rounded-full shrink-0 ${ok ? 'bg-chart-2 shadow-[0_0_8px] shadow-chart-2/50' : 'bg-destructive shadow-[0_0_8px] shadow-destructive/30'}`} />
      <span className="text-sm text-foreground/80">{label}</span>
      <span className="ml-auto text-xs font-semibold font-mono tabular-nums text-muted-foreground">
        {ok ? 'Operativo' : 'No configurado'}
      </span>
    </div>
  )
}

// ═══════════════════════════════════════════════════════════════════
// Pestaña 1: Buzones IMAP
// ═══════════════════════════════════════════════════════════════════

function ImapTab() {
  const [loading, setLoading] = useState(true)

  // Form fields
  const [server, setServer] = useState('')
  const [port, setPort] = useState('993')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [pollInterval, setPollInterval] = useState('5')

  // State
  const [saving, setSaving] = useState(false)
  const [feedback, setFeedback] = useState<{ msg: string; type: 'success' | 'error' | null }>({ msg: '', type: null })

  // Test connection
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState<TestImapResponse | null>(null)

  const fetchSettings = useCallback(async () => {
    try {
      const s = await getImapSettings()
      setServer(s.server)
      setPort(String(s.port))
      setEmail(s.email)
      setPassword(s.password)
      setPollInterval(String(s.poll_interval_minutes))
    } catch {
      setFeedback({ msg: 'Error al cargar configuración IMAP', type: 'error' })
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchSettings() }, [fetchSettings])

  const handleSave = async () => {
    setSaving(true)
    setFeedback({ msg: '', type: null })
    try {
      const body: ImapUpdate = { server, port: Number(port), email }
      if (password && !password.startsWith('*')) body.password = password
      if (pollInterval) body.poll_interval_minutes = Number(pollInterval)
      await updateImapSettings(body)
      setFeedback({ msg: 'Configuración IMAP guardada correctamente', type: 'success' })
      fetchSettings()
    } catch (e) {
      setFeedback({ msg: e instanceof Error ? e.message : 'Error al guardar', type: 'error' })
    } finally {
      setSaving(false)
    }
  }

  const handleTest = async () => {
    setTesting(true)
    setTestResult(null)
    try {
      const pwd = password.startsWith('*') ? '' : password
      if (!pwd) {
        setTestResult({ success: false, message: 'Introduce la contraseña para probar', folders: [] })
        setTesting(false)
        return
      }
      const result = await testImapConnection({ server, port: Number(port), email, password: pwd })
      setTestResult(result)
    } catch (e) {
      setTestResult({ success: false, message: e instanceof Error ? e.message : 'Error de conexión', folders: [] })
    } finally {
      setTesting(false)
    }
  }

  if (loading) return <div className="text-center py-12 text-muted-foreground text-sm">Cargando configuración...</div>

  return (
    <div className="space-y-6">
      <SectionCard title="Conexión IMAP" description="Configura el buzón de correo del que se extraerán los emails para clasificar.">
        <div className="grid sm:grid-cols-2 gap-4 mb-5">
          <Input label="Servidor IMAP" value={server} onChange={setServer} placeholder="imap.gmail.com" />
          <Input label="Puerto" value={port} onChange={setPort} placeholder="993" />
          <Input label="Email" value={email} onChange={setEmail} placeholder="correo@empresa.com" type="email" />
          <Input label="Contraseña" value={password} onChange={setPassword} type="password" placeholder="••••••••" />
          <Input label="Intervalo de polling (minutos)" value={pollInterval} onChange={setPollInterval} placeholder="5" />
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={handleSave}
            disabled={saving}
            className="px-5 py-2.5 bg-chart-1 text-white rounded-xl text-sm font-semibold
              hover:bg-chart-1/90 active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
          >
            {saving ? 'Guardando...' : 'Guardar'}
          </button>
          <button
            onClick={handleTest}
            disabled={testing}
            className="px-5 py-2.5 bg-card text-chart-1 border border-chart-1/40 rounded-xl text-sm font-semibold
              hover:bg-chart-1/10 active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
          >
            {testing ? 'Probando...' : 'Probar conexión'}
          </button>
        </div>
        <Feedback message={feedback.msg} type={feedback.type} />
      </SectionCard>

      {/* Resultado del test */}
      {testResult && (
        <motion.div
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
          className={`rounded-2xl border p-5 ${testResult.success ? 'bg-chart-2/10 border-chart-2/20' : 'bg-destructive/10 border-destructive/20'}`}
        >
          <div className="flex items-center gap-2 mb-2">
            <span className={`w-2 h-2 rounded-full ${testResult.success ? 'bg-chart-2' : 'bg-destructive'}`} />
            <span className={`text-sm font-semibold ${testResult.success ? 'text-chart-2' : 'text-destructive'}`}>
              {testResult.success ? 'Conexión exitosa' : 'Error de conexión'}
            </span>
          </div>
          <p className="text-xs text-muted-foreground mb-2">{testResult.message}</p>
          {testResult.folders.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-muted-foreground mb-1.5">Carpetas disponibles ({testResult.folders.length}):</p>
              <div className="flex flex-wrap gap-1.5">
                {testResult.folders.map(f => (
                  <span key={f} className="px-2 py-0.5 rounded-md text-[10px] font-medium bg-card border border-border/50 text-muted-foreground">
                    {f}
                  </span>
                ))}
              </div>
            </div>
          )}
        </motion.div>
      )}
    </div>
  )
}

// ═══════════════════════════════════════════════════════════════════
// Pestaña 2: Notificaciones (Telegram)
// ═══════════════════════════════════════════════════════════════════

function NotificationsTab() {
  const [botToken, setBotToken] = useState('')
  const [chatId, setChatId] = useState('')
  const [minUrgency, setMinUrgency] = useState('alta')

  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [feedback, setFeedback] = useState<{ msg: string; type: 'success' | 'error' | null }>({ msg: '', type: null })

  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState<TestTelegramResponse | null>(null)

  const fetchSettings = useCallback(async () => {
    try {
      const s = await getNotificationSettings()
      setBotToken(s.telegram_bot_token)
      setChatId(s.telegram_chat_id)
      setMinUrgency(s.telegram_min_urgency)
    } catch {
      setFeedback({ msg: 'Error al cargar configuración de notificaciones', type: 'error' })
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchSettings() }, [fetchSettings])

  const handleSave = async () => {
    setSaving(true)
    setFeedback({ msg: '', type: null })
    try {
      const body: NotificationUpdate = { telegram_chat_id: chatId, telegram_min_urgency: minUrgency }
      if (botToken && !botToken.startsWith('*')) body.telegram_bot_token = botToken
      await updateNotificationSettings(body)
      setFeedback({ msg: 'Configuración de notificaciones guardada', type: 'success' })
      fetchSettings()
    } catch (e) {
      setFeedback({ msg: e instanceof Error ? e.message : 'Error al guardar', type: 'error' })
    } finally {
      setSaving(false)
    }
  }

  const handleTest = async () => {
    setTesting(true)
    setTestResult(null)
    try {
      const result = await testTelegram()
      setTestResult(result)
    } catch (e) {
      setTestResult({ success: false, message: e instanceof Error ? e.message : 'Error', folders: [] } as unknown as TestTelegramResponse)
    } finally {
      setTesting(false)
    }
  }

  if (loading) return <div className="text-center py-12 text-muted-foreground text-sm">Cargando configuración...</div>

  return (
    <div className="space-y-6">
      <SectionCard title="Telegram" description="Configura las alertas de correos urgentes vía Telegram Bot.">
        <div className="space-y-4 mb-5">
          <Input label="Token del Bot" value={botToken} onChange={setBotToken} type="password" placeholder="123456:ABC-def..." />
          <Input label="Chat ID" value={chatId} onChange={setChatId} placeholder="767074407" />
          <Select
            label="Urgencia mínima para notificar"
            value={minUrgency}
            onChange={setMinUrgency}
            options={[
              { value: 'alta', label: 'Alta' },
              { value: 'media', label: 'Media' },
              { value: 'baja', label: 'Baja' },
            ]}
          />
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={handleSave}
            disabled={saving}
            className="px-5 py-2.5 bg-chart-1 text-white rounded-xl text-sm font-semibold
              hover:bg-chart-1/90 active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
          >
            {saving ? 'Guardando...' : 'Guardar'}
          </button>
          <button
            onClick={handleTest}
            disabled={testing}
            className="px-5 py-2.5 bg-card text-chart-3 border border-chart-3/40 rounded-xl text-sm font-semibold
              hover:bg-chart-3/10 active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
          >
            {testing ? 'Enviando...' : 'Enviar prueba'}
          </button>
        </div>
        <Feedback message={feedback.msg} type={feedback.type} />
      </SectionCard>

      {testResult && (
        <motion.div
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
          className={`rounded-2xl border p-4 ${testResult.success ? 'bg-chart-2/10 border-chart-2/20' : 'bg-destructive/10 border-destructive/20'}`}
        >
          <div className="flex items-center gap-2">
            <span className={`w-2 h-2 rounded-full ${testResult.success ? 'bg-chart-2' : 'bg-destructive'}`} />
            <span className={`text-sm font-semibold ${testResult.success ? 'text-chart-2' : 'text-destructive'}`}>
              {testResult.success ? 'Notificación enviada' : 'Error'}
            </span>
          </div>
          <p className="text-xs text-muted-foreground mt-1">{testResult.message}</p>
        </motion.div>
      )}
    </div>
  )
}

// ═══════════════════════════════════════════════════════════════════
// Pestaña 3: Cuenta (cambio de contraseña)
// ═══════════════════════════════════════════════════════════════════

function AccountTab() {
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [saving, setSaving] = useState(false)
  const [feedback, setFeedback] = useState<{ msg: string; type: 'success' | 'error' | null }>({ msg: '', type: null })

  const handleSave = async () => {
    setFeedback({ msg: '', type: null })

    if (newPassword.length < 6) {
      setFeedback({ msg: 'La nueva contraseña debe tener al menos 6 caracteres', type: 'error' })
      return
    }
    if (newPassword !== confirmPassword) {
      setFeedback({ msg: 'Las contraseñas no coinciden', type: 'error' })
      return
    }

    setSaving(true)
    try {
      await changePassword({ current_password: currentPassword, new_password: newPassword })
      setFeedback({ msg: 'Contraseña cambiada correctamente', type: 'success' })
      setCurrentPassword('')
      setNewPassword('')
      setConfirmPassword('')
    } catch (e) {
      setFeedback({ msg: e instanceof Error ? e.message : 'Error al cambiar contraseña', type: 'error' })
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="max-w-lg">
      <SectionCard title="Cambiar contraseña" description="Actualiza la contraseña de tu cuenta de administrador.">
        <div className="space-y-4 mb-5">
          <Input label="Contraseña actual" value={currentPassword} onChange={setCurrentPassword} type="password" placeholder="••••••••" />
          <Input label="Nueva contraseña" value={newPassword} onChange={setNewPassword} type="password" placeholder="Mínimo 6 caracteres" />
          <Input label="Confirmar nueva contraseña" value={confirmPassword} onChange={setConfirmPassword} type="password" placeholder="Repite la contraseña" />
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={handleSave}
            disabled={saving || !currentPassword || !newPassword}
            className="px-5 py-2.5 bg-chart-1 text-white rounded-xl text-sm font-semibold
              hover:bg-chart-1/90 active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
          >
            {saving ? 'Cambiando...' : 'Cambiar contraseña'}
          </button>
        </div>
        <Feedback message={feedback.msg} type={feedback.type} />
      </SectionCard>
    </div>
  )
}

// ═══════════════════════════════════════════════════════════════════
// Pestaña 4: Estado del Sistema
// ═══════════════════════════════════════════════════════════════════

function formatUptime(seconds: number | null): string {
  if (!seconds) return '-'
  const d = Math.floor(seconds / 86400)
  const h = Math.floor((seconds % 86400) / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const parts: string[] = []
  if (d > 0) parts.push(`${d}d`)
  if (h > 0) parts.push(`${h}h`)
  parts.push(`${m}m`)
  return parts.join(' ')
}

function StatusTab() {
  const [status, setStatus] = useState<SystemStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchStatus = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const s = await getSystemStatus()
      setStatus(s)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Error al cargar estado')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchStatus() }, [fetchStatus])

  if (loading) return <div className="text-center py-12 text-muted-foreground text-sm">Cargando estado del sistema...</div>
  if (error) return <div className="text-destructive text-sm py-8 text-center">{error}</div>
  if (!status) return null

  const infoRows = [
    { label: 'Versión', value: status.version },
    { label: 'Base de datos', value: status.database },
    { label: 'Tiempo activo', value: formatUptime(status.uptime_seconds) },
    { label: 'Última sincronización', value: status.last_sync_at ? new Date(status.last_sync_at).toLocaleString('es-ES') : 'Nunca' },
    { label: 'Último re-entrenamiento', value: status.last_retrain_at ? new Date(status.last_retrain_at).toLocaleString('es-ES') : 'Nunca' },
  ]

  if (status.last_retrain_accuracy !== null) {
    infoRows.push({ label: 'Accuracy del modelo', value: `${(status.last_retrain_accuracy * 100).toFixed(1)}%` })
  }

  return (
    <div className="grid lg:grid-cols-2 gap-6">
      <SectionCard title="Servicios" description="Estado de los servicios del sistema.">
        <div className="space-y-2">
          <StatusBadge ok={status.imap_configured} label="IMAP (Buzón de correo)" />
          <StatusBadge ok={status.ollama_reachable} label="Ollama (IA local)" />
          <StatusBadge ok={status.openrouter_configured} label="OpenRouter (IA cloud)" />
          <StatusBadge ok={status.telegram_configured} label="Telegram (Notificaciones)" />
          <StatusBadge ok={status.crm_configured} label="VTiger CRM" />
        </div>
      </SectionCard>

      <SectionCard title="Información" description="Detalles del sistema.">
        <div className="space-y-1">
          {infoRows.map(row => (
            <div key={row.label} className="flex justify-between py-2 border-b border-border/30 last:border-b-0">
              <span className="text-sm text-muted-foreground">{row.label}</span>
              <span className="text-sm text-foreground/80 font-medium">{row.value}</span>
            </div>
          ))}
        </div>
        <div className="mt-5">
          <button
            onClick={fetchStatus}
            disabled={loading}
            className="px-4 py-2 bg-card text-chart-1 border border-chart-1/40 rounded-xl text-xs font-semibold
              hover:bg-chart-1/10 active:scale-95 transition-all"
          >
            {loading ? 'Actualizando...' : 'Refrescar estado'}
          </button>
        </div>
      </SectionCard>
    </div>
  )
}

// ═══════════════════════════════════════════════════════════════════
// Componente principal
// ═══════════════════════════════════════════════════════════════════

export default function Settings() {
  const [activeTab, setActiveTab] = useState('imap')

  const renderTab = () => {
    switch (activeTab) {
      case 'imap': return <ImapTab />
      case 'notifications': return <NotificationsTab />
      case 'account': return <AccountTab />
      case 'status': return <StatusTab />
      default: return null
    }
  }

  return (
    <div className="px-6 py-8">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
      >
        <h1 className="text-3xl font-bold tracking-tight mb-2 font-display">Ajustes</h1>
        <p className="text-muted-foreground text-sm mb-6">Configuración del sistema</p>

        {/* Tabs */}
        <div className="flex gap-1 mb-8 bg-secondary/50 rounded-2xl p-1.5 w-fit">
          {TABS.map(tab => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`relative flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium transition-all ${
                activeTab === tab.key
                  ? 'bg-card text-foreground shadow-sm'
                  : 'text-muted-foreground hover:text-foreground'
              }`}
            >
              <tab.icon />
              {tab.label}
            </button>
          ))}
        </div>

        {/* Contenido */}
        <motion.div
          key={activeTab}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3 }}
        >
          {renderTab()}
        </motion.div>
      </motion.div>
    </div>
  )
}
