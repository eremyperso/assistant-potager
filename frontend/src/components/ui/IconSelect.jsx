import { useState } from 'react'
import { Filter, Check } from 'lucide-react'
import { Pop } from './Pop.jsx'

// Classes écrites en toutes lettres : Tailwind analyse le source statiquement et
// ne génère rien pour une classe construite dynamiquement (cf. Pop.jsx, RoleSelect).
const TINTS = {
  brand:  { box: 'bg-brand-soft',  icon: 'text-brand'  },
  amber:  { box: 'bg-amber-soft',  icon: 'text-amber'  },
  red:    { box: 'bg-red-soft',    icon: 'text-red'    },
  blue:   { box: 'bg-blue-soft',   icon: 'text-blue'   },
  violet: { box: 'bg-violet-soft', icon: 'text-violet' },
  neutre: { box: 'bg-card-alt',    icon: 'text-txt3'   },
}

/**
 * Liste déroulante à pastilles d'icônes colorées — portage d'`IconSelect`
 * (`web-parts.jsx`, maquette 2026) [US-063].
 *
 * Distinct de `Select` (liste déroulante native) : chaque option porte l'icône et
 * la teinte de ce qu'elle désigne, de sorte que le menu de filtre affiche la même
 * grammaire visuelle que les lignes qu'il filtre. À réserver aux filtres dont les
 * valeurs ont déjà une identité visuelle ailleurs dans l'écran ; pour un choix
 * sans iconographie, `Select` reste le bon composant.
 *
 * `options` : `[{ value, label, icon, tint }]` — `icon`/`tint` optionnels
 * (pastille neutre à défaut, comme l'entrée « Toutes les actions » de la maquette).
 */
export function IconSelect({ value, options, onChange, className = '', 'aria-label': ariaLabel }) {
  const [open, setOpen] = useState(false)
  const courant = options.find((o) => o.value === value) || options[0]
  const CourantIcon = courant?.icon || Filter

  return (
    <div className={`relative ${className}`}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-label={ariaLabel}
        className="inline-flex items-center gap-2 h-[38px] px-3 rounded-[10px] bg-card border border-border text-txt2 text-[13.5px] font-semibold whitespace-nowrap"
      >
        <CourantIcon size={16} className="text-txt3 shrink-0" />
        <span>{courant?.label}</span>
      </button>

      {open && (
        <Pop width={210} onClose={() => setOpen(false)}>
          <div role="listbox" className="p-1.5 flex flex-col gap-px">
            {options.map((o) => {
              const on = o.value === value
              const t = TINTS[o.tint] || TINTS.neutre
              const Icon = o.icon
              return (
                <button
                  key={o.label}
                  type="button"
                  role="option"
                  aria-selected={on}
                  onClick={() => {
                    onChange(o.value)
                    setOpen(false)
                  }}
                  className={`w-full flex items-center gap-2.5 px-2 py-1.5 rounded-lg text-left text-[13px] ${
                    on ? 'bg-brand-soft text-brand-text font-semibold' : 'text-txt hover:bg-card-alt'
                  }`}
                >
                  <span className={`w-6 h-6 rounded-lg flex items-center justify-center shrink-0 ${t.box}`}>
                    {Icon && <Icon size={14} className={t.icon} />}
                  </span>
                  <span className="flex-1 min-w-0 truncate">{o.label}</span>
                  {on && <Check size={15} strokeWidth={2.4} className="text-brand shrink-0" />}
                </button>
              )
            })}
          </div>
        </Pop>
      )}
    </div>
  )
}

export default IconSelect
