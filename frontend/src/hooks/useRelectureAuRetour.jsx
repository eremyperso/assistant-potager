// [US-196 / CA12] L'écran qui a lancé un geste se relit UNE FOIS au retour.
//
// Le geste part dans le compagnon Telegram, dans un autre onglet ou une autre
// application. Quand le jardinier revient, son écran doit montrer ce qu'il
// vient de confirmer — sans qu'il ait à tirer pour rafraîchir, et **sans
// interrogation périodique** : aucun `setInterval`, aucun sondage. Un seul
// signal, `visibilitychange`, et une seule relecture, celle de l'écran qui a
// lancé le geste.
//
// Le drapeau est armé par `BoutonGeste` (via `useArmerRelecture`) et désarmé
// par la relecture : revenir sur l'onglet sans avoir lancé de geste ne relit
// rien. C'est ce qui distingue ce crochet du rafraîchissement d'US-046 dans
// `PotagerContext`, qui, lui, écoute toutes les reprises de visibilité.
import { createContext, useCallback, useContext, useEffect, useRef } from 'react'

const ContexteRelecture = createContext(null)

/**
 * @param relire  La fonction de chargement de l'écran — celle-là même qu'il
 *                appelle à l'ouverture et au changement de date.
 */
export function RelectureAuRetourProvider({ relire, children }) {
  const arme = useRef(false)
  // Une ref plutôt qu'une dépendance : `relire` est redéfinie à chaque rendu
  // dans les vues, et ré-abonner l'écouteur à chaque rendu perdrait le drapeau.
  const relireRef = useRef(relire)
  relireRef.current = relire

  useEffect(() => {
    const auRetour = () => {
      if (document.visibilityState !== 'visible' || !arme.current) return
      arme.current = false
      relireRef.current?.()
    }
    document.addEventListener('visibilitychange', auRetour)
    return () => document.removeEventListener('visibilitychange', auRetour)
  }, [])

  const armer = useCallback(() => { arme.current = true }, [])
  return <ContexteRelecture.Provider value={armer}>{children}</ContexteRelecture.Provider>
}

/**
 * Arme la relecture de l'écran courant. Sans fournisseur au-dessus — un écran
 * qui n'a rien à relire, une prévisualisation — c'est un geste sans effet,
 * jamais une erreur.
 */
export function useArmerRelecture() {
  return useContext(ContexteRelecture) ?? (() => {})
}
