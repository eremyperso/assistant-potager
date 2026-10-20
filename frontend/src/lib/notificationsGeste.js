// Ce que la PWA dit au jardinier quand il vient de déposer un geste.
//
// Le dépôt (`POST /gestes/intentions`) n'écrit aucun événement : le geste attend
// dans la file la confirmation du compagnon. La notification doit dire exactement
// cela — « préparé, en file, rien n'est encore enregistré » — et jamais
// « enregistré », sans quoi le jardinier croirait son journal à jour.
//
// Fonctions pures : le composant n'a qu'à les passer à `notifier()`.

/** « Semis — Tomate — Parcelle A », ou rien si le geste ne dit rien de lisible. */
export function resumeGeste(geste) {
  if (!geste) return ''
  return [geste.action, geste.culture, geste.parcelleNom].filter(Boolean).join(' — ')
}

const pluriel = (n) => (n > 1 ? 's' : '')

/**
 * La notification d'un dépôt réussi.
 * @param res    Réponse de `POST /gestes/intentions` (`doublon`, `en_attente`…).
 * @param geste  Le geste tel que l'écran le connaît.
 */
export function notificationDepot(res, geste) {
  const resume = resumeGeste(geste)
  const nb = Number(res?.en_attente)
  const file = nb > 0 ? `${nb} geste${pluriel(nb)} en attente de confirmation.` : ''

  // [US-224 / CA4] Signalé, pas refusé : le geste est bien en file.
  if (res?.doublon) {
    return {
      cle: 'depot-geste',
      tone: 'amber',
      titre: 'Geste ajouté — un identique attendait déjà',
      message: [resume, 'Les deux sont en file ; retirez-en un si c’est une erreur.', file]
        .filter(Boolean).join(' · '),
    }
  }
  return {
    cle: 'depot-geste',
    tone: 'brand',
    titre: 'Geste préparé',
    message: [
      resume,
      'À confirmer dans votre compagnon — rien n’est encore enregistré.',
      file,
    ].filter(Boolean).join(' · '),
  }
}

/**
 * La notification d'un dépôt qui a échoué. Un échec réseau (fetch rejeté) n'a
 * pas de message exploitable côté navigateur : on le remplace par une phrase.
 * @param erreur  L'exception levée par `api.preparerGeste`.
 * @param relancer  Rappelle le dépôt — proposé en « Réessayer ».
 */
export function notificationEchec(erreur, relancer) {
  const reseau = erreur instanceof TypeError
  const message = reseau
    ? 'Le serveur est injoignable. Vérifiez votre connexion — le geste n’a pas été préparé.'
    : String(erreur?.message || 'Une erreur est survenue — le geste n’a pas été préparé.')
  return {
    cle: 'depot-geste',
    tone: 'red',
    titre: 'Le geste n’a pas pu être préparé',
    message,
    action: relancer ? { libelle: 'Réessayer', onClick: relancer } : null,
  }
}
