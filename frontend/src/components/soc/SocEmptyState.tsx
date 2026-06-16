import { Inbox } from 'lucide-react'
import type { SurfaceId } from '../../services/soc/contracts'
import { t } from '../../content/socCopy'

interface SocEmptyStateProps {
  surfaceId: SurfaceId
  ctaLabel?: string
  onCtaClick?: () => void
}

export default function SocEmptyState({ surfaceId, ctaLabel, onCtaClick }: SocEmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center gap-4 py-16 text-muted-foreground">
      <Inbox className="h-12 w-12 text-muted-foreground/40" />
      <p className="text-sm">{t(`empty.${surfaceId}`)}</p>
      {ctaLabel && onCtaClick && (
        <button
          onClick={onCtaClick}
          className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 cursor-pointer"
        >
          {ctaLabel}
        </button>
      )}
    </div>
  )
}
