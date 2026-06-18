/**
 * socCopy — SOC term neutralization and copy resolver.
 *
 * Provides a term map to translate legacy/race terminology into
 * SOC-aligned equivalents, a forbidden-terms check, and a simple key-based
 * copy resolver (future: load from a locale map).
 */

// ── Term map ──

const SOC_TERM_MAP: Record<string, string> = {
  'Aiuken Legacy': 'Aiuken SOC',
  'race': 'priority tier',
  'Race': 'Priority tier',
  'Pit': 'Operations',
  'pit': 'operations',
  'Lap': 'Cycle',
  'lap': 'cycle',
  'Circuit': 'Pipeline',
  'circuit': 'pipeline',
  'Garage': 'Workspace',
  'garage': 'workspace',
  'Mission Control': 'Command Center',
}

// ── Forbidden terms ──

const forbiddenTerms: string[] = [
  'race',
  'Race',
  'Pit',
  'pit',
  'Lap',
  'lap',
  'Circuit',
  'circuit',
  'Garage',
  'garage',
  'Mission Control',
]

// ── Context‑sensitive Team → Squad map ──
// Only replace "Team" when it appears in specific racing/physical contexts.

const TEAM_SQUAD_CONTEXTS = [
  /\bPit\s+Team\b/i,
  /\bLap\s+Team\b/i,
  /\bCircuit\s+Team\b/i,
  /\bGarage\s+Team\b/i,
  /\brace\s+Team\b/i,
  /\bRace\s+Team\b/i,
  /\bracing\s+Team\b/i,
]

// ── Helpers ──

/**
 * Check whether `text` contains any forbidden term.
 */
function containsForbiddenTerms(text: string): boolean {
  const lower = text.toLowerCase()
  return forbiddenTerms.some((term) => lower.includes(term.toLowerCase()))
}

/**
 * Replace old terms with SOC equivalents.
 *
 * Applies SOC_TERM_MAP first, then handles "Team" → "Squad" in specific
 * racing/physical contexts (but NOT e.g. "product team", "dev team").
 */
function applyNeutralCopy(text: string): string {
  let result = text

  // 1. Apply direct term replacements (longest-first to avoid partial matches)
  const sortedTerms = Object.entries(SOC_TERM_MAP).sort(
    (a, b) => b[0].length - a[0].length,
  )
  for (const [oldTerm, newTerm] of sortedTerms) {
    // Use case-insensitive global replacement
    const regex = new RegExp(
      oldTerm.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'),
      'gi',
    )
    result = result.replace(regex, (match) => {
      // Preserve casing pattern of the match vs the replacement
      if (match === match.toUpperCase()) return newTerm.toUpperCase()
      if (match[0] === match[0].toUpperCase() && match.slice(1) === match.slice(1).toLowerCase()) {
        return newTerm.charAt(0).toUpperCase() + newTerm.slice(1)
      }
      return newTerm.toLowerCase()
    })
  }

  // 2. Handle Team → Squad in racing/physical contexts
  for (const contextPattern of TEAM_SQUAD_CONTEXTS) {
    result = result.replace(contextPattern, (match) => {
      return match.replace(/\bTeam\b/i, 'Squad')
    })
  }

  return result
}

/**
 * Copy catalog (es). Keys not present fall back to the key itself, so callers
 * still work for not-yet-translated strings.
 */
const COPY: Record<string, string> = {
  loading: 'Cargando…',
  'loading.surface': 'Cargando {{surface}}…',
}

/**
 * Simple key-based copy resolver.
 *
 * Looks up `key` in the COPY catalog (falls back to the key), interpolates any
 * `{{var}}` placeholders from `vars`, then drops unfilled placeholders and tidies
 * whitespace.
 *
 * @example
 *   t('loading')                          // → "Cargando…"
 *   t('loading.surface', { surface })     // → "Cargando <surface>…"
 *   t('error.ECONNREFUSED')               // → "error.ECONNREFUSED" (passthrough)
 */
function t(key: string, vars?: Record<string, string>): string {
  let result = COPY[key] ?? key
  if (vars) {
    for (const [k, v] of Object.entries(vars)) {
      result = result.replace(new RegExp(`\\{\\{${k}\\}\\}`, 'g'), v)
    }
  }
  // Drop any unfilled placeholders and collapse the resulting whitespace.
  result = result.replace(/\{\{\w+\}\}/g, '').replace(/\s{2,}/g, ' ').trim()
  return result
}

export { SOC_TERM_MAP, forbiddenTerms, containsForbiddenTerms, applyNeutralCopy, t }
