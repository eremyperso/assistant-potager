import { X } from 'lucide-react'

/**
 * Fenêtre modale du design system [US-055].
 *
 * Extraite de `LierTelegram`/`GestionMembres` lors de leur restylage sur le
 * modèle `Modal` de la maquette 2026 (`web-account.jsx`) — en-tête à pastille
 * d'icône sur fond `brand-soft`, corps scrollable, pied optionnel.
 */
export function Modal({ title, icon: Icon, sub, onClose, width = 460, children, foot }) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-5"
      style={{ background: 'rgba(12,18,8,.55)' }}
      onClick={onClose}
    >
      <div
        className="bg-card rounded-[18px] w-full flex flex-col max-h-full overflow-hidden shadow-[0_30px_80px_rgba(0,0,0,.35)]"
        style={{ maxWidth: width }}
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

        <div className="p-4 overflow-y-auto min-h-0">{children}</div>

        {foot && <div className="px-4 py-3 border-t border-border bg-card-alt text-[12px] text-txt3">{foot}</div>}
      </div>
    </div>
  )
}

export default Modal
