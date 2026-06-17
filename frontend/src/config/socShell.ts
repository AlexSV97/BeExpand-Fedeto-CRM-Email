const SOC_SHELL_FEATURE_KEY = 'soc_shell_enabled'
const FORCE_SOC_SHELL_HOSTS = {
  PUBLIC_RENDER: 'beconnect-frontend.onrender.com',
} as const

function shouldForceSocShellEnabled(): boolean {
  if (typeof window === 'undefined') return false

  const envDefault = import.meta.env.VITE_SOC_SHELL_DEFAULT === 'true'
  const isPublicRenderHost = window.location.hostname === FORCE_SOC_SHELL_HOSTS.PUBLIC_RENDER

  return envDefault || isPublicRenderHost
}

function isSocShellEnabled(): boolean {
  if (shouldForceSocShellEnabled()) return true
  return localStorage.getItem(SOC_SHELL_FEATURE_KEY) === 'true'
}

function setSocShellEnabled(enabled: boolean): void {
  localStorage.setItem(SOC_SHELL_FEATURE_KEY, String(enabled))
}

export { SOC_SHELL_FEATURE_KEY, isSocShellEnabled, setSocShellEnabled, shouldForceSocShellEnabled }
