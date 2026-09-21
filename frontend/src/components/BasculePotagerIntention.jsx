import { useEffect, useRef } from 'react'
import { usePotager } from '../context/PotagerContext.jsx'
import { useNavigation } from '../context/NavigationContext.jsx'
import { adresseAvecIntention } from '../lib/intentions.js'

/**
 * [US-195 / CA7] Une intention reçue par l'adresse peut nommer un potager.
 *
 * - membre, potager déjà actif → rien à faire, la bascule est simplement **dite** ;
 * - membre, autre potager → bascule par le mécanisme existant (US-054 / US-088),
 *   **et dite** ;
 * - non-membre → l'intention est abandonnée avec un message qui ne révèle **rien**
 *   du potager : ni son nom, ni son existence, ni qui en est membre.
 *
 * ⚠️ `PotagerContext.activer` recharge la page entière (US-054 / CA3). L'intention
 * vit en mémoire de page : elle serait perdue. On la remet donc dans l'adresse
 * juste avant le rechargement, pour qu'elle soit relue — et à nouveau effacée —
 * une fois le bon potager actif.
 */
export function BasculePotagerIntention({ intentionAdresse }) {
  const { potagers, potagerActif, loading, activer } = usePotager()
  const { signaler, annoncer } = useNavigation()
  const faite = useRef(false)

  useEffect(() => {
    const cible = intentionAdresse?.potager
    if (!cible || loading || faite.current) return
    faite.current = true

    const potager = potagers.find((p) => p.id === cible)
    if (!potager) {
      // Aucune information sur le potager visé : le message est le même qu'il
      // existe ou non, et ne le nomme pas.
      signaler("Ce lien désigne un potager auquel vous n'avez pas accès.")
      return
    }
    if (potagerActif?.id === cible) {
      annoncer(`Potager « ${potager.nom} » — ouvert par le lien.`)
      return
    }
    window.history.replaceState({}, '', adresseAvecIntention(intentionAdresse))
    annoncer(`Bascule sur le potager « ${potager.nom} »…`)
    activer(cible)
  }, [loading, potagers, potagerActif, intentionAdresse])

  return null
}

export default BasculePotagerIntention
