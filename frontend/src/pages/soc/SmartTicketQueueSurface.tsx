/**
 * SmartTicketQueueSurface — ticket queue / list view.
 *
 * Features a filter bar (status, priority, search), a ticket table,
 * pagination, and row-click navigation to the TicketCopilot surface.
 */

import { useState, useEffect, useMemo } from 'react'
import { useSocShell } from '../../services/soc/SocShellProvider'
import { SURFACE_IDS } from '../../services/soc/contracts'

import { SOC_ENDPOINTS } from '../../services/soc/endpoints'
import { useSocResource } from '../../services/soc/useSocResource'
import { normalizeTicketQueue } from '../../services/soc/normalize/ticketQueue'
import type { TicketItemView } from '../../services/soc/normalize/ticketQueue'
import { MOCK_TICKET_QUEUE } from '../../services/soc/mockData'
import { SocLoadingState, SocEmptyState } from '../../components/soc'
import { applyNeutralCopy, t } from '../../content/socCopy'
import { cn } from '../../lib/utils'
import {
  Search,
  ChevronLeft,
  ChevronRight,
  ChevronsLeft,
  ChevronsRight,
  Ticket,
  CheckSquare,
  Square,
  Filter,
  X,
  AlertTriangle,
} from 'lucide-react'

// ─── Constants ───────────────────────────────────────────────────────────

const SURFACE_ID = SURFACE_IDS.SMART_TICKET_QUEUE
const PAGE_SIZE = 15

const STATUS_OPTIONS = ['open', 'in_progress', 'pending', 'resolved', 'closed'] as const
const PRIORITY_OPTIONS = ['critical', 'high', 'medium', 'low'] as const

// ─── Module-level selected ticket (shared with TicketCopilot) ────────────

let _selectedTicketId: string | null = null

export function getSelectedTicketId(): string | null {
  return _selectedTicketId
}

export function setSelectedTicketId(id: string | null): void {
  _selectedTicketId = id
}

// ─── Helpers ──────────────────────────────────────────────────────────────

function formatTimeAgo(iso: string): string {
  const date = new Date(iso)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  if (diffMins < 1) return t('time.justNow')
  if (diffMins < 60) return t('time.minAgo', { count: String(diffMins) })
  const diffHours = Math.floor(diffMins / 60)
  if (diffHours < 24) return t('time.hoursAgo', { count: String(diffHours) })
  const diffDays = Math.floor(diffHours / 24)
  return t('time.daysAgo', { count: String(diffDays) })
}

function statusBadgeClass(status: string): string {
  switch (status.toLowerCase()) {
    case 'open':
      return 'bg-chart-1/10 text-chart-1 border-chart-1/20'
    case 'in_progress':
    case 'in progress':
      return 'bg-warning/10 text-warning border-warning/20'
    case 'pending':
      return 'bg-chart-2/10 text-chart-2 border-chart-2/20'
    case 'resolved':
      return 'bg-success/10 text-success border-success/20'
    case 'closed':
      return 'bg-muted text-muted-foreground border-border/50'
    default:
      return 'bg-muted text-muted-foreground border-border/50'
  }
}

function priorityBadgeClass(priority: string): string {
  switch (priority.toLowerCase()) {
    case 'critical':
      return 'bg-destructive/10 text-destructive border-destructive/20'
    case 'high':
      return 'bg-warning/10 text-warning border-warning/20'
    case 'medium':
      return 'bg-chart-1/10 text-chart-1 border-chart-1/20'
    case 'low':
      return 'bg-muted text-muted-foreground border-border/50'
    default:
      return 'bg-muted text-muted-foreground border-border/50'
  }
}

function statusLabel(status: string): string {
  return t(`ticket.status.${status.toLowerCase().replace(/\s+/g, '_')}`)
}

function priorityLabel(priority: string): string {
  return t(`ticket.priority.${priority.toLowerCase()}`)
}

// ─── Sub-components ───────────────────────────────────────────────────────

function FilterChip({
  label,
  active,
  onClick,
}: {
  label: string
  active: boolean
  onClick: () => void
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        'px-3 py-1.5 text-xs font-medium rounded-lg border transition-colors cursor-pointer',
        active
          ? 'bg-primary text-primary-foreground border-primary'
          : 'bg-card text-muted-foreground border-border/50 hover:border-border hover:text-foreground',
      )}
    >
      {label}
    </button>
  )
}

