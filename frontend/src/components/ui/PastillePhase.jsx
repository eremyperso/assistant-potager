import {
  phase as lirePhase, entreesLegende, libelleComplet, depuisLisible,
  FORME_CARRE, FORME_ANNEAU, PHASE_LIBRE,
  PHASE_SEMEE, PHASE_EN_PLACE, PHASE_EN_RECOLTE,
} from '../../lib/phases.js'

export function IconePhase({ phase, taille = 14, className = '' }) {
  if (phase === PHASE_LIBRE.cle) {
    return <span aria-hidden="true" data-icone-phase={phase} style={{ width: taille, height: taille }}
      className={`inline-block shrink-0 rounded-full border border-dashed border-current ${className}`} />
  }
  if (!lirePhase(phase)) return null
  return (
    <svg width={taille} height={taille} viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"
      aria-hidden="true" data-icone-phase={phase} className={`shrink-0 ${className}`}>
      {phase === PHASE_SEMEE && <>
        <path d="M3 20.5h18M12 4v6M9.5 7.5 12 10l2.5-2.5" />
        <ellipse cx="7" cy="15.5" rx="2" ry="2.8" transform="rotate(-30 7 15.5)" />
        <ellipse cx="16.5" cy="15.5" rx="2" ry="2.8" transform="rotate(30 16.5 15.5)" />
      </>}
      {phase === PHASE_EN_PLACE && <path d="M3 20.5h18M12 20.5V11M12 14c0-4 2.6-6.6 6.6-6.6 0 4-2.6 6.6-6.6 6.6zM12 11c0-3.4-2.2-5.6-5.6-5.6 0 3.4 2.2 5.6 5.6 5.6z" />}
      {phase === PHASE_EN_RECOLTE && <path d="M3 10h18l-1.7 9.2a2 2 0 0 1-2 1.6H6.7a2 2 0 0 1-2-1.6zM8 10l3-6.5M16 10l-3-6.5M9 14.5v2.5M15 14.5v2.5" />}
    </svg>
  )
}

/**
 * Classes de FORME d'une pastille [US-200] — carré pour la récolte, anneau
 * creux pour ce qui est semé, disque plein pour ce qui est en place. C'est ce
 * qui permet de retirer le mot des rangs du Plan sans que la couleur porte
 * l'information seule (V16).
 */
function classesForme(p, pleine) {
  const arrondi = p.forme === FORME_CARRE ? 'rounded-[3px]' : 'rounded-full'
  // Un anneau est un contour SANS remplissage : la teinte passe en bordure.
  if (p.forme === FORME_ANNEAU) {
    return `${arrondi} bg-transparent ring-2 ring-inset ${p.anneau || 'ring-txt3'}`
  }
  return `${arrondi} ${pleine} ${p.contour}`
}

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
      <IconePhase phase={p.cle} />
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
          <IconePhase phase={p.cle} taille={16} className={p.teinte.split(' ')[1]} />
          {p.libelle}
        </span>
      ))}
    </div>
  )
}

/**
 * [US-200, retour de terrain] La phase SANS son mot : une pastille plus grosse,
 * dont la **forme** dit la phase autant que la teinte. Destinée aux listes
 * denses — un rang du Plan — où répéter « En place » à chaque ligne mangeait la
 * largeur du libellé de culture.
 *
 * ⚠️ Elle ne se suffit à elle-même que si la légende de l'écran donne les mots
 * (`LegendePhases`, V13) : c'est la condition qui tient V16. Le mot reste dans
 * l'infobulle, et dans le nom accessible de la ligne qui la porte (CA10).
 */
export function PucePhase({ ligne, libre = false, className = '' }) {
  const p = libre ? PHASE_LIBRE : lirePhase(ligne?.phase)
  if (!p) return null
  return (
    <span
      title={libre ? 'Rang libre' : libelleComplet(ligne)}
      className={`inline-block w-[11px] h-[11px] shrink-0 ${classesForme(p, p.puce || p.pastille)} ${className}`}
    />
  )
}

export default PastillePhase
