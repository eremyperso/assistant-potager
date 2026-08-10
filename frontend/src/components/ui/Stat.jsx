import { Tip } from './Tip.jsx'

/**
 * Tuile de statistique du design system [US-052] : icône, valeur, unité, libellé.
 *
 * `@container/stat` : sous 13rem de large, la tuile passe en pile verticale
 * plutôt que de comprimer la valeur — indépendant de la taille de l'écran.
 */
const TINTS = {
  brand: 'bg-brand-soft text-brand',
  amber: 'bg-amber-soft text-amber',
  red: 'bg-red-soft text-red',
  blue: 'bg-blue-soft text-blue',
  violet: 'bg-violet-soft text-violet',
}

export function Stat({ icon: Icon, tint = 'brand', value, unit, label, tip, className = '' }) {
  return (
    <div
      className={`@container/stat bg-card border border-border rounded-2xl shadow-card px-4 py-3.5 ${className}`}
    >
      <div className="flex items-center gap-3 @max-[13rem]/stat:flex-col @max-[13rem]/stat:items-start">
        {Icon && (
          <div className={`w-11 h-11 rounded-xl flex items-center justify-center shrink-0 ${TINTS[tint]}`}>
            <Icon size={21} />
          </div>
        )}
        <div className="min-w-0">
          <div className="flex items-baseline gap-1">
            <span className="text-[25px] font-bold text-txt tracking-tight leading-tight">{value}</span>
            {unit && <span className="text-[13px] font-semibold text-txt3">{unit}</span>}
          </div>
          <div className="text-[12.5px] text-txt2 mt-0.5 flex items-center gap-1.5">
            {label}
            {tip && <Tip text={tip} />}
          </div>
        </div>
      </div>
    </div>
  )
}

export default Stat
