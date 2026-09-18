// [US-180, US-183] Niveau de confiance lu du moteur d'US-178
// (`GET /plan/confiances/candidates`) : pastille des tuiles du Plan, puce de
// Stocks, fiche « pourquoi ce niveau » et fiche calendrier d'une culture.
//
// Le serveur CALCULE (étoiles, points, motifs, récolte attendue) ; ici, rien que
// du choix et de la mise en forme. Deux règles tenues :
//
// 1. **Aucune valeur de repli** (US-180 / CA7) : lecture en échec ou culture sans
//    calendrier, rien n'est affiché à la place — jamais une étoile par défaut.
// 2. **Aucune seconde règle de priorité** (US-180 / CA2) : à score égal, c'est
//    celle de la frise (`PRIORITE_PHASES`, US-176 / CA3bis) qui tranche.
//
// Les libellés (« Confiance moyenne », « Voir les 5 règles »…) sont ceux de la
// maquette gelée du 18/09/2026 (`US-183 - Fiche calendrier culture`).
import { PRIORITE_PHASES, TIRET, jourLisible } from './calendrier.js'

/** Action du moteur (US-178) → clé de phase de la frise (US-176). */
export const CLE_PHASE_PAR_ACTION = Object.freeze({
  semis_pepiniere: 'pepiniere',
  semis_pleine_terre: 'pleineTerre',
  plantation: 'plantation',
})

/** Ordre du geste — celui du sélecteur de la fiche (US-183 / CA4). */
export const ORDRE_ACTIONS = Object.freeze(['semis_pepiniere', 'semis_pleine_terre', 'plantation'])

/**
 * Le geste à l'INFINITIF, comme on le dirait au jardinier. Le moteur rend un
 * substantif (« plantation ») parce que le gabarit du bot le fige (US-179) : ce
 * libellé-ci est d'interface, et c'est ici qu'il s'écrit.
 */
export const LIBELLE_ACTION = Object.freeze({
  semis_pepiniere: 'Semer en pépinière',
  semis_pleine_terre: 'Semer en place',
  plantation: 'Planter',
})

export const libelleAction = (action) => LIBELLE_ACTION[action] || ''

/** [US-183 / CA6] Libellé du bouton d'enregistrement de l'action choisie. */
export const LIBELLE_ENREGISTRER = Object.freeze({
  semis_pepiniere: 'Enregistrer le semis',
  semis_pleine_terre: 'Enregistrer le semis',
  plantation: 'Enregistrer la plantation',
})

/**
 * [US-180 / CA3, CA7] Les états d'une tuile. `confiance` porte la pastille ;
 * `sans_calendrier` se dit en toutes lettres (maquette gelée) ; `indisponible`
 * (lecture échouée) garde l'étiquette « calendrier » vers la fiche. `rien_a_faire`
 * ne survient plus que pour une réponse sans aucune action évaluée.
 */
export const ETAT_CONFIANCE = 'confiance'
export const ETAT_RIEN_A_FAIRE = 'rien_a_faire'
export const ETAT_SANS_CALENDRIER = 'sans_calendrier'
export const ETAT_INDISPONIBLE = 'indisponible'

/** Niveau → libellé de la maquette gelée, toujours à côté des étoiles. */
export const LIBELLE_NIVEAU = Object.freeze({ 1: 'Confiance faible', 2: 'Confiance moyenne', 3: 'Confiance élevée' })
export const NIVEAU_COURT = Object.freeze({ 1: 'faible', 2: 'moyenne', 3: 'élevée' })

const ETOILES_MAX = 3

const borne = (etoiles) => Math.max(1, Math.min(ETOILES_MAX, etoiles || 1))

/** Rang de l'action dans la règle de priorité de la frise — plus petit, mieux placé. */
function rangDePhase(action) {
  const rang = PRIORITE_PHASES.indexOf(CLE_PHASE_PAR_ACTION[action])
  return rang === -1 ? PRIORITE_PHASES.length : rang
}

/**
 * [US-180 / CA2, US-183 / CA4] La mieux placée d'une liste d'évaluations : le
 * meilleur score ; à score égal, le geste le plus avancé, comme sur la frise.
 * `null` si la liste est vide.
 */
export function meilleureCandidate(candidates) {
  return (candidates || []).reduce((gagnante, c) => {
    if (!gagnante) return c
    const [sc, sg] = [c.score ?? 0, gagnante.score ?? 0]
    if (sc !== sg) return sc > sg ? c : gagnante
    return rangDePhase(c.action) < rangDePhase(gagnante.action) ? c : gagnante
  }, null)
}

