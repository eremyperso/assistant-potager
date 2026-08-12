/**
 * Carte de contenu générique du design system [US-052].
 *
 * `@container/card` : l'agencement interne s'adapte à la largeur de la carte
 * elle-même, pas à celle de l'écran — la même carte peut donc vivre en pleine
 * largeur ou dans une grille à 3 colonnes sans variante dédiée.
 *
 * `bg` : token de fond, `bg-card` par défaut. Passer `bg-surface` pour une carte
 * imbriquée dans une autre carte, qui doit s'en détacher [US-059]. Prop dédiée
 * plutôt que surcharge via `className` : deux utilitaires de même propriété se
 * départagent sur l'ordre du CSS généré, pas sur l'ordre de la chaîne de classes.
 */
export function Card({ children, className = '', pad = 'p-4', bg = 'bg-card', ...props }) {
  return (
    <div
      className={`@container/card ${bg} border border-border rounded-2xl shadow-card ${pad} ${className}`}
      {...props}
    >
      {children}
    </div>
  )
}

/**
 * En-tête de carte : pastille d'icône, titre, sous-titre et zone d'actions.
 * Passe en pile sous 24rem de largeur de carte, en ligne au-delà.
 */
export function CardHead({ icon: Icon, tint = 'brand', title, sub, right, className = '' }) {
  const tints = {
    brand: 'bg-brand-soft text-brand',
    amber: 'bg-amber-soft text-amber',
    red: 'bg-red-soft text-red',
    blue: 'bg-blue-soft text-blue',
    violet: 'bg-violet-soft text-violet',
  }
  return (
    <div className={`flex flex-wrap items-center gap-3 mb-3.5 ${className}`}>
      {Icon && (
        <div className={`w-10 h-10 rounded-xl flex items-center justify-center shrink-0 ${tints[tint]}`}>
          <Icon size={20} />
        </div>
      )}
      <div className="flex-1 min-w-0 basis-[150px]">
        <div className="font-serif font-semibold text-[17px] text-txt tracking-tight truncate">{title}</div>
        {sub && <div className="text-[12.5px] text-txt3 mt-px truncate">{sub}</div>}
      </div>
      {/* Mobile-first : la zone d'actions passe à la ligne dans une carte étroite,
          et revient en ligne dès 24rem de large (variantes `min-width` uniquement,
          cf. commentaire dans InfoBanner). */}
      {right && (
        <div className="flex items-center gap-2 basis-full @[24rem]/card:basis-auto">{right}</div>
      )}
    </div>
  )
}

export default Card
