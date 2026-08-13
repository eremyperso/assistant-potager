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

/**
 * Couleur de la valeur elle-même [US-059] — distincte de `tint`, qui colore la
 * pastille d'icône. Une tuile sans icône n'a que ce levier pour porter le sens
 * d'un chiffre (un total perdu en rouge, par exemple).
 *
 * La prop `valueColor` accepte en plus une couleur CSS brute. C'est l'échappatoire
 * laissée aux écrans du Lot B pas encore migrés, qui passent encore leur propre
 * couleur au bandeau de métriques : elle évite que les composants transverses
 * aient à connaître les anciens alias pour les traduire. À retirer en même temps
 * que le bloc d'alias `--g-*` (Lot D, cf. §7.4 de l'analyse de refonte).
 */
const TONES = {
  txt: 'text-txt',
  txt2: 'text-txt2',
  txt3: 'text-txt3',
  brand: 'text-brand',
  'brand-text': 'text-brand-text',
  amber: 'text-amber',
  red: 'text-red',
  blue: 'text-blue',
  violet: 'text-violet',
}

export function Stat({
  icon: Icon,
  tint = 'brand',
  tone = 'txt',
  valueColor,
  value,
  unit,
  label,
  tip,
  className = '',
}) {
  return (
    <div
      className={`@container/stat bg-card border border-border rounded-2xl shadow-card px-4 py-3.5 ${className}`}
    >
      {/* Mobile-first : empilé dans une tuile étroite, en ligne dès 13rem de large
          (variantes `min-width` uniquement, cf. commentaire dans InfoBanner). */}
      <div className="flex flex-col items-start gap-3 @[13rem]/stat:flex-row @[13rem]/stat:items-center">
        {Icon && (
          <div className={`w-11 h-11 rounded-xl flex items-center justify-center shrink-0 ${TINTS[tint]}`}>
            <Icon size={21} />
          </div>
        )}
        <div className="min-w-0">
          <div className="flex items-baseline gap-1">
            <span
              className={`text-[25px] font-bold tracking-tight leading-tight ${TONES[tone] ?? TONES.txt}`}
              style={valueColor ? { color: valueColor } : undefined}
            >
              {value}
            </span>
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
