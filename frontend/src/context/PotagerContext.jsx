// [US-046] Contexte du potager actif — liste des potagers du compte connecté,
// potager actuellement actif, et changement explicite (CA2/CA3/CA4).
import { createContext, useContext, useState, useEffect, useCallback } from 'react'
import { api } from '../lib/api.js'

const PotagerContext = createContext(null)

export function PotagerContextProvider({ children }) {
  const [potagers, setPotagers] = useState([])
  const [loading, setLoading] = useState(true)

  const recharger = useCallback(async () => {
    setLoading(true)
    try {
      const res = await api.potagers()
      setPotagers(res.potagers)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { recharger() }, [recharger])

  async function activer(potagerId) {
    await api.activerPotager(potagerId)
    // [CA3] Toutes les vues doivent refléter le nouveau potager — un rechargement
    // complet évite tout état obsolète dans les composants déjà montés.
    window.location.reload()
  }

  // [US-048 / CA1] Crée un potager — devient owner + potager actif, rechargement
  // complet pour repartir sur un état propre (même principe que `activer`).
  async function creerPotager(nom, latitude, longitude) {
    await api.creerPotager(nom, latitude, longitude)
    window.location.reload()
  }

  // [US-048 / CA4] Accepte une invitation par code — devient membre du potager
  // (potager actif si l'utilisateur n'en avait encore aucun).
  async function accepterInvitation(code) {
    await api.accepterInvitation(code)
    window.location.reload()
  }

  const potagerActif = potagers.find((p) => p.actif) || null
  // [CA5] Une liste vide (endpoint identité seule, jamais d'erreur) signifie
  // que le compte n'appartient encore à aucun potager.
  const aucunPotager = !loading && potagers.length === 0

  return (
    <PotagerContext.Provider
      value={{ potagers, potagerActif, aucunPotager, loading, activer, recharger, creerPotager, accepterInvitation }}
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
