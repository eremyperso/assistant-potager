// [US-352 / CA4] L'infobulle d'étape : survol à la souris, APPUI LONG DE 380 ms au doigt,
// sur une pastille, un rang du plan ou une case du calendrier. Tout élément qui porte
// `data-tip="…"` en bénéficie ; `components/ui/InfobulleEtapes.jsx` l'écoute une fois pour toutes.
//
// Ce fichier ne touche pas au DOM : il porte la machine à états de l'appui long (déclenchement,
// annulation au déplacement, suppression du clic qui suit) avec des horloges injectables.

/** Délai de l'appui long (CA4). */
export const DELAI_APPUI_LONG_MS = 380
/** Un doigt qui bouge de plus de ce nombre de pixels fait défiler la page : ce n'est plus un appui long. */
export const TOLERANCE_DEPLACEMENT_PX = 10
/** Durée pendant laquelle la bulle reste affichée après le relâchement du doigt. */
export const PERSISTANCE_BULLE_MS = 900
/** Durée pendant laquelle le clic qui suit un appui long est avalé. */
export const FENETRE_CLIC_AVALE_MS = 700

/** Le nom de l'attribut qui porte le texte d'une infobulle. */
export const ATTRIBUT_INFOBULLE = 'data-tip'

/**
 * La machine de l'appui long. `surDeclenche(cible)` s'appelle quand les 380 ms sont écoulées sans
 * relâchement ni déplacement ; `surFin()` quand la bulle doit disparaître.
 * Les horloges sont injectables pour les tests (`setTimeout` / `clearTimeout` / `now`).
 */
export function creerAppuiLong({
  surDeclenche,
  surFin = () => {},
  delai = DELAI_APPUI_LONG_MS,
  persistance = PERSISTANCE_BULLE_MS,
  fenetreClic = FENETRE_CLIC_AVALE_MS,
  // Enveloppées : `window.setTimeout` appelée comme méthode d'un autre objet lève « Illegal invocation ».
  horloge = {
    setTimeout: (fn, ms) => setTimeout(fn, ms),
    clearTimeout: (id) => clearTimeout(id),
    now: () => Date.now(),
  },
} = {}) {
  let minuteur = null
  let fin = null
  let origine = null
  let declenche = false
  let finDeFenetre = 0

  const annuler = () => {
    if (minuteur) horloge.clearTimeout(minuteur)
    minuteur = null
    origine = null
  }

  return {
    /** Un doigt (ou un bouton) se pose sur `cible`, aux coordonnées (x, y). */
    debut(cible, x = 0, y = 0) {
      if (fin) horloge.clearTimeout(fin)
      fin = null
      annuler()
      declenche = false
      if (!cible) return
      origine = { x, y }
      minuteur = horloge.setTimeout(() => {
        minuteur = null
        declenche = true
        finDeFenetre = horloge.now() + fenetreClic
        surDeclenche(cible)
      }, delai)
    },
    /** Le pointeur bouge : au-delà de la tolérance, c'est un défilement. */
    deplacement(x, y) {
      if (!origine || declenche) return
      if (Math.hypot(x - origine.x, y - origine.y) > TOLERANCE_DEPLACEMENT_PX) annuler()
    },
    /** Le doigt se relève, ou le geste est interrompu. */
    fin() {
      annuler()
      if (declenche && !fin) {
        fin = horloge.setTimeout(() => { fin = null; declenche = false; surFin() }, persistance)
      }
    },
    /** Faut-il avaler le clic qui vient d'arriver ? Vrai juste après un appui long (CA4 : il n'ouvre pas ce qui est dessous). */
    avaleLeClic() {
      return declenche || horloge.now() < finDeFenetre
    },
    /** Un appui long est en cours ou vient d'avoir lieu. */
    get actif() { return declenche },
  }
}

/** Le texte d'une infobulle d'après l'élément qui la porte (ou un de ses parents), sinon `''`. */
export function texteInfobulle(element) {
  const porteur = element?.closest?.(`[${ATTRIBUT_INFOBULLE}]`)
  return porteur?.getAttribute?.(ATTRIBUT_INFOBULLE) || ''
}

/**
 * La position de la bulle : centrée au-dessus de la cible, rabattue en dessous si elle sortirait
 * de l'écran par le haut, et gardée à 8 px des bords horizontaux.
 */
export function positionBulle(rect, { largeurBulle = 160, hauteurBulle = 28, largeurEcran = 375 } = {}) {
  const marge = 8
  const centre = rect.left + rect.width / 2
  const x = Math.min(Math.max(centre, marge + largeurBulle / 2), largeurEcran - marge - largeurBulle / 2)
  const dessus = rect.top - hauteurBulle - marge
  return dessus >= marge
    ? { x, y: dessus, sous: false }
    : { x, y: rect.bottom + marge, sous: true }
}
