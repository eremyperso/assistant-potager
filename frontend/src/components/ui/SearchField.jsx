import { Search } from 'lucide-react'

/**
 * Champ de recherche du design system [US-052].
 */
export function SearchField({
  value,
  onChange,
  placeholder = 'Rechercher…',
  wide = false,
  className = '',
  ...props
}) {
  return (
    <div
      className={`flex items-center gap-2 bg-card border border-border rounded-[10px] px-3 h-[38px] min-w-0 ${wide ? 'flex-1' : ''} ${className}`}
    >
      <Search size={15} className="text-txt3 shrink-0" />
      <input
        value={value}
        onChange={(e) => onChange?.(e.target.value)}
        placeholder={placeholder}
        className="flex-1 min-w-0 bg-transparent border-none outline-none text-[13.5px] text-txt placeholder:text-txt3"
        {...props}
      />
    </div>
  )
}

export default SearchField
