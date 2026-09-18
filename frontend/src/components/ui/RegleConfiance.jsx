import { useState } from 'react'
import { Check, AlertCircle, HelpCircle, ChevronDown } from 'lucide-react'
import {
  etoilesPleines, etoilesVides, libelleEtoiles, reglesVisibles, libelleAction,
  LIBELLE_NIVEAU, NIVEAU_COURT,
} from '../../lib/confiance.js'

/**
 * Bloc « règle de confiance » du design system [US-180, US-183].
 *
 * Porté depuis la maquette gelée du 18/09/2026 (`fiche-calendrier.jsx`) : conçu
 * une fois, dans une seule taille, pour la fiche calendrier d'une culture
 * (US-183) et la fiche « pourquoi ce niveau » des tuiles du Plan (US-180).
 *
 * ⚠️ Les étoiles sont à l'encre du design system (`txt` / `txt3`), jamais une
 * teinte de phase de la frise, et jamais seules : le libellé du niveau les
 * accompagne partout (US-180 / CA8, CA9).
 */

/** État d'une règle : icône, teinte d'icône, libellé lu — jamais la couleur seule. */
const ETATS = {
  gagne: { Icone: Check, teinte: 'text-brand', libelle: 'gagnée' },
  perdu: { Icone: AlertCircle, teinte: 'text-amber', libelle: 'perdue' },
  indetermine: { Icone: HelpCircle, teinte: 'text-txt3', libelle: 'indéterminée' },
}

/** Étoiles pleines et vides, avec leur équivalent textuel pour les lecteurs d'écran. */
export function Etoiles({ etoiles, taille = 17, className = '' }) {
  return (
    <span
      role="img"
      aria-label={libelleEtoiles(etoiles)}
      className={`whitespace-nowrap leading-none tracking-[.06em] ${className}`}
      style={{ fontSize: taille }}
    >
      <span className="text-txt">{etoilesPleines(etoiles)}</span>
      <span className="text-txt3">{etoilesVides(etoiles)}</span>
    </span>
  )
}

/** Une règle : état, motif en clair, points obtenus sur points maximum. */
export function LigneRegle({ regle }) {
  const { Icone, teinte, libelle } = ETATS[regle.etat] || ETATS.indetermine
  return (
    <li className="flex items-start gap-[9px] py-2">
      <Icone size={15} strokeWidth={2.2} className={`${teinte} shrink-0 mt-px`} aria-hidden="true" />
      <span className={`flex-1 min-w-0 text-[12.5px] leading-[1.45] ${regle.etat === 'indetermine' ? 'text-txt2' : 'text-txt'}`}>
        {regle.libelle}
        <span className="sr-only"> — règle {libelle}</span>
      </span>
      <span className={`shrink-0 text-[11.5px] font-bold tabular-nums ${regle.etat === 'gagne' ? 'text-txt2' : 'text-txt3'}`}>
        {regle.points} / {regle.points_max}
      </span>
    </li>
  )
}

/**
 * Le bloc : étoiles, libellé du niveau, score sur 100, puis les règles. Les
 * perdues et indéterminées sont toujours visibles ; les gagnées se replient sous
 * « Voir les 5 règles ». `note` : ce que le score ne dit pas (plafond sans météo).
 */
export function BlocConfiance({ confiance, note }) {
  const [tout, setTout] = useState(false)
  const regles = confiance.motifs || []
  const visibles = reglesVisibles(regles, tout)
  const caches = regles.length - visibles.length
  const lien = 'inline-flex items-center gap-[5px] bg-transparent border-none pt-1 cursor-pointer font-sans text-[12px] font-semibold text-brand-text'
  return (
    <div className="bg-card-alt rounded-[14px] px-3.5 py-[13px]">
      <div className="flex items-center gap-[9px] flex-wrap">
        <Etoiles etoiles={confiance.etoiles} taille={19} />
        <span className="text-[14px] font-bold text-txt">{LIBELLE_NIVEAU[confiance.etoiles]}</span>
        <span className="ml-auto text-[11.5px] font-bold text-txt3 tabular-nums">{confiance.score} / 100</span>
      </div>
      <ul className="mt-1.5 border-t border-border">
        {visibles.map((r) => <LigneRegle key={r.regle} regle={r} />)}
      </ul>
      {caches > 0 && (
        <button type="button" className={lien} onClick={() => setTout(true)} aria-expanded="false">
          Voir les {regles.length} règles<ChevronDown size={14} strokeWidth={2} />
        </button>
      )}
      {tout && caches === 0 && regles.some((r) => r.etat === 'gagne') && (
        <button type="button" className={lien} onClick={() => setTout(false)} aria-expanded="true">
          Ne garder que ce qui a coûté des points<ChevronDown size={14} strokeWidth={2} className="rotate-180" />
        </button>
      )}
      {note && <div className="text-[11.5px] text-txt3 leading-normal mt-2">{note}</div>}
    </div>
  )
}

