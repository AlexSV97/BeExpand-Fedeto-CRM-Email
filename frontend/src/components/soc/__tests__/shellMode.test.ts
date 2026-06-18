import { describe, expect, it } from 'vitest'

import { getSocShellMode } from '../shellMode'


describe('getSocShellMode', () => {
  it('returns Live styling for backend data', () => {
    const mode = getSocShellMode('backend')
    expect(mode.label).toBe('Live')
    expect(mode.badgeClassName).toContain('success')
  })

  it('returns Demo styling for mock data', () => {
    const mode = getSocShellMode('mock')
    expect(mode.label).toBe('Demo')
    expect(mode.badgeClassName).toContain('warning')
  })

  it('returns Degraded styling for error data', () => {
    const mode = getSocShellMode('error')
    expect(mode.label).toBe('Degraded')
    expect(mode.badgeClassName).toContain('destructive')
  })
})
