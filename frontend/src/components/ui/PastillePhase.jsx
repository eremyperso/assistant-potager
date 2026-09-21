import { phase as lirePhase, entreesLegende, libelleComplet, depuisLisible } from '../../lib/phases.js'

/**
 * Pastille de phase du moment du design system [US-194 / CA9, CA10].
 *
 * La phase — *semée*, *en place*, *en récolte* — vient telle quelle du serveur
 * (`GET /plan`) : ce composant ne calcule rien, il affiche. Sa teinte vient de
 * `lib/phases.js`, seul endroit où la correspondance phase → libellé → teinte
 * est écrite.
 *
 * ⚠️ Le MOT est toujours rendu : la pastille reste lisible en niveaux de gris,
 * et la teinte ne porte jamais l'information seule (RT4).
 *
 * Consommateurs prévus : la couleur des cartes de la Vue plan (US-200), la
 * pastille « en récolte · 2 parcelles » de l'écran Cultures (US-205) et la ligne
 * de variété de la fiche culture (US-207).
 */
export function PastillePhase({ ligne, avecDate = false, className = '' }) {
  const p = lirePhase(ligne?.phase)
  if (!p) return null
  const date = avecDate ? depuisLisible(ligne) : ''
  return (
    <span
      className={`inline-flex items-center gap-1.5 text-[11.5px] font-semibold px-2.5 py-0.5 rounded-full whitespace-nowrap ${p.teinte} ${className}`}
      title={libelleComplet(ligne)}
    >
      <span aria-hidden="true" className={`w-1.5 h-1.5 rounded-full ${p.pastille} ${p.contour}`} />
      {p.libelle}
      {date && <span className="font-normal opacity-80">{date}</span>}
      <span className="sr-only"> — {libelleComplet(ligne)}</span>
    </span>
  )
}

/**
 * Légende des trois phases [US-194 / CA9], plus « libre » pour un écran qui
 * colore aussi les parcelles vides (Vue plan, US-200). Même forme que
 * `MonthStripLegend` : les teintes ne sont définies qu'une fois, dans la lib.
 */
export function LegendePhases({ avecLibre = false, className = '' }) {
  return (
    <div className={`flex flex-wrap gap-3 ${className}`}>
      {entreesLegende({ avecLibre }).map((p) => (
        <span key={p.cle} className="flex items-center gap-1.5 text-[11.5px] text-txt2">
          <span aria-hidden="true" className={`w-2 h-2 rounded-sm ${p.pastille} ${p.contour}`} />
          {p.libelle}
        </span>
      ))}
    </div>
  )
}

export default PastillePhase
