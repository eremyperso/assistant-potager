/**
 * Tuiles de sous-navigation du design system [US-052].
 * Défilement horizontal quand les tuiles dépassent la largeur disponible.
 * Consommé par le PageHeader de la coquille applicative (US-053).
 */
export function TileNav({ items = [], active, onPick, className = '' }) {
  return (
    <div className={`flex gap-2.5 overflow-x-auto pb-0.5 ${className}`} role="tablist">
      {items.map((it) => {
        const on = it.id === active
        const Icon = it.icon
        return (
          <button
            key={it.id}
            role="tab"
            aria-selected={on}
            onClick={() => onPick?.(it.id)}
            title={it.help}
            className={`relative flex flex-col items-center justify-center gap-1.5 w-[84px] h-[72px] rounded-[13px] shrink-0 border transition-colors ${
              on ? 'bg-brand-soft border-brand text-brand-text' : 'bg-card border-border text-txt2'
            }`}
          >
            {Icon && <Icon size={20} className={on ? 'text-brand' : 'text-txt3'} />}
            <span className={`text-[11.5px] text-center leading-tight ${on ? 'font-bold' : 'font-medium'}`}>
              {it.label}
            </span>
            {it.badge > 0 && (
              <span className="absolute -top-1.5 -right-1.5 min-w-[19px] h-[19px] px-1.5 rounded-full bg-brand text-white dark:text-bg text-[11px] font-bold flex items-center justify-center">
                {it.badge}
              </span>
            )}
          </button>
        )
      })}
    </div>
  )
}

export default TileNav
