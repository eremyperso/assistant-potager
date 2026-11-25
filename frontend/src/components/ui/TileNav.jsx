/**
 * Tuiles de sous-navigation du design system [US-052].
 * Défilement horizontal quand les tuiles dépassent la largeur disponible.
 * Consommé par le PageHeader de la coquille applicative (US-053).
 *
 * [US-353 / CA5] Ordinateur : tuiles de 84 × 64 ; mobile : pastilles compactes de 36 px (structure de
 * page, donc le breakpoint `nav:` de la coquille). `compact` : l'en-tête resserré masque les tuiles
 * sur ordinateur, les pastilles de mobile restent.
 */
export function TileNav({ items = [], active, onPick, compact = false, className = '' }) {
  return (
    <div className={`flex gap-1.5 nav:gap-2 overflow-x-auto pb-0.5 ${compact ? 'nav:hidden' : ''} ${className}`} role="tablist">
      {items.map((it) => {
        const on = it.id === active
        const Icon = it.icon
        return (
          <button
            key={it.id}
            role="tab"
            aria-selected={on}
            // [US-223 / CA2] Un onglet désactivé reste dans la barre mais ne se
            // focalise pas, s'annonce « indisponible » et n'ouvre rien.
            disabled={it.disabled}
            aria-disabled={it.disabled || undefined}
            onClick={() => { if (!it.disabled) onPick?.(it.id) }}
            title={it.help}
            className={`relative flex shrink-0 items-center justify-center border transition-colors h-9 gap-1.5 rounded-full px-[13px] nav:h-16 nav:w-[84px] nav:flex-col nav:gap-[5px] nav:rounded-[13px] nav:px-0 ${
              on ? 'bg-brand-soft border-brand text-brand-text' : 'bg-card border-border text-txt2'
            } ${it.disabled ? 'opacity-55 cursor-not-allowed' : ''}`}
          >
            {Icon && <Icon size={17} className={`nav:h-[19px] nav:w-[19px] ${on ? 'text-brand' : 'text-txt3'}`} />}
            <span className={`whitespace-nowrap text-[12.5px] leading-tight nav:whitespace-normal nav:text-center nav:text-[11.5px] nav:leading-[1.15] ${on ? 'font-bold' : 'font-medium'}`}>
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
