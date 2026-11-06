// [US-271] Une media query suivie en direct — pour la STRUCTURE DE PAGE seulement (placer le chat du
// compagnon en plein écran ou en carte flottante). Un composant réutilisable se met en page par
// container queries (frontend/CLAUDE.md), pas avec ceci.
import { useEffect, useState } from 'react'

export function useMedia(requete) {
  const lire = () => (typeof window !== 'undefined' && window.matchMedia ? window.matchMedia(requete).matches : false)
  const [vrai, setVrai] = useState(lire)
  useEffect(() => {
    if (typeof window === 'undefined' || !window.matchMedia) return undefined
    const m = window.matchMedia(requete)
    const maj = () => setVrai(m.matches)
    maj()
    m.addEventListener?.('change', maj)
    return () => m.removeEventListener?.('change', maj)
  }, [requete])
  return vrai
}
