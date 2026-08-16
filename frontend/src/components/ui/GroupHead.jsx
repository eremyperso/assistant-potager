import { useState } from 'react'
import { ChevronDown, Leaf } from 'lucide-react'

/**
 * En-tête de groupe repliable du design system — porté depuis `GroupHead`
 * (`web-parts.jsx` de la maquette 2026), utilisé par les écrans qui regroupent
 * leurs cartes par famille botanique [US-061].
 *
 * Le chevron pivote au lieu de changer d'icône, et la marge basse ne s'applique
 * qu'à l'état ouvert : replié, l'en-tête colle au suivant.
 */
export function GroupHead({ label, count, right, open, onToggle }) {
  return (
    <button
      onClick={onToggle}
      aria-expanded={open}
      className={`w-full flex items-center gap-2.5 pb-2.5 border-b border-border text-left ${open ? 'mb-3' : 'mb-0'}`}
    >
      <ChevronDown
        size={15}
        strokeWidth={2.2}
        className={`text-txt3 shrink-0 transition-transform duration-200 ${open ? '' : '-rotate-90'}`}
      />
      <Leaf size={18} className="text-brand shrink-0" />
      <span className="font-serif text-[19px] font-semibold text-txt tracking-[-0.015em] truncate">{label}</span>
      <span className="text-[13px] text-txt3 shrink-0">({count})</span>
      {right && <span className="ml-auto text-[12.5px] text-txt3 shrink-0">{right}</span>}
    </button>
  )
}

/**
 * État d'ouverture des groupes — tout est ouvert par défaut, seul le repli est
 * mémorisé (même parti pris que `useGroups` dans la maquette).
 */
export function useGroups() {
  const [closed, setClosed] = useState({})
  return [
    (k) => !closed[k],
    (k) => setClosed((c) => ({ ...c, [k]: !c[k] })),
  ]
}

export default GroupHead
