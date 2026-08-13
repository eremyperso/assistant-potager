const M_INI = ['J', 'F', 'M', 'A', 'M', 'J', 'J', 'A', 'S', 'O', 'N', 'D']

const LEGEND = [
  ['bg-blue', 'Semis'],
  ['bg-brand', 'Plantation'],
  ['bg-amber', 'Récolte'],
]

/**
 * Légende des trois phases du calendrier [US-060] — extraite de `MonthStrip`
 * pour pouvoir vivre ailleurs que sous une frise : l'écran Plan la place dans
 * l'en-tête de sa carte « Cultures en place », où elle vaut pour toutes les
 * tuiles à la fois (CA6). Les couleurs restent définies une seule fois.
 */
export function MonthStripLegend({ className = '' }) {
  return (
    <div className={`flex flex-wrap gap-3 ${className}`}>
      {LEGEND.map(([bg, l]) => (
        <span key={l} className="flex items-center gap-1.5 text-[11.5px] text-txt2">
          <span className={`w-2 h-2 rounded-sm ${bg}`} />
          {l}
        </span>
      ))}
    </div>
  )
}

/**
 * Calendrier cultural sur 12 mois du design system [US-052].
 * Les index de mois sont 0-based (0 = janvier), comme `Date.getMonth()`.
 * Le mois en cours est entouré pour repérer d'un coup d'œil ce qui est à faire.
 *
 * `moisCourant` [US-060 / CA10] : mois à mettre en évidence, quand l'écran hôte
 * raisonne sur une **date de référence** (US-030/031) et non sur l'horloge du
 * navigateur — sans quoi l'écran serait dans le passé et la frise dans le
 * présent. Non fourni, la frise retombe sur le mois courant réel : les autres
 * écrans qui l'utilisent ne changent pas de comportement.
 */
export function MonthStrip({ semis = [], plant = [], rec = [], legend = false, moisCourant, className = '' }) {
  const mois = moisCourant ?? new Date().getMonth()

  const couleur = (i) => {
    if (rec.includes(i)) return 'bg-amber'
    if (plant.includes(i)) return 'bg-brand'
    if (semis.includes(i)) return 'bg-blue'
    return 'bg-card-alt'
  }

  return (
    <div className={className}>
      <div className="grid grid-cols-12 gap-[2.5px]">
        {M_INI.map((_, i) => (
          <div
            key={i}
            className={`h-[9px] rounded-[3px] ${couleur(i)} ${i === mois ? 'outline outline-[1.5px] outline-offset-[1.5px] outline-txt' : ''}`}
          />
        ))}
      </div>
      <div className="grid grid-cols-12 gap-[2.5px] mt-1">
        {M_INI.map((m, i) => (
          <div
            key={i}
            className={`text-center text-[9px] ${i === mois ? 'font-bold text-txt' : 'font-medium text-txt3'}`}
          >
            {m}
          </div>
        ))}
      </div>
      {legend && <MonthStripLegend className="mt-2" />}
    </div>
  )
}

export default MonthStrip
