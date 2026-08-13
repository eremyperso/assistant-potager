import { useEffect, useRef } from 'react'

/**
 * Menu déroulant contextuel du design system [US-054].
 *
 * Se ferme au clic extérieur et à la touche Échap. Le conteneur parent doit
 * porter `relative` — le menu s'ancre sous le bouton déclencheur (`placement="above"`
 * pour l'ancrer au-dessus, ex. déclencheur en bas d'une modale scrollable où
 * l'espace sous le bouton est insuffisant, cf. `RoleSelect`).
 * Mutualisé avec le menu Compte (US-055).
 */
export function Pop({ align = 'left', placement = 'below', width = 286, onClose, children, className = '' }) {
  const ref = useRef(null)

  useEffect(() => {
    function auClicExterieur(e) {
      // Le déclencheur gère lui-même sa bascule : on ignore les clics qui le visent,
      // sinon ouverture et fermeture s'annuleraient sur le même clic.
      if (ref.current && !ref.current.parentElement.contains(e.target)) onClose?.()
    }
    function aLaToucheEchap(e) {
      if (e.key === 'Escape') onClose?.()
    }
    document.addEventListener('mousedown', auClicExterieur)
    document.addEventListener('keydown', aLaToucheEchap)
    return () => {
      document.removeEventListener('mousedown', auClicExterieur)
      document.removeEventListener('keydown', aLaToucheEchap)
    }
  }, [onClose])

  return (
    <div
      ref={ref}
      role="menu"
      className={`absolute z-50 max-w-[calc(100vw-1.5rem)] bg-card border border-border rounded-2xl shadow-[0_18px_46px_rgba(12,18,8,.26)] overflow-hidden ${
        placement === 'above' ? 'bottom-full mb-1.5' : 'top-full mt-1.5'
      } ${align === 'right' ? 'right-0' : 'left-0'} ${className}`}
      style={{ width }}
    >
      {children}
    </div>
  )
}

// Classes écrites en toutes lettres : Tailwind analyse le source statiquement et
// ne génère rien pour une classe construite dynamiquement (`text-${tint}`).
const TEINTES_ICONE = {
  brand: 'text-brand',
  amber: 'text-amber',
  red: 'text-red',
  blue: 'text-blue',
  violet: 'text-violet',
}

/**
 * Entrée de menu : icône, libellé, sous-libellé et zone droite optionnelle.
 *
 * `disabled` grise l'entrée sans la retirer du menu (fonctionnalité annoncée
 * mais pas encore disponible) ; `className` permet de restreindre une entrée à
 * une taille d'écran (ex. `nav:hidden` pour une action doublée dans le bandeau
 * en desktop) [US-055].
 */
export function PopItem({
  icon: Icon,
  label,
  sub,
  right,
  onClick,
  danger = false,
  disabled = false,
  tint,
  className = '',
}) {
  const couleurIcone = danger ? 'text-red' : TEINTES_ICONE[tint] || 'text-txt2'
  return (
    <button
      role="menuitem"
      onClick={onClick}
      disabled={disabled}
      aria-disabled={disabled || undefined}
      className={`w-full flex items-center gap-2.5 px-3.5 py-2.5 text-left transition-colors ${
        disabled ? 'opacity-45 cursor-default' : 'hover:bg-card-alt'
      } ${className}`}
    >
      {Icon && <Icon size={16} className={`shrink-0 ${couleurIcone}`} />}
      <span className="flex-1 min-w-0">
        <span className={`block text-[13.5px] font-medium truncate ${danger ? 'text-red' : 'text-txt'}`}>
          {label}
        </span>
        {sub && <span className="block text-[11.5px] text-txt3 truncate mt-px">{sub}</span>}
      </span>
      {right}
    </button>
  )
}

/** Intitulé de section dans un menu. */
export function PopHead({ children }) {
  return (
    <div className="px-3.5 pt-2.5 pb-2 text-[11px] font-bold text-txt3 uppercase tracking-wider">
      {children}
    </div>
  )
}

/** Séparateur entre deux groupes d'entrées. */
export function PopSep() {
  return <div className="h-px bg-border-soft" />
}

export default Pop
