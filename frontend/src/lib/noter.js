// [US-324] « Noter » ce que je vois avec Gaston, d'un seul bouton.
//
// Le chemin en quatre temps de la maquette : toucher « Noter » → Gaston s'ouvre avec le contexte
// (US-323) et un message d'accueil → on parle (micro ouvert seul si la voix est activée, sinon
// clavier et pastilles) → on confirme la carte « À enregistrer », puis « Retour au plan ».
//
// Aucune règle de geste ici : une suggestion envoie un CODE de raccourci que le serveur traduit en
// geste (`app/services/compagnon/noter.py`). Le choix des suggestions et la phrase d'ouverture
// vivent dans `ouvertureGaston.js` (US-358), d'après l'étape que le serveur a calculée (US-320).

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
/** [US-358] `REDIGER` : pré-écrit le champ (« Note : ») sans rien envoyer. */
export const SORTE = Object.freeze({ ENVOYER: 'envoyer', SAISIR: 'saisir', PAS_ENCORE: 'pas_encore', REDIGER: 'rediger' })

export const TEXTE_RETOUR_PLAN = 'Retour au plan'
export const PLACEHOLDER_QUANTITE = 'Quelle quantité ? 800 g, 2 kg, 12…'
/** La vue du plan vu du dessus (US-327), où « Retour au plan » ramène. */
export const VUE_PLAN = 'plan-vue'

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
