/**
 * KnowledgeVaultSurface — knowledge base browser.
 *
 * Features a search bar, category filter pills, and a results list
 * of article cards with excerpt, category badge, date, and relevance.
 */

import { useState, useEffect, useCallback, useMemo } from 'react'
import { useSocShell } from '../../services/soc/SocShellProvider'
import { SURFACE_IDS } from '../../services/soc/contracts'
import type { SocError } from '../../services/soc/contracts'
import { socFetch } from '../../services/soc/client'
import { SOC_ENDPOINTS } from '../../services/soc/endpoints'
import { normalizeKnowledgeVault } from '../../services/soc/normalize/knowledgeVault'
import type { KnowledgeVaultView } from '../../services/soc/normalize/knowledgeVault'
import { SocLoadingState, SocEmptyState, SocErrorState } from '../../components/soc'
import { applyNeutralCopy, t } from '../../content/socCopy'
import { cn } from '../../lib/utils'
import {
  Search,
  BookOpen,
  X,
  Filter,
  Clock,
  Star,
  FileText,
  Lightbulb,
  GitFork,
  Megaphone,
} from 'lucide-react'

// ─── Constants ───────────────────────────────────────────────────────────

const SURFACE_ID = SURFACE_IDS.KNOWLEDGE_VAULT

const CATEGORIES = ['SOPs', 'Playbooks', 'Known Issues', 'Release Notes'] as const

const CATEGORY_ICONS: Record<string, typeof FileText> = {
  SOPs: FileText,
  Playbooks: GitFork,
  'Known Issues': Lightbulb,
  'Release Notes': Megaphone,
}

// ─── Mock data ────────────────────────────────────────────────────────────

interface MockArticle {
  id: string
  title: string
  excerpt: string
  category: string
  tags: string[]
  updatedAt: string
  relevance: number // 0–100
}

const MOCK_ARTICLES: MockArticle[] = [
  {
    id: 'KB-001',
    title: 'BGP Route Flap Mitigation — Standard Operating Procedure',
    excerpt: 'Step-by-step SOP for identifying and mitigating BGP route flaps across all managed peers. Covers monitoring, confirmation, rollback, and post-mortem.',
    category: 'SOPs',
    tags: ['bgp', 'routing', 'flap', 'mitigation'],
    updatedAt: '2026-06-15T10:30:00Z',
    relevance: 98,
  },
  {
    id: 'KB-002',
    title: 'DDoS Mitigation Playbook — Layer 3/4 Attacks',
    excerpt: 'Comprehensive playbook for detecting, classifying, and mitigating volumetric DDoS attacks targeting customer-facing infrastructure.',
    category: 'Playbooks',
    tags: ['ddos', 'mitigation', 'layer3', 'layer4'],
    updatedAt: '2026-06-14T08:00:00Z',
    relevance: 95,
  },
  {
    id: 'KB-003',
    title: 'Known Issue: MX-480 Line Card LC-4XGE-XFP Hard Lockup',
    excerpt: 'Under sustained 90%+ throughput, LC-4XGE-XFP line cards may enter a hard lockup state requiring manual OIR. Affected firmware versions: 18.2R1–18.4R2.',
    category: 'Known Issues',
    tags: ['mx-480', 'line-card', 'lockup', 'hardware'],
    updatedAt: '2026-06-13T14:15:00Z',
    relevance: 91,
  },
  {
    id: 'KB-004',
    title: 'Release Notes — v3.2.0 Security Policy Engine',
    excerpt: 'New security policy engine introduces zone-based firewalling, application-layer inspection, and TLS 1.3 termination. Backward-compatible config migration.',
    category: 'Release Notes',
    tags: ['release', 'security', 'policy', 'engine'],
    updatedAt: '2026-06-12T16:45:00Z',
    relevance: 88,
  },
  {
    id: 'KB-005',
    title: 'SOP: SSL/TLS Certificate Renewal via ACME Automation',
    excerpt: 'Automated certificate lifecycle management using ACME protocol with Let\'s Encrypt and Sectigo. Covers validation, renewal, and revocation workflows.',
    category: 'SOPs',
    tags: ['ssl', 'tls', 'certificate', 'acme', 'renewal'],
    updatedAt: '2026-06-11T09:00:00Z',
    relevance: 85,
  },
  {
    id: 'KB-006',
    title: 'Incident Response Playbook — Ransomware Detection',
    excerpt: 'Detection, containment, eradication, and recovery steps for ransomware incidents affecting customer environments. Includes IOC indicators and C2 blocklists.',
    category: 'Playbooks',
    tags: ['ransomware', 'incident', 'response', 'security'],
    updatedAt: '2026-06-10T11:30:00Z',
    relevance: 92,
  },
  {
    id: 'KB-007',
    title: 'Known Issue: SNMP BulkWalk Timeout on Large OID Trees',
    excerpt: 'SNMP bulkwalk operations against OID trees exceeding 10,000 nodes may time out after 30s. Workaround: use walk with max-repetitions 25 or split queries.',
    category: 'Known Issues',
    tags: ['snmp', 'bulkwalk', 'timeout', 'monitoring'],
    updatedAt: '2026-06-09T13:20:00Z',
    relevance: 78,
  },
  {
    id: 'KB-008',
    title: 'Release Notes — v2.1.0 Log Aggregation Pipeline',
    excerpt: 'New log aggregation pipeline with Elasticsearch 8.x backend, improved indexing performance, and support for structured syslog over TCP/TLS.',
    category: 'Release Notes',
    tags: ['release', 'logging', 'elasticsearch', 'pipeline'],
    updatedAt: '2026-06-08T10:00:00Z',
    relevance: 82,
  },
]

