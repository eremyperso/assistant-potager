import { ChevronRight } from 'lucide-react'
import { PastilleEtape } from './ui'

/**
 * [US-354] Les briques de liste que partagent le Tableau de bord, les Stocks et le Journal (maquette
 * « Socle commun », `.sec`, `.sh`, `.list`, `.it`). Aucune règle métier : elles dessinent ce qu'on leur
 * donne, à la largeur du conteneur qui les porte.
 */

/** Un titre de section en capitales, avec son lien d'angle (« Tout voir », « Journal »). */
export function EnTeteSection({ titre, lien = null, onLien }) {
  return (
    <div className="mx-0.5 mb-2 flex items-baseline justify-between gap-2">
      <h2 className="text-[11.5px] font-bold uppercase tracking-[.06em] text-txt2">{titre}</h2>
      {lien && (
        <button
          type="button" onClick={onLien}
          className="text-[12.5px] font-bold text-brand-text hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand"
        >
          {lien}
        </button>
      )}
    </div>
  )
}

/** Le bloc blanc qui porte des lignes séparées par un filet. */
export function ListeSocle({ children, className = '' }) {
  return (
    <div className={`overflow-hidden rounded-[14px] border border-border bg-card ${className}`}>
      {children}
    </div>
  )
}

/**
 * Une ligne de liste : pastille d'étape (ou rien), « emoji nom · variété », une ligne de détail
 * (orange quand elle est due), éventuellement une quantité à droite, et le chevron quand elle ouvre
 * quelque chose.
 */
export function LigneSocle({
  etape = null, prevue = false, due = false, emoji = '', titre, variete = '', detail = '',
  droite = null, onOuvrir, nomAccessible,
}) {
  const contenu = (
    <>
      {etape && <PastilleEtape etape={etape} prevue={prevue} due={due} petite className="shrink-0" />}
      <span className="min-w-0 flex-1">
        <b className="block truncate text-[14px] font-semibold text-txt">
          {emoji && <span aria-hidden="true" className="mr-1.5">{emoji}</span>}
          {titre}
          {variete && <span className="font-normal text-txt2"> · {variete}</span>}
        </b>
        {detail && (
          <small className={`block truncate text-[12.5px] ${due ? 'font-semibold text-due-tx' : 'text-txt2'}`}>{detail}</small>
        )}
      </span>
      {droite && (
        <span className="shrink-0 text-right text-[12.5px] font-bold tabular-nums text-txt">{droite}</span>
      )}
      {onOuvrir && <ChevronRight size={16} aria-hidden="true" className="shrink-0 text-txt3" />}
    </>
  )
  const classes = 'flex min-h-[60px] w-full items-center gap-[11px] border-t border-border-soft px-3 py-2 text-left first:border-t-0'
  return onOuvrir
    ? (
      <button
        type="button" onClick={onOuvrir} aria-label={nomAccessible}
        className={`${classes} hover:bg-card-alt focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand`}
      >
        {contenu}
      </button>
    )
    : <div className={classes} aria-label={nomAccessible}>{contenu}</div>
}