// ─── Main surface ─────────────────────────────────────────────────────────

export default function SmartTicketQueueSurface() {
  const { navigate } = useSocShell()

  const { data: view, loading, error: _error, source, refresh } = useSocResource(
    SOC_ENDPOINTS[SURFACE_IDS.SMART_TICKET_QUEUE],
    normalizeTicketQueue,
    MOCK_TICKET_QUEUE,
    SURFACE_ID,
  )

  // Filters
  const [statusFilter, setStatusFilter] = useState<string | null>(null)
  const [priorityFilter, setPriorityFilter] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')

  // Pagination
  const [currentPage, setCurrentPage] = useState(1)
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())

  // ── Derived: filtered tickets ─────────────────────────────────────

  const filteredTickets = useMemo(() => {
    let tickets = view.tickets

    if (statusFilter) {
      tickets = tickets.filter(
        (t) => t.status.toLowerCase() === statusFilter.toLowerCase(),
      )
    }
    if (priorityFilter) {
      tickets = tickets.filter(
        (t) => t.priority.toLowerCase() === priorityFilter.toLowerCase(),
      )
    }
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase()
      tickets = tickets.filter(
        (t) =>
          t.id.toLowerCase().includes(q) ||
          t.subject.toLowerCase().includes(q) ||
          (t.assignee && t.assignee.toLowerCase().includes(q)),
      )
    }
    return tickets
  }, [view, statusFilter, priorityFilter, searchQuery])

  // ── Derived: paginated tickets ────────────────────────────────────

  const totalPages = Math.max(1, Math.ceil(filteredTickets.length / PAGE_SIZE))
  const safePage = Math.min(currentPage, totalPages)
  const paginatedTickets = useMemo(() => {
    const start = (safePage - 1) * PAGE_SIZE
    return filteredTickets.slice(start, start + PAGE_SIZE)
  }, [filteredTickets, safePage])

  // Reset page when filters change
  useEffect(() => {
    setCurrentPage(1)
  }, [statusFilter, priorityFilter, searchQuery])

  // ── Handlers ──────────────────────────────────────────────────────

  const handleRowClick = (ticket: TicketItemView) => {
    setSelectedTicketId(ticket.id)
    navigate(SURFACE_IDS.TICKET_COPILOT)
  }

  const handleSelectAll = () => {
    if (selectedIds.size === paginatedTickets.length) {
      setSelectedIds(new Set())
    } else {
      setSelectedIds(new Set(paginatedTickets.map((t) => t.id)))
    }
  }

  const handleSelectOne = (id: string) => {
    const next = new Set(selectedIds)
    if (next.has(id)) {
      next.delete(id)
    } else {
      next.add(id)
    }
    setSelectedIds(next)
  }

  const clearFilters = () => {
    setStatusFilter(null)
    setPriorityFilter(null)
    setSearchQuery('')
  }

  const hasActiveFilters = statusFilter !== null || priorityFilter !== null || searchQuery.trim() !== ''

  // ── Loading ───────────────────────────────────────────────────────

  if (loading) {
    return <SocLoadingState surfaceLabel={t('surfaces.smartTicketQueue')} />
  }

  // ── Error ─────────────────────────────────────────────────────────
  // NOTE: no early return — useSocResource always provides mock data,
  // so we show data + error banner instead of a hard error block.

  // ── Main content ──────────────────────────────────────────────────

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

      {/* Demo badge when source is mock */}
      {source === 'mock' && (
        <div className="flex items-center gap-2 px-4 py-2 rounded-lg bg-warning/10 border border-warning/20 text-warning text-xs font-medium">
          <AlertTriangle className="h-3.5 w-3.5" />
          {"Demo mode — data shown from local cache"}
        </div>
      )}

      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Ticket className="h-5 w-5 text-chart-1" />
          <h2 className="text-lg font-semibold">{t('surfaces.smartTicketQueue')}</h2>
          <span className="text-xs text-muted-foreground">
            ({view.total} {t('ticket.total')})
          </span>
        </div>
      </div>

      {/* Filter bar */}
      <div className="bg-card rounded-2xl border border-border/50 shadow-sm p-4 space-y-3">
        {/* Search + clear */}
        <div className="flex items-center gap-2">
          <div className="relative flex-1 max-w-xs">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder={t('ticket.searchPlaceholder')}
              className={cn(
                'w-full pl-9 pr-8 py-2 text-sm bg-muted/50 border border-border/50 rounded-lg',
                'placeholder:text-muted-foreground/60 focus:outline-none focus:ring-1 focus:ring-ring',
              )}
            />
            {searchQuery && (
              <button
                onClick={() => setSearchQuery('')}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground cursor-pointer"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            )}
          </div>

          {hasActiveFilters && (
            <button
              onClick={clearFilters}
              className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
            >
              <Filter className="h-3 w-3" />
              {t('ticket.clearFilters')}
            </button>
          )}
        </div>

        {/* Status filters */}
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider mr-1">
            {t('ticket.statusLabel')}:
          </span>
          {STATUS_OPTIONS.map((s) => (
            <FilterChip
              key={s}
              label={statusLabel(s)}
              active={statusFilter === s}
              onClick={() => setStatusFilter(statusFilter === s ? null : s)}
            />
          ))}
        </div>

        {/* Priority filters */}
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider mr-1">
            {t('ticket.priorityLabel')}:
          </span>
          {PRIORITY_OPTIONS.map((p) => (
            <FilterChip
              key={p}
              label={priorityLabel(p)}
              active={priorityFilter === p}
              onClick={() => setPriorityFilter(priorityFilter === p ? null : p)}
            />
          ))}
        </div>
      </div>

      {/* Ticket table */}
      {filteredTickets.length === 0 ? (
        hasActiveFilters ? (
          <div className="flex flex-col items-center justify-center py-16 text-muted-foreground bg-card rounded-2xl border border-border/50 shadow-sm">
            <Filter className="h-10 w-10 mb-3 text-muted-foreground/40" />
            <p className="text-sm">{t('empty.commandCenter.noFilterResults')}</p>
            <button
              onClick={clearFilters}
              className="mt-3 text-xs text-primary hover:underline cursor-pointer"
            >
              {t('ticket.clearFilters')}
            </button>
          </div>
        ) : (
          <SocEmptyState surfaceId={SURFACE_ID} />
        )
      ) : (
        <>
          {/* Table wrapper */}
          <div className="bg-card rounded-2xl border border-border/50 shadow-sm overflow-hidden">
            {/* Column headers */}
            <div className="hidden md:flex items-center gap-3 px-4 py-3 text-[10px] font-medium text-muted-foreground uppercase tracking-wider border-b border-border/20 bg-muted/30">
              <button onClick={handleSelectAll} className="shrink-0 cursor-pointer">
                {selectedIds.size === paginatedTickets.length ? (
                  <CheckSquare className="h-3.5 w-3.5 text-primary" />
                ) : (
                  <Square className="h-3.5 w-3.5" />
                )}
              </button>
              <span className="w-20 shrink-0">{t('ticket.id')}</span>
              <span className="flex-1">{t('ticket.subject')}</span>
              <span className="w-24 shrink-0 text-center">{t('ticket.status')}</span>
              <span className="w-24 shrink-0 text-center">{t('ticket.priority')}</span>
              <span className="w-28 shrink-0">{t('ticket.assignee')}</span>
              <span className="w-28 shrink-0 text-right">{t('ticket.updated')}</span>
            </div>

            {/* Rows */}
            <div className="divide-y divide-border/30">
              {paginatedTickets.map((ticket) => (
                <div
                  key={ticket.id}
                  onClick={() => handleRowClick(ticket)}
                  className={cn(
                    'flex flex-col md:flex-row items-start md:items-center gap-2 md:gap-3 px-4 py-3',
                    'hover:bg-muted/50 transition-colors cursor-pointer',
                    selectedIds.has(ticket.id) && 'bg-chart-1/5',
                  )}
                >
                  <button
                    onClick={(e) => { e.stopPropagation(); handleSelectOne(ticket.id) }}
                    className="shrink-0 hidden md:block cursor-pointer"
                  >
                    {selectedIds.has(ticket.id) ? (
                      <CheckSquare className="h-3.5 w-3.5 text-primary" />
                    ) : (
                      <Square className="h-3.5 w-3.5 text-muted-foreground" />
                    )}
                  </button>

                  <div className="flex md:hidden items-center gap-2 w-full">
                    <span className="font-mono text-xs font-medium text-foreground">{ticket.id}</span>
                    <span className={cn('text-[10px] font-medium px-1.5 py-0.5 rounded border', statusBadgeClass(ticket.status))}>
                      {statusLabel(ticket.status)}
                    </span>
                    <span className={cn('text-[10px] font-medium px-1.5 py-0.5 rounded border', priorityBadgeClass(ticket.priority))}>
                      {priorityLabel(ticket.priority)}
                    </span>
                  </div>

                  <span className="flex-1 text-sm text-foreground truncate md:ml-0">
                    {applyNeutralCopy(ticket.subject)}
                  </span>

                  <span className={cn(
                    'hidden md:inline-flex text-[10px] font-medium px-2 py-0.5 rounded border w-24 shrink-0 text-center justify-center',
                    statusBadgeClass(ticket.status),
                  )}>
                    {statusLabel(ticket.status)}
                  </span>
                  <span className={cn(
                    'hidden md:inline-flex text-[10px] font-medium px-2 py-0.5 rounded border w-24 shrink-0 text-center justify-center',
                    priorityBadgeClass(ticket.priority),
                  )}>
                    {priorityLabel(ticket.priority)}
                  </span>

                  <span className="hidden md:block text-xs text-muted-foreground w-28 shrink-0 truncate">
                    {ticket.assignee ?? '—'}
                  </span>

                  <span className="hidden md:block text-xs text-muted-foreground w-28 shrink-0 text-right">
                    {formatTimeAgo(ticket.updatedAt)}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Pagination */}
          <div className="flex items-center justify-between bg-card rounded-2xl border border-border/50 shadow-sm px-4 py-3">
            <span className="text-xs text-muted-foreground">
              {t('ticket.showingOf', {
                from: String((safePage - 1) * PAGE_SIZE + 1),
                to: String(Math.min(safePage * PAGE_SIZE, filteredTickets.length)),
                total: String(filteredTickets.length),
              })}
            </span>

            <div className="flex items-center gap-1">
              <button onClick={() => setCurrentPage(1)} disabled={safePage === 1}
                className="p-1.5 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted transition-colors disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer">
                <ChevronsLeft className="h-3.5 w-3.5" />
              </button>
              <button onClick={() => setCurrentPage((p) => Math.max(1, p - 1))} disabled={safePage === 1}
                className="p-1.5 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted transition-colors disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer">
                <ChevronLeft className="h-3.5 w-3.5" />
              </button>

              <div className="flex items-center gap-1 mx-1">
                {Array.from({ length: Math.min(totalPages, 7) }, (_, i) => {
                  let pageNum: number
                  if (totalPages <= 7) {
                    pageNum = i + 1
                  } else if (safePage <= 4) {
                    pageNum = i + 1
                  } else if (safePage >= totalPages - 3) {
                    pageNum = totalPages - 6 + i
                  } else {
                    pageNum = safePage - 3 + i
                  }
                  return (
                    <button key={pageNum} onClick={() => setCurrentPage(pageNum)}
                      className={cn(
                        'min-w-[28px] h-7 text-xs font-medium rounded-lg transition-colors cursor-pointer',
                        pageNum === safePage
                          ? 'bg-primary text-primary-foreground'
                          : 'text-muted-foreground hover:text-foreground hover:bg-muted',
                      )}>
                      {pageNum}
                    </button>
                  )
                })}
              </div>

              <button onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))} disabled={safePage === totalPages}
                className="p-1.5 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted transition-colors disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer">
                <ChevronRight className="h-3.5 w-3.5" />
              </button>
              <button onClick={() => setCurrentPage(totalPages)} disabled={safePage === totalPages}
                className="p-1.5 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted transition-colors disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer">
                <ChevronsRight className="h-3.5 w-3.5" />
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  )
}

