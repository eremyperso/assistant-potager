// [US-059 CA1] Squelette de chargement — habillage de carte du design system,
// tokens sémantiques uniquement.
import { Card } from './ui'

export default function LoadingSkeleton({ lines = 3 }) {
  return (
    <div className="space-y-3 animate-pulse" aria-hidden="true">
      {Array.from({ length: lines }).map((_, i) => (
        <Card key={i} className="space-y-2">
          <div className="h-3 bg-border rounded w-2/5" />
          <div className="h-10 bg-border rounded" />
          <div className="h-3 bg-border rounded w-3/5" />
        </Card>
      ))}
    </div>
  )
}
