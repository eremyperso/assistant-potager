/**
 * Bouton du design system [US-052] — 4 variantes : primary, ghost, soft, quiet.
 */
const KINDS = {
  primary: 'bg-brand text-white dark:text-bg border border-brand',
  ghost: 'bg-card text-txt2 border border-border',
  soft: 'bg-brand-soft text-brand-text border border-transparent',
  quiet: 'bg-transparent text-txt3 border border-transparent',
}

export function Btn({
  children,
  icon: Icon,
  kind = 'ghost',
  small = false,
  className = '',
  ...props
}) {
  const size = small ? 'text-[12.5px] px-3 py-1.5 gap-1.5' : 'text-[13.5px] px-4 py-2.5 gap-2'
  return (
    <button
      className={`inline-flex items-center justify-center rounded-[10px] font-semibold whitespace-nowrap transition-colors disabled:opacity-40 ${size} ${KINDS[kind]} ${className}`}
      {...props}
    >
      {Icon && <Icon size={small ? 14 : 16} />}
      {children}
    </button>
  )
}

export default Btn
