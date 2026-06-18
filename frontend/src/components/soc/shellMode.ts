export type SocConnectionSource = 'backend' | 'mock' | 'error'

export type SocShellMode = {
  label: 'Live' | 'Demo' | 'Degraded'
  badgeClassName: string
  dotClassName: string
}

export function getSocShellMode(source: SocConnectionSource): SocShellMode {
  switch (source) {
    case 'backend':
      return {
        label: 'Live',
        badgeClassName: 'bg-success/10 border-success/20 text-success',
        dotClassName: 'bg-success animate-pulse',
      }
    case 'error':
      return {
        label: 'Degraded',
        badgeClassName: 'bg-destructive/10 border-destructive/20 text-destructive',
        dotClassName: 'bg-destructive',
      }
    case 'mock':
    default:
      return {
        label: 'Demo',
        badgeClassName: 'bg-warning/10 border-warning/20 text-warning',
        dotClassName: 'bg-warning',
      }
  }
}
