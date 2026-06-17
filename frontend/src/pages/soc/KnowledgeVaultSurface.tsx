/**
 * KnowledgeVaultSurface — professional search-driven knowledge base UI.
 *
 * Features a prominent search bar, category filter chips, search
 * suggestions, and a two-column results grid of article cards with
 * staggered framer-motion entrance animations, relative timestamps,
 * tags, and per-category badge coloring.
 */

import { useState, useMemo } from 'react'
import { motion } from 'framer-motion'
import { SURFACE_IDS } from '../../services/soc/contracts'

import { SOC_ENDPOINTS } from '../../services/soc/endpoints'
import { useSocResource } from '../../services/soc/useSocResource'
import { normalizeKnowledgeVault } from '../../services/soc/normalize/knowledgeVault'
import { MOCK_KNOWLEDGE_VAULT, MOCK_ARTICLES } from '../../services/soc/mockData'
import type { MockArticle } from '../../services/soc/mockData'
import { applyNeutralCopy, t } from '../../content/socCopy'
import { cn } from '../../lib/utils'
import {
  Search,
  BookOpen,
  X,
  Filter,
  AlertTriangle,
  RefreshCw,
  FileSearch,
} from 'lucide-react'

// ─── Constants ───────────────────────────────────────────────────────────

const SURFACE_ID = SURFACE_IDS.KNOWLEDGE_VAULT

const CATEGORIES = ['All', 'Cases', 'Runbooks', 'FAQs', 'Security', 'Operations'] as const

// ─── Helpers ──────────────────────────────────────────────────────────────

function timeAgo(iso: string): string {
  const now = Date.now()
  const then = new Date(iso).getTime()
  const diffSec = Math.floor((now - then) / 1000)

  if (diffSec < 60) return 'just now'
  const diffMin = Math.floor(diffSec / 60)
  if (diffMin < 60) return `${diffMin} min ago`
  const diffHr = Math.floor(diffMin / 60)
  if (diffHr < 24) return `${diffHr} hour${diffHr > 1 ? 's' : ''} ago`
  const diffDays = Math.floor(diffHr / 24)
  if (diffDays < 30) return `${diffDays} day${diffDays > 1 ? 's' : ''} ago`

  return new Date(iso).toLocaleDateString('en-US', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  })
}

const CATEGORY_BADGE_COLORS: Record<string, string> = {
  Cases:      'bg-chart-1/10 text-chart-1 border-chart-1/20',
  Runbooks:   'bg-chart-2/10 text-chart-2 border-chart-2/20',
  FAQs:       'bg-warning/10 text-warning border-warning/20',
  Security:   'bg-destructive/10 text-destructive border-destructive/20',
  Operations: 'bg-chart-3/10 text-chart-3 border-chart-3/20',
}

function categoryBadgeColor(category: string): string {
  return CATEGORY_BADGE_COLORS[category] ?? 'bg-muted text-muted-foreground border-border/50'
}

// ─── Sub-components ───────────────────────────────────────────────────────

function SkeletonCard() {
  return (
    <div className="bg-card rounded-2xl border border-border/50 shadow-sm p-5 animate-pulse">
      <div className="h-5 w-3/4 bg-muted rounded mb-1" />
      <div className="flex items-center gap-2 mb-3">
        <div className="h-4 w-16 bg-muted rounded" />
        <div className="h-3 w-10 bg-muted rounded" />
      </div>
      <div className="space-y-1.5 mb-3">
        <div className="h-3 w-full bg-muted rounded" />
        <div className="h-3 w-2/3 bg-muted rounded" />
      </div>
      <div className="flex gap-1.5">
        <div className="h-4 w-12 bg-muted rounded" />
        <div className="h-4 w-14 bg-muted rounded" />
        <div className="h-4 w-10 bg-muted rounded" />
      </div>
    </div>
  )
}

const cardVariants = {
  hidden: { opacity: 0, y: 20 },
  visible: (i: number) => ({
    opacity: 1,
    y: 0,
    transition: { duration: 0.3, delay: i * 0.05 },
  }),
}

