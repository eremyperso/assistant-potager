import { useState } from 'react'
import { api } from '../lib/api.js'
import { useObservationsUI } from '../context/ObservationsUIContext.jsx'

/**
 * [US-039] État + chargement lazy des observations pour un point d'accès
 * (carte parcelle, ligne de culture dans Plan, ou ligne de culture dans Stocks).
 * key    : identifiant unique de ce point d'accès sur l'écran (ex: "parcelle:3"),
 *          utilisé pour qu'un seul panneau reste ouvert à la fois.
 * params : { parcelleId, culture, variete } — voir api.observations().
 */
export function useObservations(key, params) {
  const { openKey, setOpenKey } = useObservationsUI()
  const [items, setItems] = useState(null)
  const [loading, setLoading] = useState(false)
  const open = openKey === key

  async function toggle() {
    if (open) {
      setOpenKey(null)
      return
    }
    setOpenKey(key)
    if (items === null) {
      setLoading(true)
      try {
        const data = await api.observations(params)
        setItems(data.items || [])
      } catch {
        setItems([])
      } finally {
        setLoading(false)
      }
    }
  }

  return { open, items, loading, toggle }
}
