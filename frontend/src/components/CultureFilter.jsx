// [US-031 CA17-CA19] Champ de recherche culture — local par écran, non persisté.
import { Search } from 'lucide-react'

export default function CultureFilter({ value, onChange, placeholder = 'Filtrer par culture…', className = 'relative' }) {
  return (
    <div className={className}>
      <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-g-sec pointer-events-none" aria-hidden="true" />
      <input
        type="text"
        value={value}
        onChange={e => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full pl-9 pr-3 py-2 text-sm rounded-xl border border-g-brd bg-g-card text-g-pri placeholder-g-sec focus:outline-none focus:ring-1 focus:ring-g-acc"
      />
    </div>
  )
}
