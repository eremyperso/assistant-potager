/**
 * Pastille de statut du design system [US-052].
 * `solid` inverse le contraste pour les usages sur fond clair/coloré.
 */
const SOFT = {
  brand: 'bg-brand-soft text-brand',
  amber: 'bg-amber-soft text-amber',
  red: 'bg-red-soft text-red',
  blue: 'bg-blue-soft text-blue',
  violet: 'bg-violet-soft text-violet',
}

const SOLID = {
  brand: 'bg-brand text-white dark:text-bg',
  amber: 'bg-amber text-white dark:text-bg',
  red: 'bg-red text-white dark:text-bg',
  blue: 'bg-blue text-white dark:text-bg',
  violet: 'bg-violet text-white dark:text-bg',
}

export function Badge({ children, tint = 'brand', solid = false, className = '' }) {
  const palette = solid ? SOLID : SOFT
  return (
    <span
      className={`inline-flex items-center gap-1 text-[11.5px] font-semibold px-2.5 py-0.5 rounded-full whitespace-nowrap ${palette[tint]} ${className}`}
    >
      {children}
    </span>
  )
}

export default Badge
