const SOC_SHELL_FEATURE_KEY = 'soc_shell_enabled'

/**
 * SOC shell está habilitado por defecto — Aiuken SOC es la interfaz principal.
 * Para volver al CRM legacy, setear VITE_SOC_SHELL_DEFAULT=false en .env
 * o localStorage['soc_shell_enabled'] = 'false'.
 */
function isSocShellEnabled(): boolean {
  if (typeof window === 'undefined') return true

  const envFlag = import.meta.env.VITE_SOC_SHELL_DEFAULT
  // Si el env var está explícitamente false, respetarlo
  if (envFlag === 'false') return false
  // localStorage override para testing
  const stored = localStorage.getItem(SOC_SHELL_FEATURE_KEY)
  if (stored !== null) return stored === 'true'

  return true // DEFAULT: SOC ON
}

function setSocShellEnabled(enabled: boolean): void {
  localStorage.setItem(SOC_SHELL_FEATURE_KEY, String(enabled))
}

export { SOC_SHELL_FEATURE_KEY, isSocShellEnabled, setSocShellEnabled }
