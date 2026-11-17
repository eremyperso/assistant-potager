import { useCallback, useEffect, useRef, useState } from 'react'
import { INTERVALLE_MS, rafraichissementAutomatique } from '../lib/rafraichissement.js'

/**
 * Charge des données, garde les DERNIÈRES valeurs connues quand l'API tombe, et se rafraîchit
 * seule sur la vue du jour tant que l'onglet est visible [US-311 / CA5].
 *
 * Les dernières valeurs ne vivent qu'en mémoire : rien de `/admin/...` n'est écrit sur l'appareil
 * (CA7) ; hors ligne après un rechargement, il n'y a donc pas de données.
 *
 * @param charger  `async () => données`, recréé (useCallback) quand les filtres changent
 * @param options.cle         empreinte de ce qui est affiché : la changer repart de zéro
 * @param options.periode     identifiant de période (pour le rafraîchissement automatique)
 * @param options.declencheur entier incrémenté par le bouton « rafraîchir » de la coquille
 * @param options.surMiseAJour  `({a, enPanne}) => void`, pour l'heure affichée dans l'en-tête
 */
export function useDonnees(charger, { cle, periode, declencheur = 0, surMiseAJour }) {
  const [donnees, setDonnees] = useState(null)
  const [misAJour, setMisAJour] = useState(null)
  const [erreur, setErreur] = useState(null)
  const [enCours, setEnCours] = useState(true)
  const dernierCle = useRef(null)
  const compteur = useRef(0)
  const notifier = useRef(surMiseAJour)
  notifier.current = surMiseAJour

  const executer = useCallback(async () => {
    const numero = ++compteur.current
    setEnCours(true)
    try {
      const resultat = await charger()
      if (numero !== compteur.current) return           // une réponse plus récente a pris le relais
      const maintenant = new Date()
      setDonnees(resultat)
      setMisAJour(maintenant)
      setErreur(null)
      notifier.current?.({ a: maintenant, enPanne: false })
    } catch (e) {
      if (numero !== compteur.current) return
      setErreur(e)
      notifier.current?.({ a: null, enPanne: true })
    } finally {
      if (numero === compteur.current) setEnCours(false)
    }
  }, [charger])

  // Les filtres changent : on repart de zéro (d'anciens chiffres sous de nouveaux filtres mentiraient).
  useEffect(() => {
    if (dernierCle.current !== cle) {
      dernierCle.current = cle
      setDonnees(null)
      setMisAJour(null)
    }
    executer()
  }, [cle, declencheur, executer])

  useEffect(() => {
    const tick = () => {
      if (rafraichissementAutomatique({ periode, visibilite: document.visibilityState })) executer()
    }
    const minuteur = setInterval(tick, INTERVALLE_MS)
    document.addEventListener('visibilitychange', tick)
    return () => { clearInterval(minuteur); document.removeEventListener('visibilitychange', tick) }
  }, [periode, executer])

  return { donnees, misAJour, erreur, enCours, enPanne: Boolean(erreur) }
}
