import { useState } from 'react'
import {
  barresParAnnee, culturesDeLAnnee, libelleSaison, MENTION_STATISTIQUES,
} from '../lib/stocksSocle.js'

/**
 * [US-354 / CA5] « Récoltes par saison » : une barre par année qui a des récoltes (proportionnelle au
 * maximum) ; un appui sur une année affiche ses cultures en barres, le reste en « Autres ». Une feuille
 * sur mobile, le panneau droit partagé sur ordinateur : le contenu est le même, il remplit ce qu'on lui
 * donne. Les saisons arrivent lues (une lecture de `GET /stats/rendement` par année) ; les récoltes en
 * pièces n'y figurent jamais (US-036, INC-008).
 */
export default function RecoltesParSaison({ saisons, jourLu, anneeInitiale }) {
  const barres = barresParAnnee(saisons)
  const [annee, setAnnee] = useState(anneeInitiale ?? saisons[saisons.length - 1]?.annee ?? null)
  const saison = saisons.find((s) => s.annee === annee) ?? null
  const cultures = culturesDeLAnnee(saison)

  if (!saisons.length) {
    return (
      <div className="p-4 text-[13px] text-txt2">
        Aucune récolte pesée n’est encore enregistrée. {MENTION_STATISTIQUES}
      </div>
    )
  }

  return (
    <div className="@container/saisons px-[18px] pb-6 pt-4">
      <h2 className="font-serif text-[21px] font-semibold leading-[1.2] text-txt">Récoltes par saison</h2>
      <p className="mt-0.5 text-[13px] text-txt2">{libelleSaison(annee, jourLu)}</p>

      <div className="mt-3.5 flex flex-col gap-1.5" role="group" aria-label="Choisir une année">
        {barres.map((b) => {
          const choisie = b.annee === annee
          return (
            <button
              key={b.annee} type="button" aria-pressed={choisie} onClick={() => setAnnee(b.annee)}
              className={`grid min-h-[42px] w-full grid-cols-[44px_1fr_64px] items-center gap-2.5 rounded-[10px] px-1.5 text-left text-[13px] font-semibold ${
                choisie ? 'bg-card-alt shadow-[inset_0_0_0_1px_var(--border)]' : ''
              }`}
            >
              <span>{b.annee}</span>
              <span className="block h-3.5" aria-hidden="true">
                <span
                  className={`block h-3.5 rounded-[7px] ${choisie ? 'bg-[#F2A54A]' : 'bg-[#F9D9B2]'}`}
                  style={{ width: `${b.pct}%` }}
                />
              </span>
              <span className="text-right tabular-nums">{b.libelle}</span>
            </button>
          )
        })}
      </div>

      <h3 className="mb-2 mt-5 text-[11.5px] font-bold uppercase tracking-[.06em] text-txt2">{annee} · par culture</h3>
      <ul>
        {cultures.map((c) => (
          <li
            key={c.cle}
            className="grid min-h-9 grid-cols-[26px_1fr_100px_64px] items-center gap-2 border-t border-border-soft text-[13px] first:border-t-0"
          >
            <span aria-hidden="true" className="text-center text-[17px]">{c.emoji}</span>
            <span className="truncate">{c.nom}</span>
            <span className="block h-2" aria-hidden="true">
              <span className="block h-2 rounded bg-[#F2A54A]" style={{ width: `${c.pct}%` }} />
            </span>
            <span className="text-right font-bold tabular-nums">{c.libelle}</span>
          </li>
        ))}
      </ul>

      <p className="mt-3.5 text-[12px] text-txt2">{MENTION_STATISTIQUES}</p>
    </div>
  )
}
