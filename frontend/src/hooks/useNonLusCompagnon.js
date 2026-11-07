// [US-272 / CA5] La pastille de Gaston : ce que le compagnon a dit ou proposé depuis la dernière
// ouverture du panneau (message spontané, carte née dans Telegram ou dans un autre onglet).
//
// Relue à intervalle court tant que le panneau est fermé (`GET /compagnon/etat`), sans WebSocket,
// et seulement quand la page est visible. Le « vu » est une commodité de cet appareil
// (`localStorage`) : ce n'est pas un suivi de présence (D12), rien n'est envoyé au serveur.
import { useCallback, useEffect, useState } from 'react'
import { api } from '../lib/api.js'
import { INTERVALLE_FERME_MS, compterNonLus, ecrireVu, lireVu, vuDepuisEtat } from '../lib/compagnon.js'

const stockage = () => (typeof window !== 'undefined' ? window.localStorage : null)

export function useNonLusCompagnon(panneauOuvert) {
  const [nonLus, setNonLus] = useState(0)

  useEffect(() => {
    if (panneauOuvert) return undefined
    let vivant = true
    const relire = () => {
      if (typeof document !== 'undefined' && document.hidden) return
      api.etatCompagnon()
        .then((etat) => {
          if (!vivant) return
          const vu = lireVu(stockage())
          if (!vu) {
            // Première visite sur cet appareil : on part de maintenant, rien n'est « non lu ».
            ecrireVu(stockage(), vuDepuisEtat(etat))
            setNonLus(0)
            return
          }
          setNonLus(compterNonLus(etat, vu))
        })
        .catch(() => { /* hors ligne : la pastille garde sa dernière valeur */ })
    }
    relire()
    const minuterie = setInterval(relire, INTERVALLE_FERME_MS)
    const auRetour = () => { if (!document.hidden) relire() }
    document.addEventListener?.('visibilitychange', auRetour)
    return () => {
      vivant = false
      clearInterval(minuterie)
      document.removeEventListener?.('visibilitychange', auRetour)
    }
  }, [panneauOuvert])

  /** Le panneau a montré cet état : tout ce qu'il contient est lu. */
  const marquerVu = useCallback((etat) => {
    ecrireVu(stockage(), vuDepuisEtat(etat, lireVu(stockage())))
    setNonLus(0)
  }, [])

  return { nonLus, marquerVu }
}
