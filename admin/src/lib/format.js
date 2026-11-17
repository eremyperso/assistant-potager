// Chiffres à la française [US-311 / US-312] : espace insécable comme séparateur de milliers,
// virgule décimale, symbole après le nombre (« 1 204 », « 68,4 % », « 0,042 € »).
// Écrit à la main plutôt qu'avec Intl : le séparateur d'Intl varie selon le moteur (U+202F ou
// U+00A0) et le rendu doit être identique partout, tests compris.

const ESPACE = ' '
const MOINS = '−'

function groupes(entier) {
  return String(entier).replace(/\B(?=(\d{3})+(?!\d))/g, ESPACE)
}

/** Un nombre à `decimales` chiffres après la virgule, groupé par milliers. `null` → « — ». */
export function nombre(valeur, decimales = 0) {
  if (valeur === null || valeur === undefined || Number.isNaN(valeur)) return '—'
  const negatif = valeur < 0
  const fixe = Math.abs(valeur).toFixed(decimales)
  const [entier, fraction] = fixe.split('.')
  const texte = groupes(entier) + (fraction ? `,${fraction}` : '')
  return (negatif && Number(fixe) !== 0 ? MOINS : '') + texte
}

export const entier = (valeur) => nombre(valeur === null || valeur === undefined ? valeur : Math.round(valeur), 0)

/** Un rapport (0,684) en pourcentage (« 68,4 % »). */
export function pourcent(rapport, decimales = 1) {
  if (rapport === null || rapport === undefined) return '—'
  return `${nombre(rapport * 100, decimales)}${ESPACE}%`
}

/** Une grande quantité en forme courte : « 2,31 M » à partir d'un million, « 14 820 » en dessous. */
export function compact(valeur) {
  if (valeur === null || valeur === undefined) return '—'
  if (Math.abs(valeur) >= 1_000_000) return `${nombre(valeur / 1_000_000, 2)}${ESPACE}M`
  return entier(valeur)
}

/** Des micro-euros en euros : trois décimales sous un euro (« 0,042 € »), deux au-dessus. */
export function euro(microEuros) {
  if (microEuros === null || microEuros === undefined) return '—'
  const euros = microEuros / 1_000_000
  return `${nombre(euros, Math.abs(euros) < 1 ? 3 : 2)}${ESPACE}€`
}

/** Forme abrégée des maquettes : « 2,31 M » dès un million, « 615 k » dès 10 000, sinon le nombre. */
export function abrege(valeur) {
  if (valeur === null || valeur === undefined) return '—'
  if (Math.abs(valeur) >= 1_000_000) return `${nombre(valeur / 1_000_000, 2)}${ESPACE}M`
  if (Math.abs(valeur) >= 10_000) return `${entier(valeur / 1000)}${ESPACE}k`
  return entier(valeur)
}

export function millisecondes(valeur) {
  return valeur === null || valeur === undefined ? '—' : `${entier(valeur)}${ESPACE}ms`
}

/** « 14 h 32 » — heure locale du navigateur. */
export function heure(date) {
  const h = date.getHours()
  const m = String(date.getMinutes()).padStart(2, '0')
  return `${h}${ESPACE}h${ESPACE}${m}`
}

/** « 2026-11-10 » en heure locale (jamais en UTC : un jour ne doit pas glisser la nuit). */
export function jourIso(date) {
  const a = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, '0')
  const j = String(date.getDate()).padStart(2, '0')
  return `${a}-${m}-${j}`
}

const JOURS = ['dim.', 'lun.', 'mar.', 'mer.', 'jeu.', 'ven.', 'sam.']
const MOIS = ['janv.', 'févr.', 'mars', 'avr.', 'mai', 'juin', 'juil.', 'août', 'sept.', 'oct.', 'nov.', 'déc.']

/** « lun. 9 nov. » depuis « 2026-11-09 ». */
export function jourCourt(iso) {
  const [a, m, j] = iso.split('-').map(Number)
  const date = new Date(a, m - 1, j)
  return `${JOURS[date.getDay()]} ${j} ${MOIS[m - 1]}`
}

/** « 9 nov. » depuis « 2026-11-09 ». */
export function jourBref(iso) {
  const [, m, j] = iso.split('-').map(Number)
  return `${j} ${MOIS[m - 1]}`
}
