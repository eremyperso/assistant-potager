// [US-290] La demande de connexion d'un assistant IA, entre `/oauth/authorize` et la
// page de consentement. Elle arrive par l'adresse (`/connecteur-ia?demande=…`) et doit
// survivre à une connexion Google, qui recharge la PWA sur `/auth/callback` : elle est
// donc gardée dans le sessionStorage (onglet courant seulement, 15 min de validité
// côté API). Toute lecture ou écriture du stockage est protégée : navigation privée.

export const CLE_DEMANDE = 'demande_connecteur_ia'
export const CHEMIN_CONSENTEMENT = '/connecteur-ia'

function stockage() {
  try {
    return window.sessionStorage
  } catch {
    return null
  }
}

/** Lit la demande portée par l'adresse, la range, et nettoie la barre d'adresse. */
export function capterDemandeAdresse(loc = window.location, histoire = window.history) {
  if (loc.pathname !== CHEMIN_CONSENTEMENT) return null
  const demande = new URLSearchParams(loc.search).get('demande')
  if (demande) {
    try { stockage()?.setItem(CLE_DEMANDE, demande) } catch { /* stockage refusé */ }
  }
  histoire.replaceState({}, '', '/')
  return demande
}

/** La demande en attente : celle de l'adresse, sinon celle gardée avant une connexion. */
export function demandeEnAttente(depuisAdresse) {
  if (depuisAdresse) return depuisAdresse
  try {
    return stockage()?.getItem(CLE_DEMANDE) || null
  } catch {
    return null
  }
}

export function oublierDemande() {
  try { stockage()?.removeItem(CLE_DEMANDE) } catch { /* stockage refusé */ }
}

/** Potagers cochés d'office : le potager actif, ou l'unique potager. */
export function potagersPreselectionnes(potagers = []) {
  const actif = potagers.find((p) => p.actif)
  if (actif) return [actif.id]
  return potagers.length === 1 ? [potagers[0].id] : []
}

/** L'écriture n'a de sens que sur un potager où le jardinier n'est pas lecteur. */
export function ecriturePossible(potagers = [], choisis = []) {
  return potagers.some((p) => choisis.includes(p.id) && p.role !== 'lecteur')
}
