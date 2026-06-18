/**
 * SocShell — Aiuken SOC shell layout.
 *
 * Renders a top navigation bar with Aiuken SOC branding and a tab strip
 * of all registered surfaces.  The active surface component is rendered
 * below the strip.  Uses t() for all copy and reuses the AnimatedBackground
 * pattern from the existing Layout.
 *
 * This component does NOT use React Router — surface navigation is driven
 * by the zustand store + browser history (useHistorySync).
 */

import { Suspense } from 'react'
import { useSocShell } from '../../services/soc/SocShellProvider'
import { useHistorySync } from '../../services/soc/socShellStore'
import { surfaceRegistry } from '../../services/soc/surfaceRegistry'
import { t } from '../../content/socCopy'
import { cn } from '../../lib/utils'
import { motion } from 'framer-motion'
import { SocLoadingState } from './index'
import { getSocShellMode } from './shellMode'

// ── Fondo animado ambiental (reutilizado de Layout.tsx) ──

function AnimatedBackground() {
  return (
    <div className="fixed inset-0 -z-10 overflow-hidden">
      <div className="absolute inset-0 bg-gradient-to-br from-background via-background to-muted/50" />
      <div className="absolute top-0 left-1/4 w-[800px] h-[800px] bg-gradient-to-br from-chart-1/5 to-transparent rounded-full blur-3xl animate-float" />
      <div className="absolute bottom-0 right-1/4 w-[600px] h-[600px] bg-gradient-to-br from-chart-2/5 to-transparent rounded-full blur-3xl animate-float-delayed" />
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[1000px] h-[1000px] bg-gradient-to-br from-chart-3/3 to-transparent rounded-full blur-3xl animate-float-slow" />
      <div
        className="absolute inset-0 opacity-[0.015] dark:opacity-[0.03]"
        style={{
          backgroundImage: `linear-gradient(to right, currentColor 1px, transparent 1px),
                           linear-gradient(to bottom, currentColor 1px, transparent 1px)`,
          backgroundSize: '60px 60px',
        }}
      />
    </div>
  )
}

// ── Componente principal ──

export default function SocShell() {
  // Sync browser back/forward with surface navigation
  useHistorySync()

  const { activeSurfaceId, navigate, featureEnabled, dataSource } = useSocShell()
  const shellMode = getSocShellMode(dataSource[activeSurfaceId] ?? 'mock')

  // Safety guard — if the flag somehow flips off while mounted, render nothing
  if (!featureEnabled) return null

  const allSurfaces = surfaceRegistry.getAll()
  const activeDescriptor = surfaceRegistry.get(activeSurfaceId)
  const SurfaceComponent = activeDescriptor?.component

  return (
    <div className="min-h-screen relative">
      <AnimatedBackground />

      {/* ── Navegación superior ── */}
      <motion.nav
        initial={{ y: -20, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
        className="fixed top-0 left-0 right-0 z-50 backdrop-blur-xl"
        style={{ backgroundColor: 'var(--glass)', borderBottom: '1px solid var(--glass-border)' }}
      >
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          {/* Brand */}
          <div className="flex items-center gap-3">
            <motion.div
              whileHover={{ scale: 1.02 }}
              transition={{ type: 'spring', stiffness: 400, damping: 17 }}
              className="flex items-center gap-3"
            >
              <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-foreground to-foreground/70 flex items-center justify-center">
                <span className="text-background font-bold text-sm font-display">AS</span>
              </div>
              <span className="font-semibold text-lg tracking-tight font-display text-foreground">
                {t('Aiuken SOC')}
              </span>
              <span
                className={cn(
                  'flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded-full border leading-none',
                  shellMode.badgeClassName,
                )}
              >
                <span className={cn('w-1.5 h-1.5 rounded-full', shellMode.dotClassName)} />
                {shellMode.label}
              </span>
            </motion.div>
          </div>

          {/* Pestañas de superficie */}
          <div className="hidden md:flex items-center gap-1 bg-secondary/50 rounded-full p-1">
            {allSurfaces.map((surface) => {
              const isActive = surface.id === activeSurfaceId
              return (
                <button
                  key={surface.id}
                  onClick={() => navigate(surface.id)}
                  className={cn(
                    'relative px-5 py-2 text-sm font-medium rounded-full transition-colors cursor-pointer',
                    isActive
                      ? 'text-primary-foreground'
                      : 'text-muted-foreground hover:text-foreground',
                  )}
                >
                  {isActive && (
                    <motion.div
                      layoutId="socActiveTab"
                      className="absolute inset-0 bg-primary rounded-full"
                      transition={{ type: 'spring', stiffness: 500, damping: 35 }}
                    />
                  )}
                  <span className="relative z-10 flex items-center gap-2">
                    {surface.icon}
                    {t(surface.label)}
                  </span>
                </button>
              )
            })}
          </div>

          {/* Espaciador derecho para mantener centradas las pestañas */}
          <div className="w-[100px]" />
        </div>
      </motion.nav>

      {/* ── Contenido de la superficie activa ── */}
      <main className="pt-16 p-6 max-w-7xl mx-auto">
        <Suspense fallback={<SocLoadingState />}>
          {SurfaceComponent ? <SurfaceComponent /> : null}
        </Suspense>
      </main>
    </div>
  )
}
