import { useEffect, useState } from 'react'
import { INTERVALLE_MS } from '../lib/rafraichissement.js'
import { nbAlertesOuvertes } from '../lib/seuils.js'

/**
 * Le nombre d'alertes ouvertes, pour la pastille de « Seuils » dans la navigation [US-316 / maquette
 * d'US-318]. Lecture légère (`?etats=false` : aucun seuil n'est mesuré), toutes les minutes onglet
 * visible. Sans réponse, la pastille s'efface : elle ne doit jamais inventer une alerte.
 */
export function useAlertesOuvertes(client, actif, declencheur = 0) {
  const [nombre, setNombre] = useState(0)
  useEffect(() => {
    if (!actif) return undefined
    let vivant = true
    const lire = () => {
      if (document.visibilityState !== 'visible') return
      client.appeler('/admin/pilotage/seuils', { etats: 'false' })
        .then((corps) => { if (vivant) setNombre(nbAlertesOuvertes(corps)) })
        .catch(() => { if (vivant) setNombre(0) })
    }
    lire()
    const minuteur = setInterval(lire, INTERVALLE_MS)
    document.addEventListener('visibilitychange', lire)
    return () => { vivant = false; clearInterval(minuteur); document.removeEventListener('visibilitychange', lire) }
  }, [client, actif, declencheur])
  return nombre
}
