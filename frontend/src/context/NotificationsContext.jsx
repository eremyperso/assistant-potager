// Notifications d'action de la PWA : « c'est fait » ou « ça n'a pas marché ».
//
// Un geste déposé depuis une fiche (modale, feuille plein écran) ne doit jamais
// laisser le jardinier sans réponse : le retour est posé au niveau de l'application,
// au-dessus des modales, et non dans le flux d'un écran qu'un défilement ou une
// fermeture de fiche ferait disparaître.
//
// Règles :
//   * un succès ou un avertissement s'efface seul (5 s / 7 s) — la fermer à la
//     main reste possible ;
//   * une erreur RESTE jusqu'à ce que le jardinier la ferme : un message qui
//     disparaît seul est un message qu'on n'a pas lu ;
//   * deux notifications de même `cle` ne s'empilent pas : la plus récente
//     remplace l'ancienne (trois appuis = une carte, pas trois) ;
//   * pas d'interrogation, pas de stockage : tout est en mémoire de l'onglet.
import {
  createContext, useCallback, useContext, useEffect, useMemo, useRef, useState,
} from 'react'
import { Toast } from '../components/ui/Toast.jsx'

const Contexte = createContext(null)

const DUREES = { brand: 5000, blue: 5000, amber: 7000, red: 0 }
const MAX_VISIBLES = 3

let compteur = 0

export function NotificationsProvider({ children }) {
  const [items, setItems] = useState([])
  const minuteurs = useRef(new Map())

  const fermer = useCallback((id) => {
    const m = minuteurs.current.get(id)
    if (m) { clearTimeout(m); minuteurs.current.delete(id) }
    setItems((courants) => courants.filter((n) => n.id !== id))
  }, [])

  /**
   * @param n  { tone: 'brand'|'amber'|'red'|'blue', titre, message?, action?:
   *             {libelle, onClick}, cle?, duree? } — `duree` en ms, 0 = reste.
   * @returns l'identifiant, pour fermer la notification à la main.
   */
  const notifier = useCallback((n) => {
    const id = ++compteur
    const tone = n.tone ?? 'brand'
    const duree = n.duree ?? DUREES[tone] ?? 5000

    setItems((courants) => {
      const sansDoublon = n.cle ? courants.filter((c) => {
        if (c.cle !== n.cle) return true
        const m = minuteurs.current.get(c.id)
        if (m) { clearTimeout(m); minuteurs.current.delete(c.id) }
        return false
      }) : courants
      return [...sansDoublon, { ...n, id, tone }].slice(-MAX_VISIBLES)
    })
    if (duree > 0) minuteurs.current.set(id, setTimeout(() => fermer(id), duree))
    return id
  }, [fermer])

  useEffect(() => {
    const tous = minuteurs.current
    return () => { tous.forEach(clearTimeout); tous.clear() }
  }, [])

  const valeur = useMemo(() => ({ notifier, fermer, actif: true }), [notifier, fermer])

  return (
    <Contexte.Provider value={valeur}>
      {children}
      {/* Au-dessus des modales (z-50) et de la fiche du lot (z-[70]). Sous 900 px,
          la barre d'onglets basse occupe le pied de l'écran : la pile se pose
          au-dessus d'elle. `pointer-events-none` : la zone vide ne capte rien. */}
      <div
        role="region"
        aria-label="Notifications"
        className="pointer-events-none fixed inset-x-0 z-[80] flex flex-col items-center gap-2 px-4 bottom-[calc(76px+env(safe-area-inset-bottom))] nav:bottom-6 nav:items-end nav:px-6"
      >
        {items.map((n) => (
          <Toast
            key={n.id}
            tone={n.tone}
            titre={n.titre}
            message={n.message}
            action={n.action ? {
              libelle: n.action.libelle,
              // Relancer ferme la carte : la suivante dira le nouveau résultat.
              onClick: () => { fermer(n.id); n.action.onClick?.() },
            } : null}
            onClose={() => fermer(n.id)}
            className="w-full max-w-[420px]"
          />
        ))}
      </div>
    </Contexte.Provider>
  )
}

/**
 * Sans fournisseur au-dessus — prévisualisation, test de composant isolé — rend
 * un notifieur muet, `actif: false` : l'appelant garde alors son message en
 * ligne. Un écran ne casse jamais parce qu'il ignore les notifications.
 */
export function useNotifier() {
  return useContext(Contexte) ?? { notifier: () => null, fermer: () => {}, actif: false }
}
