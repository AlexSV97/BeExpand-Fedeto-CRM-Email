/**
 * KnowledgeVaultSurface — knowledge base browser.
 *
 * Features a search bar, category filter pills, and a results list
 * of article cards with excerpt, category badge, date, and relevance.
 */

import { useState, useMemo } from 'react'
import { SURFACE_IDS } from '../../services/soc/contracts'

import { SOC_ENDPOINTS } from '../../services/soc/endpoints'
import { useSocResource } from '../../services/soc/useSocResource'
import { normalizeKnowledgeVault } from '../../services/soc/normalize/knowledgeVault'
import { MOCK_KNOWLEDGE_VAULT, MOCK_ARTICLES } from '../../services/soc/mockData'
import type { MockArticle } from '../../services/soc/mockData'
import { SocLoadingState, SocEmptyState } from '../../components/soc'
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
  AlertTriangle,
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
                <span key={tag} className="text-[10px] px-1.5 py-0.5 rounded bg-muted text-muted-foreground">
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
  const { data, loading, error: _error, source, refresh } = useSocResource(
    SOC_ENDPOINTS[SURFACE_IDS.KNOWLEDGE_VAULT],
    normalizeKnowledgeVault,
    MOCK_KNOWLEDGE_VAULT,
    SURFACE_ID,
  )

  // UI state
  const [searchQuery, setSearchQuery] = useState('')
  const [activeCategory, setActiveCategory] = useState<string | null>(null)
  const [articles] = useState<MockArticle[]>(MOCK_ARTICLES)

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

    return [...result].sort((a, b) => b.relevance - a.relevance)
  }, [articles, activeCategory, searchQuery])

  const hasActiveFilters = activeCategory !== null || searchQuery.trim() !== ''

  const clearFilters = () => {
    setActiveCategory(null)
    setSearchQuery('')
  }

  const isDemo = source === 'mock'

  // ── Loading ──
  if (loading) {
    return <SocLoadingState surfaceLabel={t('surfaces.knowledgeVault')} />
  }

  // ── Error ──
  // NOTE: no early return — useSocResource always provides mock data,
  // so we show data + error banner instead of a hard error block.

  // ── Empty (only when source is backend and data is empty) ──
  if (source === 'backend' && data.articles.length === 0 && articles.length === 0) {
    return <SocEmptyState surfaceId={SURFACE_ID} />
  }

  // ── Content ──
  return (
    <div className="space-y-4">
      {/* Error fallback banner when API failed */}
      {source === 'error' && (
        <div className="flex items-center justify-between px-4 py-2 rounded-lg bg-destructive/10 border border-destructive/20 text-destructive text-xs font-medium">
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-3.5 w-3.5" />
            <span>Failed to load data from server. Showing cached/demo data.</span>
          </div>
          <button onClick={refresh} className="underline hover:no-underline cursor-pointer">Retry</button>
        </div>
      )}

      {/* Header + demo badge */}
      <div className="flex items-center gap-2">
        <BookOpen className="h-5 w-5 text-chart-2" />
        <h2 className="text-lg font-semibold">{t('surfaces.knowledgeVault')}</h2>
        <span className="text-xs text-muted-foreground">
          ({articles.length} {t('knowledge.articles')})
        </span>
        {isDemo && (
          <div className="ml-auto flex items-center gap-2 px-3 py-1 rounded-lg bg-warning/10 border border-warning/20 text-warning text-xs font-medium">
            <AlertTriangle className="h-3.5 w-3.5" />
            {"Demo"}
          </div>
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
            <button onClick={clearFilters} className="mt-3 text-xs text-primary hover:underline cursor-pointer">
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

