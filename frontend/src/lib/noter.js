// [US-324] « Noter » ce que je vois avec Gaston, d'un seul bouton.
//
// Le chemin en quatre temps de la maquette : toucher « Noter » → Gaston s'ouvre avec le contexte
// (US-323) et un message d'accueil → on parle (micro ouvert seul si la voix est activée, sinon
// clavier et pastilles) → on confirme la carte « À enregistrer », puis « Retour au plan ».
//
// Aucune règle de geste ici : une pastille envoie un CODE de raccourci que le serveur traduit en
// geste (`app/services/compagnon/noter.py`). Ce fichier ne choisit que les pastilles à montrer,
// d'après l'étape que le serveur a calculée (US-320).

/** Les codes compris par `POST /compagnon/messages` (`raccourci`). */
export const RACCOURCI = Object.freeze({
  ETAPE_LEVEE: 'etape_levee',
  RECOLTE: 'recolte',
  CULTURE_TERMINEE: 'culture_terminee',
  RANG_LIBERE: 'rang_libere',
  ARROSE: 'arrose',
  PAILLE: 'paille',
  DESHERBE: 'desherbe',
})

/** Ce que fait une pastille : envoyer tout de suite, attendre une quantité, ou repousser l'étape. */
export const SORTE = Object.freeze({ ENVOYER: 'envoyer', SAISIR: 'saisir', PAS_ENCORE: 'pas_encore' })

export const TEXTE_ACCUEIL_CULTURE = 'Je vous écoute. Dites ce que vous voyez, je le note sur cette culture.'
export const TEXTE_ACCUEIL_PARCELLE = 'Je vous écoute. Dites ce que vous voyez, je le note sur cette parcelle.'
export const TEXTE_ACCUEIL_POTAGER = 'Je vous écoute. Dites ce que vous voyez, je le note dans le journal du potager.'
export const TEXTE_RETOUR_PLAN = 'Retour au plan'
export const PLACEHOLDER_QUANTITE = 'Quelle quantité ? 800 g, 2 kg, 12…'
/** La vue du plan vu du dessus (US-327), où « Retour au plan » ramène. */
export const VUE_PLAN = 'plan-vue'

const p = (libelle, raccourci, sorte = SORTE.ENVOYER) => ({ libelle, raccourci, sorte })
const PAS_ENCORE = { libelle: 'Pas encore', raccourci: null, sorte: SORTE.PAS_ENCORE }
const RECOLTE = p('Récolte', RACCOURCI.RECOLTE, SORTE.SAISIR)
const CULTURE_TERMINEE = p('Culture terminée', RACCOURCI.CULTURE_TERMINEE)
const RANG_LIBERE = p('Rang libéré', RACCOURCI.RANG_LIBERE)
const GESTES_DE_PARCELLE = [p('Arrosé', RACCOURCI.ARROSE), p('Paillé', RACCOURCI.PAILLE), p('Désherbé', RACCOURCI.DESHERBE)]

/** La pastille d'une étape à noter : « Levée vue », « Récolte », « Culture terminée ». */
function pastilleDEtape(code) {
  if (code === 'levee') return p('Levée vue', RACCOURCI.ETAPE_LEVEE)
  if (code === 'en_recolte') return RECOLTE
  if (code === 'terminee') return CULTURE_TERMINEE
  return null
}

/** L'étape qui suit la courante dans la séquence servie par le serveur. */
function etapeSuivante(etapes) {
  const liste = etapes?.etapes || []
  const i = liste.findIndex((x) => x.code === etapes?.etape)
  return i >= 0 && i + 1 < liste.length ? liste[i + 1].code : null
}

/**
 * [US-324 / CA2] Les pastilles de la maquette, selon la situation :
 *
 * | étape à confirmer | « Levée vue » (l'étape), « Pas encore » |
 * | en récolte        | « Récolte », « Culture terminée »       |
 * | terminé           | « Rang libéré »                         |
 * | autre étape       | « [étape suivante] vue »                |
 * | parcelle, potager | « Arrosé », « Paillé », « Désherbé »    |
 */
export function raccourcisNoter(contexte) {
  const etapes = contexte?.etapes
  if (!contexte?.culture || !etapes) return GESTES_DE_PARCELLE
  if (etapes.a_liberer || etapes.etape === 'terminee') return [RANG_LIBERE]
  if (etapes.a_confirmer) {
    const pastille = pastilleDEtape(etapes.etape)
    return pastille ? [pastille, PAS_ENCORE] : [PAS_ENCORE]
  }
  if (etapes.etape === 'en_recolte') return [RECOLTE, CULTURE_TERMINEE]
  const suivante = pastilleDEtape(etapeSuivante(etapes))
  return suivante ? [suivante] : GESTES_DE_PARCELLE
}

/** [US-324 / temps 2] Le message d'accueil de Gaston, selon ce qu'il a sous les yeux. */
export function accueilNoter(contexte) {
  if (contexte?.culture) return TEXTE_ACCUEIL_CULTURE
  if (contexte?.parcelleId != null) return TEXTE_ACCUEIL_PARCELLE
  return TEXTE_ACCUEIL_POTAGER
}

/** [US-324 / CA2, E7] Ce que « Pas encore » envoie à `POST /plan/etapes/pas-encore` ; null sans série. */
export function reportDEtape(contexte) {
  const e = contexte?.etapes
  if (!e?.serie_id || !e?.etape) return null
  return { serieId: e.serie_id, etape: e.etape }
}

/**
 * [US-324 / CA5] Après « Confirmer » : ce que Gaston dit de ce qui a changé, et s'il propose
 * « Retour au plan » (seulement quand Gaston a été ouvert par « Noter »).
 */
export function apresConfirmation(issue, { noter = false } = {}) {
  if (!issue || issue.erreur) return null
  const annonce = issue.annonce || null
  if (!annonce && !noter) return null
  return { texte: annonce || 'C’est noté.', retourPlan: Boolean(noter) }
}
