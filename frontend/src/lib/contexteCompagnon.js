// [US-323] Ce que le jardinier a sous les yeux, transmis à Gaston.
//
// Ouvert par « Noter » (suivi d'une culture, parcelle, barre basse), le panneau porte une
// BARRE DE CONTEXTE sous son en-tête : la culture sélectionnée, sinon la parcelle, sinon
// « Tout le potager » (C1). Ouvert par le visage de Gaston, il n'en a pas (C6).
//
// Le contexte part avec chaque message en IDENTIFIANTS (C4) : parcelle, culture, variété, rang.
// Le serveur les vérifie et relit les noms ; ceux d'ici ne servent qu'à l'affichage.

import { nomCulture } from './planDessus.js'
import { symboleDeCulture } from './pictosCultures.js'

/** L'événement de fenêtre que la coquille (`App.jsx`) écoute pour ouvrir Gaston (US-322 / S6). */
export const EVENEMENT_OUVRIR_COMPAGNON = 'potager:ouvrir-compagnon'

export const TEXTE_TOUT_LE_POTAGER = 'Tout le potager'
export const TEXTE_A_PROPOS = 'À propos de :'
export const TEXTE_PRECISER = 'Préciser'
export const TEXTE_CONTEXTE_INTROUVABLE =
  'Je ne retrouve plus ce que vous regardiez (la culture a peut-être été terminée ou déplacée). '
  + 'Retirez le contexte ou précisez la parcelle. Rien n’a été enregistré.'

/**
 * Un contexte d'écran bien formé, ou null (tout le potager). Une culture sans parcelle n'en
 * est pas un : le serveur la refuserait (C4).
 */
export function normaliserContexte(c) {
  if (!c || c.parcelleId == null || c.parcelleId === '') return null
  const rang = Number.isInteger(c.rang) && c.rang > 0 ? c.rang : null
  return {
    parcelleId: c.parcelleId,
    parcelle: c.parcelle || '',
    culture: c.culture || null,
    variete: c.culture ? (c.variete || null) : null,
    rang,
    // [US-324] L'étape servie par le suivi (US-320), pour choisir les pastilles. Jamais envoyée.
    etapes: c.culture ? (c.etapes ?? null) : null,
  }
}

/**
 * [C1, C6] Ce que l'ouverture du panneau dit de sa barre de contexte.
 * `detail` absent (visage de Gaston) : pas de barre. `detail.contexte` présent : la barre,
 * sur ce contexte ou sur « Tout le potager ».
 */
export function ouvertureDuPanneau(detail) {
  if (!detail || !('contexte' in detail)) return { barre: false, contexte: null }
  const ouverture = { barre: true, contexte: normaliserContexte(detail.contexte) }
  // [US-328 / CA4] Une carte « À placer » posée sur un rang : la proposition part à l'ouverture.
  if (detail.placement) ouverture.placement = detail.placement
  return ouverture
}

/** Ouvre Gaston avec un contexte (null : « Tout le potager »). */
export function ouvrirGastonAvec(contexte, cible = typeof window !== 'undefined' ? window : null) {
  cible?.dispatchEvent(new CustomEvent(EVENEMENT_OUVRIR_COMPAGNON, { detail: { contexte: contexte ?? null } }))
}

/**
 * [US-328 / CA4] Ouvre Gaston sur le rang où une carte « À placer » a été posée : la phrase de
 * proposition part aussitôt, avec la carte (`placement`) ; le serveur répond par une carte de
 * plantation à confirmer. `jeton` distingue deux placements identiques successifs.
 */
export function ouvrirGastonPourPlacer({ phrase, contexte, placement }, cible = typeof window !== 'undefined' ? window : null) {
  cible?.dispatchEvent(new CustomEvent(EVENEMENT_OUVRIR_COMPAGNON, {
    detail: { contexte, placement: { phrase, carte: placement, jeton: Date.now() + Math.random() } },
  }))
}

