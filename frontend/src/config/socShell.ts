const SOC_SHELL_FEATURE_KEY = 'soc_shell_enabled'

function isSocShellEnabled(): boolean {
  return localStorage.getItem(SOC_SHELL_FEATURE_KEY) === 'true'
}

function setSocShellEnabled(enabled: boolean): void {
  localStorage.setItem(SOC_SHELL_FEATURE_KEY, String(enabled))
}

export { SOC_SHELL_FEATURE_KEY, isSocShellEnabled, setSocShellEnabled }
