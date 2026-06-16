import { createContext, useContext, useEffect, type ReactNode } from 'react'
import { isSocShellEnabled } from '../../config/socShell'
import { useSocShellStore, type SocShellStore } from './socShellStore'

// ── Context ──

const SocShellContext = createContext<SocShellStore | null>(null)

// ── Provider ──

export function SocShellProvider({ children }: { children: ReactNode }) {
  const store = useSocShellStore()

  // Initialize feature flag from localStorage on mount
  useEffect(() => {
    const enabled = isSocShellEnabled()
    if (enabled !== store.featureEnabled) {
      useSocShellStore.setState({ featureEnabled: enabled })
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // Always provide context — components check featureEnabled themselves.
  // This avoids a first-render timing gap where SocShell would try to
  // call useSocShell() before the Provider has synced the flag.
  return (
    <SocShellContext.Provider value={store}>
      {children}
    </SocShellContext.Provider>
  )
}

// ── Hook ──

export function useSocShell(): SocShellStore {
  const ctx = useContext(SocShellContext)
  if (!ctx) {
    throw new Error(
      'useSocShell() must be used inside <SocShellProvider> when the SOC shell feature is enabled.',
    )
  }
  return ctx
}