/**
 * [US-332, US-333] Ouvre Gaston sur une demande née du plan : créer une forme posée dans l'éditeur
 * (`plan = { action: 'creer', forme, longueur_m, largeur_m, x_m, y_m, … }`) ou « Rendre inactive ou
 * supprimer… » (`plan = { action: 'retirer', parcelle_id }`). Gaston vérifie, puis répond par une
 * carte à confirmer : rien n'est écrit avant « Confirmer ».
 */
export function ouvrirGastonPourPlan({ phrase, contexte = null, plan }, cible = typeof window !== 'undefined' ? window : null) {
  cible?.dispatchEvent(new CustomEvent(EVENEMENT_OUVRIR_COMPAGNON, {
    detail: { contexte, placement: { phrase, plan, jeton: Date.now() + Math.random() } },
  }))
}

/** « Planche centrale, rang 3 » */
const lieu = (c) => (c.rang ? `${c.parcelle}, rang ${c.rang}` : c.parcelle)

/**
 * [C2, C3] Le libellé de la barre : « 🥦 Chou de Bruxelles · Planche centrale, rang 3 »,
 * « 📍 Serre », ou « Tout le potager » (avec « Préciser »).
 */
export function barreDeContexte(contexte) {
  const c = normaliserContexte(contexte)
  if (!c) return { aPropos: false, emoji: '', texte: TEXTE_TOUT_LE_POTAGER, retirable: false, preciser: true }
  if (c.culture) {
    return {
      aPropos: true,
      emoji: symboleDeCulture(c.culture, c.variete || ''),
      texte: `${nomCulture(c.culture, null)} · ${lieu(c)}`,
      retirable: true,
      preciser: false,
    }
  }
  return { aPropos: true, emoji: '📍', texte: lieu(c), retirable: true, preciser: false }
}

/** [C4] Les identifiants envoyés avec le message ; undefined sans contexte. */
export function contexteAEnvoyer(contexte) {
  const c = normaliserContexte(contexte)
  if (!c) return undefined
  const corps = { parcelle_id: c.parcelleId }
  if (c.culture) corps.culture = c.culture
  if (c.variete) corps.variete = c.variete
  if (c.rang) corps.rang = c.rang
  return corps
}

/** [C3] Les parcelles proposées par « Préciser » : celles du potager, hors pépinières. */
export function parcellesAPreciser(plan) {
  const liste = Array.isArray(plan) ? plan : plan?.parcelles ?? []
  return liste
    .filter((p) => p && p.id != null && !p.est_pepiniere && p.actif !== false)
    .sort((a, b) => (a.ordre ?? 0) - (b.ordre ?? 0) || String(a.nom).localeCompare(String(b.nom), 'fr'))
    .map((p) => ({ parcelleId: p.id, parcelle: p.nom }))
}

/**
 * [US-325 / CA3] L'événement par lequel l'écran Plan publie sa sélection courante (culture choisie,
 * enrichie par le suivi une fois lu) ; `detail.contexte` null quand rien n'est choisi.
 */
export const EVENEMENT_SELECTION_PLAN = 'potager:selection-plan'

export function publierSelection(contexte, cible = typeof window !== 'undefined' ? window : null) {
  cible?.dispatchEvent(new CustomEvent(EVENEMENT_SELECTION_PLAN, { detail: { contexte: contexte ?? null } }))
}

export const TEXTE_PEPINIERE_NOTER = 'Les lots de la pépinière se notent dans Ma pépinière.'

/**
 * [US-325] La pastille du bouton « Noter » : l'emoji de la culture choisie, l'épingle d'une
 * parcelle, le micro sinon. `pepiniere` : « Noter » renvoie vers Ma pépinière.
 */
export function pastilleNoter(selection) {
  if (selection?.pepiniere) return { sorte: 'pepiniere', emoji: '🌱' }
  const c = normaliserContexte(selection)
  if (!c) return { sorte: 'micro', emoji: '' }
  if (c.culture) return { sorte: 'culture', emoji: symboleDeCulture(c.culture, c.variete || '') }
  return { sorte: 'parcelle', emoji: '📍' }
}

/** L'erreur 404 d'un contexte qui n'est plus valable (culture terminée entre-temps…). */
export const contexteIntrouvable = (err) => err?.statut === 404 && /contexte introuvable/i.test(err?.message ?? '')
