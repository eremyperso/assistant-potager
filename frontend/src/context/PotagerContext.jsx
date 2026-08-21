// [US-046] Contexte du potager actif — liste des potagers du compte connecté,
// potager actuellement actif, et changement explicite (CA2/CA3/CA4).
import { createContext, useContext, useState, useEffect, useCallback } from 'react'
import { api } from '../lib/api.js'

const PotagerContext = createContext(null)

export function PotagerContextProvider({ children }) {
  const [potagers, setPotagers] = useState([])
  const [loading, setLoading] = useState(true)
  // [US-083 / CA7] Potager consulté en lecture seule (e.g. un potager archivé)
  // — distinct du potager actif, permet de visualiser sans rendre actif
  const [potagerId, setPotagerId] = useState(null)

  // `silencieux` évite de repasser `loading` à true : PotagerGate (App.jsx)
  // démonte tout l'arbre applicatif tant que `loading` est vrai, ce qui est
  // voulu au chargement initial mais ferait clignoter toute l'appli si on
  // l'utilisait pour un simple rafraîchissement en arrière-plan.
  const recharger = useCallback(async ({ silencieux = false } = {}) => {
    if (!silencieux) setLoading(true)
    try {
      const res = await api.potagers()
      setPotagers(res.potagers)
    } finally {
      if (!silencieux) setLoading(false)
    }
  }, [])

  useEffect(() => { recharger() }, [recharger])

  // [Bugfix] Le potager actif peut être changé côté bot Telegram (/potager)
  // pendant que le PWA reste ouvert en arrière-plan : recharger la liste
  // (silencieusement) quand l'onglet redevient visible évite que le menu
  // affiche un potager actif obsolète tant que l'utilisateur n'a pas
  // rafraîchi manuellement la page.
  useEffect(() => {
    function onVisible() {
      if (document.visibilityState === 'visible') recharger({ silencieux: true })
    }
    document.addEventListener('visibilitychange', onVisible)
    window.addEventListener('focus', onVisible)
    return () => {
      document.removeEventListener('visibilitychange', onVisible)
      window.removeEventListener('focus', onVisible)
    }
  }, [recharger])

  async function activer(potagerId) {
    await api.activerPotager(potagerId)
    // [CA3] Toutes les vues doivent refléter le nouveau potager — un rechargement
    // complet évite tout état obsolète dans les composants déjà montés.
    window.location.reload()
  }

  // [US-048 / CA1] Crée un potager — devient owner + potager actif, rechargement
  // complet pour repartir sur un état propre (même principe que `activer`).
  // [US-074 / CA3] `ville` optionnelle, choisie via VilleSearch.
  // [US-081 / CA5] Sans bascule (`activer: false`), rien à recharger : le
  // potager courant et toutes les vues montées restent valides, un simple
  // rafraîchissement silencieux de la liste suffit à faire apparaître le
  // nouveau potager dans le menu.
  async function creerPotager(nom, ville, latitude, longitude, activer = true) {
    const cree = await api.creerPotager(nom, ville, latitude, longitude, activer)
    if (cree.actif) {
      window.location.reload()
    } else {
      await recharger({ silencieux: true })
    }
    return cree
  }

  // [US-074 / CA4, CA5] Modifie nom/ville/localisation d'un potager déjà créé —
  // pas de rechargement complet nécessaire : un simple `recharger()` suffit à
  // refléter le nouveau nom/ville dans PotagerMenu (aucune autre vue montée ne
  // dépend de ces champs).
  async function modifierPotager(potagerId, payload) {
    await api.modifierPotager(potagerId, payload)
    await recharger()
  }

  // [US-048 / CA4] Accepte une invitation par code — devient membre du potager
  // (potager actif si l'utilisateur n'en avait encore aucun).
  async function accepterInvitation(code) {
    await api.accepterInvitation(code)
    window.location.reload()
  }

  // [US-058 / CA5] Finalise l'assistant de premier potager : crée le potager
  // (avec sa localisation) puis, seulement si une parcelle a été renseignée,
  // la première parcelle — dans cet ordre, une seule fois « Entrer dans mon
  // potager » validé. `creerPotager` rend ce potager actif côté serveur avant
  // que ce await ne résolve, donc `creerParcelle` (résolu via le potager actif
  // de la requête suivante) cible déjà le bon potager sans rechargement intermédiaire.
  async function finaliserOnboarding({ nom, ville, latitude, longitude, parcelle }) {
    await api.creerPotager(nom, ville, latitude, longitude)
    if (parcelle?.nom?.trim()) {
      await api.creerParcelle(parcelle)
    }
    window.location.reload()
  }

  const potagerActif = potagers.find((p) => p.actif) || null
  // [CA5] Une liste vide (endpoint identité seule, jamais d'erreur) signifie
  // que le compte n'appartient encore à aucun potager.
  const aucunPotager = !loading && potagers.length === 0

  return (
    <PotagerContext.Provider
      value={{
        potagers, potagerActif, aucunPotager, loading,
        activer, recharger, creerPotager, modifierPotager, accepterInvitation, finaliserOnboarding,
        potagerId, setPotagerId,
      }}
    >
      {children}
    </PotagerContext.Provider>
  )
}

export function usePotager() {
  const ctx = useContext(PotagerContext)
  if (!ctx) throw new Error('usePotager doit être utilisé dans PotagerContextProvider')
  return ctx
}
