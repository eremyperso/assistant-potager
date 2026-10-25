// Règle des temps : logique pure de la réglette de date (maquette « Curseur de
// date »). Aucun accès au DOM ici — `npm test` la couvre, le composant
// `components/RegleTemps.jsx` ne fait que la dessiner.
//
// La réglette couvre `n` jours, du plus ancien (index 0) à aujourd'hui (index
// n - 1). Pas de futur : l'API plafonne `date_ref` à aujourd'hui (US-030) et
// le sélecteur de date l'interdit (US-031 / CA9).

const MS_JOUR = 864e5
const MOIS = ['janv.', 'févr.', 'mars', 'avr.', 'mai', 'juin', 'juil.', 'août', 'sept.', 'oct.', 'nov.', 'déc.']
const JOURS = ['dim.', 'lun.', 'mar.', 'mer.', 'jeu.', 'ven.', 'sam.']

/** Nombre de mois d'historique que la réglette couvre par défaut. */
export const MOIS_COUVERTS = 24

const utc = (iso) => {
  const [a, m, j] = String(iso).slice(0, 10).split('-').map(Number)
  return Date.UTC(a, m - 1, j)
}
const enIso = (ms) => new Date(ms).toISOString().slice(0, 10)

export function ajouterJours(iso, n) {
  return enIso(utc(iso) + n * MS_JOUR)
}

export function ecartEnJours(de, a) {
  return Math.round((utc(a) - utc(de)) / MS_JOUR)
}

/**
 * L'étendue de la réglette : du 1er du mois situé `mois` mois avant aujourd'hui
 * jusqu'à aujourd'hui compris.
 */
export function construireRegle(aujourdhui, mois = MOIS_COUVERTS) {
  const [a, m] = aujourdhui.split('-').map(Number)
  const debut = enIso(Date.UTC(a, m - 1 - mois, 1))
  return { debut, fin: aujourdhui, n: ecartEnJours(debut, aujourdhui) + 1 }
}

/** Index d'un jour dans la réglette, ramené dans ses bornes. */
export function indexDuJour(regle, iso) {
  if (!iso) return regle.n - 1
  const i = ecartEnJours(regle.debut, iso)
  return Math.max(0, Math.min(regle.n - 1, Number.isFinite(i) ? i : regle.n - 1))
}

export function jourDeIndex(regle, i) {
  return ajouterJours(regle.debut, Math.max(0, Math.min(regle.n - 1, i)))
}

/**
 * Ce que la réglette écrit dans la date de référence : `null` sur aujourd'hui
 * (= « en direct », comme le bouton de remise à zéro du sélecteur), sinon le jour.
 */
export function versDateRef(regle, i) {
  return i >= regle.n - 1 ? null : jourDeIndex(regle, i)
}

/** Index lu depuis le défilement : `px` parcourus à `ppj` pixels par jour. */
export function indexDepuisDefilement(regle, px, ppj) {
  return Math.max(0, Math.min(regle.n - 1, Math.round(px / ppj)))
}

const jourDeSemaine = (iso) => new Date(utc(iso)).getUTCDay()
const quantieme = (iso) => new Date(utc(iso)).getUTCDate()
const moisDe = (iso) => new Date(utc(iso)).getUTCMonth()

const jm = (iso) => `${quantieme(iso) === 1 ? '1er' : quantieme(iso)} ${MOIS[moisDe(iso)]}`
const majuscule = (s) => s[0].toUpperCase() + s.slice(1)

/** « Lun. 19 oct. 2026 » */
export function libelleLong(iso) {
  return `${majuscule(JOURS[jourDeSemaine(iso)])} ${jm(iso)} ${iso.slice(0, 4)}`
}

/** « lun. 19 oct. » */
export function libelleCourt(iso) {
  return `${JOURS[jourDeSemaine(iso)]} ${jm(iso)}`
}

/** « historique » dès qu'on lit un jour passé, rien sur le jour même. */
export function mentionDuJour(iso, aujourdhui) {
  return iso < aujourdhui ? 'historique' : ''
}

/**
 * Un trait par jour : plus long le lundi, plus long encore le 1er du mois, qui
 * porte son nom (et l'année en janvier).
 */
export function graduations(regle) {
  const traits = []
  for (let i = 0; i < regle.n; i++) {
    const iso = jourDeIndex(regle, i)
    if (quantieme(iso) === 1) {
      traits.push({
        i, type: 'mois',
        etiquette: MOIS[moisDe(iso)] + (moisDe(iso) === 0 ? ` ${iso.slice(0, 4)}` : ''),
      })
    } else {
      traits.push({ i, type: jourDeSemaine(iso) === 1 ? 'semaine' : 'jour', etiquette: null })
    }
  }
  return traits
}

/**
 * Le saut d'une touche du clavier, en jours (négatif = vers le passé), ou
 * `null` pour une touche étrangère. Maj = une semaine.
 */
export function pasDuClavier(touche, maj = false) {
  const pas = maj ? 7 : 1
  if (touche === 'ArrowRight') return pas
  if (touche === 'ArrowLeft') return -pas
  return null
}

/** Touches qui ramènent à aujourd'hui. */
export const estToucheAujourdhui = (touche) => touche === 'Home' || touche === 't' || touche === 'T'
