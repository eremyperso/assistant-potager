import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'
import { validerIntention, creerMemoireEcrans, etatInitial } from '../lib/intentions.js'

/**
 * Navigation contextuelle de la coquille [US-195].
 *
 * La coquille d'US-053 ne savait que changer de vue. Elle sait maintenant en
 * ouvrir une **en lui passant un contexte** — la bonne parcelle, le bon lot, le
 * journal du bon jour — et **rendre un écran quitté dans son état exact**.
 *
 * Aucun routeur (CA10) : `aller()` reste un `setState`, le bouton Retour du
 * navigateur garde son comportement. Tout ce qui est mémorisé vit dans la page
 * et meurt avec elle (CA9).
 */
const NavigationContext = createContext(null)

export function useNavigation() {
  const ctx = useContext(NavigationContext)
  if (!ctx) throw new Error('useNavigation doit être utilisé dans <NavigationProvider>')
  return ctx
}

export function NavigationProvider({
  vue, onVue, vueValide = () => true, intentionInitiale = null, children,
}) {
  // L'intention en attente d'être appliquée, et la vue à laquelle elle est
  // destinée. `null` dès qu'elle a été consommée (CA1).
  const [enAttente, setEnAttente] = useState(() =>
    intentionInitiale?.vue
      ? { vue: intentionInitiale.vue, intention: validerIntention(intentionInitiale.vue, intentionInitiale.intention) }
      : null
  )
  const [message, setMessage] = useState('')
  const [annonce, setAnnonce] = useState('')
  const memoire = useRef(creerMemoireEcrans())

  /**
   * [CA1] Ouvrir une vue, avec ou sans intention. L'intention est validée ICI —
   * une clé inconnue ou une valeur invalide est écartée avant d'atteindre la vue.
   */
  const aller = useCallback((cible, intention) => {
    if (!vueValide(cible)) return
    const propre = validerIntention(cible, intention)
    setEnAttente(propre ? { vue: cible, intention: propre } : null)
    setMessage('')
    onVue(cible)
  }, [onVue, vueValide])

  /** [CA3] Ce qu'une intention n'a pas pu désigner — dit en clair, jamais une erreur. */
  const signaler = useCallback((texte) => {
    setMessage(texte || '')
    setAnnonce(texte || '')
  }, [])

  /** [CA4] Annonce aux lecteurs d'écran l'arrivée sur ce que l'intention désignait. */
  const annoncer = useCallback((texte) => setAnnonce(texte || ''), [])

  // [CA3, CA4] Message et annonce portent sur l'intention qui vient d'aboutir ou
  // d'échouer, pas sur l'écran : changer de vue les périme, quel que soit le
  // chemin emprunté — `aller()` comme les onglets de navigation. Une annonce
  // laissée en place serait relue plus tard, hors de son contexte.
  const premiere = useRef(true)
  useEffect(() => {
    if (premiere.current) { premiere.current = false; return }
    setMessage('')
    setAnnonce('')
  }, [vue])

  const valeur = useMemo(() => ({
    vue,
    aller,
    message,
    signaler,
    annoncer,
    effacerMessage: () => setMessage(''),
    // Réservé aux hooks ci-dessous — les écrans passent par `useIntention`.
    _enAttente: enAttente,
    _consommer: () => setEnAttente(null),
    _memoire: memoire.current,
  }), [vue, aller, message, signaler, annoncer, enAttente])

  return (
    <NavigationContext.Provider value={valeur}>
      {children}
      {/* [CA4] Région d'annonce unique de la coquille : l'arrivée d'une intention
          et l'échec d'une intention s'y disent, sans voler le focus. */}
      <p aria-live="polite" className="sr-only">{annonce}</p>
    </NavigationContext.Provider>
  )
}

/**
 * [CA1] L'intention destinée à cet écran, appliquée **une fois** puis consommée.
 *
 * `appliquer` reçoit l'intention nettoyée. Revenir plus tard sur l'écran par la
 * navigation normale ne la rejoue pas : elle n'existe plus.
 */
export function useIntention(vue, appliquer) {
  const { _enAttente, _consommer } = useNavigation()
  const aJour = useRef(appliquer)
  aJour.current = appliquer

  const recue = _enAttente?.vue === vue ? _enAttente.intention : null
  // L'intention est CONSOMMÉE tout de suite au niveau de la coquille — plus
  // personne ne la rejouera — mais l'écran la garde tant qu'il est monté : ses
  // données arrivent souvent après (`GET /pepiniere/lots`), et il doit pouvoir
  // dire alors que ce qu'elle désignait n'existe plus (CA3).
  const [gardee, setGardee] = useState(recue)

  useEffect(() => {
    if (!recue) return
    setGardee(recue)
    aJour.current?.(recue)
    _consommer()
  }, [recue])

  return gardee
}

/**
 * [CA8, CA9] L'état d'écran qui survit à un aller-retour : le même couple
 * `[etat, setEtat]` qu'un `useState`, mais relu de la mémoire de session au
 * montage et réécrit à chaque changement.
 *
 * `intention` (celle que `useIntention` vient de rendre) l'emporte sur ce dont
 * on se souvient — c'est la règle 25 de la v4 croisée avec le CA1.
 *
 * Y mettre ce qui fait l'état exact d'un écran : sous-onglet, sélection,
 * recherche, tri, filtre, position de défilement. Jamais les données chargées.
 */
export function useEtatEcran(vue, defauts, intention = null) {
  const { _memoire } = useNavigation()
  const [etat, setEtatBrut] = useState(() =>
    etatInitial({ defauts, memorise: _memoire.lire(vue), intention })
  )

  const setEtat = useCallback((maj) => {
    setEtatBrut((prec) => {
      const suivant = typeof maj === 'function' ? maj(prec) : { ...prec, ...maj }
      _memoire.ecrire(vue, suivant)
      return suivant
    })
  }, [vue, _memoire])

  // L'état de départ est mémorisé lui aussi : quitter un écran sans y avoir
  // rien touché doit quand même le rendre tel qu'on l'a laissé.
  useEffect(() => { _memoire.ecrire(vue, etat) }, [])

  return [etat, setEtat]
}

export default NavigationContext
