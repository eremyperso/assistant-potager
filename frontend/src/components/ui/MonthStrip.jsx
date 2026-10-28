import { useState } from 'react'
import {
  couleurDuMois, couleurDuMoisReferentiel, couleurDuMoisFiltre, phasesDuMois,
  PHASES_REFERENTIEL, ETAT_CROISSANCE,
} from '../../lib/calendrier.js'

const M_INI = ['J', 'F', 'M', 'A', 'M', 'J', 'J', 'A', 'S', 'O', 'N', 'D']
const M_NOMS = [
  'janvier', 'février', 'mars', 'avril', 'mai', 'juin',
  'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre',
]

// [teinte, libellé, clé de phase dans la frise]
const LEGEND = [
  ['bg-blue', 'Semis', 'semis'],
  ['bg-brand', 'Plantation', 'plant'],
  ['bg-amber', 'Récolte', 'rec'],
]

/**
 * [US-176 / CA3, CA3bis] Les quatre phases du référentiel cultural (US-068) —
 * semis en pépinière, semis en pleine terre, plantation, récolte — dérivées de
 * `PHASES_REFERENTIEL`, jamais recopiées : teinte et libellé n'y sont écrits
 * qu'une fois.
 */
const LEGEND_REFERENTIEL = PHASES_REFERENTIEL.map(({ teinte, libelle, cle }) => [teinte, libelle, cle])

/**
 * Légende des phases du calendrier [US-060] — extraite de `MonthStrip`
 * pour pouvoir vivre ailleurs que sous une frise : l'écran Plan la place dans
 * l'en-tête de sa carte « Cultures en place », où elle vaut pour toutes les
 * tuiles à la fois (CA6). Les couleurs restent définies une seule fois.
 */
export function MonthStripLegend({
  variante, avecCroissance = false, className = '', actif = null, onChoisir,
}) {
  // [US-070 / CA7] « En croissance » n'est nommé que si une frise recalée l'affiche.
  const entrees = variante === 'referentiel'
    ? [...LEGEND_REFERENTIEL, ...(avecCroissance ? [[ETAT_CROISSANCE.teinte, ETAT_CROISSANCE.libelle, ETAT_CROISSANCE.cle]] : [])]
    : LEGEND
  return (
    <div className={`flex flex-wrap gap-3 ${className}`}>
      {entrees.map(([bg, l, cle]) => {
        const pastille = (
          <span className={`w-2 h-2 rounded-sm ${bg} ${bg === ETAT_CROISSANCE.teinte ? 'ring-1 ring-inset ring-brand' : ''}`} />
        )
        // Sans `onChoisir`, la légende reste un simple libellé.
        if (!onChoisir) {
          return (
            <span key={l} className="flex items-center gap-1.5 text-[11.5px] text-txt2">{pastille}{l}</span>
          )
        }
        // [US-255 / CA1, CA6] Bouton à bascule : l'actif se détache, les autres s'atténuent.
        const choisi = actif === cle
        return (
          <button
            key={l}
            type="button"
            aria-pressed={choisi}
            onClick={() => onChoisir(choisi ? null : cle)}
            className={`flex items-center gap-1.5 text-[11.5px] min-h-[44px] px-2 -mx-2 rounded-md cursor-pointer ${
              choisi ? 'font-semibold text-txt bg-card-alt' : actif ? 'text-txt3' : 'text-txt2'
            }`}
          >
            {pastille}
            {l}
          </button>
        )
      })}
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
  // [US-255] Filtre de légende : état local à cette frise, jamais mémorisé.
  const [filtre, setFiltre] = useState(null)
  const phases = referentiel ? frise : { semis, plant, rec }
  const entreeFiltre = filtre
    && (referentiel ? [...PHASES_REFERENTIEL, ETAT_CROISSANCE] : null)?.find((p) => p.cle === filtre)
  const teinteFiltre = referentiel ? entreeFiltre?.teinte : LEGEND.find(([, , c]) => c === filtre)?.[0]
  const couleur = filtre && teinteFiltre
    ? couleurDuMoisFiltre(phases, filtre, teinteFiltre)
    : referentiel ? couleurDuMoisReferentiel(frise) : couleurDuMois({ semis, plant, rec })
  const phaseVide = Boolean(filtre && teinteFiltre && !(phases[filtre] || []).length)
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
        <MonthStripLegend
          variante={referentiel ? 'referentiel' : undefined} avecCroissance={recalee} className="mt-2"
          actif={filtre} onChoisir={setFiltre}
        />
      )}
      {legend && phaseVide && (
        <p className="mt-1 text-[11px] text-txt3">Aucun mois pour cette phase</p>
      )}
    </div>
  )
}

export default MonthStrip
