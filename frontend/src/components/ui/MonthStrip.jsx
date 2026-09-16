import {
  couleurDuMois, couleurDuMoisReferentiel, phasesDuMois, PHASES_REFERENTIEL, ETAT_CROISSANCE,
} from '../../lib/calendrier.js'

const M_INI = ['J', 'F', 'M', 'A', 'M', 'J', 'J', 'A', 'S', 'O', 'N', 'D']
const M_NOMS = [
  'janvier', 'février', 'mars', 'avril', 'mai', 'juin',
  'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre',
]

const LEGEND = [
  ['bg-blue', 'Semis'],
  ['bg-brand', 'Plantation'],
  ['bg-amber', 'Récolte'],
]

/**
 * [US-176 / CA3, CA3bis] Les quatre phases du référentiel cultural (US-068) —
 * semis en pépinière, semis en pleine terre, plantation, récolte — dérivées de
 * `PHASES_REFERENTIEL`, jamais recopiées : teinte et libellé n'y sont écrits
 * qu'une fois.
 */
const LEGEND_REFERENTIEL = PHASES_REFERENTIEL.map(({ teinte, libelle }) => [teinte, libelle])

/**
 * Légende des phases du calendrier [US-060] — extraite de `MonthStrip`
 * pour pouvoir vivre ailleurs que sous une frise : l'écran Plan la place dans
 * l'en-tête de sa carte « Cultures en place », où elle vaut pour toutes les
 * tuiles à la fois (CA6). Les couleurs restent définies une seule fois.
 */
export function MonthStripLegend({ variante, avecCroissance = false, className = '' }) {
  // [US-070 / CA7] « En croissance » n'est nommé que si une frise recalée l'affiche.
  const entrees = variante === 'referentiel'
    ? [...LEGEND_REFERENTIEL, ...(avecCroissance ? [[ETAT_CROISSANCE.teinte, ETAT_CROISSANCE.libelle]] : [])]
    : LEGEND
  return (
    <div className={`flex flex-wrap gap-3 ${className}`}>
      {entrees.map(([bg, l]) => (
        <span key={l} className="flex items-center gap-1.5 text-[11.5px] text-txt2">
          <span className={`w-2 h-2 rounded-sm ${bg} ${bg === ETAT_CROISSANCE.teinte ? 'ring-1 ring-inset ring-brand' : ''}`} />
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
 *
 * [US-176 / CA3, CA3bis, CA14] `pepiniere` / `pleineTerre` / `plantation` : les
 * phases du référentiel. Dès que l'une est fournie, la frise passe en variante
 * « référentiel » (légende comprise) : une teinte par mois selon
 * `PRIORITE_PHASES`, et un libellé qui nomme TOUTES les phases du mois — celle
 * que la priorité n'a pas peinte reste dite. Sans elles, `semis` / `plant` /
 * `rec` se lisent exactement comme avant.
 *
 * [US-070 / CA7] `croissance` : la frise RECALÉE d'une culture en place ajoute
 * l'état « en croissance », peint après toutes les phases. Un mois vide s'y dit
 * « rien de prévu » — la frise ne conseille plus, elle suit la culture.
 */
export function MonthStrip({
  semis = [], plant = [], rec = [], pepiniere, pleineTerre, plantation, croissance,
  legend = false, moisCourant, className = '',
}) {
  const mois = moisCourant ?? new Date().getMonth()
  const recalee = croissance !== undefined
  const referentiel = recalee || pepiniere !== undefined || pleineTerre !== undefined || plantation !== undefined
  const frise = {
    pepiniere: pepiniere ?? [], pleineTerre: pleineTerre ?? [], plantation: plantation ?? [], rec,
    croissance: croissance ?? [],
  }
  const couleur = referentiel ? couleurDuMoisReferentiel(frise) : couleurDuMois({ semis, plant, rec })
  const libelle = (i) => {
    if (!referentiel) return undefined
    const phases = phasesDuMois(frise, i)
    const vide = recalee ? 'rien de prévu' : 'rien de conseillé'
    return `${M_NOMS[i]} : ${phases.length ? phases.join(', ').toLowerCase() : vide}`
  }

  return (
    <div className={className}>
      <div className="grid grid-cols-12 gap-[2.5px]" role={referentiel ? 'list' : undefined}>
        {M_INI.map((_, i) => (
          <div
            key={i}
            role={referentiel ? 'listitem' : undefined}
            title={libelle(i)}
            aria-label={libelle(i)}
            className={`h-[9px] rounded-[3px] ${couleur(i)} ${
              // [US-070 / CA7] Teinte pâle : un liseré la distingue du fond de tuile.
              couleur(i) === ETAT_CROISSANCE.teinte ? 'ring-1 ring-inset ring-brand' : ''
            } ${i === mois ? 'outline outline-[1.5px] outline-offset-[1.5px] outline-txt' : ''}`}
          />
        ))}
      </div>
      <div className="grid grid-cols-12 gap-[2.5px] mt-1" aria-hidden={referentiel ? 'true' : undefined}>
        {M_INI.map((m, i) => (
          <div
            key={i}
            className={`text-center text-[9px] ${i === mois ? 'font-bold text-txt' : 'font-medium text-txt3'}`}
          >
            {m}
          </div>
        ))}
      </div>
      {legend && (
        <MonthStripLegend variante={referentiel ? 'referentiel' : undefined} avecCroissance={recalee} className="mt-2" />
      )}
    </div>
  )
}

export default MonthStrip
