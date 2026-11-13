import { useState } from 'react'
import { HelpCircle, ChevronDown } from 'lucide-react'

/**
 * Légende repliable sur mobile — règle commune à TOUTES les vues : sous 640 px la légende est
 * masquée derrière un bouton « Légende » qui la déploie ; à partir de `sm` elle reste toujours
 * visible, sans bouton (même seuil que l'écran Cultures).
 */
export function LegendeRepliable({ children, titre = 'Légende', className = '' }) {
  const [ouverte, setOuverte] = useState(false)
  return (
    <div className={className}>
      <button type="button" onClick={() => setOuverte((o) => !o)} aria-expanded={ouverte}
        className="sm:hidden inline-flex min-h-[36px] items-center gap-1.5 rounded-[10px] border border-border bg-card px-2.5 text-[12.5px] font-semibold text-txt2">
        <HelpCircle size={15} aria-hidden="true" />{titre}
        <ChevronDown size={14} aria-hidden="true" className={ouverte ? 'rotate-180' : ''} />
      </button>
      <div className={`${ouverte ? 'mt-2 block' : 'hidden'} sm:mt-0 sm:block`}>{children}</div>
    </div>
  )
}
