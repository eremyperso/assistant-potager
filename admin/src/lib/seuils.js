// La vue « Seuils » [US-316 / CA10, US-317 / CA7] : mise en forme des seuils, de leur état, de la
// prévisualisation d'une modification et de l'historique. Toute l'arithmétique des alertes (mesure,
// comparaison aux 7 jours, rappel, résolution) est côté API ; ici, seulement du texte et de la
// comparaison d'une valeur saisie à la valeur déjà mesurée.

import { entier, nombre, millisecondes } from './format.js'

const ESPACE = ' '
const MOIS = ['janv.', 'févr.', 'mars', 'avr.', 'mai', 'juin', 'juil.', 'août', 'sept.', 'oct.', 'nov.', 'déc.']

export const GRAVITES = [
  { id: 'basse', libelle: 'Basse' },
  { id: 'moyenne', libelle: 'Moyenne' },
  { id: 'haute', libelle: 'Haute' },
]
export const libelleGravite = (id) => (GRAVITES.find((g) => g.id === id) || { libelle: id }).libelle.toLowerCase()

/** Les fenêtres proposées, en jours : l'API lit `conso_tokens.date`, au jour près. */
export const FENETRES = [
  { id: 1, libelle: "Aujourd'hui" },
  { id: 3, libelle: '3 derniers jours' },
  { id: 7, libelle: '7 derniers jours' },
]

export const COMPARAISONS = [
  { id: 'fixe', libelle: 'Valeur fixe' },
  { id: 'ecart_7j', libelle: 'Écart à la moyenne 7 j' },
]

/** Un état = une icône ET un libellé : jamais la couleur seule. */
export const ETATS = {
  franchi: { libelle: 'Franchi' },
  norme: { libelle: 'Dans la norme' },
  nodata: { libelle: 'Pas assez de données' },
  inactif: { libelle: 'Inactif' },
}

const UNITES = { eur: '€', jetons: 'jetons', appels: 'appels', pourcent: '%', ms: 'ms', nombre: '' }
export const uniteDuSaisie = (unite, comparaison) => (comparaison === 'ecart_7j' ? '%' : (UNITES[unite] ?? ''))

/** Une valeur dans l'unité de l'indicateur : « 8 900 jetons », « 5,00 € », « 12,5 % ». */
export function formaterValeur(unite, valeur) {
  if (valeur === null || valeur === undefined) return '—'
  if (unite === 'eur') return `${nombre(valeur, 2)}${ESPACE}€`
  if (unite === 'jetons') return `${entier(valeur)}${ESPACE}jetons`
  if (unite === 'pourcent') return `${nombre(valeur, 1)}${ESPACE}%`
  if (unite === 'ms') return millisecondes(valeur)
  if (unite === 'appels') return `${nombre(valeur, 1)}${ESPACE}appels`
  return entier(valeur)
}

/** « +48 % » : un écart signé, sans décimale. */
export function formaterEcart(ecart) {
  if (ecart === null || ecart === undefined) return '—'
  return `${ecart >= 0 ? '+' : '−'}${entier(Math.abs(ecart))}${ESPACE}%`
}

/** Le libellé d'état d'un seuil : « Franchi · 8 900 jetons (+48 %) », « Dans la norme · 0,8 % »… */
export function badgeEtat(seuil) {
  const etat = seuil.actif ? seuil.etat : 'inactif'
  const base = (ETATS[etat] || ETATS.nodata).libelle
  const actuel = seuil.valeur_courante_texte
  const ecart = seuil.comparaison === 'ecart_7j' && seuil.ecart_courant !== null && seuil.ecart_courant !== undefined
    ? ` (${formaterEcart(seuil.ecart_courant)})` : ''
  const detail = (etat === 'franchi' || etat === 'norme') && actuel ? ` · ${actuel}${ecart}` : ''
  return { etat, libelle: `${base}${detail}` }
}

/** La règle en une phrase pour une définition en cours de saisie (même formulation que l'API). */
export function regleEnClair(seuil, { comparaison, valeur, fenetre_jours: fenetre }) {
  const v = Number.isFinite(valeur) ? valeur : seuil.valeur
  if (comparaison === 'ecart_7j') return `plus de ${nombre(v, v % 1 ? 1 : 0)}${ESPACE}% au-dessus de la moyenne des 7 jours précédents`
  const quand = seuil.indicateur === 'cout_mois_projete'
    ? ' sur le mois en cours (projection)'
    : fenetre === 1 ? " aujourd'hui" : ` sur les ${fenetre} derniers jours`
  return `plus de ${formaterValeur(seuil.unite, v)}${quand}`
}

/**
 * Dit si la valeur saisie franchirait le seuil MAINTENANT, d'après la mesure que l'API a déjà faite
 * (`valeur_courante`, `ecart_courant`) — sans rien envoyer. `franchi: null` quand on ne peut pas juger.
 */
