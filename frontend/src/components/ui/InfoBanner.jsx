import { useState } from 'react'
import { X, HelpCircle } from 'lucide-react'

/**
 * Bandeau d'information contextuel du design system [US-052].
 *
 * `@container/banner` : sous 620px de large, le bouton d'action passe à la ligne
 * et occupe toute la largeur, le texte gardant une largeur minimale lisible
 * plutôt que d'être écrasé.
 */
const TINTS = {
  brand: { box: 'bg-brand-soft', icon: 'text-brand', title: 'text-brand-text' },
  amber: { box: 'bg-amber-soft', icon: 'text-amber', title: 'text-amber' },
  red: { box: 'bg-red-soft', icon: 'text-red', title: 'text-red' },
  blue: { box: 'bg-blue-soft', icon: 'text-blue', title: 'text-blue' },
  violet: { box: 'bg-violet-soft', icon: 'text-violet', title: 'text-violet' },
}

export function InfoBanner({
  title,
  body,
  action,
  onClose,
  tint = 'brand',
  icon: Icon = HelpCircle,
  dismissible = true,
  className = '',
}) {
  const [open, setOpen] = useState(true)
  if (!open) return null
  const t = TINTS[tint]

  return (
    <div
      className={`@container/banner flex flex-wrap items-start gap-3 rounded-2xl px-4 py-3.5 border border-transparent dark:border-border ${t.box} ${className}`}
    >
      <div className="w-8 h-8 rounded-[9px] bg-card flex items-center justify-center shrink-0">
        <Icon size={17} className={t.icon} />
      </div>
      <div className="flex-1 min-w-[190px]">
        <div className={`text-sm font-bold dark:text-txt ${t.title}`}>{title}</div>
        <div className={`text-[13px] mt-0.5 leading-relaxed opacity-90 dark:opacity-100 dark:text-txt2 ${t.title}`}>
          {body}
        </div>
      </div>
      {/* La croix reste sur la première ligne, à droite du texte : elle est placée
          avant l'action dans le DOM, sinon le passage à la ligne de celle-ci
          l'entraînerait sur une troisième ligne. */}
      {dismissible && (
        <button
          onClick={() => {
            setOpen(false)
            onClose?.()
          }}
          aria-label="Fermer"
          className="shrink-0 p-0.5 @[620px]/banner:order-last"
        >
          <X size={16} className={t.icon} />
        </button>
      )}
      {action && (
        // Mobile-first : pleine largeur sous le texte par défaut, puis remonté en
        // ligne dès 620px de large. Le plugin container-queries de Tailwind 3 ne
        // fournit que des variantes `min-width` — écrire `@max-[620px]:…` ne
        // génère aucune règle et ne produit donc aucun effet.
        <div className="flex basis-full mt-1 @[620px]/banner:basis-auto @[620px]/banner:mt-0">{action}</div>
      )}
    </div>
  )
}

export default InfoBanner
