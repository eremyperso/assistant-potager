import { entier, pourcent } from '../lib/format.js'

/** Une barre de part (6 px), comme dans la maquette d'US-318. */
function BarrePart({ part, large = false }) {
  const pc = Math.max(0, Math.min(100, (part || 0) * 100))
  return (
    <i aria-hidden="true" className={`relative block h-1.5 overflow-hidden rounded-[3px] bg-card-alt ${large ? 'mt-1.5 w-full' : 'w-[52px]'}`}>
      <b className="absolute inset-y-0 left-0 rounded-[3px] bg-[color:var(--serie-1)]" style={{ width: `${pc}%` }} />
    </i>
  )
}

/**
 * Tableau de ventilation [US-312 / CA4, CA5] : appels, jetons d'entrée et de sortie, part du total,
 * jetons d'entrée médians par appel, ligne de total. Un tableau quand la carte a la place
 * (container query), une liste de cartes sinon : jamais de défilement horizontal à 360 px.
 */
export default function TableauVentilation({ titre, premiereColonne, lignes, vide = false }) {
  const entete = (
    <div className="mb-2.5">
      <h3 className="font-serif text-base font-semibold leading-tight text-txt">{titre}</h3>
      {vide ? null : <p className="mt-0.5 text-xs text-txt2">Jetons d'entrée, de sortie, part et médiane par appel</p>}
    </div>
  )
  if (vide || !lignes.length) {
    return (
      <section className="rounded-2xl border border-border bg-card p-3.5 shadow-card">
        {entete}
        <div className="flex flex-col items-center gap-1.5 px-3 py-[22px] text-center text-[13px] text-txt2">
          <b className="text-sm text-txt">Aucun appel sur la période</b>
          <span>Rien à ventiler.</span>
        </div>
      </section>
    )
  }
  const total = lignes.reduce((a, l) => ({ appels: a.appels + l.appels, entree: a.entree + l.jetonsEntree, sortie: a.sortie + l.jetonsSortie }),
    { appels: 0, entree: 0, sortie: 0 })
  const th = 'border-b border-border px-2 py-1.5 text-right text-[11.5px] font-bold text-txt2 whitespace-nowrap first:text-left'
  const td = 'border-b border-border-soft p-2 whitespace-nowrap'
  return (
    <section className="@container rounded-2xl border border-border bg-card p-3.5 shadow-card">
      {entete}

      <table className="hidden w-full border-collapse text-[13px] tabular-nums @lg:table">
        <thead>
          <tr>
            <th scope="col" className={th}>{premiereColonne}</th>
            <th scope="col" className={th}>Appels</th>
            <th scope="col" className={th}>Jetons d'entrée</th>
            <th scope="col" className={th}>Jetons de sortie</th>
            <th scope="col" className={th}>Part du total</th>
            <th scope="col" className={th}>Médiane par appel</th>
          </tr>
        </thead>
        <tbody>
          {lignes.map((l) => (
            <tr key={l.cle}>
              <td className={`${td} text-left`}><code className="font-mono text-[12.5px] text-txt">{l.libelle}</code></td>
              <td className={`${td} text-right`}>{l.texte.appels}</td>
              <td className={`${td} text-right`}>{l.texte.jetonsEntree}</td>
              <td className={`${td} text-right`}>{l.texte.jetonsSortie}</td>
              <td className={`${td} text-right`}><span className="inline-flex items-center justify-end gap-1.5">{l.texte.part}<BarrePart part={l.part} /></span></td>
              <td className={`${td} text-right`}>{l.texte.mediane}</td>
            </tr>
          ))}
          <tr className="font-bold">
            <td className="p-2 text-left">Total</td>
            <td className="p-2 text-right">{entier(total.appels)}</td>
            <td className="p-2 text-right">{entier(total.entree)}</td>
            <td className="p-2 text-right">{entier(total.sortie)}</td>
            <td className="p-2 text-right">{pourcent(1, 0)}</td>
            <td className="p-2" />
          </tr>
        </tbody>
      </table>

      <ul className="flex flex-col tabular-nums @lg:hidden">
        {lignes.map((l) => (
          <li key={l.cle} className="border-t border-border-soft px-0.5 py-2.5 first:border-t-0">
            <div className="flex items-baseline justify-between gap-2.5">
              <code className="break-all font-mono text-[13px] font-semibold text-txt">{l.court}</code>
              <b className="text-sm text-txt">{l.texte.abrege}</b>
            </div>
            <BarrePart part={l.part} large />
            <div className="mt-[3px] text-xs text-txt2">
              {l.texte.part} du total · médiane {l.texte.mediane} · {l.texte.appels} appels · {l.texte.jetonsSortie} en sortie
            </div>
          </li>
        ))}
      </ul>
    </section>
  )
}
