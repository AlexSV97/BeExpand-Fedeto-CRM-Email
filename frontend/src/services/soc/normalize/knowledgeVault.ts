/**
 * normalizeKnowledgeVault — transforms raw API payload into KnowledgeVaultView.
 */

// ── View model ──

interface KnowledgeVaultView {
  articles: KnowledgeArticleView[]
  categories: string[]
  searchSuggestions: string[]
}

interface KnowledgeArticleView {
  id: string
  title: string
  excerpt: string
  category: string
  tags: string[]
  updatedAt: string
}

// ── Normalizer ──

function normalizeKnowledgeVault(raw: Record<string, unknown>): KnowledgeVaultView {
  return {
    articles: (raw.articles as KnowledgeArticleView[]) ?? [],
    categories: (raw.categories as string[]) ?? [],
    searchSuggestions: (raw.searchSuggestions as string[]) ?? [],
  }
}

export { normalizeKnowledgeVault }
export type { KnowledgeVaultView, KnowledgeArticleView }
