// [US-194] La phase du moment d'une culture en place — semée, en place, en récolte.
//
// Le serveur CALCULE la phase (`phase`, `phase_depuis`, `phase_depuis_nature`,
// `nb_series` de `GET /plan`, `app/services/recalage_calendrier.phase_de_serie`) ;
// ici, rien que de la mise en forme. **Aucune phase n'est recalculée côté front**
// (US-194 / CA1) : ce fichier ne lit aucune date de semis ni de récolte.
//
// [CA10] La correspondance phase → libellé → teinte est écrite UNE FOIS, ici.
// La pastille reste lisible en niveaux de gris parce qu'elle porte son MOT (RT4) :
// la teinte accompagne le libellé, elle ne le remplace jamais.
import { TEINTE_EN_CROISSANCE_RESERVEE, jourLisible } from './calendrier.js'

export const PHASE_SEMEE = 'semee'
export const PHASE_EN_PLACE = 'en_place'
export const PHASE_EN_RECOLTE = 'en_recolte'

/** D'où vient `phase_depuis` — le serveur le dit, le front ne le devine pas (CA5). */
export const DEPUIS_RECOLTE = 'recolte'
export const DEPUIS_PLANTATION = 'plantation'
export const DEPUIS_LEVEE_ATTENDUE = 'levee_attendue'
export const DEPUIS_SEMIS = 'semis'

/**
 * [CA9] Les trois phases, dans l'ordre du cycle. Les teintes sont les tokens
 * sémantiques du design system, cohérents avec la frise (US-176, US-070 / CA7) :
 *
 * - *semée* reprend la famille du **semis en pleine terre** (`violet`) ;
 * - *en place* reprend la teinte **réservée à « en croissance »** (`bg-brand-soft`),
 *   qu'aucune phase du référentiel ne prend ;
 * - *en récolte* reprend celle de la **récolte** (`amber`).
 *
 * Mode sombre compris : ce sont des variables CSS redéfinies dans `index.css`,
 * jamais une couleur en dur.
 */
export const PHASES = Object.freeze([
  Object.freeze({
    cle: PHASE_SEMEE,
    libelle: 'Semée',
    court: 'semée',
    teinte: 'bg-violet-soft text-violet',
    pastille: 'bg-violet',
    contour: '',
  }),
  Object.freeze({
    cle: PHASE_EN_PLACE,
    libelle: 'En place',
    court: 'en place',
    teinte: 'bg-brand-soft text-brand',
    pastille: TEINTE_EN_CROISSANCE_RESERVEE,
    // La teinte réservée est CLAIRE : posée sur le fond clair de la pastille,
    // elle s'effacerait. Même traitement que `MonthStripLegend` pour « en
    // croissance » — un cerclage la rend visible sans changer sa famille.
    contour: 'ring-1 ring-inset ring-brand',
  }),
  Object.freeze({
    cle: PHASE_EN_RECOLTE,
    libelle: 'En récolte',
    court: 'en récolte',
    teinte: 'bg-amber-soft text-amber',
    pastille: 'bg-amber',
    contour: '',
  }),
])

/** [CA9] « Libre » : une parcelle sans culture en place. Option de la légende. */
export const PHASE_LIBRE = Object.freeze({
  cle: 'libre',
  libelle: 'Libre',
  court: 'libre',
  teinte: 'bg-card-alt text-txt3',
  pastille: 'bg-border',
  contour: 'ring-1 ring-inset ring-txt3/40',
})

const PAR_CLE = Object.freeze(Object.fromEntries(PHASES.map((p) => [p.cle, p])))

/** La phase déclarée, ou `null` si la clé est absente ou inconnue — jamais un repli. */
export function phase(cle) {
  return PAR_CLE[cle] || null
}

export const libellePhase = (cle) => phase(cle)?.libelle || ''
export const teintePhase = (cle) => phase(cle)?.teinte || ''

/**
 * [CA5] Le complément de date d'une pastille, au vocabulaire du serveur : une
 * levée ATTENDUE reste attendue, jamais présentée comme constatée. `''` si le
 * serveur n'a pas donné de date.
 */
export function depuisLisible(ligne) {
  const jour = jourLisible(ligne?.phase_depuis)
  if (!jour) return ''
  return ligne?.phase_depuis_nature === DEPUIS_LEVEE_ATTENDUE
    ? `depuis la levée attendue du ${jour}`
    : `depuis le ${jour}`
}

/**
 * Le texte lu par un lecteur d'écran, et par n'importe quel œil en niveaux de
 * gris : le mot d'abord, la date ensuite, le nombre de séries s'il y en a
 * plusieurs — jamais moyenné (⚖️ arbitrage d'US-194).
 */
export function libelleComplet(ligne) {
  const p = phase(ligne?.phase)
  if (!p) return ''
  const morceaux = [p.libelle]
  const depuis = depuisLisible(ligne)
  if (depuis) morceaux.push(depuis)
  if (ligne?.nb_series > 1) morceaux.push(`${ligne.nb_series} séries`)
  return morceaux.join(' · ')
}

/**
 * [CA6, CA2] Une ligne d'occupation a-t-elle une phase ? Non pour un semis de
 * pépinière (CA4) et pour une ligne sans série en place : on n'affiche alors
 * rien du tout, jamais une phase par défaut.
 */
export const aUnePhase = (ligne) => Boolean(phase(ligne?.phase))

/** Les entrées de la légende — les trois phases, plus « libre » sur demande (CA9). */
export function entreesLegende({ avecLibre = false } = {}) {
  return avecLibre ? [...PHASES, PHASE_LIBRE] : [...PHASES]
}
