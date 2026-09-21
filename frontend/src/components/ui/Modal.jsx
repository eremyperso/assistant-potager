import { useEffect, useRef } from 'react'
import { X } from 'lucide-react'

/**
 * Fenêtre modale du design system [US-055].
 *
 * Extraite de `LierTelegram`/`GestionMembres` lors de leur restylage sur le
 * modèle `Modal` de la maquette 2026 (`web-account.jsx`) — en-tête à pastille
 * d'icône sur fond `brand-soft`, corps scrollable, pied optionnel.
 *
 * [US-183 / CA3] `disposition="adaptative"` : feuille plein écran sous 480 px,
 * modale centrée en tablette, panneau latéral droit à partir de `lg` — la
 * disposition de la maquette gelée de la fiche calendrier. Ce sont des
 * breakpoints d'ÉCRAN, à bon droit : une surcouche occupe la page, pas un
 * conteneur. `centree` (défaut) garde le comportement historique.
 *
 * [US-183 / CA15] Échap ferme la fenêtre, quelle que soit la disposition.
 *
 * [US-195 / CA8] Deux fiches peuvent s'empiler (fiche culture puis fiche
 * calendrier) : Échap ne ferme alors que **la plus haute**. Chaque fenêtre
 * ouverte s'inscrit dans `PILE` et n'écoute la touche que si elle est au sommet
 * — sans quoi les deux se fermeraient d'un coup. À la fermeture, le focus
 * clavier revient sur l'élément qui l'avait avant l'ouverture : fermer une fiche
 * rend l'écran dans son état exact.
 */

/** Les fenêtres modales ouvertes, de la plus ancienne à la plus haute. */
const PILE = []
const DISPOSITIONS = {
  centree: {
    fond: 'items-center justify-center p-5',
    boite: 'rounded-[18px] max-h-full',
  },
  // [US-180, maquette gelée] « Pourquoi ce niveau ? » : feuille posée en bas
  // de l'écran sur mobile, modale centrée au-delà.
  basse: {
    fond: 'items-end justify-center min-[480px]:items-center min-[480px]:p-5',
    boite: 'rounded-t-[18px] min-[480px]:rounded-[18px] max-h-[90%] min-[480px]:max-w-[420px]',
  },
  adaptative: {
    fond: 'min-[480px]:items-center min-[480px]:justify-center min-[480px]:p-5 lg:p-0 lg:items-stretch lg:justify-end',
    boite: 'h-full min-[480px]:h-auto min-[480px]:max-h-[calc(100%-48px)] min-[480px]:rounded-[18px] lg:h-full lg:max-h-full lg:rounded-none lg:border-l lg:border-border min-[480px]:max-w-[560px] lg:max-w-[460px]',
  },
}

export function Modal({
  title,
  icon: Icon,
  sub,
  onClose,
  width = 460,
  children,
  foot,
  bodyClassName = 'p-4 overflow-y-auto min-h-0',
  disposition = 'centree',
}) {
  const jeton = useRef({})

  useEffect(() => {
    const moi = jeton.current
    const precedent = typeof document !== 'undefined' ? document.activeElement : null
    PILE.push(moi)
    return () => {
      const i = PILE.indexOf(moi)
      if (i >= 0) PILE.splice(i, 1)
      // [US-195 / CA8] Le focus retourne d'où il venait — la carte, le bouton
      // ou la ligne qui a ouvert la fiche.
      if (precedent?.isConnected) precedent.focus?.()
    }
  }, [])

  useEffect(() => {
    if (!onClose) return undefined
    const surTouche = (e) => {
      // [US-195 / CA8] Seule la fenêtre au SOMMET de la pile répond à Échap.
      if (e.key === 'Escape' && PILE[PILE.length - 1] === jeton.current) onClose()
    }
    window.addEventListener('keydown', surTouche)
    return () => window.removeEventListener('keydown', surTouche)
  }, [onClose])

  const d = DISPOSITIONS[disposition] || DISPOSITIONS.centree
  return (
    <div
      className={`fixed inset-0 z-50 flex ${d.fond}`}
      style={{ background: 'rgba(12,18,8,.55)' }}
      onClick={onClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={typeof title === 'string' ? title : undefined}
        className={`bg-card w-full flex flex-col overflow-hidden shadow-[0_30px_80px_rgba(0,0,0,.35)] ${d.boite}`}
        // Les dispositions `basse` et `adaptative` portent leurs largeurs en classes.
        style={disposition === 'centree' ? { maxWidth: width } : undefined}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center gap-2.5 px-4 py-3.5 border-b border-border bg-brand-soft">
          {Icon && (
            <div className="w-8 h-8 rounded-[9px] bg-card flex items-center justify-center shrink-0">
              <Icon size={17} className="text-brand" />
            </div>
          )}
          <div className="flex-1 min-w-0">
            <div className="font-serif text-[16.5px] font-bold text-txt truncate">{title}</div>
            {sub && <div className="text-xs text-txt3 mt-px truncate">{sub}</div>}
          </div>
          <button onClick={onClose} aria-label="Fermer" className="shrink-0 text-txt2 hover:text-txt">
            <X size={18} />
          </button>
        </div>

        <div className={bodyClassName}>{children}</div>

        {foot && <div className="px-4 py-3 border-t border-border bg-card-alt text-[12px] text-txt3">{foot}</div>}
      </div>
    </div>
  )
}

export default Modal
