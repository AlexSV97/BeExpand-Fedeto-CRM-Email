import { AlertCircle } from 'lucide-react'
import type { SocError } from '../../services/soc/contracts'
import { t } from '../../content/socCopy'

interface SocErrorStateProps {
  error: SocError
}

export default function SocErrorState({ error }: SocErrorStateProps) {
  return (
    <div className="flex flex-col items-center justify-center gap-4 py-16 text-muted-foreground">
      <AlertCircle className="h-12 w-12 text-destructive" />
      <div className="flex flex-col items-center gap-1">
        <p className="text-sm font-medium text-foreground">
          {t(`error.${error.code}`)}
        </p>
        <p className="text-xs text-muted-foreground">{error.message}</p>
      </div>
      {error.retry && (
        <button
          onClick={error.retry}
          className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 cursor-pointer"
        >
          {t('error.retry')}
        </button>
      )}
    </div>
  )
}
