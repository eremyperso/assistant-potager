import { entier, jourCourt } from '../lib/format.js'
import { descriptionCellule } from '../lib/fiabilite.js'

const HEURES = Array.from({ length: 24 }, (_, h) => h)

/** L'intensité d'une cellule : la teinte « quota » de la maquette (--serie-2, ambre), de 18 % à 100 %. */
const fond = (n, maximum) => (n === 0 ? undefined : { background: `color-mix(in srgb, var(--serie-2) ${Math.round(18 + (82 * n) / maximum)}%, transparent)` })

/**
 * La grille heure × jour des appels en quota [US-314 / CA5] : une ligne par jour, une colonne par heure.
 * L'intensité ne porte jamais seule le chiffre : chaque cellule a son texte pour lecteur d'écran et son
 * infobulle, le nombre s'écrit dans la cellule quand la carte a la place, et le total du jour est
 * toujours écrit en bout de ligne.
 */
export default function GrilleChaleur({ jours, cellules, titre }) {
  const maximum = Math.max(1, ...cellules.flat())
  return (
    <div className="@container">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[320px] border-separate border-spacing-[2px] text-[10.5px] tabular-nums" aria-label={titre}>
          <thead>
            <tr>
              <td />
              {HEURES.map((h) => (
                <th key={h} scope="col" className="p-0 text-center font-semibold text-txt2">
                  <span aria-hidden="true" className={h % 6 === 0 ? '' : 'invisible'}>{h}</span>
                  <span className="sr-only">{h} h</span>
                </th>
              ))}
              <th scope="col" className="pl-1.5 text-right font-bold text-txt2">Total</th>
            </tr>
          </thead>
          <tbody>
            {jours.map((jour, j) => {
              const total = cellules[j].reduce((a, b) => a + b, 0)
              return (
                <tr key={jour}>
                  <th scope="row" className="whitespace-nowrap pr-1.5 text-left font-semibold text-txt2">{jourCourt(jour)}</th>
                  {HEURES.map((h) => {
                    const n = cellules[j][h]
                    return (
                      <td key={h} title={descriptionCellule(jour, h, n)} aria-label={descriptionCellule(jour, h, n)}
                        className={`h-[22px] rounded-[4px] p-0 text-center text-[10px] font-bold text-txt ${n === 0 ? 'bg-card-alt' : ''}`} style={fond(n, maximum)}>
                        {n > 0 ? <span className="hidden @lg:inline">{n}</span> : null}
                      </td>
                    )
                  })}
                  <td className="pl-1.5 text-right font-bold text-txt">{entier(total)}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
