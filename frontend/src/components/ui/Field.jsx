import { useState } from 'react'
import { Eye, EyeOff } from 'lucide-react'

/**
 * Champ de formulaire avec libellé du design system [US-056].
 *
 * Anneau de focus (`ring`) plutôt que simple changement de bordure — cohérent
 * avec le champ de connexion de la maquette. Le type "password" ajoute un
 * bouton d'affichage/masquage intégré (porté depuis `Auth.jsx` historique).
 */
export function Field({
  id,
  label,
  type = 'text',
  required = false,
  hint,
  right,
  icon: Icon,
  suffix,
  className = '',
  ...props
}) {
  const [afficher, setAfficher] = useState(false)
  const estMdp = type === 'password'

  return (
    <div className={className}>
      <label htmlFor={id} className="flex items-center gap-1.5 text-[12.5px] font-semibold text-txt2 mb-1.5">
        {label}
        {required && <span aria-hidden="true" className="text-red">*</span>}
        {right && <span className="ml-auto">{right}</span>}
      </label>
      <div className="flex items-center gap-2 bg-card border border-border rounded-[11px] h-[46px] px-3 has-[input:focus]:border-brand has-[input:focus]:ring-[3px] has-[input:focus]:ring-brand-soft transition-shadow">
        {Icon && <Icon size={16} className="text-txt3 shrink-0" />}
        <input
          id={id}
          type={estMdp && afficher ? 'text' : type}
          required={required}
          className="flex-1 min-w-0 h-full border-none outline-none bg-transparent text-[14.5px] text-txt placeholder:text-txt3"
          {...props}
        />
        {suffix && <span className="text-[13px] text-txt3 font-semibold shrink-0">{suffix}</span>}
        {estMdp && (
          <button
            type="button"
            onClick={() => setAfficher((v) => !v)}
            aria-label={afficher ? 'Masquer le mot de passe' : 'Afficher le mot de passe'}
            aria-pressed={afficher}
            className="w-[30px] h-[30px] rounded-lg flex items-center justify-center shrink-0 text-txt3"
          >
            {afficher ? <EyeOff size={17} /> : <Eye size={17} />}
          </button>
        )}
      </div>
      {hint && <div className="text-[11.5px] text-txt3 mt-1">{hint}</div>}
    </div>
  )
}

export default Field
