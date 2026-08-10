/**
 * Jauge de progression du design system [US-052].
 * Sans `tint` explicite, la couleur suit le taux de remplissage
 * (vert < 55 %, ambre < 80 %, rouge au-delà) — sémantique d'occupation.
 */
// Classes écrites en toutes lettres : Tailwind ne génère rien pour une classe
// construite dynamiquement (`bg-${tint}`).
const TEINTES = {
  brand: 'bg-brand',
  amber: 'bg-amber',
  red: 'bg-red',
  blue: 'bg-blue',
  violet: 'bg-violet',
}

export function ProgressBar({ pct, tint, className = '', label }) {
  const value = Math.max(0, Math.min(100, pct ?? 0))
  const auto = value >= 80 ? 'bg-red' : value >= 55 ? 'bg-amber' : 'bg-brand'
  const fill = TEINTES[tint] || auto
  return (
    <div
      className={`h-1.5 bg-card-alt rounded overflow-hidden ${className}`}
      role="progressbar"
      aria-valuenow={value}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-label={label}
    >
      <div className={`h-full rounded transition-[width] duration-300 ${fill}`} style={{ width: `${value}%` }} />
    </div>
  )
}

export default ProgressBar