/**
 * [US-183 / CA4, CA15] Sélecteur d'action : une ligne de segments, pré-positionnée
 * par l'appelant, exposée comme un groupe de boutons radio nommé. Rien sous deux
 * actions : il n'y a alors rien à choisir.
 */
export function SelecteurAction({ actions, value, onChange }) {
  if (!actions || actions.length < 2) return null
  return (
    <div role="radiogroup" aria-label="Geste à évaluer" className="flex gap-1 bg-card-alt rounded-[11px] p-1 mb-3">
      {actions.map((a) => {
        const actif = a.action === value
        return (
          <button
            key={a.action}
            type="button"
            role="radio"
            aria-checked={actif}
            onClick={() => onChange(a.action)}
            className={`flex-1 min-w-0 px-1.5 py-2 rounded-lg border-none cursor-pointer font-sans text-[12.5px] flex items-center justify-center gap-1.5 ${
              actif ? 'bg-card font-bold text-txt shadow-card' : 'bg-transparent font-medium text-txt2'
            }`}
          >
            <span className="truncate">{libelleAction(a.action)}</span>
            <Etoiles etoiles={a.etoiles} taille={11} />
          </button>
        )
      })}
    </div>
  )
}

/**
 * [US-180 / CA1, maquette gelée] Pastille d'une tuile du Plan, à droite de la
 * ligne « famille · durée » : étoiles et niveau court. Un appui ouvre « pourquoi
 * ce niveau ». Le geste est nommé pour les lecteurs d'écran.
 */
export function PastilleConfiance({ confiance, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      title="Pourquoi ce niveau de confiance ?"
      aria-label={`${libelleAction(confiance.action)} — ${libelleEtoiles(confiance.etoiles)} — pourquoi ce niveau ?`}
      className="ml-auto inline-flex items-center gap-[5px] bg-card border border-border rounded-full px-[9px] py-[3px] cursor-pointer font-sans shrink-0"
    >
      <Etoiles etoiles={confiance.etoiles} taille={11} />
      <span aria-hidden="true" className="text-[11px] font-semibold text-txt2">{NIVEAU_COURT[confiance.etoiles]}</span>
    </button>
  )
}

/**
 * [US-183 / CA1, maquette gelée] Puce de l'écran Stocks, sous le nom de la
 * culture : elle ouvre la fiche calendrier. Toujours présente — avec les étoiles
 * de la semaine quand un geste est d'actualité, « pas de calendrier » quand la
 * zone n'en a aucun, « calendrier » sinon.
 */
export function PuceConfiance({ confiance, sansCalendrier = false, onClick }) {
  const base = 'inline-flex items-center gap-[5px] rounded-md px-[7px] py-0.5 cursor-pointer font-sans text-[10.5px]'
  if (confiance) {
    return (
      <button type="button" onClick={onClick} title="Ouvrir la fiche calendrier"
        aria-label={`Fiche calendrier — ${libelleEtoiles(confiance.etoiles)}`}
        className={`${base} bg-card-alt border border-border`}>
        <Etoiles etoiles={confiance.etoiles} taille={10.5} />
        <span aria-hidden="true" className="font-bold text-txt2">{NIVEAU_COURT[confiance.etoiles]}</span>
      </button>
    )
  }
  return (
    <button type="button" onClick={onClick} title="Ouvrir la fiche calendrier"
      className={`${base} font-semibold text-txt3 bg-transparent border border-dashed border-border`}>
      {sansCalendrier ? 'pas de calendrier' : 'calendrier'}
    </button>
  )
}