// ─── Helpers ──────────────────────────────────────────────────────────────

function formatDate(iso: string): string {
  const date = new Date(iso)
  return date.toLocaleDateString('es-ES', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  })
}

function categoryColor(category: string): string {
  switch (category) {
    case 'SOPs':
      return 'bg-chart-1/10 text-chart-1 border-chart-1/20'
    case 'Playbooks':
      return 'bg-chart-2/10 text-chart-2 border-chart-2/20'
    case 'Known Issues':
      return 'bg-warning/10 text-warning border-warning/20'
    case 'Release Notes':
      return 'bg-chart-3/10 text-chart-3 border-chart-3/20'
    default:
      return 'bg-muted text-muted-foreground border-border/50'
  }
}

function relevanceColor(score: number): string {
  if (score >= 90) return 'text-success'
  if (score >= 70) return 'text-chart-1'
  return 'text-muted-foreground'
}

// ─── Sub-components ───────────────────────────────────────────────────────

function ArticleCard({ article }: { article: MockArticle }) {
  const IconComponent = CATEGORY_ICONS[article.category] ?? FileText

  return (
    <div className="bg-card rounded-2xl border border-border/50 shadow-sm p-5 hover:shadow-md hover:-translate-y-0.5 transition-all duration-300">
      <div className="flex items-start gap-4">
        <div className={cn('rounded-xl p-2.5 shrink-0', categoryColor(article.category))}>
          <IconComponent className="h-5 w-5" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-3">
            <div className="space-y-1">
              <h4 className="text-sm font-semibold text-foreground leading-snug">{applyNeutralCopy(article.title)}</h4>
              <p className="text-xs text-muted-foreground leading-relaxed line-clamp-2">{applyNeutralCopy(article.excerpt)}</p>
            </div>
            {/* Relevance score */}
            <div className={cn('flex items-center gap-1 text-xs font-medium shrink-0', relevanceColor(article.relevance))}>
              <Star className="h-3 w-3 fill-current" />
              {article.relevance}%
            </div>
          </div>
          <div className="flex items-center gap-3 mt-3">
            <span className={cn('text-[10px] font-medium px-2 py-0.5 rounded border', categoryColor(article.category))}>
              {article.category}
            </span>
            <span className="text-[10px] text-muted-foreground flex items-center gap-1">
              <Clock className="h-3 w-3" />
              {formatDate(article.updatedAt)}
            </span>
          </div>
          {article.tags.length > 0 && (
            <div className="flex flex-wrap gap-1 mt-2">
              {article.tags.map((tag) => (
                <span
                  key={tag}
                  className="text-[10px] px-1.5 py-0.5 rounded bg-muted text-muted-foreground"
                >
                  {tag}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// ─── Main surface ─────────────────────────────────────────────────────────

export default function KnowledgeVaultSurface() {
  const { setSurfaceStatus } = useSocShell()
  const [data, setData] = useState<KnowledgeVaultView | null>(null)
  const [error, setError] = useState<SocError | null>(null)
  const [loading, setLoading] = useState(true)

  // UI state
  const [searchQuery, setSearchQuery] = useState('')
  const [activeCategory, setActiveCategory] = useState<string | null>(null)
  const [articles] = useState<MockArticle[]>(MOCK_ARTICLES)

  const fetchData = useCallback(async () => {
    setLoading(true)
    setError(null)
    setSurfaceStatus(SURFACE_ID, 'loading')

    try {
      const raw = await socFetch<Record<string, unknown>>(SOC_ENDPOINTS[SURFACE_ID])
      const view = normalizeKnowledgeVault(raw)
      setData(view)
      setSurfaceStatus(SURFACE_ID, 'ready')
    } catch (err: unknown) {
      // Fallback: use mock data when backend is unavailable
      setSurfaceStatus(SURFACE_ID, 'ready')
      const socErr: SocError = {
        code: 'FALLBACK_MODE',
        message: err instanceof Error ? err.message : String(err),
      }
      setError(socErr)
    } finally {
      setLoading(false)
    }
  }, [setSurfaceStatus])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  // ── Derived: filtered articles ──

  const filteredArticles = useMemo(() => {
    let result = articles

    if (activeCategory) {
      result = result.filter((a) => a.category === activeCategory)
    }

    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase()
      result = result.filter(
        (a) =>
          a.title.toLowerCase().includes(q) ||
          a.excerpt.toLowerCase().includes(q) ||
          a.tags.some((tag) => tag.toLowerCase().includes(q)),
      )
    }

    // Sort by relevance descending
    return [...result].sort((a, b) => b.relevance - a.relevance)
  }, [articles, activeCategory, searchQuery])

  const isFallback = error?.code === 'FALLBACK_MODE'

  const hasActiveFilters = activeCategory !== null || searchQuery.trim() !== ''

  const clearFilters = () => {
    setActiveCategory(null)
    setSearchQuery('')
  }

  // ── Loading ──

  if (loading) {
    return <SocLoadingState surfaceLabel={t('surfaces.knowledgeVault')} />
  }

  // ── Error (only when NOT in fallback mode) ──

  if (error && !isFallback) {
    return <SocErrorState error={error} />
  }

  // ── Empty (skip in fallback mode — show mock data) ──

  if (!isFallback && (!data || (data.articles.length === 0 && articles.length === 0))) {
    return <SocEmptyState surfaceId={SURFACE_ID} />
  }

  // ── Content ──

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center gap-2">
        <BookOpen className="h-5 w-5 text-chart-2" />
        <h2 className="text-lg font-semibold">{t('surfaces.knowledgeVault')}</h2>
        <span className="text-xs text-muted-foreground">
          ({articles.length} {t('knowledge.articles')})
        </span>
        {isFallback && (
          <span className="ml-auto text-[10px] font-medium px-2 py-0.5 rounded bg-warning/10 text-warning border border-warning/20">
            Fallback Mode
          </span>
        )}
      </div>

      {/* Search bar */}
      <div className="relative max-w-xl">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder={t('knowledge.searchPlaceholder')}
          className={cn(
            'w-full pl-10 pr-10 py-2.5 text-sm bg-card border border-border/50 rounded-xl',
            'placeholder:text-muted-foreground/60 focus:outline-none focus:ring-1 focus:ring-ring',
          )}
        />
        {searchQuery && (
          <button
            onClick={() => setSearchQuery('')}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>

      {/* Category filter pills */}
      <div className="flex flex-wrap items-center gap-2">
        {CATEGORIES.map((category) => (
          <button
            key={category}
            onClick={() => setActiveCategory(activeCategory === category ? null : category)}
            className={cn(
              'flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg border transition-colors cursor-pointer',
              activeCategory === category
                ? 'bg-primary text-primary-foreground border-primary'
                : 'bg-card text-muted-foreground border-border/50 hover:border-border hover:text-foreground',
            )}
          >
            {(() => {
              const Icon = CATEGORY_ICONS[category]
              return Icon ? <Icon className="h-3.5 w-3.5" /> : null
            })()}
            {category}
          </button>
        ))}
        {hasActiveFilters && (
          <button
            onClick={clearFilters}
            className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors ml-2 cursor-pointer"
          >
            <Filter className="h-3 w-3" />
            {t('knowledge.clearFilters')}
          </button>
        )}
      </div>

      {/* Results */}
      {filteredArticles.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 text-muted-foreground bg-card rounded-2xl border border-border/50 shadow-sm">
          <Search className="h-10 w-10 mb-3 text-muted-foreground/40" />
          <p className="text-sm">{t('knowledge.noResults')}</p>
          {hasActiveFilters && (
            <button
              onClick={clearFilters}
              className="mt-3 text-xs text-primary hover:underline cursor-pointer"
            >
              {t('knowledge.clearFilters')}
            </button>
          )}
        </div>
      ) : (
        <div className="space-y-3">
          {filteredArticles.map((article) => (
            <ArticleCard key={article.id} article={article} />
          ))}
        </div>
      )}
    </div>
  )
}
