import { useState } from 'react'
import { BarChart3, Table2 } from 'lucide-react'
import Graphique from './Graphique.jsx'
import { entier } from '../lib/format.js'

/** L'équivalent en tableau du graphique, atteignable au clavier. */
function TableGraphique({ modele, formatValeur }) {
  const entetes = ['Période', ...modele.series.map((s) => s.libelle), ...(modele.series.length > 1 ? ['Total'] : [])]
  return (
    <div className="max-h-96 overflow-auto rounded-lg border border-border-soft" tabIndex={0} role="region" aria-label="Valeurs du graphique">
      <table className="w-full text-[13px] tabular-nums">
        <thead className="sticky top-0 bg-card-alt text-[11.5px] text-txt2">
          <tr>{entetes.map((e, i) => <th key={e} scope="col" className={`px-2 py-1.5 font-bold ${i ? 'text-right' : 'text-left'}`}>{e}</th>)}</tr>
        </thead>
        <tbody>
          {modele.points.map((p, i) => (
            <tr key={p.cle} className="border-t border-border-soft">
              <th scope="row" className="px-2 py-1.5 text-left font-semibold text-txt">{p.libelle}</th>
              {modele.series.map((s) => <td key={s.cle} className="px-2 py-1.5 text-right">{formatValeur(s.valeurs[i])}</td>)}
              {modele.series.length > 1 ? <td className="px-2 py-1.5 text-right">{formatValeur(modele.total[i])}</td> : null}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/**
 * La carte de graphique des vues Coût, Fiabilité et Dérives : même carte, même titre, même bascule
 * « Voir en tableau » et même état vide que le graphique de la vue Consommation [US-313/314/315 / CA10].
 */
export default function CarteGraphique({
  titre, sousTitre, actions = null, modele, titreAccessible, formatValeur = entier, formatAxe, reperes = [],
  vide = false, titreVide = 'Aucun appel sur la période', messageVide = 'Le graphique se remplira au premier appel.',
}) {
  const [enTableau, setEnTableau] = useState(false)
  return (
    <section aria-label="Graphique" className="rounded-2xl border border-border bg-card p-3.5 shadow-card">
      <div className="mb-2.5 flex flex-wrap items-start justify-between gap-x-3 gap-y-2">
        <div>
          <h2 className="font-serif text-base font-semibold leading-tight text-txt">{titre}</h2>
          {sousTitre ? <p className="mt-0.5 text-xs text-txt2">{sousTitre}</p> : null}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {actions}
          <button type="button" aria-pressed={enTableau} onClick={() => setEnTableau((v) => !v)}
            className="flex min-h-[34px] items-center gap-1.5 rounded-[10px] border border-border bg-card px-2.5 text-[12.5px] font-semibold text-txt">
            {enTableau ? <BarChart3 size={15} aria-hidden="true" /> : <Table2 size={15} aria-hidden="true" />}
            {enTableau ? 'Voir le graphique' : 'Voir en tableau'}
          </button>
        </div>
      </div>

      {vide ? (
        <div className="flex min-h-[190px] flex-col items-center justify-center gap-1.5 px-3 py-[22px] text-center text-[13px] text-txt2">
          <span className="grid h-11 w-11 place-items-center rounded-xl bg-card-alt text-txt3"><BarChart3 size={22} aria-hidden="true" /></span>
          <b className="text-sm text-txt">{titreVide}</b>
          <span>{messageVide}</span>
        </div>
      ) : enTableau ? (
        <TableGraphique modele={modele} formatValeur={formatValeur} />
      ) : (
        <Graphique modele={modele} titre={titreAccessible || titre} formatValeur={formatValeur} formatAxe={formatAxe} reperes={reperes} />
      )}
    </section>
  )
}
