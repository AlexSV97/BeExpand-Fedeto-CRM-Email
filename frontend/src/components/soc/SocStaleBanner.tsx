import { RefreshCw } from 'lucide-react'
import { t } from '../../content/socCopy'

interface SocStaleBannerProps {
  lastUpdateMinAgo: number
  onRefresh: () => void
}

export default function SocStaleBanner({ lastUpdateMinAgo, onRefresh }: SocStaleBannerProps) {
  return (
    <div className="flex items-center justify-center gap-3 border border-dashed border-warning/30 bg-warning/5 px-4 py-2 text-xs text-muted-foreground rounded-lg">
      <span>
        {t('stale.lastUpdated', { minutes: String(lastUpdateMinAgo) })}
      </span>
      <button
        onClick={onRefresh}
        className="inline-flex items-center gap-1 text-xs font-medium text-foreground transition-colors hover:text-primary cursor-pointer"
      >
        <RefreshCw className="h-3 w-3" />
        {t('stale.refresh')}
      </button>
    </div>
  )
}
