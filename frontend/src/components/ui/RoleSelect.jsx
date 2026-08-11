import { useState } from 'react'
import { ChevronDown, Check } from 'lucide-react'
import { Pop } from './Pop.jsx'
import { libelleRole, teinteRole } from '../../lib/roles.js'

// Classes écrites en toutes lettres : Tailwind analyse le source statiquement
// et ne génère rien pour une classe construite dynamiquement (cf. Pop.jsx).
const TINTS = {
  brand: { box: 'bg-brand-soft', icon: 'text-brand' },
  blue: { box: 'bg-blue-soft', icon: 'text-blue' },
  violet: { box: 'bg-violet-soft', icon: 'text-violet' },
  amber: { box: 'bg-amber-soft', icon: 'text-amber' },
  red: { box: 'bg-red-soft', icon: 'text-red' },
}

/**
 * Sélecteur de rôle enrichi (icône + description par option) — porté depuis
 * `RoleSelect` de la maquette `web-account.jsx` [US-055]. Remplace la liste
 * déroulante générique (`Select`) pour l'invitation d'un membre : chaque
 * option affiche l'effet concret du rôle plutôt que son seul nom.
 *
 * `options` : `[{ value, icon, sub }]` — libellé et teinte dérivés de
 * `lib/roles.js` (source unique déjà partagée avec PotagerMenu/AccountMenu).
 */
export function RoleSelect({ value, options, onChange, className = '' }) {
  const [open, setOpen] = useState(false)
  const courant = options.find((o) => o.value === value) || options[0]
  const CourantIcon = courant.icon
  const t = TINTS[teinteRole(courant.value)]

  return (
    <div className={`relative flex-1 min-w-[210px] ${className}`}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="listbox"
        aria-expanded={open}
        className={`w-full flex items-center gap-2.5 px-2.5 py-2 rounded-[11px] bg-card border-[1.5px] text-left transition-shadow ${
          open ? 'border-brand shadow-[0_0_0_3px_var(--brand-soft)]' : 'border-border'
        }`}
      >
        <span className={`w-[26px] h-[26px] rounded-lg flex items-center justify-center shrink-0 ${t.box}`}>
          <CourantIcon size={15} className={t.icon} />
        </span>
        <span className="flex-1 min-w-0">
          <span className="block text-[13px] font-bold text-txt">{libelleRole(courant.value)}</span>
          <span className="block text-[11.5px] text-txt2 mt-px truncate">{courant.sub}</span>
        </span>
        <ChevronDown size={15} className={`text-txt2 shrink-0 transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>

      {open && (
        // [Fix] `placement="above"` : ce sélecteur vit typiquement en bas d'une
        // modale scrollable (panneau « Inviter un membre ») — ouvrir vers le bas
        // fait couper le menu par le conteneur `overflow-y-auto` de `Modal`.
        <Pop width="100%" placement="above" onClose={() => setOpen(false)}>
          <div role="listbox" className="p-1">
            {options.map((o) => {
              const on = o.value === value
              const ot = TINTS[teinteRole(o.value)]
              const Icon = o.icon
              return (
                <button
                  key={o.value}
                  type="button"
                  role="option"
                  aria-selected={on}
                  onClick={() => {
                    onChange(o.value)
                    setOpen(false)
                  }}
                  className={`w-full flex items-center gap-2.5 px-2.5 py-2 rounded-[9px] text-left ${
                    on ? 'bg-brand-soft' : 'hover:bg-card-alt'
                  }`}
                >
                  <span className={`w-[26px] h-[26px] rounded-lg flex items-center justify-center shrink-0 ${ot.box}`}>
                    <Icon size={15} className={ot.icon} />
                  </span>
                  <span className="flex-1 min-w-0">
                    <span className={`block text-[13px] text-txt ${on ? 'font-bold' : 'font-semibold'}`}>
                      {libelleRole(o.value)}
                    </span>
                    <span className="block text-[11.5px] text-txt2 mt-px leading-snug">{o.sub}</span>
                  </span>
                  {on && <Check size={16} strokeWidth={2.4} className="text-brand shrink-0" />}
                </button>
              )
            })}
          </div>
        </Pop>
      )}
    </div>
  )
}

export default RoleSelect
