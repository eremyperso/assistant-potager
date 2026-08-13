const M_INI = ['J', 'F', 'M', 'A', 'M', 'J', 'J', 'A', 'S', 'O', 'N', 'D']

const LEGEND = [
  ['bg-blue', 'Semis'],
  ['bg-brand', 'Plantation'],
  ['bg-amber', 'Récolte'],
]

/**
 * Calendrier cultural sur 12 mois du design system [US-052].
 * Les index de mois sont 0-based (0 = janvier), comme `Date.getMonth()`.
 * Le mois en cours est entouré pour repérer d'un coup d'œil ce qui est à faire.
 */
export function MonthStrip({ semis = [], plant = [], rec = [], legend = false, className = '' }) {
  const moisCourant = new Date().getMonth()

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
            className={`h-[9px] rounded-[3px] ${couleur(i)} ${i === moisCourant ? 'outline outline-[1.5px] outline-offset-[1.5px] outline-txt' : ''}`}
          />
        ))}
      </div>
      <div className="grid grid-cols-12 gap-[2.5px] mt-1">
        {M_INI.map((m, i) => (
          <div
            key={i}
            className={`text-center text-[9px] ${i === moisCourant ? 'font-bold text-txt' : 'font-medium text-txt3'}`}
          >
            {m}
          </div>
        ))}
      </div>
      {legend && (
        <div className="flex flex-wrap gap-3 mt-2">
          {LEGEND.map(([bg, l]) => (
            <span key={l} className="flex items-center gap-1.5 text-[11px] text-txt2">
              <span className={`w-2 h-2 rounded-sm ${bg}`} />
              {l}
            </span>
          ))}
        </div>
      )}
    </div>
  )
}

export default MonthStrip
