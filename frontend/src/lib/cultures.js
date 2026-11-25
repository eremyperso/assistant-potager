// [US-205 / US-361] Ce que l'écran Cultures du socle emploie de la lecture `GET /cultures/vue` : la frise
// de l'espèce, le libellé de fenêtre et la normalisation des noms. Rien n'est recalculé : la fenêtre vient
// telle quelle du serveur. La lecture ne porte plus de confiance (US-361) ; le tri, les filtres et la
// carte de l'ancien écran ont disparu.
import { libelleAction } from './confiance.js'
import { MOIS_NOMS } from './calendrier.js'

export const FENETRE_MAINTENANT = 'maintenant'
export const FENETRE_BIENTOT = 'bientot'
export const FENETRE_PLUS_TARD = 'plus_tard'
export const FENETRE_AUCUNE = 'aucune'

/** [CA5 ter] `mois_zone` (1..12, clés serveur) → 0-based, dans l'ordre de `MonthStrip`. */
const SERVEUR_VERS_FRISE = Object.freeze({
  semis_pepiniere: 'pepiniere', semis_pleine_terre: 'pleineTerre', plantation: 'plantation', recolte: 'rec',
})
const versIndex = (mois) => (mois || []).filter((m) => Number.isInteger(m) && m >= 1 && m <= 12).map((m) => m - 1)

/** [CA5] La frise conseillée de la carte, dans la forme attendue par `MonthStrip`. */
export function friseDeLigne(ligne) {
  const mois = ligne?.mois_zone || {}
  const frise = {}
  for (const [srv, cle] of Object.entries(SERVEUR_VERS_FRISE)) frise[cle] = versIndex(mois[srv])
  return frise
}

/** « février → mars », un seul mois nommé si la fenêtre tient en un mois. */
function plageMois(mois) {
  const valides = (mois || []).filter((m) => Number.isInteger(m) && m >= 1 && m <= 12)
  if (valides.length === 0) return ''
  const debut = MOIS_NOMS[valides[0] - 1]
  const fin = MOIS_NOMS[valides[valides.length - 1] - 1]
  return debut === fin ? debut : `${debut} → ${fin}`
}

const minuscule = (s) => (s ? s.charAt(0).toLowerCase() + s.slice(1) : s)

/**
 * [CA5] Le libellé de fenêtre de la carte — « Semer en place maintenant » (en
 * gras), « bientôt : planter octobre → novembre », « prochaine fenêtre :
 * semer en pépinière février → mars ». `null` sans calendrier pour la zone
 * (CA6, la carte montre alors « pas de calendrier » à la place).
 */
export function libelleFenetre(ligne) {
  if (!ligne?.a_calendrier || ligne.fenetre_etat === FENETRE_AUCUNE) return null
  const geste = libelleAction(ligne.fenetre_geste)
  if (!geste) return null
  const plage = plageMois(ligne.fenetre_mois)
  if (ligne.fenetre_etat === FENETRE_MAINTENANT) return { gras: true, texte: `${geste} maintenant` }
  if (ligne.fenetre_etat === FENETRE_BIENTOT) return { gras: false, texte: `bientôt : ${minuscule(geste)} ${plage}` }
  return { gras: false, texte: `prochaine fenêtre : ${minuscule(geste)} ${plage}` }
}

/** Normalisation accent-insensible pour la recherche et la comparaison de familles. */
export const normaliser = (s) => (s || '').normalize('NFD').replace(/\p{Diacritic}/gu, '').toLowerCase()
