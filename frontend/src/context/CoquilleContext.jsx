import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'
import { cleMasque } from '../lib/motDeGaston.js'

/**
 * La coquille commune [US-353] : ce que chaque vue DÉCLARE à l'écran qui l'enveloppe, et le panneau
 * partagé.
 *
 * - **Déclaration d'écran** : le Mot de Gaston (`mot`, rendu de `calculerMot`) et la barre d'outils
 *   (`barre` : recherche, filtre, menu ⋯, date). La vue la publie par `useDeclarerEcran`, la
 *   coquille la dessine dans les bandes FIXES — la vue ne dessine plus ni son mot ni sa barre.
 * - **Panneau partagé** : un seul occupant à la fois (fiche commune, fiche catalogue, Récoltes par
 *   saison…) ; Gaston en est un autre, tenu par `App.jsx` (voir `compagnon`).
 */
const CoquilleContext = createContext(null)

export function useCoquille() {
  const ctx = useContext(CoquilleContext)
  if (!ctx) throw new Error('useCoquille doit être utilisé dans <CoquilleProvider>')
  return ctx
}

const lireMasques = () => {
  try { return sessionStorage }
  catch { return null }
}

export function CoquilleProvider({ children }) {
  const [declaration, setDeclaration] = useState(null)
  const [masques, setMasques] = useState(() => new Set())
  const [occupant, setOccupant] = useState(null)   // { cle, titre, contenu } | null
  // [US-360] Le nœud DOM où une vue dessine le contenu de l'occupant (portail React) : la vue garde
  // ses états et ses gestionnaires à jour, sans republier un élément dans le contexte à chaque rendu.
  const [hote, setHote] = useState(null)

  /** [CA6] Le × masque le mot pour la session et pour cette vue. */
  const masquerMot = useCallback((vue) => {
    try { lireMasques()?.setItem(cleMasque(vue), '1') } catch { /* sans stockage : masqué pour cette page seulement */ }
    setMasques((m) => new Set(m).add(vue))
  }, [])

  const motMasque = useCallback((vue) => {
    if (masques.has(vue)) return true
    try { return lireMasques()?.getItem(cleMasque(vue)) === '1' } catch { return false }
  }, [masques])

  const ouvrirPanneau = useCallback((o) => setOccupant(o), [])
  const fermerPanneau = useCallback(() => setOccupant(null), [])

  const valeur = useMemo(() => ({
    declaration, setDeclaration, masquerMot, motMasque, occupant, ouvrirPanneau, fermerPanneau, hote, setHote,
  }), [declaration, masquerMot, motMasque, occupant, ouvrirPanneau, fermerPanneau, hote])

  return <CoquilleContext.Provider value={valeur}>{children}</CoquilleContext.Provider>
}

/**
 * [US-360] Le contenu d'un occupant « à portail » : un nœud vide que la coquille pose dans le
 * panneau et que la vue remplit par `createPortal(contenu, hote)`. Utilisation :
 *   ouvrirPanneau({ cle: 'fiche', titre, contenu: <HotePanneau /> })
 *   … {hote && createPortal(<MaFiche />, hote)}
 */
export function HotePanneau() {
  const { setHote } = useCoquille()
  return <div ref={setHote} className="flex min-h-0 flex-1 flex-col" data-hote-panneau="" />
}

/**
 * Publie la déclaration de l'écran (`{ mot, barre }`) tant que la vue est montée, et la retire à son
 * démontage. `deps` fait comme celles d'un `useEffect` : la déclaration est republiée quand elles
 * changent (les gestionnaires qu'elle porte doivent donc y figurer, ou rester stables).
 */
export function useDeclarerEcran(declaration, deps = []) {
  const { setDeclaration } = useCoquille()
  const derniere = useRef(declaration)
  derniere.current = declaration
  useEffect(() => {
    setDeclaration(derniere.current)
    return () => setDeclaration(null)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)
}

export default CoquilleContext
