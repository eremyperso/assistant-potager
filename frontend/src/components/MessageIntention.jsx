import { AlertCircle } from 'lucide-react'
import { InfoBanner } from './ui'
import { useNavigation } from '../context/NavigationContext.jsx'

/**
 * [US-195 / CA3, CA7] Ce qu'une intention n'a pas pu désigner.
 *
 * Une parcelle supprimée, un lot inconnu, une culture hors référentiel, un
 * potager dont on n'est pas membre : l'écran s'ouvre **normalement**, et ce
 * bandeau dit en une phrase pourquoi il ne montre pas ce que le lien promettait.
 * Jamais une erreur, jamais un écran vide.
 *
 * Placé une fois dans la coquille, au-dessus du contenu de la vue : aucune vue
 * n'a à porter son propre bandeau.
 */
export function MessageIntention() {
  const { message, effacerMessage } = useNavigation()
  if (!message) return null
  return (
    <InfoBanner
      key={message}
      tint="amber"
      icon={AlertCircle}
      title="Ce lien ne mène nulle part"
      body={message}
      onClose={effacerMessage}
      className="mb-4"
    />
  )
}

export default MessageIntention
