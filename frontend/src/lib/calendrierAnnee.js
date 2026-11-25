// [US-352 / CA3] Calendrier de l'année : douze cases, cinq gestes. UNE table de
// présentation, lue par Cultures, le catalogue et la fiche Référence.
//
// Ce fichier ne CALCULE aucune fenêtre : le serveur la donne (`mois_zone` de
// `GET /cultures/vue`, calendrier de zone). Ici, seulement la réduction de ces
// fenêtres à UNE couleur par mois, et les mots de l'infobulle.

/** Les cinq gestes du calendrier, dans l'ordre du cycle. La couleur est celle de l'étape voisine. */
export const GESTES_MOIS = Object.freeze([
  Object.freeze({ cle: 'semis', libelle: 'semis', famille: 'semee' }),
  Object.freeze({ cle: 'levee', libelle: 'levée ou plantation', famille: 'levee' }),
  Object.freeze({ cle: 'croissance', libelle: 'croissance', famille: 'croissance' }),
  Object.freeze({ cle: 'floraison', libelle: 'floraison', famille: 'fleur' }),
  Object.freeze({ cle: 'recolte', libelle: 'récolte', famille: 'recolte' }),
])

const PAR_CLE = Object.freeze(Object.fromEntries(GESTES_MOIS.map((g) => [g.cle, g])))

/** Le mot d'un mois sans geste. */
export const RIEN_A_FAIRE = 'rien à faire'

/** Initiales et noms courts des mois (index 0 = janvier). */
export const INITIALES_MOIS = Object.freeze(['J', 'F', 'M', 'A', 'M', 'J', 'J', 'A', 'S', 'O', 'N', 'D'])
export const MOIS_COURTS = Object.freeze([
  'janv.', 'févr.', 'mars', 'avr.', 'mai', 'juin', 'juil.', 'août', 'sept.', 'oct.', 'nov.', 'déc.',
])

/** La classe CSS de la case d'un geste (`etape-<famille>`), ou `''` pour un mois vide. */
export const classeGeste = (cle) => (PAR_CLE[cle] ? `etape-${PAR_CLE[cle].famille}` : '')

/**
 * Priorité d'un mois qui porte plusieurs gestes : le plus avancé dans le cycle l'emporte
 * (récolte, floraison, plantation, semis), la croissance ne peint que les mois laissés vides.
 */
const PRIORITE = Object.freeze(['recolte', 'floraison', 'levee', 'semis', 'croissance'])

/**
 * Les gestes d'une frise, quelle que soit sa forme d'origine, ramenés aux cinq clés :
 *  - forme du référentiel : `pepiniere`, `pleineTerre` (→ semis), `plantation` (→ levée),
 *    `rec` (→ récolte), `croissance`, `floraison` ;
 *  - forme historique : `semis`, `plant` (→ levée), `rec`.
 */
function gestesDeFrise(frise = {}) {
  const liste = (v) => (Array.isArray(v) ? v : [])
  return {
    semis: [...liste(frise.semis), ...liste(frise.pepiniere), ...liste(frise.pleineTerre)],
    levee: [...liste(frise.plant), ...liste(frise.plantation), ...liste(frise.levee)],
    croissance: liste(frise.croissance),
    floraison: liste(frise.floraison),
    recolte: [...liste(frise.rec), ...liste(frise.recolte)],
  }
}

/**
 * Les douze mois (index 0 = janvier) d'une frise : la clé du geste qui peint la case, ou
 * `null` si rien n'est à faire.
 */
export function moisDeFrise(frise) {
  const gestes = gestesDeFrise(frise)
  return Array.from({ length: 12 }, (_, i) => PRIORITE.find((cle) => gestes[cle].includes(i)) || null)
}

/** Les douze mois d'une chaîne de la maquette (`'..slllcfpp...'`) : s, l, c, f, p, point = vide. */
export function moisDeChaine(chaine) {
  const table = { s: 'semis', l: 'levee', c: 'croissance', f: 'floraison', p: 'recolte' }
  return Array.from({ length: 12 }, (_, i) => table[(chaine || '')[i]] || null)
}

/**
 * [CA4] L'infobulle d'une case : « nov. (ce mois-ci) · récolte ». Un mois qui porte plusieurs
 * gestes (frise du référentiel) les dit tous, dans l'ordre du cycle.
 */
export function texteMois(i, cle, { courant = false, autres = [] } = {}) {
  const gestes = [cle, ...autres].filter((c, k, t) => c && t.indexOf(c) === k && PAR_CLE[c])
    .sort((a, b) => GESTES_MOIS.findIndex((g) => g.cle === a) - GESTES_MOIS.findIndex((g) => g.cle === b))
    .map((c) => PAR_CLE[c].libelle)
  return `${MOIS_COURTS[i]}${courant ? ' (ce mois-ci)' : ''} · ${gestes.length ? gestes.join(', ') : RIEN_A_FAIRE}`
}

/** Le nom accessible du calendrier entier. */
export const NOM_CALENDRIER = 'Calendrier sur l’année'

/**
 * Les cases prêtes à dessiner : clé du geste, classe de couleur, infobulle, mois courant.
 * `frise` fournit les gestes secondaires de chaque mois (ceux que la priorité n'a pas peints).
 */
export function casesCalendrier(mois, { moisCourant = null, frise = null } = {}) {
  const tous = frise ? gestesDeFrise(frise) : null
  return (mois || []).slice(0, 12).map((cle, i) => ({
    i,
    cle: cle || null,
    classe: classeGeste(cle),
    courant: i === moisCourant,
    info: texteMois(i, cle, {
      courant: i === moisCourant,
      autres: tous ? GESTES_MOIS.map((g) => g.cle).filter((c) => tous[c].includes(i)) : [],
    }),
  }))
}