export function previsualisation(seuil, brouillon) {
  const ecart = brouillon.comparaison === 'ecart_7j'
  const mesure = ecart ? seuil.ecart_courant : seuil.valeur_courante
  const valeur = brouillon.valeur
  if (!Number.isFinite(valeur) || mesure === null || mesure === undefined) {
    return { franchi: null, texte: 'Pas assez de données aujourd’hui pour juger cette règle.' }
  }
  const franchi = mesure > valeur
  const lu = ecart ? formaterEcart(mesure) : formaterValeur(seuil.unite, mesure)
  const limite = ecart ? `+${nombre(valeur, valeur % 1 ? 1 : 0)}${ESPACE}%` : formaterValeur(seuil.unite, valeur)
  return {
    franchi,
    texte: franchi ? `Franchi avec cette valeur · ${lu} > ${limite}` : `Pas franchi avec cette valeur · ${lu} ≤ ${limite}`,
  }
}

/** Un nombre saisi à la française (« 7 500 », « 0,5 ») ; `NaN` si illisible. */
export function lireSaisie(texte) {
  const propre = String(texte ?? '').replace(/[\s  ]/g, '').replace(',', '.')
  if (!/^\d+(\.\d+)?$/.test(propre)) return NaN
  return Number(propre)
}

/** Le brouillon d'un seuil, prêt à être édité. */
export const brouillonDe = (seuil) => ({
  comparaison: seuil.comparaison,
  valeur: seuil.valeur,
  fenetre_jours: seuil.fenetre_jours,
  gravite: seuil.gravite,
})

/** Le corps du PATCH : seulement ce qui a changé. `null` quand rien n'a changé. */
export function corpsModification(seuil, brouillon) {
  const corps = {}
  for (const cle of ['comparaison', 'valeur', 'fenetre_jours', 'gravite']) {
    if (brouillon[cle] !== seuil[cle]) corps[cle] = brouillon[cle]
  }
  return Object.keys(corps).length ? corps : null
}

// ── Dates et durées ────────────────────────────────────────────────────────────────────────────
export function dateCourte(iso) {
  const d = new Date(iso)
  const h = d.getHours()
  const m = String(d.getMinutes()).padStart(2, '0')
  return `${d.getDate()} ${MOIS[d.getMonth()]}, ${h}${ESPACE}h${ESPACE}${m}`
}

export function heureCourte(iso) {
  const d = new Date(iso)
  return `${d.getHours()}${ESPACE}h${ESPACE}${String(d.getMinutes()).padStart(2, '0')}`
}

/** « 25 min », « 1 h 10 », « 3 h », « 2 j 4 h ». */
export function duree(debut, fin) {
  const minutes = Math.max(0, Math.round((new Date(fin) - new Date(debut)) / 60000))
  if (minutes < 60) return `${minutes}${ESPACE}min`
  const heures = Math.floor(minutes / 60)
  const reste = minutes % 60
  if (heures < 24) return reste ? `${heures}${ESPACE}h${ESPACE}${String(reste).padStart(2, '0')}` : `${heures}${ESPACE}h`
  const jours = Math.floor(heures / 24)
  return `${jours}${ESPACE}j${heures % 24 ? `${ESPACE}${heures % 24}${ESPACE}h` : ''}`
}

export const LIBELLE_CANAUX = { telegram: 'Telegram', email: 'e-mail' }
export const libelleCanaux = (canaux) => (canaux && canaux.length ? canaux.map((c) => LIBELLE_CANAUX[c] || c).join(', ') : 'Aucun')

/** « Depuis 9 h 05 (5 h 27) » pour une alerte ouverte. */
export const depuis = (iso, maintenant) => `${heureCourte(iso)} (${duree(iso, maintenant)})`

/** Les lignes du tableau d'historique [CA10] : les 50 dernières alertes. */
export function lignesHistorique(alertes, maintenant = new Date()) {
  return alertes.map((a) => ({
    cle: String(a.id),
    titre: a.libelle,
    cellules: {
      debut: dateCourte(a.declenchee_le),
      valeur: a.ecart_texte ? `${a.valeur_texte} (${a.ecart_texte})` : a.valeur_texte,
      duree: a.resolue_le ? duree(a.declenchee_le, a.resolue_le) : `en cours (${duree(a.declenchee_le, maintenant)})`,
      canaux: libelleCanaux(a.canaux_notifies),
    },
  }))
}
export const COLONNES_HISTORIQUE = [
  { id: 'debut', libelle: 'Début' },
  { id: 'valeur', libelle: 'Valeur' },
  { id: 'duree', libelle: 'Durée' },
  { id: 'canaux', libelle: 'Canaux notifiés' },
]

/** Le nombre d'alertes ouvertes, pour la pastille de la navigation. */
export const nbAlertesOuvertes = (donnees) => (donnees && Array.isArray(donnees.alertes_ouvertes) ? donnees.alertes_ouvertes.length : 0)

/** Les envois périodiques, tels que la configuration les porte (lecture seule) [US-317 / CA7]. */
export function envoisPeriodiques(reglages, canaux) {
  const heureTexte = `${reglages.resume_heure}${ESPACE}h`
  return [
    {
      id: 'resume', titre: 'Résumé quotidien', actif: Boolean(reglages.resume_quotidien),
      detail: `Telegram, chaque jour à ${heureTexte}`, variable: 'PILOTAGE_RESUME_QUOTIDIEN', canalJoignable: Boolean(canaux.telegram),
    },
    {
      id: 'bilan', titre: 'Bilan hebdomadaire', actif: Boolean(reglages.bilan_hebdomadaire),
      detail: `E-mail, le lundi à ${heureTexte}`, variable: 'PILOTAGE_BILAN_HEBDO', canalJoignable: Boolean(canaux.email),
    },
  ]
}

