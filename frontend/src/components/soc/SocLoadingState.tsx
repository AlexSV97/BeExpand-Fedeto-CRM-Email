import { Loader2 } from 'lucide-react'
import { t } from '../../content/socCopy'

interface SocLoadingStateProps {
  surfaceLabel?: string
}

export default function SocLoadingState({ surfaceLabel }: SocLoadingStateProps) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-16 text-muted-foreground">
      <Loader2 className="h-8 w-8 animate-spin text-primary" />
      <p className="text-sm">
        {surfaceLabel
          ? t('loading.surface', { surface: surfaceLabel })
          : t('loading')}
      </p>
    </div>
  )
}
