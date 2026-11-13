// [US-330] Le détail d'une parcelle ouvert dans le Plan : ce qui se calcule, sans React.
//
// Remplace l'onglet « Parcelles » d'US-222 : le détail (D1 à D6) vit dans le panneau de droite
// du Plan (ordinateur) ou dans une feuille plein écran (mobile). Les textes des cartes
// Caractéristiques, Rotation et Sol restent ceux de `planParcelles.js` — aucun second dessin.
import { capitaliser, nombre } from './planVue.js'
import { occupationDetail, libelleForme } from './planParcelles.js'

/** [CA4] Les deux modes de la même vue : le dessin, ou la liste (parcelles non placées, recherche, lecteurs d'écran). */
export const AFFICHAGE_PLAN = 'plan'
export const AFFICHAGE_LISTE = 'liste'
export const AFFICHAGES = Object.freeze([
  Object.freeze({ id: AFFICHAGE_PLAN, label: 'Plan' }),
  Object.freeze({ id: AFFICHAGE_LISTE, label: 'Liste' }),
])

/** [D3 à D6] Les onglets du détail. `lots` remplace `enplace` pour une pépinière, qui n'a pas de rotation. */
export const ONGLET_EN_PLACE = 'enplace'
export const ONGLET_LOTS = 'lots'
export const ONGLET_CARACTERISTIQUES = 'caracteristiques'
export const ONGLET_ROTATION = 'rotation'
export const ONGLET_ENTRETIEN = 'entretien'

export function ongletsDeParcelle(parcelle) {
  if (parcelle?.est_pepiniere) {
    return [
      { id: ONGLET_LOTS, label: 'Lots' },
      { id: ONGLET_CARACTERISTIQUES, label: 'Caractéristiques' },
      { id: ONGLET_ENTRETIEN, label: 'Entretien' },
    ]
  }
  return [
    { id: ONGLET_EN_PLACE, label: 'En place' },
    { id: ONGLET_CARACTERISTIQUES, label: 'Caractéristiques' },
    { id: ONGLET_ROTATION, label: 'Rotation' },
    { id: ONGLET_ENTRETIEN, label: 'Entretien' },
  ]
}

/** L'onglet à ouvrir : celui demandé s'il existe pour cette parcelle, sinon le premier. */
export function ongletValide(parcelle, demande) {
  const onglets = ongletsDeParcelle(parcelle)
  return onglets.some((o) => o.id === demande) ? demande : onglets[0].id
}

const PICTOS_FORME = { planche: '🌱', bac: '🪴', butte: '⛰️', serre: '🏡', pepiniere: '🌿' }

/** [D1] Le pictogramme de la parcelle : celui de sa forme, sinon la planche. */
export function pictoParcelle(parcelle) {
  const f = (parcelle?.geometrie?.forme || (parcelle?.est_pepiniere ? 'pepiniere' : 'planche')).toLowerCase()
  return PICTOS_FORME[f] || PICTOS_FORME.planche
}

const pluriel = (n, mot) => `${n} ${mot}${n > 1 ? 's' : ''}`

/**
 * [D1] « Planche · 60 m² · 8 rangs » — ou « Pépinière froide · 3 lots ». Chaque morceau absent
 * disparaît : le titre ne dit que ce qu'il sait.
 */
export function sousTitreDetail(parcelle) {
  if (parcelle?.est_pepiniere) {
    const type = (parcelle.type_pepiniere || '').trim()
    const lots = (parcelle.disposition?.lots_en_cours || []).length
    return [`Pépinière${type ? ` ${type}` : ''}`, pluriel(lots, 'lot')].join(' · ')
  }
  const forme = libelleForme(parcelle?.geometrie?.forme) || 'Planche'
  const surface = parcelle?.superficie_m2 ? `${nombre(parcelle.superficie_m2)} m²` : null
  const rangs = parcelle?.nb_rangs ? pluriel(parcelle.nb_rangs, 'rang') : null
  return [forme, surface, rangs].filter(Boolean).join(' · ')
}

/**
 * [D2] « Sur le plan : 12 × 5 m, rangs dans la longueur » — ou, faute de place, ce qui manque.
 * `placee` dit s'il y a un dessin à ajuster.
 */
export function geometrieDetail(parcelle) {
  const g = parcelle?.geometrie ?? {}
  if (!g.placee) return { placee: false, texte: 'Pas encore posée sur le plan' }
  const dims = g.longueur_m && g.largeur_m ? `${nombre(g.longueur_m)} × ${nombre(g.largeur_m)} m` : null
  const sens = g.sens_rangs === 'travers' ? 'rangs dans la largeur' : g.sens_rangs === 'longueur' ? 'rangs dans la longueur' : null
  return { placee: true, texte: `Sur le plan : ${[dims, sens].filter(Boolean).join(', ') || 'position posée'}` }
}

/** [D3] « 7 rangs occupés sur 8 · 1 à confirmer ». `lignes` : celles du chemin (US-329). */
export function resumeEnPlace(parcelle, lignes = []) {
  const aConfirmer = lignes.filter((l) => l.aConfirmer).length
  return [occupationDetail(parcelle), aConfirmer ? `${aConfirmer} à confirmer` : null].filter(Boolean).join(' · ')
}

/** [CA4] Une ligne de la liste : le nom, ce que la parcelle est, et si elle est posée sur le plan. */
export function ligneDeListe(parcelle) {
  const pepiniere = Boolean(parcelle?.est_pepiniere)
  return {
    id: parcelle.id,
    nom: parcelle.nom,
    picto: pictoParcelle(parcelle),
    sousTitre: sousTitreDetail(parcelle),
    placee: Boolean(parcelle?.geometrie?.placee),
    pepiniere,
    occupation: pepiniere ? null : occupationDetail(parcelle),
  }
}

/** [CA4] Les parcelles de la liste : toutes, posées ou non, dans l'ordre du chemin. */
export function parcellesDeListe(plan) {
  return [...(plan?.parcelles || [])]
    .sort((a, b) => (a.ordre ?? 0) - (b.ordre ?? 0) || String(a.nom).localeCompare(String(b.nom), 'fr'))
    .map(ligneDeListe)
}

/** [CA2, CA5] La parcelle désignée par son identifiant, ou `null` si elle n'existe plus. */
export function parcelleParId(plan, id) {
  if (id == null) return null
  return (plan?.parcelles || []).find((p) => p.id === id) ?? null
}

/** Le texte d'annonce quand le détail d'une parcelle s'ouvre. */
export const annonceParcelle = (parcelle) => `${capitaliser(parcelle?.nom || '')} : détail ouvert`

/** [CA5] Ce qu'on dit quand le lien désigne une parcelle supprimée. */
export const TEXTE_PARCELLE_INTROUVABLE = 'Cette parcelle n’existe plus.'