/**
 * [US-180 / CA1, CA3, CA7] Ce que la tuile d'une culture montre.
 *
 * Maquette gelée du 18/09/2026 : une culture qui a un calendrier porte TOUJOURS
 * son niveau — celui du geste le mieux noté parmi tous ceux qui ont une fenêtre
 * (`actions`), exactement le geste présélectionné par la fiche calendrier. Hors
 * saison, ce niveau dit « pas maintenant » par ses règles perdues ; il ne se tait
 * plus. `candidates` ne sert plus que de repli pour une réponse sans `actions`.
 *
 * `confiances` est la réponse de `GET /plan/confiances/candidates`, ou `null`
 * quand sa lecture a échoué : l'écran reste utilisable, l'indicateur est absent.
 */
export function confianceDeTuile(confiances, culture) {
  const entree = confiances?.cultures?.[culture]
  if (!entree) return { etat: ETAT_INDISPONIBLE, confiance: null }
  const confiance = meilleureCandidate(entree.actions?.length ? entree.actions : entree.candidates)
  if (confiance) return { etat: ETAT_CONFIANCE, confiance }
  return { etat: entree.a_calendrier ? ETAT_RIEN_A_FAIRE : ETAT_SANS_CALENDRIER, confiance: null }
}

/**
 * [US-183 / CA4] Les actions du sélecteur de la fiche : celles dont la phase a
 * une fenêtre pour la zone, dans l'ordre du geste — jamais une action inventée.
 */
export function actionsDeFiche(entree) {
  const rang = (a) => ORDRE_ACTIONS.indexOf(a.action)
  return [...(entree?.actions || [])].sort((a, b) => rang(a) - rang(b))
}

/** `2` → `'★★'` puis `'☆'` — les étoiles vides comptent : le niveau se lit sans couleur. */
export const etoilesPleines = (etoiles) => '★'.repeat(borne(etoiles))
export const etoilesVides = (etoiles) => '☆'.repeat(ETOILES_MAX - borne(etoiles))
export const etoilesAffichables = (etoiles) => etoilesPleines(etoiles) + etoilesVides(etoiles)

/**
 * [US-180 / CA8, US-183 / CA15] Équivalent textuel des étoiles, exposé aux
 * lecteurs d'écran : « 2 étoiles sur 3 — Confiance moyenne ».
 */
export function libelleEtoiles(etoiles) {
  const n = borne(etoiles)
  return `${n} étoile${n > 1 ? 's' : ''} sur ${ETOILES_MAX} — ${LIBELLE_NIVEAU[n]}`
}

/**
 * [US-183, maquette gelée] Règles visibles dans le bloc de confiance : les
 * perdues et les indéterminées toujours, les gagnées repliées sous « Voir les
 * 5 règles » — ce qui a coûté des points se lit d'abord.
 */
export function reglesVisibles(motifs, tout = false) {
  const regles = motifs || []
  return tout ? regles : regles.filter((m) => m.etat !== 'gagne')
}

/** [US-180 / CA5, US-183 / CA7] Une règle météo indéterminée : inviter à localiser. */
export function meteoIndeterminee(confiance) {
  return (confiance?.motifs || []).some(
    (m) => m.etat === 'indetermine' && (m.regle === 'R3' || m.regle === 'R4'),
  )
}

/**
 * [US-180 / CA5, US-183 / CA5] La récolte attendue si le geste est fait à la
 * date de référence — une FOURCHETTE ou un tiret, jamais une date sèche.
 * « entre le 18 et le 28 septembre » quand les deux bornes partagent le mois.
 */
export function recolteLisible(confiance) {
  const { min, max } = confiance?.recolte_attendue || {}
  if (!min || !max) return TIRET
  if (min === max) return `vers le ${jourLisible(min)}`
  const [, mMin, jMin] = min.split('-').map(Number)
  const [, mMax] = max.split('-').map(Number)
  if (mMin === mMax) return `entre le ${jMin === 1 ? '1er' : jMin} et le ${jourLisible(max)}`
  return `entre le ${jourLisible(min)} et le ${jourLisible(max)}`
}

/** « 2026-06-15 » → « 15 juin 2026 », la date de référence dans l'en-tête des fiches. */
export function dateLongue(iso) {
  const [a, m] = String(iso || '').split('-').map(Number)
  const jour = jourLisible(iso)
  return jour && a && m ? `${jour} ${a}` : ''
}
