import { X, CheckCircle2, AlertCircle, AlertTriangle, Info } from 'lucide-react'

/**
 * Notification éphémère du design system — la confirmation d'une action.
 *
 * Même vocabulaire que `InfoBanner` (teintes `*-soft`, pastille d'icône sur
 * `bg-card`, croix) : seule la mise en page change, une carte compacte posée
 * par-dessus l'écran plutôt qu'un bandeau dans le flux.
 *
 * `role="alert"` pour une erreur (annoncée tout de suite), `role="status"`
 * sinon (annoncée poliment, sans couper la lecture en cours).
 */
const TINTS = {
  brand: { box: 'bg-brand-soft', icon: 'text-brand', title: 'text-brand-text', Icone: CheckCircle2 },
  amber: { box: 'bg-amber-soft', icon: 'text-amber', title: 'text-amber', Icone: AlertTriangle },
  red: { box: 'bg-red-soft', icon: 'text-red', title: 'text-red', Icone: AlertCircle },
  blue: { box: 'bg-blue-soft', icon: 'text-blue', title: 'text-blue', Icone: Info },
}

export function Toast({ tone = 'brand', titre, message, action, onClose, className = '' }) {
  const t = TINTS[tone] ?? TINTS.brand
  const Icone = t.Icone
  return (
    <div
      role={tone === 'red' ? 'alert' : 'status'}
      className={`pointer-events-auto flex items-start gap-3 rounded-2xl px-3.5 py-3 border border-border shadow-[0_18px_46px_rgba(12,18,8,.26)] bg-card ${className}`}
    >
      <div className={`w-8 h-8 rounded-[9px] flex items-center justify-center shrink-0 ${t.box}`}>
        <Icone size={17} className={t.icon} aria-hidden="true" />
      </div>
      <div className="flex-1 min-w-0">
        <div className={`text-sm font-bold ${t.title} dark:text-txt`}>{titre}</div>
        {message && (
          <div className="text-[12.5px] mt-0.5 leading-relaxed text-txt2 break-words">{message}</div>
        )}
        {action && (
          <button
            type="button"
            onClick={action.onClick}
            className={`mt-1.5 min-h-[32px] text-[12.5px] font-semibold ${t.title} dark:text-txt underline underline-offset-2`}
          >
            {action.libelle}
          </button>
        )}
      </div>
      {onClose && (
        <button
          type="button"
          onClick={onClose}
          aria-label="Fermer la notification"
          className="shrink-0 p-1 -m-1 text-txt3 hover:text-txt"
        >
          <X size={16} aria-hidden="true" />
        </button>
      )}
    </div>
  )
}

export default Toast