function ArticleCard({ article, index }: { article: MockArticle; index: number }) {
  return (
    <motion.div
      custom={index}
      variants={cardVariants}
      initial="hidden"
      animate="visible"
    >
      <div className="bg-card rounded-2xl border border-border/50 shadow-sm p-5 hover:shadow-md hover:-translate-y-0.5 hover:border-primary/30 transition-all duration-300 h-full">
        <h4 className="text-base font-bold text-foreground leading-snug mb-2">
          {applyNeutralCopy(article.title)}
        </h4>

        <div className="flex items-center gap-2 mb-3">
          <span className={cn('text-[10px] font-medium px-2 py-0.5 rounded border', categoryBadgeColor(article.category))}>
            {article.category}
          </span>
          <span className="text-[10px] text-muted-foreground">
            • {timeAgo(article.updatedAt)}
          </span>
        </div>

        <p className="text-xs text-muted-foreground leading-relaxed line-clamp-2 mb-3">
          {applyNeutralCopy(article.excerpt)}
        </p>

        {article.tags.length > 0 && (
          <div className="flex flex-wrap gap-1">
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
    </motion.div>
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
  const [lastUpdated] = useState<Date>(new Date())

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

    return result
  }, [articles, activeCategory, searchQuery])

  const hasActiveFilters = activeCategory !== null || searchQuery.trim() !== ''

  const clearFilters = () => {
    setActiveCategory(null)
    setSearchQuery('')
  }

  const handleRefresh = () => {
    refresh()
  }

  const handleSuggestionClick = (suggestion: string) => {
    setSearchQuery(suggestion)
  }

  const isDemo = source === 'mock'

  // ── Loading: 6 skeleton cards (2 columns × 3 rows) ──
  if (loading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {Array.from({ length: 6 }).map((_, i) => (
          <SkeletonCard key={i} />
        ))}
      </div>
    )
  }

  // ── Error ──
  // NOTE: no early return — useSocResource always provides mock data,
  // so we show data + error banner instead of a hard error block.

  // ── Empty (only when source is backend and data is empty) ──
  if (source === 'backend' && data.articles.length === 0 && articles.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center gap-4 py-16 text-muted-foreground">
        <FileSearch className="h-12 w-12 text-muted-foreground/40" />
        <p className="text-sm">{t(`empty.${SURFACE_ID}`)}</p>
      </div>
    )
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
          <button onClick={handleRefresh} className="underline hover:no-underline cursor-pointer">Retry</button>
        </div>
      )}

      {/* ── Header ─────────────────────────────────────────────── */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <BookOpen className="h-5 w-5 text-chart-2" />
          <h2 className="text-lg font-semibold">Knowledge Vault</h2>
          <span className="inline-flex items-center justify-center min-w-[1.25rem] h-5 px-1.5 rounded-full bg-chart-1/10 text-chart-1 text-[10px] font-semibold leading-none">
            {articles.length}
          </span>
        </div>

        <div className="flex items-center gap-3">
          {isDemo && (
            <span className="text-[10px] font-medium px-2 py-0.5 rounded bg-warning/10 text-warning border border-warning/20">
              Demo
            </span>
          )}
          <button
            onClick={handleRefresh}
            className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            Refresh
          </button>
          <span className="text-[10px] text-muted-foreground">
            Updated {timeAgo(lastUpdated.toISOString())}
          </span>
        </div>
      </div>

      {/* ── Search bar — prominent ─────────────────────────────── */}
      <div className="relative">
        <Search className="absolute left-4 top-1/2 -translate-y-1/2 h-5 w-5 text-muted-foreground" />
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Search knowledge base..."
          className="w-full pl-12 pr-10 py-3 text-base bg-card border border-border/50 rounded-xl placeholder:text-muted-foreground/60 focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary"
        />
        {searchQuery && (
          <button
            onClick={() => setSearchQuery('')}
            className="absolute right-4 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>

      {/* ── Search suggestions ──────────────────────────────────── */}
      {searchQuery.trim() && data.searchSuggestions.length > 0 && (
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-xs text-muted-foreground font-medium">Suggestions:</span>
          {data.searchSuggestions.map((suggestion) => (
            <button
              key={suggestion}
              onClick={() => handleSuggestionClick(suggestion)}
              className="text-xs px-2.5 py-1 rounded-full bg-muted text-muted-foreground hover:text-foreground hover:bg-accent transition-colors cursor-pointer"
            >
              &ldquo;{suggestion}&rdquo;
            </button>
          ))}
        </div>
      )}

      {/* ── Category filter chips ──────────────────────────────── */}
      <div className="flex flex-wrap items-center gap-2">
        {CATEGORIES.map((category) => (
          <button
            key={category}
            onClick={() => setActiveCategory(category === 'All' ? null : category)}
            className={cn(
              'px-3 py-1.5 text-xs font-medium rounded-lg border transition-colors cursor-pointer',
              (category === 'All' && activeCategory === null) || activeCategory === category
                ? 'bg-primary text-primary-foreground border-primary'
                : 'bg-card text-muted-foreground border-border/50 hover:border-border hover:text-foreground',
            )}
          >
            {category}
          </button>
        ))}
        {hasActiveFilters && (
          <button
            onClick={clearFilters}
            className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors ml-2 cursor-pointer"
          >
            <Filter className="h-3 w-3" />
            Clear filters
          </button>
        )}
      </div>

      {/* ── Results grid ────────────────────────────────────────── */}
      {filteredArticles.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 text-muted-foreground bg-card rounded-2xl border border-border/50 shadow-sm">
          <FileSearch className="h-10 w-10 mb-3 text-muted-foreground/40" />
          <p className="text-sm">
            {searchQuery.trim()
              ? `No articles found for "${searchQuery}"`
              : 'No articles found'}
          </p>
          <p className="text-xs text-muted-foreground/60 mt-1">
            Try different keywords or adjust your filters
          </p>
          {hasActiveFilters && (
            <button onClick={clearFilters} className="mt-3 text-xs text-primary hover:underline cursor-pointer">
              Clear filters
            </button>
          )}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {filteredArticles.map((article, idx) => (
            <ArticleCard key={article.id} article={article} index={idx} />
          ))}
        </div>
      )}

      {/* Results count footer */}
      {filteredArticles.length > 0 && (
        <p className="text-[10px] text-muted-foreground text-center pt-1">
          Showing {filteredArticles.length} of {articles.length} articles
        </p>
      )}
    </div>
  )
}
